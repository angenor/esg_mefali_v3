"""F20 — Router public REST pour les Resources.

Endpoints :
- GET    /api/resources                                 → liste paginée publique.
- GET    /api/resources/{slug}                          → détail public.
- POST   /api/resources/{slug}/view                     → +1 view_count.
- GET    /api/intermediaries/{id}/guide                 → fiche pratique.

Auth : aucune requise pour les GET et le POST view (anonyme).
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.resources.exceptions import ResourceNotFoundError
from app.modules.resources.schemas import (
    ResourceListItem,
    ResourceListResponse,
    ResourceReadPublic,
    ViewCountResponse,
)
from app.modules.resources.service import ResourceService

logger = logging.getLogger(__name__)

router = APIRouter()
intermediaries_router = APIRouter()


@router.get("", response_model=ResourceListResponse)
async def list_resources(
    type: str | None = Query(default=None),
    category: str | None = Query(default=None),
    language: str | None = Query(default=None),
    intermediary_id: uuid.UUID | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> ResourceListResponse:
    service = ResourceService(db)
    items, total = await service.list_published(
        type_=type,
        category=category,
        language=language,
        intermediary_id=intermediary_id,
        q=q,
        page=page,
        limit=limit,
    )
    return ResourceListResponse(
        items=[ResourceListItem.model_validate(r) for r in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{slug}", response_model=ResourceReadPublic)
async def get_resource(slug: str, db: AsyncSession = Depends(get_db)) -> ResourceReadPublic:
    service = ResourceService(db)
    resource = await service.get_by_slug(slug)
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "resource_not_found", "slug": slug},
        )
    return ResourceReadPublic.model_validate(resource)


@router.post("/{slug}/view", response_model=ViewCountResponse)
async def increment_view(
    slug: str, db: AsyncSession = Depends(get_db)
) -> ViewCountResponse:
    service = ResourceService(db)
    try:
        new_count = await service.increment_view_count(slug)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "resource_not_found", "slug": slug},
        ) from exc
    await db.commit()
    return ViewCountResponse(slug=slug, view_count=new_count)


@intermediaries_router.get("/{intermediary_id}/guide", response_model=ResourceReadPublic)
async def get_intermediary_guide(
    intermediary_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> ResourceReadPublic:
    service = ResourceService(db)
    resource = await service.get_intermediary_guide(intermediary_id)
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "intermediary_guide_not_found",
                "intermediary_id": str(intermediary_id),
            },
        )
    return ResourceReadPublic.model_validate(resource)
