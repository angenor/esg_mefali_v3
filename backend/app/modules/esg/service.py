"""Service de scoring ESG : calcul, CRUD et utilitaires."""

import logging
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.esg import ESGAssessment, ESGStatusEnum
from app.modules.esg.criteria import (
    ALL_CRITERIA,
    CRITERIA_BY_CODE,
    PILLAR_CRITERIA,
    PILLAR_ORDER,
    TOTAL_CRITERIA,
)
from app.modules.esg.weights import get_criterion_weight, get_sector_benchmark

logger = logging.getLogger(__name__)


# --- Fonctions de calcul (pures, sans I/O) ---


def compute_pillar_score(
    pillar: str,
    criteria_scores: dict[str, dict],
    sector: str,
) -> float:
    """Calculer le score pondere d'un pilier (0-100).

    Score = (somme des score_critere * poids) / (somme des poids * 10) * 100
    """
    pillar_criteria = PILLAR_CRITERIA.get(pillar, ())
    if not pillar_criteria:
        return 0.0

    weighted_sum = 0.0
    weight_sum = 0.0

    for criterion in pillar_criteria:
        score_data = criteria_scores.get(criterion.code)
        if score_data is None:
            continue
        score = score_data.get("score", 0)
        weight = get_criterion_weight(sector, criterion.code)
        weighted_sum += score * weight
        weight_sum += weight

    if weight_sum == 0:
        return 0.0

    return round((weighted_sum / (weight_sum * 10)) * 100, 1)


def compute_overall_score(
    criteria_scores: dict[str, dict],
    sector: str,
) -> dict[str, float]:
    """Calculer le score global et les scores par pilier.

    Score global = moyenne des 3 piliers.
    """
    env_score = compute_pillar_score("environment", criteria_scores, sector)
    social_score = compute_pillar_score("social", criteria_scores, sector)
    gov_score = compute_pillar_score("governance", criteria_scores, sector)

    overall = round((env_score + social_score + gov_score) / 3, 1)

    return {
        "overall_score": overall,
        "environment_score": env_score,
        "social_score": social_score,
        "governance_score": gov_score,
    }


def get_score_color(score: float) -> str:
    """Obtenir la couleur associee a un score."""
    if score < 40:
        return "red"
    if score < 70:
        return "orange"
    return "green"


def generate_recommendations(criteria_scores: dict[str, dict]) -> list[dict]:
    """Generer des recommandations pour les criteres faibles (score <= 4)."""
    recommendations: list[dict] = []
    priority = 1

    # Trier par score croissant
    weak_criteria = [
        (code, data)
        for code, data in criteria_scores.items()
        if data.get("score", 10) <= 4
    ]
    weak_criteria.sort(key=lambda x: x[1].get("score", 0))

    for code, data in weak_criteria:
        criterion = CRITERIA_BY_CODE.get(code)
        if criterion is None:
            continue

        score = data.get("score", 0)
        impact = "high" if score <= 2 else "medium"
        effort = "medium"
        timeline = "3-6 mois" if score <= 2 else "6-12 mois"

        recommendations.append({
            "priority": priority,
            "criteria_code": code,
            "pillar": criterion.pillar,
            "title": f"Améliorer : {criterion.label}",
            "description": f"Score actuel : {score}/10. {criterion.description}",
            "impact": impact,
            "effort": effort,
            "timeline": timeline,
        })
        priority += 1

    return recommendations


def generate_strengths_gaps(
    criteria_scores: dict[str, dict],
) -> tuple[list[dict], list[dict]]:
    """Identifier les points forts (>= 7) et lacunes (<= 4)."""
    strengths: list[dict] = []
    gaps: list[dict] = []

    for code, data in criteria_scores.items():
        criterion = CRITERIA_BY_CODE.get(code)
        if criterion is None:
            continue

        score = data.get("score", 0)

        if score >= 7:
            strengths.append({
                "criteria_code": code,
                "pillar": criterion.pillar,
                "title": criterion.label,
                "description": data.get("justification", ""),
                "score": score,
            })
        elif score <= 4:
            gaps.append({
                "criteria_code": code,
                "pillar": criterion.pillar,
                "title": criterion.label,
                "score": score,
            })

    strengths.sort(key=lambda x: x["score"], reverse=True)
    gaps.sort(key=lambda x: x["score"])

    return strengths, gaps


def build_initial_esg_state(assessment_id: str, sector: str) -> dict:
    """Construire l'etat initial de l'evaluation ESG pour le ConversationState."""
    return {
        "assessment_id": assessment_id,
        "status": "in_progress",
        "current_pillar": "environment",
        "evaluated_criteria": [],
        "partial_scores": {},
    }


