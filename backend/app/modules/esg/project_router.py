"""F047 — Endpoints REST évaluation ESG-projet.

Préfixe applicatif : ``/api/projects/{project_id}/esg-assessment[s]/...``
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.project import Project
from app.models.referential import Referential
from app.models.user import User
from app.modules.esg.project_models import ProjectEsgAssessment
from app.modules.esg.project_report import UPLOADS_DIR, generate_project_esg_report
from app.modules.esg.project_schemas import (
    ProjectEsgAssessmentCreate,
    ProjectEsgAssessmentDetail,
    ProjectEsgAssessmentFinalize,
    ProjectEsgAssessmentFinalizeResult,
    ProjectEsgAssessmentRead,
    ProjectEsgCriterionResponseRead,
    ProjectEsgCriterionResponseSave,
)
from app.modules.esg.project_service import (
    create_project_esg_assessment,
    delete_project_esg_assessment,
    finalize_project_esg_assessment,
    get_project_esg_assessment,
    list_project_esg_assessments,
    save_project_esg_criterion_response,
)


router = APIRouter()


def _serialize(a: ProjectEsgAssessment) -> ProjectEsgAssessmentRead:
    return ProjectEsgAssessmentRead.model_validate(a)


@router.post(
    "/projects/{project_id}/esg-assessment",
    response_model=ProjectEsgAssessmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create(
    project_id: uuid.UUID,
    body: ProjectEsgAssessmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectEsgAssessmentRead:
    """Crée une évaluation ESG-projet (state=draft)."""
    a = await create_project_esg_assessment(
        db,
        account_id=current_user.account_id,
        user_id=current_user.id,
        project_id=project_id,
        referential_id=body.referential_id,
    )
    await db.commit()
    await db.refresh(a)
    return _serialize(a)


@router.get(
    "/projects/{project_id}/esg-assessments",
    response_model=list[ProjectEsgAssessmentRead],
)
async def list_for_project(
    project_id: uuid.UUID,
    state: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProjectEsgAssessmentRead]:
    items = await list_project_esg_assessments(
        db,
        account_id=current_user.account_id,
        project_id=project_id,
        state=state,
    )
    return [_serialize(a) for a in items]


@router.get(
    "/projects/{project_id}/esg-assessment/{assessment_id}",
    response_model=ProjectEsgAssessmentDetail,
)
async def get_detail(
    project_id: uuid.UUID,
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectEsgAssessmentDetail:
    assessment, responses = await get_project_esg_assessment(
        db, account_id=current_user.account_id, assessment_id=assessment_id,
    )
    base = _serialize(assessment).model_dump()
    base["responses"] = [
        ProjectEsgCriterionResponseRead.model_validate(r) for r in responses
    ]
    return ProjectEsgAssessmentDetail(**base)


@router.delete(
    "/projects/{project_id}/esg-assessment/{assessment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete(
    project_id: uuid.UUID,
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    await delete_project_esg_assessment(
        db, account_id=current_user.account_id, assessment_id=assessment_id,
    )
    await db.commit()


@router.post(
    "/projects/{project_id}/esg-assessment/{assessment_id}/criterion",
    response_model=ProjectEsgCriterionResponseRead,
    status_code=status.HTTP_200_OK,
)
async def save_criterion(
    project_id: uuid.UUID,
    assessment_id: uuid.UUID,
    body: ProjectEsgCriterionResponseSave,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectEsgCriterionResponseRead:
    row = await save_project_esg_criterion_response(
        db,
        account_id=current_user.account_id,
        assessment_id=assessment_id,
        payload=body,
    )
    await db.commit()
    await db.refresh(row)
    return ProjectEsgCriterionResponseRead.model_validate(row)


@router.post(
    "/projects/{project_id}/esg-assessment/{assessment_id}/finalize",
    response_model=ProjectEsgAssessmentFinalizeResult,
)
async def finalize(
    project_id: uuid.UUID,
    assessment_id: uuid.UUID,
    body: ProjectEsgAssessmentFinalize | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectEsgAssessmentFinalizeResult:
    result = await finalize_project_esg_assessment(
        db, account_id=current_user.account_id, assessment_id=assessment_id,
    )
    await db.commit()
    await db.refresh(result["assessment"])

    return ProjectEsgAssessmentFinalizeResult(
        assessment=_serialize(result["assessment"]),
        score=result["score"],
        pillar_scores=result["pillar_scores"],
        missing_criteria=[],  # Vide à la finalisation valide
        coverage_rate=result["coverage_rate"],
    )


# ---------------------------------------------------------------------
# F047 (US3) — Rapport ESIA-light PDF
# ---------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/esg-assessment/{assessment_id}/report",
    status_code=status.HTTP_201_CREATED,
)
async def generate_report(
    project_id: uuid.UUID,
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    accept: str | None = Header(default=None),
    include_appendix_sources: bool = True,
):
    """Génère un rapport ESIA-light. Accepte application/pdf (binaire) ou
    application/json (metadata).

    - 404 si évaluation introuvable (RLS).
    - 422 si évaluation `draft` (FR-019).
    - 201 + binaire PDF si Accept=application/pdf.
    - 201 + JSON metadata sinon.
    """
    out = await generate_project_esg_report(
        db,
        account_id=current_user.account_id,
        assessment_id=assessment_id,
        include_appendix_sources=include_appendix_sources,
    )
    pdf_bytes: bytes = out["pdf_bytes"]
    if accept and "application/pdf" in accept.lower():
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            status_code=status.HTTP_201_CREATED,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="esia-{assessment_id}.pdf"'
                ),
            },
        )
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "assessment_id": str(assessment_id),
            "file_path": out["file_path"],
            "generated_at": out["generated_at"].isoformat(),
            "template_version": out["template_version"],
            "section_count": out["section_count"],
            "chart_count": out["chart_count"],
            "sources_cited": out["sources_cited"],
        },
    )


# ---------------------------------------------------------------------
# F047 bugfix UI (2026-05-23) — endpoints de listing + téléchargement
# des rapports ESIA-light déjà générés. Affichés dans le 3e onglet
# « ESG Projet » de la page /reports.
# ---------------------------------------------------------------------


_PDF_PATTERN = re.compile(r"^esia_([0-9a-f-]{36})_(\d{8}-\d{6})\.pdf$")


def _latest_pdf_for(
    account_id: uuid.UUID, project_id: uuid.UUID, assessment_id: uuid.UUID,
) -> Path | None:
    """Retourne le PDF ESIA le plus récent pour ``assessment_id`` ou None.

    Le nom suit le pattern ``esia_{assessment_id}_{YYYYMMDD-HHMMSS}.pdf``
    (cf. ``project_report.py``). On choisit le timestamp lexicographique
    le plus grand (sort par date implicite).
    """
    out_dir = UPLOADS_DIR / str(account_id) / str(project_id)
    if not out_dir.exists():
        return None
    candidates = sorted(
        out_dir.glob(f"esia_{assessment_id}_*.pdf"),
        key=lambda p: p.name,
        reverse=True,
    )
    return candidates[0] if candidates else None


@router.get("/reports/esia")
async def list_esia_reports(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Liste paginée des rapports ESIA-light disponibles pour l'account.

    Retourne uniquement les ``ProjectEsgAssessment`` ``state=finalized``
    pour les projets de l'account courant, enrichis avec les métadonnées
    nécessaires à l'affichage dans le 3e onglet de ``/reports``.

    Le champ ``has_pdf`` indique si un PDF existe déjà sur disque ; si
    ``false``, l'utilisateur doit cliquer « Générer » (cf. POST sur
    ``/projects/{id}/esg-assessment/{aid}/report``).
    """
    account_id = current_user.account_id
    if account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account requis pour lister les rapports ESIA.",
        )

    # Charger les assessments finalized + projets + référentiels en 1 requête.
    base_stmt = (
        select(ProjectEsgAssessment, Project, Referential)
        .join(Project, Project.id == ProjectEsgAssessment.project_id)
        .join(Referential, Referential.id == ProjectEsgAssessment.referential_id)
        .where(
            ProjectEsgAssessment.account_id == account_id,
            ProjectEsgAssessment.state == "finalized",
        )
        .order_by(ProjectEsgAssessment.finalized_at.desc())
    )

    # Count total (sans pagination).
    total_stmt = (
        select(ProjectEsgAssessment.id)
        .where(
            ProjectEsgAssessment.account_id == account_id,
            ProjectEsgAssessment.state == "finalized",
        )
    )
    total = len((await db.execute(total_stmt)).all())

    paginated = base_stmt.limit(limit).offset((page - 1) * limit)
    rows = (await db.execute(paginated)).all()

    items: list[dict] = []
    for assessment, project, referential in rows:
        pdf_path = _latest_pdf_for(account_id, assessment.project_id, assessment.id)
        items.append(
            {
                "assessment_id": str(assessment.id),
                "project_id": str(assessment.project_id),
                "project_name": project.name,
                "referential_id": str(assessment.referential_id),
                "referential_code": referential.code,
                "referential_label": referential.label,
                "score": assessment.score,
                "coverage_rate": (
                    float(assessment.coverage_rate)
                    if assessment.coverage_rate is not None
                    else None
                ),
                "finalized_at": (
                    assessment.finalized_at.isoformat()
                    if assessment.finalized_at
                    else None
                ),
                "has_pdf": pdf_path is not None,
                "file_size": pdf_path.stat().st_size if pdf_path else None,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.get(
    "/projects/{project_id}/esg-assessment/{assessment_id}/report/download"
)
async def download_esia_report(
    project_id: uuid.UUID,
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Télécharge le PDF ESIA-light déjà généré pour cet assessment.

    Si aucun PDF n'existe sur disque, régénère à la volée puis renvoie.
    L'``assessment_id`` doit appartenir à un projet de l'account courant
    et être ``finalized`` (sinon 404/422 via le service de génération).
    """
    account_id = current_user.account_id
    if account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account requis.",
        )

    # Vérifier l'appartenance (RLS implicite via account_id).
    assessment = (
        await db.execute(
            select(ProjectEsgAssessment).where(
                ProjectEsgAssessment.id == assessment_id,
                ProjectEsgAssessment.project_id == project_id,
                ProjectEsgAssessment.account_id == account_id,
            )
        )
    ).scalar_one_or_none()
    if assessment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Évaluation ESG-projet introuvable.",
        )

    pdf_path = _latest_pdf_for(account_id, project_id, assessment_id)
    if pdf_path is None:
        # Pas de PDF sur disque : régénérer (le service écrit le fichier).
        out = await generate_project_esg_report(
            db,
            account_id=account_id,
            assessment_id=assessment_id,
            include_appendix_sources=True,
        )
        pdf_path = Path(out["file_path"])

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"esia-{assessment_id}.pdf",
    )
