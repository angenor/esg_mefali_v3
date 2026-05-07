"""F22 — Router FastAPI pour l'endpoint admin metrics validation-failures.

Reference : ``specs/032-decision-tree-with-retry-eval/contracts/admin_metrics_endpoint.md``.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.modules.admin_metrics.service import (
    ValidationFailuresResponse,
    get_validation_failures,
)


router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get(
    "/metrics/validation-failures",
    response_model=ValidationFailuresResponse,
    summary="Agregation des echecs de validation tools (admin only)",
)
async def admin_metrics_validation_failures(
    period: Literal["24h", "7d", "30d"] = Query(
        default="7d",
        description="Periode d'agregation : 24h, 7d ou 30d (defaut 7d).",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Top N tools concernes (1-50, defaut 10).",
    ),
    db: AsyncSession = Depends(get_db),
) -> ValidationFailuresResponse:
    """Retourne l'agregation des echecs de validation tools sur la fenetre.

    L'endpoint est protege par ``require_admin_role`` (cf. F02). Aucun
    contenu brut de ``validation_error`` n'est exposé : seuls les agregats
    (`failure_rate`, `top_tools`) sont retournes.
    """
    return await get_validation_failures(db, period=period, limit=limit)
