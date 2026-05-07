"""Sous-router admin /funds (F09).

CRUD minimal + publish gating. La logique métier complexe (versioning F04,
fund-intermediaries, RAG) est déjà couverte par F08 ; ici on expose les
opérations admin de base et le workflow draft → published.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.models.financing import Fund
from app.models.user import User
from app.modules.admin.audit_helpers import log_admin_action
from app.modules.admin.catalog_publish_helper import (
    EntityNotFoundError,
    PublishGatingError,
    publish_entity,
)
from app.modules.admin.schemas import PublishResponse

logger = logging.getLogger(__name__)


router = APIRouter()


class FundCreatePayload(BaseModel):
    name: str
    description: str | None = None
    amount_min_eur: float | None = None
    amount_max_eur: float | None = None
    sectors: list[str] | None = None
    fund_type: str | None = None


def _serialize_fund(fund: Fund) -> dict:
    return {
        "id": fund.id,
        "name": fund.name,
        "description": getattr(fund, "description", None),
        "publication_status": fund.publication_status,
        "status": fund.status.value if hasattr(fund.status, "value") else str(fund.status),
        "fund_type": getattr(fund, "fund_type", None),
        "created_at": fund.created_at,
        "updated_at": fund.updated_at,
    }


@router.get("", status_code=status.HTTP_200_OK)
async def list_funds(
    publication_status: str | None = Query(default=None),
    fund_type: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(Fund)
    count_stmt = select(func.count(Fund.id))
    if publication_status:
        stmt = stmt.where(Fund.publication_status == publication_status)
        count_stmt = count_stmt.where(Fund.publication_status == publication_status)
    if fund_type:
        stmt = stmt.where(Fund.fund_type == fund_type)
        count_stmt = count_stmt.where(Fund.fund_type == fund_type)
    if q:
        pattern = f"%{q.lower()}%"
        cond = or_(
            func.lower(Fund.name).like(pattern),
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    offset = (page - 1) * page_size
    stmt = stmt.order_by(Fund.created_at.desc()).offset(offset).limit(page_size)

    items = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one() or 0
    return {
        "items": [_serialize_fund(f) for f in items],
        "total": total,
        "page": page,
        "limit": page_size,
    }


@router.get("/{fund_id}", status_code=status.HTTP_200_OK)
async def get_fund(
    fund_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    res = await db.execute(select(Fund).where(Fund.id == fund_id))
    fund = res.scalar_one_or_none()
    if fund is None:
        raise HTTPException(status_code=404, detail="Fund introuvable")
    return _serialize_fund(fund)


@router.post(
    "/{fund_id}/publish",
    response_model=PublishResponse,
    status_code=status.HTTP_200_OK,
)
async def publish_fund(
    fund_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> PublishResponse:
    """Publier un fund (draft → published) avec gating sources verified."""
    try:
        result = await publish_entity(
            db,
            entity_type="fund",
            entity_id=fund_id,
            admin_id=current_admin.id,
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PublishGatingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "publish_gating",
                "message": str(exc),
                "blocking_sources": [str(s) for s in exc.blocking_sources],
            },
        ) from exc
    return PublishResponse(**result)
