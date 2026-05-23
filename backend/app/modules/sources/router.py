"""Router FastAPI pour le catalogue Source (F01)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_user
from app.core.constants import UserRole
from app.core.database import get_db
from app.models.indicator import Criterion
from app.models.referential import Referential
from app.models.source import PublicationStatus
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


@router.get("/referentials")
async def list_referentials(
    publication_status: str | None = Query(default="published"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Lister les référentiels ESG du catalogue F13.

    Lecture publique pour tout utilisateur authentifié. Filtre par
    `publication_status` (défaut: published). Renvoie le minimum nécessaire
    pour les sélecteurs UI (id, code, label, description, version,
    publication_status, source_id).

    **Important** : cette route DOIT précéder ``/{source_id}`` pour éviter
    que FastAPI tente de parser `referentials` comme UUID.
    """
    stmt = select(Referential)
    if publication_status:
        stmt = stmt.where(Referential.publication_status == publication_status)
    stmt = stmt.order_by(Referential.code)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(r.id),
            "code": r.code,
            "label": r.label,
            "description": r.description,
            "version": getattr(r, "version", None),
            "publication_status": r.publication_status,
            "source_id": str(r.source_id) if getattr(r, "source_id", None) else None,
        }
        for r in rows
    ]


@router.get("/criteria")
async def list_criteria(
    applies_to_project: bool | None = Query(default=None),
    referential_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Lister les critères ESG du catalogue F13 (filtres par projet et référentiel).

    Lecture publique pour tout utilisateur authentifié. Utilisé par le
    wizard ESG-projet (F047) pour charger les critères applicables au
    projet selon le référentiel sélectionné.

    **Important** : cette route DOIT précéder ``/{source_id}``.
    """
    stmt = select(Criterion)
    if applies_to_project is not None:
        stmt = stmt.where(Criterion.applies_to_project.is_(applies_to_project))
    if referential_id is not None:
        stmt = stmt.where(Criterion.referential_id == referential_id)
    stmt = stmt.order_by(Criterion.code)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(c.id),
            "code": c.code,
            "label": c.label,
            "weight": float(c.weight) if c.weight is not None else None,
            "is_required": c.is_required,
            "applies_to_project": c.applies_to_project,
            "referential_id": str(c.referential_id) if c.referential_id else None,
        }
        for c in rows
    ]


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
