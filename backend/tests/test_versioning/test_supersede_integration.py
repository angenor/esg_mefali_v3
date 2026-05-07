"""F04 — Tests d'intégration supersede() avec une vraie table SQLAlchemy."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.models.referential import Referential
from app.modules.versioning.exceptions import SupersedeCycleError
from app.modules.versioning.service import supersede


def _make_referential(name: str = "Ref") -> Referential:
    """Helper local : crée un Referential déjà publié."""
    return Referential(
        code=f"REF-{uuid.uuid4().hex[:6]}",
        label=name,
        description="Test ref",
        # publication_status default is draft, set to published
        publication_status="published",
        # Source FK + user FK requis par F02 — on triche en bypassant via
        # SQLite simple insert qui n'enforce pas FK.
        source_id=uuid.uuid4(),
        created_by_user_id=uuid.uuid4(),
    )


@pytest.mark.asyncio
async def test_supersede_updates_old_row(db_session) -> None:
    """supersede() met à jour valid_to et superseded_by sur l'ancienne ligne."""
    old = _make_referential("Old")
    new = _make_referential("New")
    db_session.add_all([old, new])
    await db_session.flush()

    await supersede(db_session, Referential, old.id, new.id, today=date(2026, 5, 7))
    await db_session.flush()

    # Recharge depuis la BDD
    result = await db_session.execute(
        select(Referential).where(Referential.id == old.id),
    )
    refreshed = result.scalar_one()
    assert refreshed.valid_to == date(2026, 5, 7)
    assert refreshed.superseded_by == new.id


@pytest.mark.asyncio
async def test_supersede_detects_cycle_in_chain(db_session) -> None:
    """supersede() refuse une chaîne A→B→A (cycle applicatif)."""
    a = _make_referential("A")
    b = _make_referential("B")
    db_session.add_all([a, b])
    await db_session.flush()

    # Étape 1 : A est superseded par B (chaîne A → B)
    await supersede(db_session, Referential, a.id, b.id)
    await db_session.flush()

    # Étape 2 : tenter B superseded par A → cycle car B.superseded_by est NULL
    # mais A.superseded_by = B → walk(A) = [A, B]. supersede(B, A) cherche
    # A dans walk(A) → True → cycle.
    with pytest.raises(SupersedeCycleError):
        await supersede(db_session, Referential, b.id, a.id)
