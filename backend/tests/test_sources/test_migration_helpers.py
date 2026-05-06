"""Tests des helpers de migration de donnees existantes (F01 / US7)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models.emission_factor import EmissionFactor
from app.models.indicator import Indicator
from app.models.referential import Referential, ReferentialIndicator
from app.models.simulation_factor import SimulationFactor
from app.modules.sources.migration_helpers import (
    run_full_migration,
    seed_emission_factors,
    seed_esg_indicators,
    seed_sector_weights,
    seed_simulation_factors,
)
from app.modules.sources.seed import seed_sources


pytestmark = pytest.mark.asyncio


async def test_seed_emission_factors_inserts_all(db_session) -> None:
    await seed_sources(db_session)
    n = await seed_emission_factors(db_session)
    assert n >= 5  # 7 facteurs dans le module carbon
    total = await db_session.execute(select(func.count(EmissionFactor.id)))
    assert total.scalar_one() == n


async def test_seed_esg_indicators_creates_30(db_session) -> None:
    await seed_sources(db_session)
    n = await seed_esg_indicators(db_session)
    assert n == 30
    # 10 par pilier
    for pillar in ("environment", "social", "governance"):
        cnt = await db_session.execute(
            select(func.count(Indicator.id)).where(Indicator.pillar == pillar)
        )
        assert cnt.scalar_one() == 10


async def test_seed_sector_weights_creates_referentials(db_session) -> None:
    await seed_sources(db_session)
    await seed_esg_indicators(db_session)
    n = await seed_sector_weights(db_session)
    assert n > 0
    # 10 secteurs prevus
    refs = await db_session.execute(select(func.count(Referential.id)))
    assert refs.scalar_one() == 10


async def test_seed_simulation_factors_pending(db_session) -> None:
    await seed_sources(db_session)
    n = await seed_simulation_factors(db_session)
    assert n == 2
    rows = (await db_session.execute(select(SimulationFactor))).scalars().all()
    for row in rows:
        assert row.status == "pending"
        assert row.source_id is None


async def test_run_full_migration(db_session) -> None:
    """L'orchestration globale produit toutes les categories."""
    stats = await run_full_migration(db_session)
    assert stats["sources"] >= 30
    assert stats["indicators"] == 30
    assert stats["emission_factors"] >= 5
    assert stats["sector_weights"] > 0
    assert stats["simulation_factors"] == 2


async def test_seed_emission_factor_idempotent(db_session) -> None:
    await seed_sources(db_session)
    n1 = await seed_emission_factors(db_session)
    n2 = await seed_emission_factors(db_session)
    assert n2 == 0  # rien de nouveau
