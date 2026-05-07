"""F04 — Tests du service currency_service (peg + table + pivot USD)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.core.money import Money
from app.models.exchange_rate import ExchangeRate
from app.modules.currency import service as currency_service
from app.modules.currency.exceptions import (
    ConversionPathUnavailableError,
    NoRateAvailableError,
)


# --- Helpers ---


async def _seed_rate(
    db_session, base: str, quote: str, rate: Decimal,
    on_date: date = date(2026, 4, 15),
) -> None:
    db_session.add(
        ExchangeRate(
            id=uuid.uuid4(),
            base_currency=base,
            quote_currency=quote,
            rate=rate,
            as_of=on_date,
            source="test-fixture",
        ),
    )
    await db_session.commit()


# --- Peg FCFA-EUR (sans HTTP, sans BDD) ---


@pytest.mark.asyncio
async def test_convert_xof_to_eur_peg(db_session) -> None:
    """1 EUR = 655.957 XOF → 655957 XOF = 1000 EUR."""
    money = Money(amount=Decimal("655957"), currency="XOF")
    result = await currency_service.convert(money, "EUR", db_session)
    assert result.currency == "EUR"
    assert result.amount == Decimal("1000.00")


@pytest.mark.asyncio
async def test_convert_eur_to_xof_peg(db_session) -> None:
    money = Money(amount=Decimal("1000"), currency="EUR")
    result = await currency_service.convert(money, "XOF", db_session)
    assert result.currency == "XOF"
    assert result.amount == Decimal("655957.00")


@pytest.mark.asyncio
async def test_convert_same_currency_returns_self(db_session) -> None:
    money = Money(amount=Decimal("100"), currency="XOF")
    result = await currency_service.convert(money, "XOF", db_session)
    assert result == money


# --- Table exchange_rates avec fallback ascendant ---


@pytest.mark.asyncio
async def test_get_rate_returns_value(db_session) -> None:
    await _seed_rate(db_session, "USD", "XOF", Decimal("615.20"))
    rate = await currency_service.get_rate(
        db_session, "USD", "XOF", on_date=date(2026, 4, 15),
    )
    assert rate == Decimal("615.2000000000")


@pytest.mark.asyncio
async def test_get_rate_fallback_ascending(db_session) -> None:
    """Aucune entrée pour la date demandée → utilise la plus récente avant."""
    await _seed_rate(db_session, "USD", "XOF", Decimal("600"), date(2026, 4, 1))
    await _seed_rate(db_session, "USD", "XOF", Decimal("615.20"), date(2026, 4, 15))
    # Demande au 30 avril → utilise le 15 avril (plus récent ≤ 30 avril)
    rate = await currency_service.get_rate(
        db_session, "USD", "XOF", on_date=date(2026, 4, 30),
    )
    assert rate == Decimal("615.2000000000")


@pytest.mark.asyncio
async def test_get_rate_raises_when_empty(db_session) -> None:
    with pytest.raises(NoRateAvailableError):
        await currency_service.get_rate(
            db_session, "USD", "XOF", on_date=date(2026, 4, 15),
        )


@pytest.mark.asyncio
async def test_convert_via_table(db_session) -> None:
    await _seed_rate(db_session, "USD", "XOF", Decimal("615.20"))
    money = Money(amount=Decimal("100"), currency="USD")
    result = await currency_service.convert(
        money, "XOF", db_session, on_date=date(2026, 4, 15),
    )
    assert result.currency == "XOF"
    assert result.amount == Decimal("61520.00")


# --- Pivot USD ---


@pytest.mark.asyncio
async def test_convert_pivot_usd_eur_to_jpy(db_session) -> None:
    """EUR→JPY via pivot USD : convert(EUR, USD) * convert(USD, JPY)."""
    await _seed_rate(db_session, "EUR", "USD", Decimal("1.087"))
    await _seed_rate(db_session, "USD", "JPY", Decimal("152.50"))
    money = Money(amount=Decimal("100"), currency="EUR")
    result = await currency_service.convert(
        money, "JPY", db_session, on_date=date(2026, 4, 15),
    )
    assert result.currency == "JPY"
    # 100 * 1.087 * 152.50 = 16576.75
    assert abs(result.amount - Decimal("16576.75")) < Decimal("1.00")


@pytest.mark.asyncio
async def test_convert_pivot_unavailable_raises(db_session) -> None:
    """Pivot impossible (un des deux taux manquant) → ConversionPathUnavailableError."""
    await _seed_rate(db_session, "EUR", "USD", Decimal("1.087"))
    # Pas de USD→JPY
    money = Money(amount=Decimal("100"), currency="EUR")
    with pytest.raises(ConversionPathUnavailableError):
        await currency_service.convert(money, "JPY", db_session)


# --- Latest rates ---


@pytest.mark.asyncio
async def test_list_latest_rates_returns_max_per_pair(db_session) -> None:
    await _seed_rate(db_session, "USD", "XOF", Decimal("600"), date(2026, 4, 1))
    await _seed_rate(db_session, "USD", "XOF", Decimal("615.20"), date(2026, 4, 15))
    rates = await currency_service.list_latest_rates(db_session)
    assert len(rates) == 1
    assert rates[0]["base_currency"] == "USD"
    assert rates[0]["quote_currency"] == "XOF"
    assert rates[0]["as_of"] == "2026-04-15"


def test_get_peg_pairs_returns_two() -> None:
    pegs = currency_service.get_peg_pairs()
    assert len(pegs) == 2
    bases = {p["base_currency"] for p in pegs}
    quotes = {p["quote_currency"] for p in pegs}
    assert bases == {"XOF", "EUR"}
    assert quotes == {"XOF", "EUR"}
