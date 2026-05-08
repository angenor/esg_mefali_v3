"""F15 BUG-002 — Garde-fou : ``_simulate_financing`` ne lève plus
``AttributeError`` sur ``fund.max_amount`` et lit correctement Money typed.

Le tool ``simulate_financing`` (legacy) appelait ``fund.max_amount`` qui
n'existait pas. La correction consiste à utiliser les properties
``max_amount_money`` / ``min_amount_money`` (Money typed F04) avec
fallback sur ``max_amount_xof`` / ``min_amount_xof``.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.money import Money
from app.graph.tools.application_tools import _simulate_financing

pytestmark = pytest.mark.unit


def _make_fund(min_money: Money | None, max_money: Money | None) -> MagicMock:
    """Construit un mock Fund avec ses properties Money typed."""
    fund = MagicMock()
    fund.min_amount_money = min_money
    fund.max_amount_money = max_money
    fund.name = "Fonds test"
    return fund


@pytest.mark.asyncio
async def test_simulate_financing_with_money_typed(monkeypatch) -> None:
    """Cas nominal : min/max Money typed → eligible_amount = (min+max)/2."""
    fund = _make_fund(
        Money(amount=Decimal("1000000"), currency="XOF"),
        Money(amount=Decimal("5000000"), currency="XOF"),
    )

    async def fake_get(_db, _fund_id):
        return fund

    monkeypatch.setattr(
        "app.modules.financing.service.get_fund_by_id",
        fake_get,
    )

    application = MagicMock()
    application.fund_id = "00000000-0000-0000-0000-000000000001"

    result = await _simulate_financing(db=AsyncMock(), application=application)

    assert "eligible_amount" in result
    assert result["currency"] == "XOF"
    assert result["fund_name"] == "Fonds test"
    assert Decimal(result["eligible_amount"]["amount"]) == Decimal("3000000.00")


@pytest.mark.asyncio
async def test_simulate_financing_only_max(monkeypatch) -> None:
    """Cas où seul max est défini : eligible_amount = max/2."""
    fund = _make_fund(
        None, Money(amount=Decimal("5000000000"), currency="XOF"),
    )

    async def fake_get(_db, _fund_id):
        return fund

    monkeypatch.setattr(
        "app.modules.financing.service.get_fund_by_id",
        fake_get,
    )

    application = MagicMock()
    application.fund_id = "00000000-0000-0000-0000-000000000001"

    result = await _simulate_financing(db=AsyncMock(), application=application)

    assert "error" not in result
    assert Decimal(result["eligible_amount"]["amount"]) == Decimal("2500000000.00")


@pytest.mark.asyncio
async def test_simulate_financing_no_money_no_error(monkeypatch) -> None:
    """Garde-fou strict : pas de Money défini → 0 et pas d'AttributeError."""
    fund = _make_fund(None, None)

    async def fake_get(_db, _fund_id):
        return fund

    monkeypatch.setattr(
        "app.modules.financing.service.get_fund_by_id",
        fake_get,
    )

    application = MagicMock()
    application.fund_id = "00000000-0000-0000-0000-000000000001"

    # Le critère bloquant : aucune AttributeError sur fund.max_amount
    result = await _simulate_financing(db=AsyncMock(), application=application)
    assert "error" not in result
    assert result["currency"] == "XOF"


@pytest.mark.asyncio
async def test_simulate_financing_fund_not_found(monkeypatch) -> None:
    """Si le fond n'existe pas, retour erreur explicite (pas d'AttributeError)."""

    async def fake_get(_db, _fund_id):
        return None

    monkeypatch.setattr(
        "app.modules.financing.service.get_fund_by_id",
        fake_get,
    )

    application = MagicMock()
    application.fund_id = "00000000-0000-0000-0000-000000000001"

    result = await _simulate_financing(db=AsyncMock(), application=application)
    assert "error" in result
