"""F047 — Services métier d'évaluation ESG-projet (US1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.indicator import Criterion
from app.models.project import Project
from app.models.referential import Referential
from app.models.source import PublicationStatus
from app.modules.esg.project_models import (
    ProjectEsgAssessment,
    ProjectEsgCriterionResponse,
)
from app.modules.esg.project_schemas import ProjectEsgCriterionResponseSave
from app.modules.esg.project_scoring import (
    compute_score,
    missing_required_criteria,
    normalize_response,
)


class _Conflict(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class _NotFound(HTTPException):
    def __init__(self, detail: str = "Ressource introuvable") -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class _Unprocessable(HTTPException):
    def __init__(self, detail: Any) -> None:
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


async def _load_project(
    db: AsyncSession, account_id: uuid.UUID, project_id: uuid.UUID,
) -> Project:
    project = (
        await db.execute(
            select(Project).where(
                Project.id == project_id, Project.account_id == account_id,
            )
        )
    ).scalar_one_or_none()
    if project is None:
        raise _NotFound("Projet introuvable")
    return project


async def _load_active_referential(
    db: AsyncSession, referential_id: uuid.UUID,
) -> Referential:
    ref = (
        await db.execute(
            select(Referential).where(Referential.id == referential_id)
        )
    ).scalar_one_or_none()
    if ref is None:
        raise _NotFound("Référentiel introuvable")
    if ref.publication_status != PublicationStatus.PUBLISHED.value:
        raise _Unprocessable(
            "Le référentiel ciblé n'est pas publié. Choisissez un référentiel actif."
        )
    return ref


async def create_project_esg_assessment(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    referential_id: uuid.UUID,
) -> ProjectEsgAssessment:
    """Crée une évaluation ``draft`` pour (project, referential).

    Raises:
        404 si projet introuvable / non accessible (RLS).
        422 si référentiel non publié.
        409 si un draft existe déjà pour ce couple.
    """
    await _load_project(db, account_id, project_id)
    ref = await _load_active_referential(db, referential_id)

    # Pas de second draft pour le même couple (project, referential)
    existing_draft = (
        await db.execute(
            select(ProjectEsgAssessment).where(
                ProjectEsgAssessment.account_id == account_id,
                ProjectEsgAssessment.project_id == project_id,
                ProjectEsgAssessment.referential_id == referential_id,
                ProjectEsgAssessment.state == "draft",
            )
        )
    ).scalar_one_or_none()
    if existing_draft is not None:
        raise _Conflict(
            "Une évaluation en cours existe déjà pour ce projet × référentiel. "
            "Reprenez-la ou supprimez-la avant d'en créer une nouvelle."
        )

    assessment = ProjectEsgAssessment(
        account_id=account_id,
        project_id=project_id,
        referential_id=referential_id,
        referential_version=str(getattr(ref, "version", "1.0")),
        state="draft",
        created_by=user_id,
    )
    db.add(assessment)
    await db.flush()
    return assessment


async def _load_assessment(
    db: AsyncSession, account_id: uuid.UUID, assessment_id: uuid.UUID,
) -> ProjectEsgAssessment:
    a = (
        await db.execute(
            select(ProjectEsgAssessment).where(
                ProjectEsgAssessment.id == assessment_id,
                ProjectEsgAssessment.account_id == account_id,
            )
        )
    ).scalar_one_or_none()
    if a is None:
        raise _NotFound("Évaluation ESG-projet introuvable")
    return a


async def save_project_esg_criterion_response(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    assessment_id: uuid.UUID,
    payload: ProjectEsgCriterionResponseSave,
) -> ProjectEsgCriterionResponse:
    """Sauvegarde (CREATE ou UPDATE révision draft) une réponse critère.

    Raises:
        404 si évaluation introuvable.
        409 si évaluation finalisée (immuable).
        422 si critère non applicable au référentiel ciblé.
    """
    assessment = await _load_assessment(db, account_id, assessment_id)
    if assessment.state == "finalized":
        raise _Conflict(
            "Cette évaluation est finalisée et immuable. Créez une nouvelle "
            "évaluation contre le même référentiel pour la corriger."
        )

    # Vérifier que le critère cible appartient bien au référentiel
    crit = (
        await db.execute(
            select(Criterion).where(Criterion.id == payload.criterion_id)
        )
    ).scalar_one_or_none()
    if crit is None:
        raise _NotFound("Critère introuvable")
    if (
        crit.referential_id != assessment.referential_id
        or not crit.applies_to_project
    ):
        raise _Unprocessable(
            "Ce critère n'est pas applicable au référentiel de l'évaluation."
        )

    normalized = normalize_response(payload.response_type, payload.response_value)

    # UPSERT par (assessment_id, criterion_id)
    existing = (
        await db.execute(
            select(ProjectEsgCriterionResponse).where(
                ProjectEsgCriterionResponse.assessment_id == assessment_id,
                ProjectEsgCriterionResponse.criterion_id == payload.criterion_id,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.response_type = payload.response_type
        existing.response_value = payload.response_value
        existing.normalized_score = normalized
        existing.source_id = payload.source_id
        existing.unsourced = payload.unsourced
        await db.flush()
        return existing

    row = ProjectEsgCriterionResponse(
        account_id=account_id,
        assessment_id=assessment_id,
        criterion_id=payload.criterion_id,
        response_type=payload.response_type,
        response_value=payload.response_value,
        normalized_score=normalized,
        source_id=payload.source_id,
        unsourced=payload.unsourced,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as e:
        raise _Unprocessable(f"Conflit d'intégrité : {e.orig}") from e
    return row


async def finalize_project_esg_assessment(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    assessment_id: uuid.UUID,
) -> dict[str, Any]:
    """Finalise une évaluation draft → finalized + calcul du score.

    Raises:
        404 / 409 / 422 selon contexte (cf. data-model.md).
    """
    assessment = await _load_assessment(db, account_id, assessment_id)
    if assessment.state == "finalized":
        raise _Conflict(
            "Cette évaluation est déjà finalisée (état immuable)."
        )

    # Critères du référentiel
    criteria = (
        await db.execute(
            select(Criterion).where(
                Criterion.referential_id == assessment.referential_id,
                Criterion.applies_to_project.is_(True),
            )
        )
    ).scalars().all()

    # Critères couverts via les réponses
    responses = (
        await db.execute(
            select(ProjectEsgCriterionResponse).where(
                ProjectEsgCriterionResponse.assessment_id == assessment_id
            )
        )
    ).scalars().all()
    covered_ids = {r.criterion_id for r in responses}

    missing_required = missing_required_criteria(list(criteria), covered_ids)
    if missing_required:
        raise _Unprocessable(
            {
                "message": (
                    "Critères obligatoires manquants — finalisation impossible."
                ),
                "missing_required": [
                    {"id": str(c.id), "code": c.code, "label": c.label}
                    for c in missing_required
                ],
            }
        )

    result = await compute_score(db, assessment_id)

    assessment.state = "finalized"
    assessment.score = result["score"]
    assessment.pillar_scores = result["pillar_scores"]
    assessment.covered_criteria = [str(x) for x in result["covered_criteria"]]
    assessment.missing_criteria = [str(x) for x in result["missing_criteria"]]
    assessment.coverage_rate = result["coverage_rate"]
    assessment.finalized_at = datetime.now(timezone.utc)
    assessment.snapshot_data = {
        "scoring_formula": "weighted_avg",
        "criterion_weights": {
            str(c.id): float(c.weight) for c in criteria
        },
        "frozen_at": assessment.finalized_at.isoformat(),
    }
    await db.flush()

    return {
        "assessment": assessment,
        **result,
    }


async def get_project_esg_assessment(
    db: AsyncSession, *, account_id: uuid.UUID, assessment_id: uuid.UUID,
) -> tuple[ProjectEsgAssessment, list[ProjectEsgCriterionResponse]]:
    assessment = await _load_assessment(db, account_id, assessment_id)
    responses = (
        await db.execute(
            select(ProjectEsgCriterionResponse).where(
                ProjectEsgCriterionResponse.assessment_id == assessment_id
            )
        )
    ).scalars().all()
    return assessment, list(responses)


async def list_project_esg_assessments(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    project_id: uuid.UUID,
    state: str | None = None,
) -> list[ProjectEsgAssessment]:
    await _load_project(db, account_id, project_id)
    stmt = select(ProjectEsgAssessment).where(
        ProjectEsgAssessment.account_id == account_id,
        ProjectEsgAssessment.project_id == project_id,
    )
    if state:
        stmt = stmt.where(ProjectEsgAssessment.state == state)
    stmt = stmt.order_by(ProjectEsgAssessment.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def delete_project_esg_assessment(
    db: AsyncSession, *, account_id: uuid.UUID, assessment_id: uuid.UUID,
) -> None:
    """Supprime une évaluation (CASCADE supprime les réponses)."""
    assessment = await _load_assessment(db, account_id, assessment_id)
    await db.delete(assessment)
    await db.flush()
