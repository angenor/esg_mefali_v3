"""Tests du seed initial du catalogue Source (F01)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models.source import Source, VerificationStatus
from app.modules.sources.seed import (
    SEED_SOURCES,
    SYSTEM_CURATOR_EMAIL,
    SYSTEM_VALIDATOR_EMAIL,
    seed_sources,
)


pytestmark = pytest.mark.asyncio


async def test_seed_creates_30_plus_sources(db_session) -> None:
    """seed_sources cree au moins 30 sources verifiees."""
    created, skipped = await seed_sources(db_session)
    assert created >= 30
    assert skipped == 0
    total = await db_session.execute(
        select(func.count(Source.id)).where(
            Source.verification_status == VerificationStatus.VERIFIED.value,
        ),
    )
    assert total.scalar_one() >= 30


async def test_seed_is_idempotent(db_session) -> None:
    """Re-executer seed_sources n'insere pas de doublons."""
    c1, s1 = await seed_sources(db_session)
    assert c1 >= 30 and s1 == 0
    c2, s2 = await seed_sources(db_session)
    assert c2 == 0
    assert s2 >= 30


async def test_seed_covers_required_publishers(db_session) -> None:
    """Le seed couvre tous les publishers requis (FR-035)."""
    await seed_sources(db_session)
    required_publishers = {
        "ADEME", "IPCC", "IEA", "UEMOA", "BCEAO", "GCF",
        "IFC", "BOAD", "Gold Standard", "Verra", "ODD ONU",
    }
    for pub in required_publishers:
        result = await db_session.execute(
            select(Source).where(Source.publisher == pub).limit(1)
        )
        assert result.scalar_one_or_none() is not None, (
            f"Publisher {pub} non seede"
        )


async def test_seed_creates_system_users(db_session) -> None:
    """seed_sources cree les 2 users systeme curator+validator."""
    from app.models.user import User
    await seed_sources(db_session)
    cur = await db_session.execute(
        select(User).where(User.email == SYSTEM_CURATOR_EMAIL)
    )
    val = await db_session.execute(
        select(User).where(User.email == SYSTEM_VALIDATOR_EMAIL)
    )
    assert cur.scalar_one_or_none() is not None
    assert val.scalar_one_or_none() is not None


async def test_all_seeded_sources_are_verified(db_session) -> None:
    """Tous les seed sources sont en statut verified."""
    await seed_sources(db_session)
    drafts = await db_session.execute(
        select(func.count(Source.id)).where(
            Source.verification_status != VerificationStatus.VERIFIED.value,
        )
    )
    assert drafts.scalar_one() == 0


async def test_seed_4_eyes_invariant(db_session) -> None:
    """captured_by != verified_by pour toutes les sources seedees."""
    await seed_sources(db_session)
    rows = await db_session.execute(select(Source))
    for src in rows.scalars().all():
        assert src.captured_by != src.verified_by, (
            f"Source {src.title} viole 4-yeux"
        )


def test_seed_data_count_at_least_30() -> None:
    """SEED_SOURCES contient bien >= 30 entrees."""
    assert len(SEED_SOURCES) >= 30
