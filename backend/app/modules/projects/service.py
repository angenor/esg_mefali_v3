"""Service métier pour le module Projets (F06)."""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.money import Money
from app.models.application import FundApplication
from app.models.document import Document
from app.models.financing import Fund, Intermediary
from app.models.project import Project
from app.models.project_document import ProjectDocument
from app.modules.projects.schemas import (
    INACTIVE_APPLICATION_STATUSES,
    BlockedApplication,
    DeleteResult,
    ProjectApplicationSummary,
    ProjectCreate,
    ProjectDetail,
    ProjectDocumentRead,
    ProjectFilters,
    ProjectListResponse,
    ProjectSummary,
    ProjectUpdate,
)


logger = logging.getLogger(__name__)


# =====================================================================
# Helpers de mapping ORM <-> schemas
# =====================================================================


def _project_to_summary(
    project: Project, *, applications_count: int = 0,
) -> ProjectSummary:
    """Mapper Project SQLAlchemy → ProjectSummary."""
    return ProjectSummary(
        id=project.id,
        name=project.name,
        status=project.status,
        maturity=project.maturity,
        objective_env=list(project.objective_env or []),
        target_amount=Money.from_columns(
            project.target_amount_amount, project.target_amount_currency,
        ),
        expected_impact_tco2e=project.expected_impact_tco2e,
        auto_generated=project.auto_generated,
        applications_count=applications_count,
        created_at=project.created_at,
    )


def _project_to_detail(
    project: Project,
    *,
    applications_count: int = 0,
    documents: list[ProjectDocument] | None = None,
) -> ProjectDetail:
    """Mapper Project SQLAlchemy → ProjectDetail (avec documents).

    ``documents`` peut être passé explicitement pour éviter la lazy-load
    de ``project.project_documents`` dans les flux d'écriture.
    """
    if documents is None:
        try:
            documents = list(project.project_documents or [])
        except Exception:
            documents = []
    docs = [ProjectDocumentRead.model_validate(pd) for pd in documents]
    return ProjectDetail(
        id=project.id,
        account_id=project.account_id,
        name=project.name,
        description=project.description,
        objective_env=list(project.objective_env or []),
        maturity=project.maturity,
        status=project.status,
        target_amount=Money.from_columns(
            project.target_amount_amount, project.target_amount_currency,
        ),
        duration_months=project.duration_months,
        financing_structure=project.financing_structure,
        expected_impact_tco2e=project.expected_impact_tco2e,
        expected_jobs_created=project.expected_jobs_created,
        expected_beneficiaries=project.expected_beneficiaries,
        expected_hectares_restored=project.expected_hectares_restored,
        expected_other_impacts=project.expected_other_impacts,
        location_country=project.location_country,
        location_region=project.location_region,
        auto_generated=project.auto_generated,
        created_at=project.created_at,
        updated_at=project.updated_at,
        project_documents=docs,
        applications_count=applications_count,
    )


def _payload_to_project_columns(
    payload: ProjectCreate | ProjectUpdate,
) -> dict[str, Any]:
    """Sérialiser un payload Pydantic vers les colonnes SQL.

    Fait l'éclatement Money → (amount, currency).
    Ne contient que les champs explicitement fournis (exclude_unset).
    """
    raw = payload.model_dump(exclude_unset=True)
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if key == "target_amount":
            if value is None:
                out["target_amount_amount"] = None
                out["target_amount_currency"] = None
            else:
                # Money model → on accepte dict (mode='python' Pydantic) ou objet
                if isinstance(value, dict):
                    amt = value.get("amount")
                    cur = value.get("currency")
                else:
                    amt = getattr(value, "amount", None)
                    cur = getattr(value, "currency", None)
                if isinstance(amt, str):
                    amt = Decimal(amt)
                out["target_amount_amount"] = amt
                out["target_amount_currency"] = cur
        else:
            out[key] = value
    return out


async def _count_active_applications(
    db: AsyncSession, project_id: uuid.UUID,
) -> int:
    """Compter les applications actives (status NOT IN inactif) pour un projet."""
    stmt = (
        select(func.count())
        .select_from(FundApplication)
        .where(FundApplication.project_id == project_id)
        .where(FundApplication.status.notin_(INACTIVE_APPLICATION_STATUSES))
    )
    result = await db.execute(stmt)
    return int(result.scalar() or 0)


async def _count_all_applications(
    db: AsyncSession, project_id: uuid.UUID,
) -> int:
    """Compter toutes les applications (pour `applications_count`)."""
    stmt = (
        select(func.count())
        .select_from(FundApplication)
        .where(FundApplication.project_id == project_id)
    )
    result = await db.execute(stmt)
    return int(result.scalar() or 0)


# =====================================================================
# CRUD
# =====================================================================


