"""F18 — Tests du seed CreditMethodologyFactor v1.2."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.credit_alternative import CreditMethodologyFactor
from app.modules.credit.alternative.seed_methodology import (
    METHODOLOGY_VERSION,
    SEED_FACTORS,
    seed_credit_methodology_factors,
)
from app.modules.sources.seed import seed_sources


@pytest.mark.asyncio
async def test_seed_inserts_all_factors(db_session):
    """Premier seed insère tous les facteurs MVP."""
    await seed_sources(db_session)
    await db_session.flush()
    created, skipped = await seed_credit_methodology_factors(db_session)
    await db_session.commit()
    assert created == len(SEED_FACTORS)
    assert skipped == 0

    rows = (
        await db_session.execute(
            select(CreditMethodologyFactor).where(
                CreditMethodologyFactor.version == METHODOLOGY_VERSION,
                CreditMethodologyFactor.publication_status == "published",
            )
        )
    ).scalars().all()
    assert len(rows) >= 5  # MVP : ≥ 5 facteurs publiés
    # Tous ont source_id NOT NULL (invariant F01).
    assert all(r.source_id is not None for r in rows)


@pytest.mark.asyncio
async def test_seed_idempotent(db_session):
    """Second appel n'insère rien."""
    await seed_sources(db_session)
    await db_session.flush()
    await seed_credit_methodology_factors(db_session)
    await db_session.commit()

    created2, skipped2 = await seed_credit_methodology_factors(db_session)
    await db_session.commit()
    assert created2 == 0
    assert skipped2 == len(SEED_FACTORS)


@pytest.mark.asyncio
async def test_seed_fails_without_sources(db_session):
    """Sans seed_sources préalable, seed_credit_methodology lève RuntimeError."""
    with pytest.raises(RuntimeError, match="Source publisher"):
        await seed_credit_methodology_factors(db_session)


@pytest.mark.asyncio
async def test_seed_factors_categories_cover_mvp(db_session):
    """Couverture MVP : mobile_money_flux + public_data + esg + photos_ia."""
    categories = {f.category for f in SEED_FACTORS}
    assert "mobile_money_flux" in categories
    assert "public_data" in categories
    assert "esg" in categories
    assert "photos_ia" in categories


@pytest.mark.asyncio
async def test_seed_public_data_total_within_cap(db_session):
    """Le poids cumulé déclaré pour public_data peut excéder 10 % au catalogue
    (le cap strict est appliqué par compute_combined_score, pas par le seed).
    Mais on garantit ici qu'il est documenté ≤ 0.10 pour ne pas tromper
    les utilisateurs lisant la méthodologie."""
    public_total = sum(
        f.weight for f in SEED_FACTORS if f.category == "public_data"
    )
    assert public_total <= Decimal("0.10")
