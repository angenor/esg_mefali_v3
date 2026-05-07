"""Router back-office Admin (F02 squelette + endpoint health + F17 seed carbone)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.models.user import User
from app.schemas.admin import AdminHealthResponse


router = APIRouter(dependencies=[Depends(get_current_admin)])


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
