"""Sous-router admin /referentials (F09 PRIO 3).

CRUD complet sur ``Referential`` (catalogue F01) avec workflow draft/published
et publish gating sur sources verified. Réutilise le pattern de
``funds_router`` / ``intermediaries_router``.
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
from app.models.referential import Referential
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


class ReferentialCreatePayload(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    label: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    source_id: UUID


class ReferentialUpdatePayload(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    source_id: UUID | None = None


def _serialize(ref: Referential) -> dict[str, Any]:
    return {
        "id": ref.id,
        "code": ref.code,
        "label": ref.label,
        "description": ref.description,
        "source_id": ref.source_id,
        "publication_status": ref.publication_status,
        "version": getattr(ref, "version", None),
        "valid_from": getattr(ref, "valid_from", None),
        "valid_to": getattr(ref, "valid_to", None),
        "created_at": ref.created_at,
        "updated_at": ref.updated_at,
    }


@router.get("", status_code=status.HTTP_200_OK)
async def list_referentials(
    publication_status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(Referential)
    count_stmt = select(func.count(Referential.id))
    if publication_status:
        stmt = stmt.where(Referential.publication_status == publication_status)
        count_stmt = count_stmt.where(
            Referential.publication_status == publication_status
        )
    if q:
        pattern = f"%{q.lower()}%"
        cond = or_(
            func.lower(Referential.code).like(pattern),
            func.lower(Referential.label).like(pattern),
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    offset = (page - 1) * page_size
    stmt = stmt.order_by(Referential.created_at.desc()).offset(offset).limit(page_size)
    items = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one() or 0
    return {
        "items": [_serialize(r) for r in items],
        "total": total,
        "page": page,
        "limit": page_size,
    }


@router.get("/{referential_id}", status_code=status.HTTP_200_OK)
async def get_referential(
    referential_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await db.execute(select(Referential).where(Referential.id == referential_id))
    ref = res.scalar_one_or_none()
    if ref is None:
        raise HTTPException(status_code=404, detail="Référentiel introuvable")
    return _serialize(ref)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_referential(
    payload: ReferentialCreatePayload = Body(...),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Créer un nouveau référentiel en draft."""
    ref = Referential(
        code=payload.code,
        label=payload.label,
        description=payload.description,
        source_id=payload.source_id,
        created_by_user_id=current_admin.id,
    )
    db.add(ref)
    await db.flush()
    await log_admin_action(
        db,
        admin_id=current_admin.id,
        action="referential_created",
        entity_type="referential",
        entity_id=ref.id,
        metadata={"code": payload.code},
    )
    await db.commit()
    return _serialize(ref)


@router.patch("/{referential_id}", status_code=status.HTTP_200_OK)
async def update_referential(
    referential_id: UUID,
    payload: ReferentialUpdatePayload = Body(...),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await db.execute(select(Referential).where(Referential.id == referential_id))
    ref = res.scalar_one_or_none()
    if ref is None:
        raise HTTPException(status_code=404, detail="Référentiel introuvable")

    changes: dict[str, Any] = {}
    if payload.label is not None:
        ref.label = payload.label
        changes["label"] = payload.label
    if payload.description is not None:
        ref.description = payload.description
        changes["description"] = "updated"
    if payload.source_id is not None:
        ref.source_id = payload.source_id
        changes["source_id"] = str(payload.source_id)

    if changes:
        await log_admin_action(
            db,
            admin_id=current_admin.id,
            action="referential_updated",
            entity_type="referential",
            entity_id=ref.id,
            metadata=changes,
        )
    await db.commit()
    return _serialize(ref)


@router.post(
    "/{referential_id}/publish",
    response_model=PublishResponse,
    status_code=status.HTTP_200_OK,
)
async def publish_referential(
    referential_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> PublishResponse:
    """Publier un référentiel (draft → published) avec gating sources verified."""
    try:
        result = await publish_entity(
            db,
            entity_type="referential",
            entity_id=referential_id,
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


@router.delete("/{referential_id}", status_code=status.HTTP_200_OK)
async def delete_referential(
    referential_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Suppression douce d'un référentiel (drafts uniquement, MVP).

    Refus si publié (workflow F04 versioning ; un référentiel publié doit
    être superseded plutôt que supprimé).
    """
    res = await db.execute(select(Referential).where(Referential.id == referential_id))
    ref = res.scalar_one_or_none()
    if ref is None:
        raise HTTPException(status_code=404, detail="Référentiel introuvable")
    if ref.publication_status == "published":
        raise HTTPException(
            status_code=409,
            detail="Référentiel publié — utiliser le workflow versioning F04",
        )
    await db.delete(ref)
    await log_admin_action(
        db,
        admin_id=current_admin.id,
        action="referential_deleted",
        entity_type="referential",
        entity_id=referential_id,
        metadata={"code": ref.code},
    )
    await db.commit()
    return {"deleted": True, "id": referential_id}
