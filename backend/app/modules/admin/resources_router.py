"""F20 — Router admin REST pour les Resources (back-office).

Endpoints (tous protégés par ``Depends(get_current_admin)``) :

- GET    /api/admin/resources                  → liste paginée toutes statuts.
- GET    /api/admin/resources/{id}             → détail complet.
- POST   /api/admin/resources                  → création (status=draft).
- PATCH  /api/admin/resources/{id}             → édition (in-place ou nouvelle version).
- POST   /api/admin/resources/{id}/publish     → publication 4-yeux.
- POST   /api/admin/resources/{id}/archive     → archivage soft.
- DELETE /api/admin/resources/{id}             → hard delete (drafts uniquement).
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.models.user import User
from app.modules.resources.exceptions import (
    IntermediaryNotFoundError,
    ResourceFourEyesViolationError,
    ResourceInvalidStatusError,
    ResourceNotFoundError,
    ResourceSlugConflictError,
    ResourceSourceNotVerifiedError,
)
from app.modules.resources.schemas import (
    ResourceCreateAdmin,
    ResourceListItem,
    ResourceListResponse,
    ResourceReadAdmin,
    ResourceUpdateAdmin,
)
from app.modules.resources.service import ResourceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resources", tags=["admin-resources"])


def _http_422(code: str, **fields) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={"code": code, **fields},
    )


def _map_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ResourceSlugConflictError):
        return _http_422("slug_conflict", slug=exc.slug)
    if isinstance(exc, ResourceSourceNotVerifiedError):
        return _http_422(
            "source_must_be_verified",
            source_id=str(exc.source_id),
            current_status=exc.current_status,
        )
    if isinstance(exc, IntermediaryNotFoundError):
        return _http_422("intermediary_not_found", intermediary_id=str(exc.intermediary_id))
    if isinstance(exc, ResourceFourEyesViolationError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "four_eyes_violation"},
        )
    if isinstance(exc, ResourceInvalidStatusError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_status_transition",
                "current_status": exc.current,
                "action": exc.action,
            },
        )
    if isinstance(exc, ResourceNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "resource_not_found", "resource_id": str(exc.resource_id)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"code": "internal_error", "message": str(exc)},
    )


@router.get("", response_model=ResourceListResponse)
async def admin_list_resources(
    type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    language: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ResourceListResponse:
    service = ResourceService(db)
    items, total = await service.admin_list(
        type_=type,
        status=status_filter,
        language=language,
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


@router.post("", response_model=ResourceReadAdmin, status_code=status.HTTP_201_CREATED)
async def admin_create_resource(
    payload: ResourceCreateAdmin,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ResourceReadAdmin:
    service = ResourceService(db)
    try:
        resource = await service.create_resource(payload, creator_id=current_admin.id)
        await db.commit()
        await db.refresh(resource)
    except (
        ResourceSlugConflictError,
        ResourceSourceNotVerifiedError,
        IntermediaryNotFoundError,
    ) as exc:
        await db.rollback()
        raise _map_error(exc) from exc
    return ResourceReadAdmin.model_validate(resource)


@router.get("/{resource_id}", response_model=ResourceReadAdmin)
async def admin_get_resource(
    resource_id: uuid.UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ResourceReadAdmin:
    service = ResourceService(db)
    try:
        resource = await service.get_by_id(resource_id)
    except ResourceNotFoundError as exc:
        raise _map_error(exc) from exc
    return ResourceReadAdmin.model_validate(resource)


@router.patch("/{resource_id}", response_model=ResourceReadAdmin)
async def admin_update_resource(
    resource_id: uuid.UUID,
    payload: ResourceUpdateAdmin,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ResourceReadAdmin:
    service = ResourceService(db)
    try:
        resource = await service.update_resource(
            resource_id, payload, editor_id=current_admin.id
        )
        await db.commit()
        await db.refresh(resource)
    except ResourceNotFoundError as exc:
        raise _map_error(exc) from exc
    except ResourceSourceNotVerifiedError as exc:
        await db.rollback()
        raise _map_error(exc) from exc
    return ResourceReadAdmin.model_validate(resource)


@router.post("/{resource_id}/publish", response_model=ResourceReadAdmin)
async def admin_publish_resource(
    resource_id: uuid.UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ResourceReadAdmin:
    service = ResourceService(db)
    try:
        resource = await service.publish_resource(
            resource_id, verifier_id=current_admin.id
        )
        await db.commit()
        await db.refresh(resource)
    except ResourceNotFoundError as exc:
        raise _map_error(exc) from exc
    except (
        ResourceFourEyesViolationError,
        ResourceInvalidStatusError,
        ResourceSourceNotVerifiedError,
    ) as exc:
        await db.rollback()
        raise _map_error(exc) from exc
    return ResourceReadAdmin.model_validate(resource)


@router.post("/{resource_id}/archive", response_model=ResourceReadAdmin)
async def admin_archive_resource(
    resource_id: uuid.UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ResourceReadAdmin:
    service = ResourceService(db)
    try:
        resource = await service.archive_resource(
            resource_id, editor_id=current_admin.id
        )
        await db.commit()
        await db.refresh(resource)
    except ResourceNotFoundError as exc:
        raise _map_error(exc) from exc
    return ResourceReadAdmin.model_validate(resource)


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_resource(
    resource_id: uuid.UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = ResourceService(db)
    try:
        await service.delete_resource(resource_id)
        await db.commit()
    except ResourceNotFoundError as exc:
        raise _map_error(exc) from exc
    except ResourceInvalidStatusError as exc:
        await db.rollback()
        raise _map_error(exc) from exc
