"""T014 — Test idempotence du seed F047 (sources + référentiels + critères)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.indicator import Criterion
from app.models.referential import Referential
from app.models.source import Source
from app.models.user import User
from app.scripts.seed_sources_047 import seed_sources_047


@pytest.fixture
async def two_admins(db_session) -> tuple[uuid.UUID, uuid.UUID]:
    """Crée 2 admins distincts pour respecter le CHECK F01 four-eyes."""
    a1 = User(
        email=f"admin1-{uuid.uuid4().hex[:6]}@mefali",
        hashed_password="x",
        full_name="Admin 1",
        company_name="Mefali",
        account_id=None,
        role="ADMIN",
    )
    a2 = User(
        email=f"admin2-{uuid.uuid4().hex[:6]}@mefali",
        hashed_password="x",
        full_name="Admin 2",
        company_name="Mefali",
        account_id=None,
        role="ADMIN",
    )
    db_session.add_all([a1, a2])
    await db_session.flush()
    return a1.id, a2.id


async def test_seed_047_first_run_inserts(db_session, two_admins):
    captured_by, verified_by = two_admins
    report = await seed_sources_047(
        db_session, captured_by_id=captured_by, verified_by_id=verified_by,
    )
    assert report["sources"] == 3
    assert report["referentials"] == 3
    assert report["criteria"] == 46

    sources_count = (
        await db_session.execute(select(Source))
    ).scalars().all()
    assert len(sources_count) >= 3

    refs = (await db_session.execute(select(Referential))).scalars().all()
    assert len(refs) >= 3

    criteria = (
        await db_session.execute(select(Criterion).where(Criterion.applies_to_project.is_(True)))
    ).scalars().all()
    assert len(criteria) == 46
    # Vérifie qu'il y a bien des critères obligatoires (≥ 1 par référentiel)
    required = [c for c in criteria if c.is_required]
    assert len(required) >= 3


async def test_seed_047_second_run_idempotent(db_session, two_admins):
    captured_by, verified_by = two_admins
    # 1ère exécution
    await seed_sources_047(
        db_session, captured_by_id=captured_by, verified_by_id=verified_by,
    )
    # 2ème : aucun nouvel insert
    report = await seed_sources_047(
        db_session, captured_by_id=captured_by, verified_by_id=verified_by,
    )
    assert report["criteria"] == 0  # déjà tous présents

    criteria = (
        await db_session.execute(select(Criterion).where(Criterion.applies_to_project.is_(True)))
    ).scalars().all()
    # Pas de duplication malgré la 2ème exécution
    assert len(criteria) == 46
