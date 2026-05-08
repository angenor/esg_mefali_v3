"""Sous-router admin /simulation-factors (F09 PRIO 3).

CRUD complet sur ``SimulationFactor`` (catalogue F01). Workflow status
verified/pending (cohabite avec publication_status draft/published).
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
from app.models.simulation_factor import SimulationFactor
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


class SimulationFactorCreatePayload(BaseModel):
    code: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=200)
    value: float = Field(...)
    unit: str = Field(..., min_length=1, max_length=50)
    scope: str = Field(..., min_length=1, max_length=100)
    source_id: UUID | None = None
    status: str = Field(default="pending", pattern="^(verified|pending)$")


class SimulationFactorUpdatePayload(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    value: float | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=50)
    scope: str | None = Field(default=None, min_length=1, max_length=100)
    source_id: UUID | None = None
    status: str | None = Field(default=None, pattern="^(verified|pending)$")


def _serialize(sf: SimulationFactor) -> dict[str, Any]:
    return {
        "id": sf.id,
        "code": sf.code,
        "label": sf.label,
        "value": float(sf.value),
        "unit": sf.unit,
        "scope": sf.scope,
        "source_id": sf.source_id,
        "status": sf.status,
        "publication_status": getattr(sf, "publication_status", "draft"),
        "version": getattr(sf, "version", None),
        "created_at": sf.created_at,
        "updated_at": sf.updated_at,
    }


@router.get("", status_code=status.HTTP_200_OK)
async def list_simulation_factors(
    publication_status: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    scope: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(SimulationFactor)
    count_stmt = select(func.count(SimulationFactor.id))
    if publication_status:
        stmt = stmt.where(SimulationFactor.publication_status == publication_status)
        count_stmt = count_stmt.where(
            SimulationFactor.publication_status == publication_status
        )
    if status_filter:
        stmt = stmt.where(SimulationFactor.status == status_filter)
        count_stmt = count_stmt.where(SimulationFactor.status == status_filter)
    if scope:
        stmt = stmt.where(SimulationFactor.scope == scope)
        count_stmt = count_stmt.where(SimulationFactor.scope == scope)
    if q:
        pattern = f"%{q.lower()}%"
        cond = or_(
            func.lower(SimulationFactor.code).like(pattern),
            func.lower(SimulationFactor.label).like(pattern),
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    offset = (page - 1) * page_size
    stmt = stmt.order_by(SimulationFactor.created_at.desc()).offset(offset).limit(page_size)
    items = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one() or 0
    return {
        "items": [_serialize(s) for s in items],
        "total": total,
        "page": page,
        "limit": page_size,
    }


@router.get("/{factor_id}", status_code=status.HTTP_200_OK)
async def get_simulation_factor(
    factor_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await db.execute(
        select(SimulationFactor).where(SimulationFactor.id == factor_id)
    )
    sf = res.scalar_one_or_none()
    if sf is None:
        raise HTTPException(status_code=404, detail="Constante de simulation introuvable")
    return _serialize(sf)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_simulation_factor(
    payload: SimulationFactorCreatePayload = Body(...),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Crée une constante. Si status=verified → source_id obligatoire (CHECK BDD)."""
    if payload.status == "verified" and payload.source_id is None:
        raise HTTPException(
            status_code=422,
            detail="status=verified requiert source_id",
        )
    if payload.status == "pending" and payload.source_id is not None:
        raise HTTPException(
            status_code=422,
            detail="status=pending requiert source_id=null",
        )
    sf = SimulationFactor(
        code=payload.code,
        label=payload.label,
        value=payload.value,
        unit=payload.unit,
        scope=payload.scope,
        source_id=payload.source_id,
        status=payload.status,
        created_by_user_id=current_admin.id,
    )
    db.add(sf)
    await db.flush()
    await log_admin_action(
        db,
        admin_id=current_admin.id,
        action="simulation_factor_created",
        entity_type="simulation_factor",
        entity_id=sf.id,
        metadata={"code": payload.code, "status": payload.status},
    )
    await db.commit()
    return _serialize(sf)


@router.patch("/{factor_id}", status_code=status.HTTP_200_OK)
async def update_simulation_factor(
    factor_id: UUID,
    payload: SimulationFactorUpdatePayload = Body(...),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await db.execute(
        select(SimulationFactor).where(SimulationFactor.id == factor_id)
    )
    sf = res.scalar_one_or_none()
    if sf is None:
        raise HTTPException(status_code=404, detail="Constante de simulation introuvable")

    changes: dict[str, Any] = {}
    if payload.label is not None:
        sf.label = payload.label
        changes["label"] = payload.label
    if payload.value is not None:
        sf.value = payload.value
        changes["value"] = payload.value
    if payload.unit is not None:
        sf.unit = payload.unit
        changes["unit"] = payload.unit
    if payload.scope is not None:
        sf.scope = payload.scope
        changes["scope"] = payload.scope
    # Cohérence status / source_id (CHECK BDD).
    new_status = payload.status if payload.status is not None else sf.status
    new_source_id = payload.source_id if payload.source_id is not None else sf.source_id
    # Si on demande explicitement source_id=null via patch (impossible avec
    # Pydantic optionnel — donc on laisse passer le check BDD le cas échéant).
    if new_status == "verified" and new_source_id is None:
        raise HTTPException(status_code=422, detail="status=verified requiert source_id")
    if new_status == "pending" and new_source_id is not None and payload.status == "pending":
        raise HTTPException(status_code=422, detail="status=pending requiert source_id=null")

    if payload.status is not None:
        sf.status = payload.status
        changes["status"] = payload.status
    if payload.source_id is not None:
        sf.source_id = payload.source_id
        changes["source_id"] = str(payload.source_id)

    await db.flush()
    if changes:
        await log_admin_action(
            db,
            admin_id=current_admin.id,
            action="simulation_factor_updated",
            entity_type="simulation_factor",
            entity_id=sf.id,
            metadata=changes,
        )
    await db.commit()
    return _serialize(sf)


@router.post(
    "/{factor_id}/publish",
    response_model=PublishResponse,
    status_code=status.HTTP_200_OK,
)
async def publish_simulation_factor(
    factor_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> PublishResponse:
    try:
        result = await publish_entity(
            db,
            entity_type="simulation_factor",
            entity_id=factor_id,
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


@router.delete("/{factor_id}", status_code=status.HTTP_200_OK)
async def delete_simulation_factor(
    factor_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await db.execute(
        select(SimulationFactor).where(SimulationFactor.id == factor_id)
    )
    sf = res.scalar_one_or_none()
    if sf is None:
        raise HTTPException(status_code=404, detail="Constante de simulation introuvable")
    if getattr(sf, "publication_status", "draft") == "published":
        raise HTTPException(
            status_code=409,
            detail="Constante publiée — utiliser le workflow versioning F04",
        )
    await db.delete(sf)
    await log_admin_action(
        db,
        admin_id=current_admin.id,
        action="simulation_factor_deleted",
        entity_type="simulation_factor",
        entity_id=factor_id,
        metadata={"code": sf.code},
    )
    await db.commit()
    return {"deleted": True, "id": factor_id}
