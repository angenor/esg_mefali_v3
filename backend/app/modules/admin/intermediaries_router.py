"""Sous-router admin /intermediaries (F09)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.models.financing import Intermediary
from app.models.user import User
from app.modules.admin.catalog_helpers import (
    compute_has_incoherence,
    escape_like_pattern,
)
from app.modules.admin.catalog_publish_helper import (
    EntityNotFoundError,
    PublishGatingError,
    publish_entity,
)
from app.modules.admin.schemas import PublishResponse

logger = logging.getLogger(__name__)


router = APIRouter()


def _serialize(intermediary: Intermediary) -> dict:
    # F25 — exposition des champs versioning F04 pour le catalogue admin US2.
    inter_type = getattr(intermediary, "intermediary_type", None)
    org_type = getattr(intermediary, "organization_type", None)
    return {
        "id": intermediary.id,
        "name": intermediary.name,
        "publication_status": intermediary.publication_status,
        "country": getattr(intermediary, "country", None),
        "intermediary_type": (
            inter_type.value if hasattr(inter_type, "value") else str(inter_type)
        ) if inter_type is not None else None,
        "organization_type": (
            org_type.value if hasattr(org_type, "value") else str(org_type)
        ) if org_type is not None else None,
        "version": getattr(intermediary, "version", None),
        "valid_from": getattr(intermediary, "valid_from", None),
        "valid_to": getattr(intermediary, "valid_to", None),
        "superseded_by": getattr(intermediary, "superseded_by", None),
        "source_id": getattr(intermediary, "source_id", None),
        "has_incoherence": compute_has_incoherence(intermediary, "intermediary"),
        "created_at": intermediary.created_at,
        "updated_at": intermediary.updated_at,
    }


@router.get("", status_code=status.HTTP_200_OK)
async def list_intermediaries(
    publication_status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(Intermediary)
    count_stmt = select(func.count(Intermediary.id))
    if publication_status:
        stmt = stmt.where(Intermediary.publication_status == publication_status)
        count_stmt = count_stmt.where(Intermediary.publication_status == publication_status)
    if q:
        pattern = f"%{escape_like_pattern(q.lower())}%"
        cond = or_(func.lower(Intermediary.name).like(pattern, escape="\\"))
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)
    offset = (page - 1) * page_size
    stmt = stmt.order_by(Intermediary.created_at.desc()).offset(offset).limit(page_size)
    items = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one() or 0
    return {
        "items": [_serialize(i) for i in items],
        "total": total,
        "page": page,
        "limit": page_size,
    }


@router.get("/{intermediary_id}", status_code=status.HTTP_200_OK)
async def get_intermediary(
    intermediary_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    res = await db.execute(
        select(Intermediary).where(Intermediary.id == intermediary_id)
    )
    inter = res.scalar_one_or_none()
    if inter is None:
        raise HTTPException(status_code=404, detail="Intermediary introuvable")
    return _serialize(inter)


@router.post(
    "/{intermediary_id}/publish",
    response_model=PublishResponse,
    status_code=status.HTTP_200_OK,
)
async def publish_intermediary(
    intermediary_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> PublishResponse:
    try:
        result = await publish_entity(
            db,
            entity_type="intermediary",
            entity_id=intermediary_id,
            admin_id=current_admin.id,
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PublishGatingError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "publish_gating",
                "message": str(exc),
                "blocking_sources": [str(s) for s in exc.blocking_sources],
            },
        ) from exc
    return PublishResponse(**result)
