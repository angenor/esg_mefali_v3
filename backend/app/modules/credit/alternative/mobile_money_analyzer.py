"""F18 — Analyzer KPIs Mobile Money.

Calculs purs et déterministes à partir d'une liste de transactions
:class:`MobileMoneyTransactionRow` ou de modèles ORM
:class:`MobileMoneyTransaction`.

KPIs produits (FR-004, ≥ 5) :
- ``monthly_volume_avg`` : volume moyen mensuel (XOF).
- ``monthly_volume_stddev`` : écart-type mensuel.
- ``regularity_30d`` : taux de régularité 30 j (0..1).
- ``avg_balance_estimate`` : solde moyen estimé.
- ``growth_12m`` : tendance 12 mois (delta relatif).
- ``top_counterparties`` : top 5 contre-parties anonymisées.
"""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable

logger = logging.getLogger(__name__)

METHODOLOGY_VERSION = "1.2"


@dataclass(frozen=True)
class TransactionLike:
    """Protocol-like minimal interface (parser row OR ORM)."""

    transaction_date: datetime
    direction: str
    amount: Decimal
    counterparty_hash: str
    balance_amount: Decimal | None


def _coerce(tx) -> TransactionLike:
    """Adapte un row parser ou un ORM en TransactionLike."""
    return TransactionLike(
        transaction_date=tx.transaction_date,
        direction=tx.direction,
        amount=Decimal(tx.amount),
        counterparty_hash=tx.counterparty_hash,
        balance_amount=(Decimal(tx.balance_amount) if tx.balance_amount is not None else None),
    )


def compute_kpis(transactions: Iterable) -> dict:
    """Calcule les KPIs à partir des transactions fournies.

    Retourne un dict sérialisable JSON conforme au schéma
    :class:`MobileMoneyKpis`.
    """
    txs = [_coerce(t) for t in transactions]
    if not txs:
        return {
            "monthly_volume_avg": "0.00",
            "monthly_volume_stddev": "0.00",
            "regularity_30d": 0.0,
            "avg_balance_estimate": "0.00",
            "growth_12m": 0.0,
            "top_counterparties": [],
            "transaction_count": 0,
            "period_start": None,
            "period_end": None,
        }

    sorted_txs = sorted(txs, key=lambda t: t.transaction_date)
    period_start = sorted_txs[0].transaction_date
    period_end = sorted_txs[-1].transaction_date

    # 1. Volume mensuel (somme des entrants par mois, en XOF)
    monthly_volumes: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal("0"))
    for t in sorted_txs:
        key = (t.transaction_date.year, t.transaction_date.month)
        if t.direction == "incoming":
            monthly_volumes[key] += t.amount

    volumes = [float(v) for v in monthly_volumes.values()]
    if volumes:
        monthly_avg = statistics.fmean(volumes)
        monthly_std = statistics.pstdev(volumes) if len(volumes) > 1 else 0.0
    else:
        monthly_avg = 0.0
        monthly_std = 0.0

    # 2. Régularité 30j : nombre de jours actifs sur les 30 derniers / 30
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    active_days = {
        t.transaction_date.date()
        for t in sorted_txs
        if t.transaction_date >= thirty_days_ago
    }
    regularity_30d = round(min(len(active_days) / 30.0, 1.0), 4)

    # 3. Solde moyen estimé (moyenne des balance non null)
    balances = [float(t.balance_amount) for t in sorted_txs if t.balance_amount is not None]
    avg_balance = statistics.fmean(balances) if balances else 0.0

    # 4. Tendance 12 mois (delta relatif entre 1er et dernier mois)
    if len(monthly_volumes) >= 2:
        sorted_keys = sorted(monthly_volumes.keys())
        first_v = float(monthly_volumes[sorted_keys[0]])
        last_v = float(monthly_volumes[sorted_keys[-1]])
        growth_12m = round((last_v - first_v) / first_v, 4) if first_v > 0 else 0.0
    else:
        growth_12m = 0.0

    # 5. Top 5 contre-parties anonymisées
    counterparty_totals: dict[str, dict] = defaultdict(
        lambda: {"total_amount": Decimal("0"), "count": 0}
    )
    for t in sorted_txs:
        counterparty_totals[t.counterparty_hash]["total_amount"] += t.amount
        counterparty_totals[t.counterparty_hash]["count"] += 1
    top_5 = sorted(
        counterparty_totals.items(),
        key=lambda kv: kv[1]["total_amount"],
        reverse=True,
    )[:5]
    top_counterparties = [
        {
            "counterparty_hash": h,
            "total_amount": str(d["total_amount"].quantize(Decimal("0.01"))),
            "transaction_count": d["count"],
        }
        for h, d in top_5
    ]

    result = {
        "monthly_volume_avg": str(Decimal(monthly_avg).quantize(Decimal("0.01"))),
        "monthly_volume_stddev": str(Decimal(monthly_std).quantize(Decimal("0.01"))),
        "regularity_30d": regularity_30d,
        "avg_balance_estimate": str(Decimal(avg_balance).quantize(Decimal("0.01"))),
        "growth_12m": growth_12m,
        "top_counterparties": top_counterparties,
        "transaction_count": len(sorted_txs),
        "period_start": period_start.isoformat() if period_start else None,
        "period_end": period_end.isoformat() if period_end else None,
    }
    logger.info(
        "mm_analysis_computed",
        extra={
            "tx_count": len(sorted_txs),
            "kpi_count": 7,
            "methodology_version": METHODOLOGY_VERSION,
        },
    )
    return result


__all__ = ["compute_kpis", "METHODOLOGY_VERSION"]
