"""Router back-office Admin (F02 squelette + endpoint health + F17 seed carbone).

F09 : ajoute les sous-routers core (sources, funds, intermediaries, offers,
users) sous des préfixes dédiés.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.models.user import User
from app.modules.admin.companies_router import router as companies_router
from app.modules.admin.criteria_router import router as criteria_router
from app.modules.admin.emission_factors_router import (
    router as emission_factors_router,
)
from app.modules.admin.funds_router import router as funds_router
from app.modules.admin.indicators_router import router as indicators_router
from app.modules.admin.intermediaries_router import router as intermediaries_router
from app.modules.admin.metrics_router import router as metrics_router
from app.modules.admin.offers_router import router as offers_router
from app.modules.admin.referentials_router import router as referentials_router
from app.modules.admin.simulation_factors_router import (
    router as simulation_factors_router,
)
from app.modules.admin.sources_router import router as sources_router
from app.modules.admin.users_router import router as users_router
from app.schemas.admin import AdminHealthResponse


router = APIRouter(dependencies=[Depends(get_current_admin)])

# F09 — sous-routers admin (PRIO 1)
router.include_router(funds_router, prefix="/funds", tags=["admin-funds"])
router.include_router(
    intermediaries_router,
    prefix="/intermediaries",
    tags=["admin-intermediaries"],
)
router.include_router(offers_router, prefix="/offers", tags=["admin-offers"])
router.include_router(sources_router, prefix="/sources", tags=["admin-sources"])
router.include_router(users_router, prefix="/users", tags=["admin-users"])

# F09 — sous-routers admin (PRIO 3)
router.include_router(
    referentials_router, prefix="/referentials", tags=["admin-referentials"],
)
router.include_router(
    indicators_router, prefix="/indicators", tags=["admin-indicators"],
)
router.include_router(
    criteria_router, prefix="/criteria", tags=["admin-criteria"],
)
router.include_router(
    emission_factors_router,
    prefix="/emission-factors",
    tags=["admin-emission-factors"],
)
router.include_router(
    simulation_factors_router,
    prefix="/simulation-factors",
    tags=["admin-simulation-factors"],
)
router.include_router(
    companies_router, prefix="/companies", tags=["admin-companies"],
)
router.include_router(
    metrics_router, prefix="/metrics", tags=["admin-metrics-overview"],
)


@router.get("/health", response_model=AdminHealthResponse)
async def admin_health(
    current_admin: User = Depends(get_current_admin),
) -> AdminHealthResponse:
    """Health check du back-office. 200 si Admin, 403 sinon."""
    return AdminHealthResponse(
        status="ok",
        role=current_admin.role,
        service="admin-backoffice",
    )


# ---------- F17 — Seed des facteurs d'emission ----------


class SeedFactorsResponse(BaseModel):
    """Reponse du seed des facteurs d'emission (F17)."""

    inserted: int
    skipped: int
    total_in_db: int


@router.post("/carbon/seed-factors", response_model=SeedFactorsResponse)
async def seed_carbon_factors(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> SeedFactorsResponse:
    """Seed idempotent des facteurs d'emission catalogue (F17).

    Reservee aux admins (workflow `Depends(get_current_admin)`). Le seed peut
    etre relance sans risque : ON CONFLICT (code) DO NOTHING au niveau
    applicatif.

    Returns:
        SeedFactorsResponse(inserted, skipped, total_in_db).
    """
    from app.modules.carbon.seed_factors import seed_emission_factors

    result = await seed_emission_factors(db, current_admin.id)
    return SeedFactorsResponse(
        inserted=result.inserted,
        skipped=result.skipped,
        total_in_db=result.total_in_db,
    )
