"""F04 — Tests modèle SQLAlchemy ExchangeRate (création + contraintes)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exchange_rate import ExchangeRate


@pytest.mark.asyncio
async def test_create_exchange_rate(db_session: AsyncSession) -> None:
    """Insertion simple d'un taux."""
    rate = ExchangeRate(
        base_currency="USD",
        quote_currency="XOF",
        rate=Decimal("615.20"),
        as_of=date(2026, 4, 15),
        source="exchangerate-api.com",
    )
    db_session.add(rate)
    await db_session.commit()
    result = await db_session.execute(
        select(ExchangeRate).where(
            ExchangeRate.base_currency == "USD",
            ExchangeRate.quote_currency == "XOF",
            ExchangeRate.as_of == date(2026, 4, 15),
        ),
    )
    fetched = result.scalar_one()
    assert fetched.rate == Decimal("615.2000000000") or fetched.rate == Decimal("615.20")


@pytest.mark.asyncio
async def test_unique_constraint_pair_as_of(db_session: AsyncSession) -> None:
    """Une seule entrée par (base, quote, as_of)."""
    rate1 = ExchangeRate(
        base_currency="USD",
        quote_currency="EUR",
        rate=Decimal("0.92"),
        as_of=date(2026, 4, 16),
        source="exchangerate-api.com",
    )
    db_session.add(rate1)
    await db_session.commit()

    rate2 = ExchangeRate(
        base_currency="USD",
        quote_currency="EUR",
        rate=Decimal("0.91"),
        as_of=date(2026, 4, 16),
        source="other-api",
    )
    db_session.add(rate2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_check_constraint_rate_positive(db_session: AsyncSession) -> None:
    """Le taux doit être strictement positif (CHECK)."""
    rate = ExchangeRate(
        base_currency="USD",
        quote_currency="GBP",
        rate=Decimal("-0.79"),
        as_of=date(2026, 4, 15),
        source="invalid",
    )
    db_session.add(rate)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_check_constraint_currency_enum(db_session: AsyncSession) -> None:
    """base_currency / quote_currency restreints à l'enum strict (CHECK)."""
    rate = ExchangeRate(
        base_currency="ABC",
        quote_currency="XOF",
        rate=Decimal("100.00"),
        as_of=date(2026, 4, 15),
        source="invalid",
    )
    db_session.add(rate)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
