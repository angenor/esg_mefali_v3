"""Sous-router admin /emission-factors (F09 PRIO 3).

CRUD complet sur ``EmissionFactor`` (catalogue F01/F17). Les facteurs sont
seedés par F17 (ADEME, IPCC, IEA) ; cette UI admin permet d'ajouter,
modifier ou publier de nouveaux facteurs.
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
from app.models.emission_factor import EmissionFactor
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


class EmissionFactorCreatePayload(BaseModel):
    code: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., min_length=1, max_length=50)
    country: str = Field(..., min_length=1, max_length=50)
    year: int = Field(..., ge=2000, le=2100)
    value: float = Field(..., ge=0)
    unit: str = Field(..., min_length=1, max_length=50)
    source_id: UUID


class EmissionFactorUpdatePayload(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    value: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, min_length=1, max_length=50)
    source_id: UUID | None = None


def _serialize(ef: EmissionFactor) -> dict[str, Any]:
    return {
        "id": ef.id,
        "code": ef.code,
        "label": ef.label,
        "category": ef.category,
        "country": ef.country,
        "year": ef.year,
        "value": float(ef.value),
        "unit": ef.unit,
        "source_id": ef.source_id,
        "publication_status": ef.publication_status,
        "version": getattr(ef, "version", None),
        "created_at": ef.created_at,
        "updated_at": ef.updated_at,
    }


@router.get("", status_code=status.HTTP_200_OK)
async def list_emission_factors(
    publication_status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    country: str | None = Query(default=None),
    year: int | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(EmissionFactor)
    count_stmt = select(func.count(EmissionFactor.id))
    if publication_status:
        stmt = stmt.where(EmissionFactor.publication_status == publication_status)
        count_stmt = count_stmt.where(
            EmissionFactor.publication_status == publication_status
        )
    if category:
        stmt = stmt.where(EmissionFactor.category == category)
        count_stmt = count_stmt.where(EmissionFactor.category == category)
    if country:
        stmt = stmt.where(EmissionFactor.country == country)
        count_stmt = count_stmt.where(EmissionFactor.country == country)
    if year is not None:
        stmt = stmt.where(EmissionFactor.year == year)
        count_stmt = count_stmt.where(EmissionFactor.year == year)
    if q:
        pattern = f"%{q.lower()}%"
        cond = or_(
            func.lower(EmissionFactor.code).like(pattern),
            func.lower(EmissionFactor.label).like(pattern),
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    offset = (page - 1) * page_size
    stmt = stmt.order_by(EmissionFactor.created_at.desc()).offset(offset).limit(page_size)
    items = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one() or 0
    return {
        "items": [_serialize(e) for e in items],
        "total": total,
        "page": page,
        "limit": page_size,
    }


@router.get("/{factor_id}", status_code=status.HTTP_200_OK)
async def get_emission_factor(
    factor_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await db.execute(select(EmissionFactor).where(EmissionFactor.id == factor_id))
    ef = res.scalar_one_or_none()
    if ef is None:
        raise HTTPException(status_code=404, detail="Facteur d'émission introuvable")
    return _serialize(ef)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_emission_factor(
    payload: EmissionFactorCreatePayload = Body(...),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ef = EmissionFactor(
        code=payload.code,
        label=payload.label,
        category=payload.category,
        country=payload.country,
        year=payload.year,
        value=payload.value,
        unit=payload.unit,
        source_id=payload.source_id,
        created_by_user_id=current_admin.id,
    )
    db.add(ef)
    await db.flush()
    await log_admin_action(
        db,
        admin_id=current_admin.id,
        action="emission_factor_created",
        entity_type="emission_factor",
        entity_id=ef.id,
        metadata={
            "code": payload.code,
            "category": payload.category,
            "country": payload.country,
            "year": payload.year,
        },
    )
    await db.commit()
    return _serialize(ef)


@router.patch("/{factor_id}", status_code=status.HTTP_200_OK)
async def update_emission_factor(
    factor_id: UUID,
    payload: EmissionFactorUpdatePayload = Body(...),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await db.execute(select(EmissionFactor).where(EmissionFactor.id == factor_id))
    ef = res.scalar_one_or_none()
    if ef is None:
        raise HTTPException(status_code=404, detail="Facteur d'émission introuvable")

    changes: dict[str, Any] = {}
    if payload.label is not None:
        ef.label = payload.label
        changes["label"] = payload.label
    if payload.value is not None:
        ef.value = payload.value
        changes["value"] = payload.value
    if payload.unit is not None:
        ef.unit = payload.unit
        changes["unit"] = payload.unit
    if payload.source_id is not None:
        ef.source_id = payload.source_id
        changes["source_id"] = str(payload.source_id)

    await db.flush()
    if changes:
        await log_admin_action(
            db,
            admin_id=current_admin.id,
            action="emission_factor_updated",
            entity_type="emission_factor",
            entity_id=ef.id,
            metadata=changes,
        )
    await db.commit()
    return _serialize(ef)


@router.post(
    "/{factor_id}/publish",
    response_model=PublishResponse,
    status_code=status.HTTP_200_OK,
)
async def publish_emission_factor(
    factor_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> PublishResponse:
    try:
        result = await publish_entity(
            db,
            entity_type="emission_factor",
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
async def delete_emission_factor(
    factor_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await db.execute(select(EmissionFactor).where(EmissionFactor.id == factor_id))
    ef = res.scalar_one_or_none()
    if ef is None:
        raise HTTPException(status_code=404, detail="Facteur d'émission introuvable")
    if ef.publication_status == "published":
        raise HTTPException(
            status_code=409,
            detail="Facteur publié — utiliser le workflow versioning F04",
        )
    await db.delete(ef)
    await log_admin_action(
        db,
        admin_id=current_admin.id,
        action="emission_factor_deleted",
        entity_type="emission_factor",
        entity_id=factor_id,
        metadata={"code": ef.code},
    )
    await db.commit()
    return {"deleted": True, "id": factor_id}