async def list_projects(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    filters: ProjectFilters,
) -> ProjectListResponse:
    """Lister les projets paginés (filtré par RLS via account_id)."""
    query = select(Project).where(Project.account_id == account_id)

    if filters.status is not None:
        query = query.where(Project.status == filters.status)
    if filters.maturity is not None:
        query = query.where(Project.maturity == filters.maturity)
    if filters.auto_generated is not None:
        query = query.where(Project.auto_generated.is_(filters.auto_generated))
    if filters.objective_env is not None:
        # Filtrage exact sur 1 valeur dans le JSONB array.
        # Compatibilité PG (jsonb @>) + SQLite (LIKE) via fallback Python plus tard si besoin.
        bind = db.bind
        dialect_name = (
            bind.dialect.name
            if bind is not None and bind.dialect is not None
            else ""
        )
        if dialect_name == "postgresql":
            query = query.where(
                Project.objective_env.op("@>")([filters.objective_env])
            )
        else:
            # SQLite : LIKE sur la sérialisation JSON.
            query = query.where(
                func.json_extract(Project.objective_env, "$").like(
                    f'%"{filters.objective_env}"%'
                )
            )

    count_query = select(func.count()).select_from(query.subquery())
    total = int((await db.execute(count_query)).scalar() or 0)

    query = query.order_by(Project.created_at.desc())
    query = query.offset((filters.page - 1) * filters.limit).limit(filters.limit)
    result = await db.execute(query)
    projects = list(result.scalars().all())

    items: list[ProjectSummary] = []
    for project in projects:
        count = await _count_all_applications(db, project.id)
        items.append(_project_to_summary(project, applications_count=count))

    return ProjectListResponse(
        items=items,
        total=total,
        page=filters.page,
        limit=filters.limit,
    )


