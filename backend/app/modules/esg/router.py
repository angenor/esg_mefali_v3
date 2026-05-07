"""Endpoints REST pour le module ESG."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.modules.esg.schemas import (
    BenchmarkResponse,
    CriteriaScoreResponse,
    ESGAssessmentCreate,
    ESGAssessmentList,
    ESGAssessmentResponse,
    ESGAssessmentSummary,
    EvaluateRequest,
    EvaluateResponse,
    PillarScoreResponse,
    ScoreResponse,
)

router = APIRouter()


@router.post("/assessments", response_model=ESGAssessmentResponse, status_code=201)
async def create_assessment(
    body: ESGAssessmentCreate | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ESGAssessmentResponse:
    """Creer une nouvelle evaluation ESG."""
    from app.modules.company.service import get_or_create_profile
    from app.modules.esg.service import create_assessment as create_assessment_svc

    # Verifier que le profil a un secteur
    profile = await get_or_create_profile(db, current_user.id)
    if not profile.sector:
        raise HTTPException(
            status_code=400,
            detail="Profil entreprise incomplet : secteur manquant. Renseignez votre secteur d'activite.",
        )

    conversation_id = body.conversation_id if body else None

    assessment = await create_assessment_svc(
        db=db,
        user_id=current_user.id,
        sector=profile.sector.value,
        conversation_id=conversation_id,
    )
    await db.commit()
    await db.refresh(assessment)

    return ESGAssessmentResponse.model_validate(assessment)


@router.get("/assessments", response_model=ESGAssessmentList)
async def list_assessments(
    status: str | None = Query(None, description="Filtrer par statut"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ESGAssessmentList:
    """Lister les evaluations ESG de l'utilisateur."""
    from app.modules.esg.service import list_assessments as list_assessments_svc

    assessments, total = await list_assessments_svc(
        db=db,
        user_id=current_user.id,
        status=status,
        page=page,
        limit=limit,
    )

    return ESGAssessmentList(
        data=[ESGAssessmentSummary.model_validate(a) for a in assessments],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/assessments/{assessment_id}", response_model=ESGAssessmentResponse)
async def get_assessment(
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ESGAssessmentResponse:
    """Detail complet d'une evaluation ESG."""
    from app.modules.esg.service import get_assessment as get_assessment_svc

    assessment = await get_assessment_svc(
        db=db,
        assessment_id=assessment_id,
        user_id=current_user.id,
    )
    if assessment is None:
        raise HTTPException(status_code=404, detail="Evaluation non trouvee.")

    return ESGAssessmentResponse.model_validate(assessment)


@router.post("/assessments/{assessment_id}/evaluate", response_model=EvaluateResponse)
async def evaluate_assessment(
    assessment_id: uuid.UUID,
    body: EvaluateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EvaluateResponse:
    """Mettre a jour l'etat de l'evaluation apres une interaction."""
    from app.modules.esg.service import (
        compute_progress_percent,
        get_assessment as get_assessment_svc,
    )

    assessment = await get_assessment_svc(
        db=db,
        assessment_id=assessment_id,
        user_id=current_user.id,
    )
    if assessment is None:
        raise HTTPException(status_code=404, detail="Evaluation non trouvee.")

    evaluated = assessment.evaluated_criteria or []
    progress = compute_progress_percent(evaluated)

    return EvaluateResponse(
        assessment_id=assessment.id,
        status=assessment.status,
        current_pillar=assessment.current_pillar,
        evaluated_criteria=evaluated,
        progress_percent=progress,
        total_criteria=30,
    )


@router.get("/assessments/{assessment_id}/score", response_model=ScoreResponse)
async def get_score(
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScoreResponse:
    """Score detaille avec ventilation par critere."""
    from app.modules.esg.criteria import CRITERIA_BY_CODE, PILLAR_CRITERIA
    from app.modules.esg.service import get_assessment as get_assessment_svc, get_score_color
    from app.modules.esg.weights import get_criterion_weight

    assessment = await get_assessment_svc(
        db=db,
        assessment_id=assessment_id,
        user_id=current_user.id,
    )
    if assessment is None:
        raise HTTPException(status_code=404, detail="Evaluation non trouvee.")

    if assessment.overall_score is None:
        raise HTTPException(status_code=400, detail="Evaluation non terminee.")

    assessment_data = assessment.assessment_data or {}
    criteria_scores = assessment_data.get("criteria_scores", {})

    pillars: dict[str, PillarScoreResponse] = {}
    pillar_score_map = {
        "environment": assessment.environment_score or 0,
        "social": assessment.social_score or 0,
        "governance": assessment.governance_score or 0,
    }

    for pillar_key, pillar_criteria in PILLAR_CRITERIA.items():
        criteria_list: list[CriteriaScoreResponse] = []
        for c in pillar_criteria:
            score_data = criteria_scores.get(c.code, {})
            criteria_list.append(CriteriaScoreResponse(
                code=c.code,
                label=c.label,
                score=score_data.get("score", 0),
                max=10,
                weight=get_criterion_weight(assessment.sector, c.code),
            ))
        pillars[pillar_key] = PillarScoreResponse(
            score=pillar_score_map[pillar_key],
            criteria=criteria_list,
        )

    return ScoreResponse(
        assessment_id=assessment.id,
        status=assessment.status,
        overall_score=assessment.overall_score,
        color=get_score_color(assessment.overall_score),
        pillars=pillars,
        strengths_count=len(assessment.strengths or []),
        gaps_count=len(assessment.gaps or []),
        recommendations_count=len(assessment.recommendations or []),
    )


@router.get("/benchmarks/{sector}", response_model=BenchmarkResponse)
async def get_benchmark(
    sector: str,
    current_user: User = Depends(get_current_user),
) -> BenchmarkResponse:
    """Benchmark sectoriel pour comparaison.

    Si le secteur n'est pas connu, retourne un benchmark general (moyenne tous secteurs).
    """
    from app.modules.esg.weights import get_sector_benchmark

    benchmark = get_sector_benchmark(sector)
    if benchmark is not None:
        return BenchmarkResponse(
            sector=benchmark["sector"],
            sector_label=benchmark["sector_label"],
            averages=benchmark["averages"],
            top_criteria=benchmark["top_criteria"],
            weak_criteria=benchmark["weak_criteria"],
        )

    # Benchmark de repli : moyenne generale
    return BenchmarkResponse(
        sector="general",
        sector_label=f"{sector.capitalize()} (moyenne generale)",
        averages={"environment": 48, "social": 47, "governance": 44, "overall": 46},
        top_criteria=[],
        weak_criteria=[],
    )


# ---------------------------------------------------------------------------
# F13 — Endpoints scoring multi-référentiels
# ---------------------------------------------------------------------------


def _serialize_referential_score(score, referential) -> dict:
    """Sérialise un ReferentialScore + Referential pour la réponse API."""
    return {
        "id": str(score.id),
        "assessment_id": str(score.assessment_id),
        "referential_id": str(score.referential_id),
        "referential_code": referential.code if referential else "",
        "referential_name": referential.label if referential else "",
        "referential_version": score.referential_version,
        "overall_score": (
            float(score.overall_score) if score.overall_score is not None else None
        ),
        "pillar_scores": score.pillar_scores or {},
        "coverage_rate": float(score.coverage_rate),
        "covered_criteria": score.covered_criteria or [],
        "missing_criteria": score.missing_criteria or [],
        "gap_to_threshold": (
            float(score.gap_to_threshold) if score.gap_to_threshold is not None else None
        ),
        "eligibility": score.eligibility,
        "computed_at": (
            score.computed_at.isoformat()
            if score.computed_at is not None
            else None
        ),
        "computed_by": (
            score.computed_by.value
            if hasattr(score.computed_by, "value")
            else score.computed_by
        ),
        "computed_request_id": (
            str(score.computed_request_id) if score.computed_request_id else None
        ),
        "is_fallback": False,
    }


@router.get("/assessments/{assessment_id}/referential-scores")
async def get_referential_scores(
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Liste des referential_scores courants (superseded_by IS NULL) pour
    une évaluation donnée.

    Filtre RLS : un PME ne voit que les scores de son compte (404 sinon).
    """
    from app.models.esg import ESGAssessment
    from app.models.referential import Referential
    from app.models.referential_score import ReferentialScore

    # Vérifier que l'assessment existe et appartient au user (RLS via account)
    assessment = (
        await db.execute(
            select(ESGAssessment).where(
                ESGAssessment.id == assessment_id,
                ESGAssessment.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if assessment is None:
        raise HTTPException(status_code=404, detail="Évaluation introuvable.")

    # Charger scores courants + referentials joints
    rows = (
        await db.execute(
            select(ReferentialScore, Referential)
            .join(Referential, ReferentialScore.referential_id == Referential.id)
            .where(
                ReferentialScore.assessment_id == assessment_id,
                ReferentialScore.superseded_by.is_(None),
            )
            .order_by(ReferentialScore.computed_at.desc())
        )
    ).all()

    return [_serialize_referential_score(score, ref) for score, ref in rows]


@router.get("/assessments/{assessment_id}/referential-scores/history")
async def get_referential_scores_history(
    assessment_id: uuid.UUID,
    referential_id: uuid.UUID | None = Query(
        None, description="Filtrer sur un référentiel précis."
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Historique des scores supersédés (versions antérieures F04)."""
    from app.models.esg import ESGAssessment
    from app.models.referential import Referential
    from app.models.referential_score import ReferentialScore

    assessment = (
        await db.execute(
            select(ESGAssessment).where(
                ESGAssessment.id == assessment_id,
                ESGAssessment.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if assessment is None:
        raise HTTPException(status_code=404, detail="Évaluation introuvable.")

    q = (
        select(ReferentialScore, Referential)
        .join(Referential, ReferentialScore.referential_id == Referential.id)
        .where(
            ReferentialScore.assessment_id == assessment_id,
            ReferentialScore.superseded_by.is_not(None),
        )
        .order_by(ReferentialScore.computed_at.desc())
    )
    if referential_id is not None:
        q = q.where(ReferentialScore.referential_id == referential_id)

    rows = (await db.execute(q)).all()
    return [_serialize_referential_score(score, ref) for score, ref in rows]


@router.post("/assessments/{assessment_id}/recompute-score", status_code=202)
async def recompute_score(
    assessment_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    referentiel_id: uuid.UUID | None = Query(
        None, description="UUID d'un référentiel à recalculer (optionnel : tous si vide)."
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Enqueue un recalcul async et retourne ``recompute_request_id``.

    Si ``referentiel_id`` est fourni, recalcule uniquement ce référentiel.
    Sinon recalcule tous les référentiels actifs.
    """
    from app.models.esg import ESGAssessment
    from app.modules.esg.multi_referential_service import recompute_score_async

    assessment = (
        await db.execute(
            select(ESGAssessment).where(
                ESGAssessment.id == assessment_id,
                ESGAssessment.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if assessment is None:
        raise HTTPException(status_code=404, detail="Évaluation introuvable.")

    request_id = uuid.uuid4()
    background_tasks.add_task(
        recompute_score_async,
        assessment_id=assessment_id,
        referentiel_id=referentiel_id,
        request_id=request_id,
    )

    return {
        "status": "accepted",
        "recompute_request_id": str(request_id),
        "referentials_to_recompute": [str(referentiel_id)] if referentiel_id else [],
        "estimated_duration_seconds": 5,
    }
