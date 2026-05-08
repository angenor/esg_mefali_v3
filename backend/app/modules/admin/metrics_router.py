"""Sous-router admin /metrics (F09 PRIO 3).

Expose ``GET /api/admin/metrics/overview`` qui agrège les KPIs sources /
comptes / candidatures / attestations pour le dashboard admin.

Note : F22 expose ``/metrics/validation-failures`` via un router séparé
(``admin_metrics_router``). Les deux cohabitent sous le préfixe
``/api/admin``.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.models.user import User
from app.modules.admin.metrics_service import compute_overview

logger = logging.getLogger(__name__)


router = APIRouter()


@router.get("/overview", status_code=status.HTTP_200_OK)
async def get_metrics_overview(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retourne l'agrégation des métriques globales pour le back-office.

    Sections :
    - sources (total, breakdown par status verification)
    - accounts (total, active, new_30d)
    - applications (total, by_status, submission_rate)
    - attestations (total, active, revoked, expired)
    - llm_costs (placeholder MVP).
    """
    return await compute_overview(db)
