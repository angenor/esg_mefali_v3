"""Router FastAPI pour le module Dashboard."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.modules.dashboard.schemas import (
    ActiveIntermediariesResponse,
    ActiveIntermediary,
    DashboardSummary,
)

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardSummary:
    """Retourner la vue synthétique du tableau de bord pour l'utilisateur courant."""
    from app.modules.dashboard.service import get_dashboard_summary

    data = await get_dashboard_summary(db, current_user.id)
    return DashboardSummary(**data)


@router.get(
    "/active-intermediaries",
    response_model=ActiveIntermediariesResponse,
)
async def get_active_intermediaries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ActiveIntermediariesResponse:
    """F21 (US3) — Lister les intermédiaires actifs de la PME courante.

    Liés à au moins une candidature non clôturée. Le fallback capitale
    UEMOA est appliqué pour positionner le marker quand l'intermédiaire
    n'a pas de coordonnées renseignées.
    """
    from app.modules.dashboard.service import _get_active_intermediaries

    items = await _get_active_intermediaries(db, current_user.id)
    return ActiveIntermediariesResponse(
        items=[ActiveIntermediary(**i) for i in items],
        total=len(items),
    )