async def get_project(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    project_id: uuid.UUID,
) -> ProjectDetail | None:
    """Récupérer un projet avec ses documents."""
    query = (
        select(Project)
        .where(Project.id == project_id)
        .where(Project.account_id == account_id)
        .options(selectinload(Project.project_documents))
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()
    if project is None:
        return None

    count = await _count_all_applications(db, project_id)
    return _project_to_detail(project, applications_count=count)


async def create_project(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    payload: ProjectCreate,
) -> ProjectDetail:
    """Créer un nouveau projet."""
    cols = _payload_to_project_columns(payload)
    cols.setdefault("status", "draft")
    project = Project(account_id=account_id, **cols)
    db.add(project)
    await db.flush()
    # Pas de relations à charger pour un nouveau projet (project_documents=[]).
    return _project_to_detail(
        project, applications_count=0, documents=[],
    )


async def update_project(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: ProjectUpdate,
) -> ProjectDetail | None:
    """Mise à jour partielle d'un projet."""
    query = (
        select(Project)
        .where(Project.id == project_id)
        .where(Project.account_id == account_id)
        .options(selectinload(Project.project_documents))
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()
    if project is None:
        return None

    # Snapshot des documents AVANT flush (pour éviter lazy-load post-flush).
    documents_snapshot = list(project.project_documents or [])

    cols = _payload_to_project_columns(payload)
    for key, value in cols.items():
        setattr(project, key, value)
    await db.flush()
    # Recharger explicitement pour matérialiser updated_at server-side.
    await db.refresh(project, attribute_names=["updated_at"])

    count = await _count_all_applications(db, project.id)
    return _project_to_detail(
        project, applications_count=count, documents=documents_snapshot,
    )


async def soft_delete_project(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    user_id: uuid.UUID | None,
    project_id: uuid.UUID,
    force: bool = False,
) -> DeleteResult | None:
    """Suppression soft d'un projet (status='cancelled').

    Retourne None si le projet n'existe pas (404).
    Retourne `DeleteResult` (avec ok=False et blocked_by) si applications actives sans force.
    Retourne `DeleteResult(ok=True)` si suppression OK.
    """
    query = (
        select(Project)
        .where(Project.id == project_id)
        .where(Project.account_id == account_id)
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()
    if project is None:
        return None

    # Liste les applications actives bloquantes
    apps_query = (
        select(FundApplication, Fund.name)
        .join(Fund, Fund.id == FundApplication.fund_id, isouter=True)
        .where(FundApplication.project_id == project_id)
        .where(FundApplication.status.notin_(INACTIVE_APPLICATION_STATUSES))
    )
    apps_result = await db.execute(apps_query)
    blocked_rows = list(apps_result.all())

    if blocked_rows and not force:
        blocked = [
            BlockedApplication(
                application_id=app.id,
                fund_name=fund_name or "(fonds inconnu)",
                status=str(app.status.value if hasattr(app.status, "value") else app.status),
            )
            for app, fund_name in blocked_rows
        ]
        return DeleteResult(
            ok=False,
            blocked_by=blocked,
            hint="force=true pour confirmer la suppression (les candidatures resteront liées)",
        )

    # Soft-delete : status = cancelled
    project.status = "cancelled"
    await db.flush()

    if force and blocked_rows:
        logger.info(
            "project_force_deleted project_id=%s account_id=%s "
            "blocked_by_count=%d user_id=%s",
            project_id,
            account_id,
            len(blocked_rows),
            user_id,
        )

    return DeleteResult(ok=True, blocked_by=[], hint=None)


async def duplicate_project(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    project_id: uuid.UUID,
    new_name: str | None = None,
) -> ProjectDetail | None:
    """Dupliquer un projet (force status=draft, suffix '(copie)' par défaut)."""
    query = (
        select(Project)
        .where(Project.id == project_id)
        .where(Project.account_id == account_id)
    )
    result = await db.execute(query)
    source = result.scalar_one_or_none()
    if source is None:
        return None

    target_name = new_name if new_name else f"{source.name} (copie)"
    target_name = target_name[:200]

    new_project = Project(
        account_id=source.account_id,
        name=target_name,
        description=source.description,
        objective_env=list(source.objective_env or []),
        maturity=source.maturity,
        status="draft",  # forcé
        target_amount_amount=source.target_amount_amount,
        target_amount_currency=source.target_amount_currency,
        duration_months=source.duration_months,
        financing_structure=source.financing_structure,
        expected_impact_tco2e=source.expected_impact_tco2e,
        expected_jobs_created=source.expected_jobs_created,
        expected_beneficiaries=source.expected_beneficiaries,
        expected_hectares_restored=source.expected_hectares_restored,
        expected_other_impacts=source.expected_other_impacts,
        location_country=source.location_country,
        location_region=source.location_region,
        auto_generated=False,  # toujours False pour duplication manuelle
    )
    db.add(new_project)
    await db.flush()
    # Pas de project_documents copiés (intentionnel, cf. spec FR-016).
    return _project_to_detail(
        new_project, applications_count=0, documents=[],
    )


async def link_document_to_project(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    doc_type: str,
) -> ProjectDocumentRead | None:
    """Associer un document à un projet.

    Retourne None si le projet n'existe pas (404).
    Lève IntegrityError si l'association existe déjà (UNIQUE).
    """
    # Vérifier que le projet appartient à l'account
    project_query = (
        select(Project)
        .where(Project.id == project_id)
        .where(Project.account_id == account_id)
    )
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    if project is None:
        return None

    # Vérifier que le document existe
    doc_query = select(Document).where(Document.id == document_id)
    doc_result = await db.execute(doc_query)
    document = doc_result.scalar_one_or_none()
    if document is None:
        # Convention : retourner None aussi pour "document not found"
        # (le caller saura différencier via le retour spécifique)
        return None

    link = ProjectDocument(
        project_id=project_id,
        document_id=document_id,
        doc_type=doc_type,
    )
    db.add(link)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise

    return ProjectDocumentRead.model_validate(link)


async def list_project_applications(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    project_id: uuid.UUID,
) -> list[ProjectApplicationSummary] | None:
    """Lister les fund_applications associées au projet.

    Retourne None si le projet n'existe pas.
    """
    project_query = (
        select(Project.id)
        .where(Project.id == project_id)
        .where(Project.account_id == account_id)
    )
    project_result = await db.execute(project_query)
    if project_result.scalar_one_or_none() is None:
        return None

    apps_query = (
        select(
            FundApplication,
            Fund.name.label("fund_name"),
            Intermediary.name.label("intermediary_name"),
        )
        .join(Fund, Fund.id == FundApplication.fund_id, isouter=True)
        .join(
            Intermediary,
            Intermediary.id == FundApplication.intermediary_id,
            isouter=True,
        )
        .where(FundApplication.project_id == project_id)
        .order_by(FundApplication.created_at.desc())
    )
    result = await db.execute(apps_query)
    summaries: list[ProjectApplicationSummary] = []
    for app, fund_name, intermediary_name in result.all():
        summaries.append(
            ProjectApplicationSummary(
                application_id=app.id,
                fund_id=app.fund_id,
                fund_name=fund_name or "(fonds inconnu)",
                status=str(
                    app.status.value if hasattr(app.status, "value") else app.status
                ),
                intermediary_id=app.intermediary_id,
                intermediary_name=intermediary_name,
                target_type=str(
                    app.target_type.value
                    if hasattr(app.target_type, "value")
                    else app.target_type
                ),
                created_at=app.created_at,
            )
        )
    return summaries


async def get_active_projects_for_user(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Récupérer les projets actifs (statut autre que cancelled/closed) pour le contexte LangGraph."""
    query = (
        select(Project)
        .where(Project.account_id == account_id)
        .where(
            Project.status.in_(
                ["draft", "seeking_funding", "funded", "in_execution"]
            )
        )
        .order_by(Project.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    projects = list(result.scalars().all())
    out: list[dict[str, Any]] = []
    for project in projects:
        out.append({
            "id": str(project.id),
            "name": project.name,
            "status": project.status,
            "maturity": project.maturity,
            "objective_env": list(project.objective_env or []),
            "auto_generated": project.auto_generated,
        })
    return out
