"""F22 — Service d'agregation des echecs de validation tools (admin metrics).

Calcule :
- ``total_calls`` : nombre total d'appels tool sur la periode.
- ``failure_count`` : nombre d'appels avec ``validation_error IS NOT NULL``.
- ``failure_rate`` : ratio des deux.
- ``top_tools`` : top N tools par nombre d'echecs (desc).
- ``alert`` : True si ``failure_rate > alert_threshold`` (defaut 0.05).

Reference : ``specs/032-decision-tree-with-retry-eval/contracts/admin_metrics_endpoint.md``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_call_log import ToolCallLog


PeriodLiteral = Literal["24h", "7d", "30d"]


PERIOD_TIMEDELTA: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


# ─── Schemas ────────────────────────────────────────────────────────────────


class TopToolFailure(BaseModel):
    """Top tool agrege par nombre d'echecs."""

    tool_name: str
    count: int
    rate: float = Field(
        ...,
        description="failure_count_for_this_tool / total_calls_for_this_tool",
    )


class ValidationFailuresResponse(BaseModel):
    """Reponse JSON de l'endpoint admin metrics."""

    period: PeriodLiteral
    from_iso: datetime
    to_iso: datetime
    total_calls: int
    failure_count: int
    failure_rate: float
    top_tools: list[TopToolFailure]
    alert: bool
    alert_threshold: float = 0.05


# ─── Service ────────────────────────────────────────────────────────────────


async def get_validation_failures(
    db: AsyncSession,
    *,
    period: PeriodLiteral = "7d",
    limit: int = 10,
    alert_threshold: float = 0.05,
) -> ValidationFailuresResponse:
    """Agregation principale des echecs de validation sur la fenetre demandee.

    Returns:
        ValidationFailuresResponse — pret pour le serializer FastAPI.
    """
    if period not in PERIOD_TIMEDELTA:
        raise ValueError(f"Periode invalide : {period!r}")

    if not 1 <= limit <= 50:
        raise ValueError(f"Limit doit etre dans [1, 50], got {limit}")

    to_iso = datetime.now(timezone.utc)
    from_iso = to_iso - PERIOD_TIMEDELTA[period]

    # Total + failure_count global
    failure_marker = case(
        (ToolCallLog.validation_error.is_not(None), 1),
        else_=0,
    )

    global_q = select(
        func.count(ToolCallLog.id).label("total"),
        func.sum(failure_marker).label("failures"),
    ).where(
        ToolCallLog.created_at >= from_iso,
        ToolCallLog.created_at < to_iso,
    )
    res = await db.execute(global_q)
    row = res.one()
    total_calls = int(row.total or 0)
    failure_count = int(row.failures or 0)

    failure_rate = (
        round(failure_count / total_calls, 3) if total_calls > 0 else 0.0
    )

    # Top tools par nombre d'echecs (desc)
    if total_calls == 0:
        top_tools: list[TopToolFailure] = []
    else:
        per_tool_q = (
            select(
                ToolCallLog.tool_name,
                func.count(ToolCallLog.id).label("total_for_tool"),
                func.sum(failure_marker).label("failures_for_tool"),
            )
            .where(
                ToolCallLog.created_at >= from_iso,
                ToolCallLog.created_at < to_iso,
            )
            .group_by(ToolCallLog.tool_name)
            .having(func.sum(failure_marker) > 0)
            .order_by(func.sum(failure_marker).desc())
            .limit(limit)
        )
        per_tool_res = await db.execute(per_tool_q)
        top_tools = [
            TopToolFailure(
                tool_name=r.tool_name,
                count=int(r.failures_for_tool or 0),
                rate=round(
                    int(r.failures_for_tool or 0)
                    / int(r.total_for_tool or 1),
                    3,
                ),
            )
            for r in per_tool_res.all()
        ]

    alert = failure_rate > alert_threshold

    return ValidationFailuresResponse(
        period=period,
        from_iso=from_iso,
        to_iso=to_iso,
        total_calls=total_calls,
        failure_count=failure_count,
        failure_rate=failure_rate,
        top_tools=top_tools,
        alert=alert,
        alert_threshold=alert_threshold,
    )
