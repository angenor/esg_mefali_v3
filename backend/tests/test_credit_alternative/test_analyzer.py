"""Tests F18 — Analyzer KPIs Mobile Money."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.modules.credit.alternative.mobile_money_analyzer import (
    METHODOLOGY_VERSION,
    compute_kpis,
)
from app.modules.credit.alternative.mobile_money_parser import (
    MobileMoneyTransactionRow,
)


def _row(
    days_ago: int,
    direction: str,
    amount: str,
    counterparty: str = "h" * 64,
    balance: str | None = None,
) -> MobileMoneyTransactionRow:
    return MobileMoneyTransactionRow(
        provider="wave",
        transaction_date=datetime.now(timezone.utc) - timedelta(days=days_ago),
        direction=direction,
        amount=Decimal(amount),
        currency="XOF",
        counterparty_hash=counterparty,
        balance_amount=Decimal(balance) if balance else None,
        balance_currency="XOF" if balance else None,
    )


def test_compute_kpis_empty_returns_zero():
    result = compute_kpis([])
    assert result["transaction_count"] == 0
    assert result["regularity_30d"] == 0.0
    assert result["top_counterparties"] == []


def test_compute_kpis_basic_5_kpis_present():
    """≥ 5 KPIs distincts (FR-004 / SC-003)."""
    txs = [
        _row(5, "incoming", "10000", balance="50000"),
        _row(15, "outgoing", "3000", balance="47000"),
        _row(45, "incoming", "20000"),
    ]
    result = compute_kpis(txs)
    # FR-004 — au moins 5 KPIs distincts
    assert "monthly_volume_avg" in result
    assert "monthly_volume_stddev" in result
    assert "regularity_30d" in result
    assert "avg_balance_estimate" in result
    assert "growth_12m" in result
    assert "top_counterparties" in result
    assert "transaction_count" in result
    assert result["transaction_count"] == 3


def test_compute_kpis_top_counterparties_capped_at_5():
    txs = [
        _row(i, "incoming", "1000", counterparty=f"hash_{i:064d}"[:64])
        for i in range(10)
    ]
    result = compute_kpis(txs)
    assert len(result["top_counterparties"]) <= 5


def test_compute_kpis_regularity_30d_in_unit_range():
    txs = [
        _row(i, "incoming", "1000")
        for i in range(0, 30)
    ]
    result = compute_kpis(txs)
    assert 0.0 <= result["regularity_30d"] <= 1.0


def test_compute_kpis_avg_balance_only_from_non_null():
    """avg_balance_estimate ignore les transactions sans balance."""
    txs = [
        _row(1, "incoming", "100", balance="500"),
        _row(2, "outgoing", "50"),  # pas de balance
    ]
    result = compute_kpis(txs)
    assert Decimal(result["avg_balance_estimate"]) == Decimal("500.00")


def test_compute_kpis_methodology_version():
    """La version méthodologie est bien définie."""
    assert METHODOLOGY_VERSION == "1.2"
