"""Router FastAPI pour le catalogue Source (F01)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_user
from app.core.constants import UserRole
from app.core.database import get_db
from app.models.user import User
from app.modules.sources.service import (
    FourEyesViolation,
    InvalidStateTransition,
    SourceNotFound,
    SourceService,
)
from app.schemas.source import (
    PaginatedSources,
    Source,
    SourceCreate,
    SourceListItem,
    SourceMarkOutdated,
    SourceUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=PaginatedSources)
async def list_sources(
    publisher: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedSources:
    """Liste paginee des sources.

    PME : seulement les sources `verified`.
    Admin : peut voir tous les statuts (filtre via parametre future).
    """
    service = SourceService(db)
    if current_user.role == UserRole.ADMIN.value:
        items, total = await service.list_admin(
            publisher=publisher, page=page, page_size=page_size,
        )
    else:
        items, total = await service.list_verified(
            publisher=publisher, search=search, page=page, page_size=page_size,
        )
    return PaginatedSources(
        items=[SourceListItem.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{source_id}", response_model=Source)
async def get_source(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Source:
    """Detail d'une source.

    PME : retourne 404 si la source n'est pas en statut `verified`
    (FR-023, evite de reveler l'existence d'une source non publique).
    """
    service = SourceService(db)
    if current_user.role == UserRole.ADMIN.value:
        source = await service.get_by_id(source_id)
    else:
        source = await service.get_verified(source_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source introuvable",
        )
    return Source.model_validate(source)


@router.post("", response_model=Source, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> Source:
    """Creer une source en draft (admin only)."""
    service = SourceService(db)
    try:
        source = await service.create_source(
            payload,
            current_user_id=current_user.id,
            account_id=current_user.account_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc),
        ) from exc
    await db.flush()
    await db.refresh(source)
    return Source.model_validate(source)


@router.post("/{source_id}/request-verification", response_model=Source)
async def request_verification(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> Source:
    """Transition draft -> pending (admin only)."""
    service = SourceService(db)
    try:
        source = await service.request_verification(source_id)
    except SourceNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source introuvable",
        )
    except InvalidStateTransition as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc),
        ) from exc
    await db.flush()
    await db.refresh(source)
    return Source.model_validate(source)


@router.post("/{source_id}/verify", response_model=Source)
async def verify_source(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> Source:
    """Validation 4-yeux (admin different du createur)."""
    service = SourceService(db)
    try:
        source = await service.verify_source(
            source_id, current_user_id=current_user.id,
        )
    except SourceNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source introuvable",
        )
    except FourEyesViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc),
        ) from exc
    except InvalidStateTransition as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc),
        ) from exc
    await db.flush()
    await db.refresh(source)
    return Source.model_validate(source)


@router.post("/{source_id}/mark-outdated", response_model=Source)
async def mark_outdated(
    source_id: UUID,
    payload: SourceMarkOutdated,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> Source:
    """Marquer une source verifiee comme obsolete (admin only)."""
    service = SourceService(db)
    try:
        source = await service.mark_outdated(source_id, payload.reason)
    except SourceNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source introuvable",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc),
        ) from exc
    except InvalidStateTransition as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc),
        ) from exc
    await db.flush()
    await db.refresh(source)
    return Source.model_validate(source)


@router.patch("/{source_id}", response_model=Source)
async def update_source(
    source_id: UUID,
    payload: SourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> Source:
    """Modifier une source en draft (admin only)."""
    service = SourceService(db)
    try:
        source = await service.update_source(source_id, payload)
    except SourceNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source introuvable",
        )
    except InvalidStateTransition as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc),
        ) from exc
    await db.flush()
    await db.refresh(source)
    return Source.model_validate(source)
