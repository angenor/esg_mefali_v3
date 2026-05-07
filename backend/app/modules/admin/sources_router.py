"""Sous-router admin /sources (F09).

Wrappers autour du service F01 pour ajouter :
- impact analysis (dependents),
- DELETE soft avec force=true,
- audit log standardisé F09.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.models.user import User
from app.modules.admin.audit_helpers import log_admin_action
from app.modules.admin.schemas import DependentsReport, SourceCreate, SourceUpdate
from app.modules.admin.sources_service import (
    get_dependents,
    soft_delete_with_cascade,
)
from app.modules.sources.service import (
    FourEyesViolation,
    InvalidStateTransition,
    SourceNotFound,
    SourceService,
)
from app.schemas.source import SourceCreate as F01SourceCreate
from app.schemas.source import SourceUpdate as F01SourceUpdate
from app.models.source import VerificationStatus

logger = logging.getLogger(__name__)


router = APIRouter()


def _serialize_source(source) -> dict:
    """Sérialise une Source en dict JSON-friendly.

    Note : appelle ``__dict__`` pour ne pas déclencher de lazy-load après
    un ``flush()`` qui aurait expiré les colonnes server-default.
    """
    sd = source.__dict__
    return {
        "id": sd.get("id"),
        "url": sd.get("url"),
        "title": sd.get("title"),
        "publisher": sd.get("publisher"),
        "version": sd.get("version"),
        "date_publi": sd.get("date_publi"),
        "page": sd.get("page"),
        "section": sd.get("section"),
        "verification_status": sd.get("verification_status"),
        "captured_by": sd.get("captured_by"),
        "verified_by": sd.get("verified_by"),
        "verified_at": sd.get("verified_at"),
        "outdated_reason": sd.get("outdated_reason"),
        "created_at": sd.get("created_at"),
        "updated_at": sd.get("updated_at"),
    }


@router.get("", status_code=status.HTTP_200_OK)
async def list_sources(
    verification_status: str | None = Query(default=None),
    publisher: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Lister les sources (admin voit tous les statuts)."""
    from sqlalchemy import func, or_, select
    from app.models.source import Source

    stmt = select(Source)
    count_stmt = select(func.count(Source.id))
    if verification_status:
        stmt = stmt.where(Source.verification_status == verification_status)
        count_stmt = count_stmt.where(Source.verification_status == verification_status)
    if publisher:
        stmt = stmt.where(Source.publisher == publisher)
        count_stmt = count_stmt.where(Source.publisher == publisher)
    if q:
        pattern = f"%{q.lower()}%"
        cond = or_(
            func.lower(Source.title).like(pattern),
            func.lower(Source.publisher).like(pattern),
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    offset = (page - 1) * page_size
    stmt = stmt.order_by(Source.date_publi.desc()).offset(offset).limit(page_size)

    rows = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one() or 0

    return {
        "items": [_serialize_source(r) for r in rows],
        "total": total,
        "page": page,
        "limit": page_size,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_source_endpoint(
    payload: SourceCreate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Créer une source en draft (captured_by=current_admin)."""
    service = SourceService(db)
    f01_payload = F01SourceCreate(
        url=payload.url,
        title=payload.title,
        publisher=payload.publisher,
        version=payload.version,
        date_publi=payload.date_publi,
        page=payload.page,
        section=payload.section,
    )
    try:
        source = await service.create_source(
            f01_payload,
            current_user_id=current_admin.id,
            account_id=current_admin.account_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # Auto-passe en pending pour amorcer le workflow 4-yeux.
    try:
        source = await service.request_verification(source.id)
    except InvalidStateTransition:
        pass

    # Capture la sérialisation AVANT l'audit log (le flush du log peut
    # expirer la session et invalider les attributs).
    payload = _serialize_source(source)

    await log_admin_action(
        db,
        admin_id=current_admin.id,
        action="source_created",
        entity_type="source",
        entity_id=source.id,
    )
    return payload


@router.get("/{source_id}", status_code=status.HTTP_200_OK)
async def get_source_endpoint(
    source_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SourceService(db)
    source = await service.get_by_id(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source introuvable")
    return _serialize_source(source)


@router.patch("/{source_id}", status_code=status.HTTP_200_OK)
async def update_source_endpoint(
    source_id: UUID,
    payload: SourceUpdate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Modifier une source.

    Cas spéciaux :
    - ``verification_status='verified'`` → applique le workflow 4-yeux
      (verified_by ≠ captured_by) via :meth:`SourceService.verify_source`.
    - ``verification_status='outdated'`` → exige ``outdated_reason``.
    - Sinon → update simple sur draft.
    """
    service = SourceService(db)

    if payload.verification_status is not None:
        target = payload.verification_status.value
        if target == VerificationStatus.VERIFIED.value:
            try:
                source = await service.verify_source(
                    source_id,
                    current_user_id=current_admin.id,
                )
            except FourEyesViolation as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "four_eyes_violation",
                        "message": str(exc),
                    },
                ) from exc
            except (InvalidStateTransition, SourceNotFound) as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                ) from exc
            await log_admin_action(
                db,
                admin_id=current_admin.id,
                action="source_verified",
                entity_type="source",
                entity_id=source_id,
            )
            return _serialize_source(source)

        if target == VerificationStatus.OUTDATED.value:
            if not payload.outdated_reason:
                raise HTTPException(
                    status_code=422,
                    detail="outdated_reason est requis pour ce statut",
                )
            try:
                source = await service.mark_outdated(
                    source_id, payload.outdated_reason
                )
            except (InvalidStateTransition, SourceNotFound) as exc:
                raise HTTPException(
                    status_code=400, detail=str(exc),
                ) from exc
            await log_admin_action(
                db,
                admin_id=current_admin.id,
                action="source_marked_outdated",
                entity_type="source",
                entity_id=source_id,
            )
            return _serialize_source(source)

    # Update simple (draft only) — F01 SourceUpdate n'accepte pas url
    update_payload = F01SourceUpdate(
        title=payload.title,
        publisher=payload.publisher,
        version=payload.version,
        date_publi=payload.date_publi,
        page=payload.page,
        section=payload.section,
    )
    try:
        source = await service.update_source(source_id, update_payload)
    except SourceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidStateTransition as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_source(source)


@router.get(
    "/{source_id}/dependents",
    response_model=DependentsReport,
    status_code=status.HTTP_200_OK,
)
async def get_dependents_endpoint(
    source_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> DependentsReport:
    return await get_dependents(db, source_id)


@router.delete("/{source_id}", status_code=status.HTTP_200_OK)
async def delete_source_endpoint(
    source_id: UUID,
    force: bool = Query(default=False),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Soft delete (passe en outdated) avec impact analysis."""
    try:
        ok, blockers = await soft_delete_with_cascade(
            db,
            source_id,
            admin_id=current_admin.id,
            force=force,
        )
    except SourceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "has_dependents",
                "blockers": blockers,
                "hint": "Utilisez ?force=true pour forcer.",
            },
        )

    return {"deleted": True, "force": force, "blockers": blockers}
