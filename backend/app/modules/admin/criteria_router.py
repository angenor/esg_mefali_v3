"""Sous-router admin /criteria (F09 PRIO 3).

CRUD complet sur ``Criterion`` (catalogue F01) avec workflow draft/published.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.models.indicator import Criterion
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


class CriterionCreatePayload(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    label: str = Field(..., min_length=1, max_length=200)
    expression: dict = Field(..., description="Expression logique JSONB")
    source_id: UUID


class CriterionUpdatePayload(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    expression: dict | None = None
    source_id: UUID | None = None


def _serialize(crit: Criterion) -> dict[str, Any]:
    return {
        "id": crit.id,
        "code": crit.code,
        "label": crit.label,
        "expression": crit.expression,
        "source_id": crit.source_id,
        "publication_status": crit.publication_status,
        "version": getattr(crit, "version", None),
        "created_at": crit.created_at,
        "updated_at": crit.updated_at,
    }


@router.get("", status_code=status.HTTP_200_OK)
async def list_criteria(
    publication_status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(Criterion)
    count_stmt = select(func.count(Criterion.id))
    if publication_status:
        stmt = stmt.where(Criterion.publication_status == publication_status)
        count_stmt = count_stmt.where(
            Criterion.publication_status == publication_status
        )
    if q:
        pattern = f"%{q.lower()}%"
        cond = or_(
            func.lower(Criterion.code).like(pattern),
            func.lower(Criterion.label).like(pattern),
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    offset = (page - 1) * page_size
    stmt = stmt.order_by(Criterion.created_at.desc()).offset(offset).limit(page_size)
    items = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one() or 0
    return {
        "items": [_serialize(c) for c in items],
        "total": total,
        "page": page,
        "limit": page_size,
    }


@router.get("/{criterion_id}", status_code=status.HTTP_200_OK)
async def get_criterion(
    criterion_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await db.execute(select(Criterion).where(Criterion.id == criterion_id))
    crit = res.scalar_one_or_none()
    if crit is None:
        raise HTTPException(status_code=404, detail="Critère introuvable")
    return _serialize(crit)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_criterion(
    payload: CriterionCreatePayload = Body(...),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    crit = Criterion(
        code=payload.code,
        label=payload.label,
        expression=payload.expression,
        source_id=payload.source_id,
        created_by_user_id=current_admin.id,
    )
    db.add(crit)
    await db.flush()
    await log_admin_action(
        db,
        admin_id=current_admin.id,
        action="criterion_created",
        entity_type="criterion",
        entity_id=crit.id,
        metadata={"code": payload.code},
    )
    await db.commit()
    return _serialize(crit)


@router.patch("/{criterion_id}", status_code=status.HTTP_200_OK)
async def update_criterion(
    criterion_id: UUID,
    payload: CriterionUpdatePayload = Body(...),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await db.execute(select(Criterion).where(Criterion.id == criterion_id))
    crit = res.scalar_one_or_none()
    if crit is None:
        raise HTTPException(status_code=404, detail="Critère introuvable")

    changes: dict[str, Any] = {}
    if payload.label is not None:
        crit.label = payload.label
        changes["label"] = payload.label
    if payload.expression is not None:
        crit.expression = payload.expression
        changes["expression"] = "updated"
    if payload.source_id is not None:
        crit.source_id = payload.source_id
        changes["source_id"] = str(payload.source_id)

    await db.flush()
    if changes:
        await log_admin_action(
            db,
            admin_id=current_admin.id,
            action="criterion_updated",
            entity_type="criterion",
            entity_id=crit.id,
            metadata=changes,
        )
    await db.commit()
    return _serialize(crit)


@router.post(
    "/{criterion_id}/publish",
    response_model=PublishResponse,
    status_code=status.HTTP_200_OK,
)
async def publish_criterion(
    criterion_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> PublishResponse:
    try:
        result = await publish_entity(
            db,
            entity_type="criterion",
            entity_id=criterion_id,
            admin_id=current_admin.id,
        )
        await db.commit()
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


@router.delete("/{criterion_id}", status_code=status.HTTP_200_OK)
async def delete_criterion(
    criterion_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await db.execute(select(Criterion).where(Criterion.id == criterion_id))
    crit = res.scalar_one_or_none()
    if crit is None:
        raise HTTPException(status_code=404, detail="Critère introuvable")
    if crit.publication_status == "published":
        raise HTTPException(
            status_code=409,
            detail="Critère publié — utiliser le workflow versioning F04",
        )
    await db.delete(crit)
    await log_admin_action(
        db,
        admin_id=current_admin.id,
        action="criterion_deleted",
        entity_type="criterion",
        entity_id=criterion_id,
        metadata={"code": crit.code},
    )
    await db.commit()
    return {"deleted": True, "id": criterion_id}
