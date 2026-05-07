"""F04 — Test régression _simulate_financing avec Money typed (FR-050)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.graph.tools.application_tools import _simulate_financing


def _make_fund_with_money(
    min_amt: Decimal | None = Decimal("5000000.00"),
    max_amt: Decimal | None = Decimal("10000000.00"),
    currency: str = "USD",
) -> MagicMock:
    fund = MagicMock()
    fund.id = uuid.uuid4()
    fund.name = "GCF F04 Test"
    fund.min_amount = min_amt
    fund.min_amount_currency = currency if min_amt else None
    fund.max_amount = max_amt
    fund.max_amount_currency = currency if max_amt else None
    fund.min_amount_xof = None
    fund.max_amount_xof = None

    # Active la real property
    from app.models.financing import Fund as RealFund

    fund.min_amount_money = RealFund.min_amount_money.fget(fund)
    fund.max_amount_money = RealFund.max_amount_money.fget(fund)
    return fund


@pytest.mark.asyncio
async def test_simulate_financing_returns_money_typed_no_attribute_error() -> None:
    """Le tool ne lève plus d'AttributeError sur fund.max_amount/min_amount."""
    fund = _make_fund_with_money()
    application = MagicMock()
    application.fund_id = fund.id

    # Mock le service get_fund_by_id
    db = AsyncMock()
    from unittest.mock import patch

    with patch(
        "app.modules.financing.service.get_fund_by_id",
        AsyncMock(return_value=fund),
    ):
        result = await _simulate_financing(db, application)

    assert "error" not in result
    eligible = result["eligible_amount"]
    assert isinstance(eligible, dict)
    assert eligible["currency"] == "USD"
    # 5_000_000 + 10_000_000 / 2 = 7_500_000
    assert Decimal(eligible["amount"]) == Decimal("7500000.00")


@pytest.mark.asyncio
async def test_simulate_financing_fallback_to_xof_legacy() -> None:
    """Si pas de Money typed → fallback sur min_amount_xof / max_amount_xof."""
    fund = MagicMock()
    fund.id = uuid.uuid4()
    fund.name = "Fonds Legacy"
    fund.min_amount = None
    fund.min_amount_currency = None
    fund.max_amount = None
    fund.max_amount_currency = None
    fund.min_amount_xof = 50_000_000
    fund.max_amount_xof = 100_000_000

    from app.models.financing import Fund as RealFund

    fund.min_amount_money = RealFund.min_amount_money.fget(fund)
    fund.max_amount_money = RealFund.max_amount_money.fget(fund)

    application = MagicMock()
    application.fund_id = fund.id
    db = AsyncMock()
    from unittest.mock import patch

    with patch(
        "app.modules.financing.service.get_fund_by_id",
        AsyncMock(return_value=fund),
    ):
        result = await _simulate_financing(db, application)

    eligible = result["eligible_amount"]
    assert isinstance(eligible, dict)
    assert eligible["currency"] == "XOF"
    assert Decimal(eligible["amount"]) == Decimal("75000000.00")


@pytest.mark.asyncio
async def test_simulate_financing_returns_zero_when_no_amount() -> None:
    """Aucun montant configuré → eligible 0 avec devise XOF par défaut."""
    fund = MagicMock()
    fund.id = uuid.uuid4()
    fund.name = "Fonds vide"
    fund.min_amount = None
    fund.min_amount_currency = None
    fund.max_amount = None
    fund.max_amount_currency = None
    fund.min_amount_xof = None
    fund.max_amount_xof = None

    from app.models.financing import Fund as RealFund

    fund.min_amount_money = RealFund.min_amount_money.fget(fund)
    fund.max_amount_money = RealFund.max_amount_money.fget(fund)

    application = MagicMock()
    application.fund_id = fund.id
    db = AsyncMock()
    from unittest.mock import patch

    with patch(
        "app.modules.financing.service.get_fund_by_id",
        AsyncMock(return_value=fund),
    ):
        result = await _simulate_financing(db, application)

    eligible = result["eligible_amount"]
    assert isinstance(eligible, dict)
    assert eligible["currency"] == "XOF"
    assert Decimal(eligible["amount"]) == Decimal("0.00")