def get_next_pillar(current_pillar: str) -> str | None:
    """Obtenir le prochain pilier dans l'ordre E -> S -> G."""
    try:
        idx = PILLAR_ORDER.index(current_pillar)
    except ValueError:
        return None
    next_idx = idx + 1
    if next_idx >= len(PILLAR_ORDER):
        return None
    return PILLAR_ORDER[next_idx]


def compute_progress_percent(evaluated_criteria: list[str]) -> float:
    """Calculer le pourcentage de progression de l'evaluation."""
    if not evaluated_criteria:
        return 0.0
    return round((len(evaluated_criteria) / TOTAL_CRITERIA) * 100, 2)


# --- Fonctions CRUD (avec I/O base de donnees) ---


async def get_resumable_assessment(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> ESGAssessment | None:
    """Trouver une evaluation en cours (draft ou in_progress) a reprendre."""
    result = await db.execute(
        select(ESGAssessment)
        .where(
            ESGAssessment.user_id == user_id,
            ESGAssessment.status.in_([ESGStatusEnum.draft, ESGStatusEnum.in_progress]),
        )
        .order_by(ESGAssessment.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_assessment(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> ESGAssessment | None:
    """Trouver l'evaluation la plus recente, quel que soit le statut."""
    result = await db.execute(
        select(ESGAssessment)
        .where(ESGAssessment.user_id == user_id)
        .order_by(ESGAssessment.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_assessment(
    db: AsyncSession,
    user_id: uuid.UUID,
    sector: str,
    conversation_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
) -> ESGAssessment:
    """Creer une nouvelle evaluation ESG.

    F02 multi-tenant : `account_id` est requis cote schema (NOT NULL).
    Si non fourni, on resout via le user (fallback) pour rester compatible
    avec les callers existants.
    """
    if account_id is None:
        from app.models.user import User as _User

        result = await db.execute(select(_User).where(_User.id == user_id))
        user_obj = result.scalar_one_or_none()
        if user_obj is None or user_obj.account_id is None:
            raise ValueError(
                "create_assessment: account_id introuvable pour l'utilisateur."
            )
        account_id = user_obj.account_id

    assessment = ESGAssessment(
        user_id=user_id,
        account_id=account_id,
        sector=sector,
        conversation_id=conversation_id,
        status=ESGStatusEnum.draft,
        evaluated_criteria=[],
    )
    db.add(assessment)
    await db.flush()
    return assessment


async def get_assessment(
    db: AsyncSession,
    assessment_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ESGAssessment | None:
    """Recuperer une evaluation par ID (filtree par user_id)."""
    result = await db.execute(
        select(ESGAssessment).where(
            ESGAssessment.id == assessment_id,
            ESGAssessment.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def list_assessments(
    db: AsyncSession,
    user_id: uuid.UUID,
    status: str | None = None,
    page: int = 1,
    limit: int = 10,
) -> tuple[list[ESGAssessment], int]:
    """Lister les evaluations paginées d'un utilisateur."""
    query = select(ESGAssessment).where(ESGAssessment.user_id == user_id)
    count_query = select(func.count()).select_from(ESGAssessment).where(
        ESGAssessment.user_id == user_id
    )

    if status:
        query = query.where(ESGAssessment.status == status)
        count_query = count_query.where(ESGAssessment.status == status)

    query = query.order_by(ESGAssessment.created_at.desc())
    query = query.offset((page - 1) * limit).limit(limit)

    result = await db.execute(query)
    assessments = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return assessments, total


async def update_assessment(
    db: AsyncSession,
    assessment: ESGAssessment,
    **kwargs: Any,
) -> ESGAssessment:
    """Mettre a jour une evaluation ESG."""
    for key, value in kwargs.items():
        if hasattr(assessment, key):
            setattr(assessment, key, value)
    await db.flush()
    return assessment


# --- Fonctions RAG (recherche documentaire par critere ESG) ---


async def _search_chunks_by_query(
    db: AsyncSession,
    query: str,
    user_id: uuid.UUID,
    limit: int = 3,
) -> list:
    """Recherche vectorielle par similarite cosinus dans les chunks de l'utilisateur."""
    from app.modules.documents.service import search_similar_chunks

    return await search_similar_chunks(
        db=db,
        user_id=user_id,
        query=query,
        limit=limit,
    )


async def search_relevant_chunks(
    db: AsyncSession,
    criteria_code: str,
    user_id: uuid.UUID,
    limit: int = 3,
) -> list[dict]:
    """Rechercher les chunks documentaires pertinents pour un critere ESG.

    Utilise le libelle et la description du critere comme requete de recherche
    vectorielle dans les documents de l'utilisateur.
    """
    criterion = CRITERIA_BY_CODE.get(criteria_code)
    if criterion is None:
        return []

    query = f"{criterion.label} {criterion.description}"

    try:
        chunks = await _search_chunks_by_query(
            db=db,
            query=query,
            user_id=user_id,
            limit=limit,
        )
    except Exception:
        logger.exception("Erreur lors de la recherche RAG pour %s", criteria_code)
        return []

    return [
        {
            "content": chunk.content,
            "document_id": str(chunk.document_id),
            "chunk_index": chunk.chunk_index,
        }
        for chunk in chunks
    ]


async def search_rag_context_for_pillar(
    db: AsyncSession,
    pillar: str,
    user_id: uuid.UUID,
    limit_per_criterion: int = 2,
) -> dict[str, list[dict]]:
    """Rechercher le contexte RAG pour tous les criteres d'un pilier.

    Retourne un dict { criteria_code: [chunks] } pour le pilier demande.
    """
    pillar_criteria = PILLAR_CRITERIA.get(pillar, ())
    context: dict[str, list[dict]] = {}

    for criterion in pillar_criteria:
        chunks = await search_relevant_chunks(
            db=db,
            criteria_code=criterion.code,
            user_id=user_id,
            limit=limit_per_criterion,
        )
        if chunks:
            context[criterion.code] = chunks

    return context


def format_rag_context(rag_context: dict[str, list[dict]]) -> str:
    """Formater le contexte RAG pour injection dans le prompt ESG."""
    if not rag_context:
        return ""

    lines: list[str] = ["Documents pertinents identifies :"]
    for code, chunks in rag_context.items():
        criterion = CRITERIA_BY_CODE.get(code)
        label = criterion.label if criterion else code
        lines.append(f"\n**{code} ({label})** :")
        for chunk in chunks:
            content_preview = chunk["content"][:300]
            lines.append(f"  - \"{content_preview}\"")

    return "\n".join(lines)


# --- Fonctions Benchmark (finalisation evaluation) ---


async def finalize_assessment_with_benchmark(
    db: AsyncSession,
    assessment: ESGAssessment,
    criteria_scores: dict[str, dict],
) -> ESGAssessment:
    """Finaliser une evaluation : calculer scores, recommandations, benchmark.

    Appele quand les 30 criteres sont evalues.
    """
    scores = compute_overall_score(criteria_scores, assessment.sector)
    strengths, gaps = generate_strengths_gaps(criteria_scores)
    recommendations = generate_recommendations(criteria_scores)
    benchmark = compute_benchmark_comparison(assessment.sector, scores)

    return await update_assessment(
        db,
        assessment,
        status=ESGStatusEnum.completed,
        overall_score=scores["overall_score"],
        environment_score=scores["environment_score"],
        social_score=scores["social_score"],
        governance_score=scores["governance_score"],
        assessment_data={
            "criteria_scores": criteria_scores,
            "pillar_details": {
                pillar: {
                    "raw_score": scores[f"{pillar}_score"],
                    "weighted_score": scores[f"{pillar}_score"],
                    "weights_applied": {},
                }
                for pillar in PILLAR_ORDER
            },
        },
        strengths=strengths,
        gaps=gaps,
        recommendations=recommendations,
        sector_benchmark=benchmark,
        current_pillar=None,
    )


def compute_benchmark_comparison(
    sector: str,
    scores: dict[str, float],
) -> dict | None:
    """Calculer la comparaison avec le benchmark sectoriel."""
    benchmark = get_sector_benchmark(sector)
    if benchmark is None:
        # Secteur inconnu : utiliser la moyenne generale
        return _compute_fallback_benchmark(scores)

    averages = benchmark.get("averages", {})
    overall_avg = averages.get("overall", 50)
    overall_score = scores.get("overall_score", 0)

    if overall_score > overall_avg * 1.1:
        position = "above_average"
    elif overall_score < overall_avg * 0.9:
        position = "below_average"
    else:
        position = "average"

    # Estimation du percentile (simplifiee)
    diff = overall_score - overall_avg
    percentile = min(99, max(1, int(50 + diff)))

    return {
        "sector": sector,
        "averages": averages,
        "position": position,
        "percentile": percentile,
    }


def _compute_fallback_benchmark(scores: dict[str, float]) -> dict:
    """Benchmark de repli quand le secteur n'est pas connu."""
    general_avg = {"environment": 48, "social": 47, "governance": 44, "overall": 46}
    overall_score = scores.get("overall_score", 0)
    overall_avg = general_avg["overall"]

    if overall_score > overall_avg * 1.1:
        position = "above_average"
    elif overall_score < overall_avg * 0.9:
        position = "below_average"
    else:
        position = "average"

    diff = overall_score - overall_avg
    percentile = min(99, max(1, int(50 + diff)))

    return {
        "sector": "general",
        "averages": general_avg,
        "position": position,
        "percentile": percentile,
    }
