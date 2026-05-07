"""Endpoints REST pour le module Projets (F06)."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.modules.projects import service as project_service
from app.modules.projects.schemas import (
    DeleteResult,
    DuplicateProjectRequest,
    LinkDocumentRequest,
    ProjectApplicationSummary,
    ProjectCreate,
    ProjectDetail,
    ProjectDocumentRead,
    ProjectFilters,
    ProjectListResponse,
    ProjectUpdate,
)


logger = logging.getLogger(__name__)


router = APIRouter()


def _require_account_id(user: User) -> uuid.UUID:
    """Lève 403 si le user n'a pas d'account (admin pur sans tenant)."""
    if user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte requis pour accéder aux projets",
        )
    return user.account_id


@router.get("", response_model=ProjectListResponse)
async def list_projects_endpoint(
    project_status: str | None = Query(default=None, alias="status"),
    maturity: str | None = Query(default=None),
    objective_env: str | None = Query(default=None),
    auto_generated: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
    """Liste paginée des projets de l'utilisateur (filtré par RLS)."""
    account_id = _require_account_id(current_user)
    filters = ProjectFilters(
        status=project_status,
        maturity=maturity,
        objective_env=objective_env,
        auto_generated=auto_generated,
        page=page,
        limit=limit,
    )
    return await project_service.list_projects(
        db, account_id=account_id, filters=filters,
    )


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project_endpoint(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectDetail:
    """Récupérer un projet par ID."""
    account_id = _require_account_id(current_user)
    project = await project_service.get_project(
        db, account_id=account_id, project_id=project_id,
    )
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Projet introuvable",
        )
    return project


@router.post(
    "", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED,
)
async def create_project_endpoint(
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectDetail:
    """Créer un nouveau projet."""
    account_id = _require_account_id(current_user)
    return await project_service.create_project(
        db, account_id=account_id, payload=payload,
    )


@router.patch("/{project_id}", response_model=ProjectDetail)
async def update_project_endpoint(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectDetail:
    """Mettre à jour un projet (PATCH partiel)."""
    account_id = _require_account_id(current_user)
    project = await project_service.update_project(
        db, account_id=account_id, project_id=project_id, payload=payload,
    )
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Projet introuvable",
        )
    return project


@router.delete("/{project_id}", response_model=DeleteResult)
async def delete_project_endpoint(
    project_id: uuid.UUID,
    force: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeleteResult:
    """Supprimer (soft) un projet — refuse si applications actives sans force=true."""
    account_id = _require_account_id(current_user)
    result = await project_service.soft_delete_project(
        db,
        account_id=account_id,
        user_id=current_user.id,
        project_id=project_id,
        force=force,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Projet introuvable",
        )
    if not result.ok:
        # 409 Conflict avec payload bloquant
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "ok": False,
                "blocked_by": [b.model_dump(mode="json") for b in result.blocked_by],
                "hint": result.hint,
            },
        )
    return result


@router.post(
    "/{project_id}/duplicate",
    response_model=ProjectDetail,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_project_endpoint(
    project_id: uuid.UUID,
    payload: DuplicateProjectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectDetail:
    """Dupliquer un projet (force status=draft)."""
    account_id = _require_account_id(current_user)
    project = await project_service.duplicate_project(
        db,
        account_id=account_id,
        project_id=project_id,
        new_name=payload.new_name,
    )
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Projet source introuvable",
        )
    return project


@router.get(
    "/{project_id}/applications",
    response_model=list[ProjectApplicationSummary],
)
async def list_project_applications_endpoint(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectApplicationSummary]:
    """Lister les candidatures d'un projet."""
    account_id = _require_account_id(current_user)
    apps = await project_service.list_project_applications(
        db, account_id=account_id, project_id=project_id,
    )
    if apps is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Projet introuvable",
        )
    return apps


@router.post(
    "/{project_id}/documents",
    response_model=ProjectDocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def link_document_endpoint(
    project_id: uuid.UUID,
    payload: LinkDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectDocumentRead:
    """Lier un document à un projet."""
    account_id = _require_account_id(current_user)
    try:
        link = await project_service.link_document_to_project(
            db,
            account_id=account_id,
            project_id=project_id,
            document_id=payload.document_id,
            doc_type=payload.doc_type,
        )
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document déjà associé à ce projet",
        )
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Projet ou document introuvable",
        )
    return link
