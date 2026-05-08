"""Sous-router admin /indicators (F09 PRIO 3).

CRUD complet sur ``Indicator`` (catalogue F01) avec workflow draft/published.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.models.indicator import Indicator
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


_VALID_PILLARS = {"environment", "social", "governance"}


class IndicatorCreatePayload(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    pillar: str = Field(...)
    label: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    source_id: UUID

    @field_validator("pillar")
    @classmethod
    def _check_pillar(cls, v: str) -> str:
        if v not in _VALID_PILLARS:
            raise ValueError(f"pillar must be in {sorted(_VALID_PILLARS)}")
        return v


class IndicatorUpdatePayload(BaseModel):
    pillar: str | None = None
    label: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    question: str | None = None
    source_id: UUID | None = None

    @field_validator("pillar")
    @classmethod
    def _check_pillar(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_PILLARS:
            raise ValueError(f"pillar must be in {sorted(_VALID_PILLARS)}")
        return v


def _serialize(ind: Indicator) -> dict[str, Any]:
    return {
        "id": ind.id,
        "code": ind.code,
        "pillar": ind.pillar,
        "label": ind.label,
        "description": ind.description,
        "question": ind.question,
        "source_id": ind.source_id,
        "publication_status": ind.publication_status,
        "version": getattr(ind, "version", None),
        "created_at": ind.created_at,
        "updated_at": ind.updated_at,
    }


@router.get("", status_code=status.HTTP_200_OK)
async def list_indicators(
    publication_status: str | None = Query(default=None),
    pillar: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(Indicator)
    count_stmt = select(func.count(Indicator.id))
    if publication_status:
        stmt = stmt.where(Indicator.publication_status == publication_status)
        count_stmt = count_stmt.where(
            Indicator.publication_status == publication_status
        )
    if pillar:
        stmt = stmt.where(Indicator.pillar == pillar)
        count_stmt = count_stmt.where(Indicator.pillar == pillar)
    if q:
        pattern = f"%{q.lower()}%"
        cond = or_(
            func.lower(Indicator.code).like(pattern),
            func.lower(Indicator.label).like(pattern),
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    offset = (page - 1) * page_size
    stmt = stmt.order_by(Indicator.created_at.desc()).offset(offset).limit(page_size)
    items = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one() or 0
    return {
        "items": [_serialize(i) for i in items],
        "total": total,
        "page": page,
        "limit": page_size,
    }


@router.get("/{indicator_id}", status_code=status.HTTP_200_OK)
async def get_indicator(
    indicator_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await db.execute(select(Indicator).where(Indicator.id == indicator_id))
    ind = res.scalar_one_or_none()
    if ind is None:
        raise HTTPException(status_code=404, detail="Indicateur introuvable")
    return _serialize(ind)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_indicator(
    payload: IndicatorCreatePayload = Body(...),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ind = Indicator(
        code=payload.code,
        pillar=payload.pillar,
        label=payload.label,
        description=payload.description,
        question=payload.question,
        source_id=payload.source_id,
        created_by_user_id=current_admin.id,
    )
    db.add(ind)
    await db.flush()
    await log_admin_action(
        db,
        admin_id=current_admin.id,
        action="indicator_created",
        entity_type="indicator",
        entity_id=ind.id,
        metadata={"code": payload.code, "pillar": payload.pillar},
    )
    await db.commit()
    return _serialize(ind)


@router.patch("/{indicator_id}", status_code=status.HTTP_200_OK)
async def update_indicator(
    indicator_id: UUID,
    payload: IndicatorUpdatePayload = Body(...),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await db.execute(select(Indicator).where(Indicator.id == indicator_id))
    ind = res.scalar_one_or_none()
    if ind is None:
        raise HTTPException(status_code=404, detail="Indicateur introuvable")

    changes: dict[str, Any] = {}
    if payload.pillar is not None:
        ind.pillar = payload.pillar
        changes["pillar"] = payload.pillar
    if payload.label is not None:
        ind.label = payload.label
        changes["label"] = payload.label
    if payload.description is not None:
        ind.description = payload.description
        changes["description"] = "updated"
    if payload.question is not None:
        ind.question = payload.question
        changes["question"] = "updated"
    if payload.source_id is not None:
        ind.source_id = payload.source_id
        changes["source_id"] = str(payload.source_id)

    await db.flush()
    if changes:
        await log_admin_action(
            db,
            admin_id=current_admin.id,
            action="indicator_updated",
            entity_type="indicator",
            entity_id=ind.id,
            metadata=changes,
        )
    await db.commit()
    return _serialize(ind)


@router.post(
    "/{indicator_id}/publish",
    response_model=PublishResponse,
    status_code=status.HTTP_200_OK,
)
async def publish_indicator(
    indicator_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> PublishResponse:
    try:
        result = await publish_entity(
            db,
            entity_type="indicator",
            entity_id=indicator_id,
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


@router.delete("/{indicator_id}", status_code=status.HTTP_200_OK)
async def delete_indicator(
    indicator_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await db.execute(select(Indicator).where(Indicator.id == indicator_id))
    ind = res.scalar_one_or_none()
    if ind is None:
        raise HTTPException(status_code=404, detail="Indicateur introuvable")
    if ind.publication_status == "published":
        raise HTTPException(
            status_code=409,
            detail="Indicateur publié — utiliser le workflow versioning F04",
        )
    await db.delete(ind)
    await log_admin_action(
        db,
        admin_id=current_admin.id,
        action="indicator_deleted",
        entity_type="indicator",
        entity_id=indicator_id,
        metadata={"code": ind.code},
    )
    await db.commit()
    return {"deleted": True, "id": indicator_id}
