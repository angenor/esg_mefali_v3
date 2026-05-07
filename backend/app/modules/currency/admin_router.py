"""F04 — Endpoint admin du module currency (fetch status)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.models.user import User
from app.modules.currency import service as currency_service
from app.modules.currency.schemas import FetchStatusResponse


router = APIRouter()


@router.get("/fetch-status", response_model=FetchStatusResponse)
async def get_fetch_status(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> FetchStatusResponse:
    """Statut courant du fetch quotidien exchangerate-api.com (admin only)."""
    summary = await currency_service.fetch_status_summary(db)
    return FetchStatusResponse(**summary)
