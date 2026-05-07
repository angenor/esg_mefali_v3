"""F07 — Tests unit du seed singleton DIRECT (T008).

Vérifie :
- Idempotence : 2 appels successifs n'insèrent qu'une ligne.
- code='DIRECT' unique.
- publication_status='published' (singleton accessible immédiatement).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.financing import Intermediary
from app.modules.offers.seed_direct import (
    DIRECT_CODE,
    seed_direct_intermediary,
)


@pytest.mark.asyncio
async def test_seed_direct_creates_singleton(
    db_session, two_admins,
) -> None:
    """Premier appel crée l'intermédiaire DIRECT."""
    result = await seed_direct_intermediary(db_session)
    assert result.code == DIRECT_CODE
    assert result.publication_status == "published"
    assert result.is_active is True


@pytest.mark.asyncio
async def test_seed_direct_idempotent(
    db_session, two_admins,
) -> None:
    """2 appels successifs n'insèrent qu'une ligne."""
    r1 = await seed_direct_intermediary(db_session)
    r2 = await seed_direct_intermediary(db_session)
    assert r1.id == r2.id

    # Vérifier qu'il n'y a qu'une seule ligne
    result = await db_session.execute(
        select(Intermediary).where(Intermediary.code == DIRECT_CODE)
    )
    rows = result.scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_seed_direct_creates_source_too(
    db_session, two_admins,
) -> None:
    """La Source DIRECT est aussi créée."""
    from app.models.source import Source
    from app.modules.offers.seed_direct import DIRECT_SOURCE_URL

    intermediary = await seed_direct_intermediary(db_session)
    assert intermediary.source_id is not None

    src_result = await db_session.execute(
        select(Source).where(Source.url == DIRECT_SOURCE_URL)
    )
    source = src_result.scalar_one()
    assert source.id == intermediary.source_id
    # Avec 2 admins → verified
    assert source.verification_status == "verified"
