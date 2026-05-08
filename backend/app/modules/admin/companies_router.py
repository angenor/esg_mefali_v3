"""Sous-router admin /companies (F09 PRIO 3).

Vue cross-tenant pour consultation admin (read-only) des comptes PME.
Chaque ``GET /api/admin/companies/{account_id}`` déclenche un audit log
``view_admin`` (F03) avec dédup quotidienne — visible côté PME via
``/api/audit/me``.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.models.user import User
from app.modules.admin.companies_service import (
    AccountNotFoundError,
    get_company_overview,
    list_accounts,
)

logger = logging.getLogger(__name__)


router = APIRouter()


@router.get("", status_code=status.HTTP_200_OK)
async def list_companies(
    is_active: bool | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Liste paginée des comptes PME (cross-tenant)."""
    return await list_accounts(
        db,
        is_active=is_active,
        q=q,
        page=page,
        page_size=page_size,
    )


@router.get("/{account_id}", status_code=status.HTTP_200_OK)
async def get_company_overview_endpoint(
    account_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Vue overview agrégée d'un compte PME.

    Déclenche un audit log ``view_admin`` (F03) avec dédup quotidienne.
    """
    try:
        overview = await get_company_overview(
            db,
            account_id=account_id,
            admin_id=current_admin.id,
        )
        await db.commit()
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return overview
