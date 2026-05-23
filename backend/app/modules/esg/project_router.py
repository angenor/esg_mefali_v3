"""F047 — Endpoints REST évaluation ESG-projet.

Préfixe applicatif : ``/api/projects/{project_id}/esg-assessment[s]/...``
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.modules.esg.project_models import ProjectEsgAssessment
from app.modules.esg.project_report import generate_project_esg_report
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
