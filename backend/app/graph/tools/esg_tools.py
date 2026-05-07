"""Tools LangChain pour le noeud d'evaluation ESG."""

import logging
import uuid

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field

from app.graph.tools.common import UUID_PATTERN, get_db_and_user, with_retry

logger = logging.getLogger(__name__)


_CRITERION_CODE_PATTERN = r"^[ESG][0-9]{1,3}$"


class CreateESGAssessmentArgs(BaseModel):
    """Args (vide) pour create_esg_assessment."""

    model_config = ConfigDict(extra="forbid")


class SaveESGCriterionScoreArgs(BaseModel):
    """Args strict pour save_esg_criterion_score."""

    model_config = ConfigDict(extra="forbid")

    assessment_id: str = Field(..., min_length=36, max_length=36, pattern=UUID_PATTERN)
    criterion_code: str = Field(..., pattern=_CRITERION_CODE_PATTERN)
    score: int = Field(..., ge=0, le=10)
    justification: str = Field(..., min_length=1, max_length=2000)


class _CriterionItem(BaseModel):
    """Element d'un batch de criteres ESG."""

    model_config = ConfigDict(extra="forbid")

    criterion_code: str = Field(..., pattern=_CRITERION_CODE_PATTERN)
    score: int = Field(..., ge=0, le=10)
    justification: str = Field(..., min_length=1, max_length=2000)


class BatchSaveESGCriteriaArgs(BaseModel):
    """Args strict pour batch_save_esg_criteria."""

    model_config = ConfigDict(extra="forbid")

    assessment_id: str = Field(..., min_length=36, max_length=36, pattern=UUID_PATTERN)
    criteria: list[_CriterionItem] = Field(..., min_length=1, max_length=30)


class FinalizeESGAssessmentArgs(BaseModel):
    """Args strict pour finalize_esg_assessment."""

    model_config = ConfigDict(extra="forbid")

    assessment_id: str = Field(..., min_length=36, max_length=36, pattern=UUID_PATTERN)


class GetESGAssessmentArgs(BaseModel):
    """Args strict pour get_esg_assessment."""

    model_config = ConfigDict(extra="forbid")

    assessment_id: str | None = Field(
        None, min_length=36, max_length=36, pattern=UUID_PATTERN,
    )


@tool(args_schema=CreateESGAssessmentArgs)
async def create_esg_assessment(config: RunnableConfig) -> str:
    """Cree une nouvelle evaluation ESG vide (statut draft) pour l'utilisateur.

    Use when:
    - l'utilisateur demarre explicitement une evaluation ESG.
    - aucune evaluation reprenable trouvee via `get_esg_assessment`.
    Don't use when:
    - une evaluation est deja en cours (utiliser `get_esg_assessment`).
    - simple consultation (utiliser `get_esg_assessment`).
    Exemple: "Demarre mon ESG" -> create_esg_assessment().
    Anti: "Ou en suis-je ?" -> NE PAS appeler.
    """
    from app.modules.esg.service import create_assessment

    try:
        db, user_id = get_db_and_user(config)
        configurable = (config or {}).get("configurable", {})
        conversation_id = configurable.get("conversation_id")

        sector = "services"
        if configurable.get("user_profile"):
            sector = configurable["user_profile"].get("sector", "services")

        assessment = await create_assessment(
            db=db,
            user_id=user_id,
            sector=sector,
            conversation_id=uuid.UUID(str(conversation_id)) if conversation_id else None,
        )

        return (
            f"Evaluation ESG creee avec succes.\n"
            f"- ID : {assessment.id}\n"
            f"- Secteur : {assessment.sector}\n"
            f"- Statut : {assessment.status.value}"
        )
    except Exception as e:
        logger.exception("Erreur lors de la creation de l'evaluation ESG")
        return f"Erreur lors de la creation de l'evaluation ESG : {e}"


@tool(args_schema=SaveESGCriterionScoreArgs)
async def save_esg_criterion_score(
    assessment_id: str,
    criterion_code: str,
    score: int,
    justification: str,
    config: RunnableConfig,
) -> str:
    """Enregistre la note (0-10) d'un seul critere ESG (E/S/G + numero).

    Use when:
    - evaluer 1-3 criteres ponctuels.
    - corriger un critere deja sauvegarde.
    Don't use when:
    - tout un pilier (utiliser `batch_save_esg_criteria`).
    - pas d'evaluation (utiliser `create_esg_assessment`).
    Exemple: "S5 solide" -> save_esg_criterion_score(criterion_code='S5', score=8).
    Anti: "Pilier E entier" -> NE PAS appeler ; utiliser `batch_save_esg_criteria`.
    """
    from app.modules.esg.service import (
        compute_overall_score,
        compute_progress_percent,
        get_assessment,
        update_assessment,
    )

    try:
        db, user_id = get_db_and_user(config)

        assessment = await get_assessment(
            db=db,
            assessment_id=uuid.UUID(assessment_id),
            user_id=user_id,
        )
        if assessment is None:
            return f"Erreur : evaluation ESG {assessment_id} introuvable."

        criteria_scores = dict((assessment.assessment_data or {}).get("criteria_scores", {}))
        criteria_scores[criterion_code] = {
            "score": score,
            "justification": justification,
        }

        evaluated_criteria = list(assessment.evaluated_criteria or [])
        if criterion_code not in evaluated_criteria:
            evaluated_criteria.append(criterion_code)

        current_pillar = assessment.current_pillar
        if criterion_code.startswith("E"):
            current_pillar = "environment"
        elif criterion_code.startswith("S"):
            current_pillar = "social"
        elif criterion_code.startswith("G"):
            current_pillar = "governance"

        assessment_data = dict(assessment.assessment_data or {})
        assessment_data["criteria_scores"] = criteria_scores

        from app.models.esg import ESGStatusEnum

        await update_assessment(
            db=db,
            assessment=assessment,
            assessment_data=assessment_data,
            evaluated_criteria=evaluated_criteria,
            current_pillar=current_pillar,
            status=ESGStatusEnum.in_progress,
        )

        progress = compute_progress_percent(evaluated_criteria)
        scores = compute_overall_score(criteria_scores, assessment.sector)

        return (
            f"Critere {criterion_code} enregistre : {score}/10.\n"
            f"- Criteres evalues : {len(evaluated_criteria)}/30\n"
            f"- Progression : {progress}%\n"
            f"- Scores partiels — E: {scores['environment_score']}, "
            f"S: {scores['social_score']}, G: {scores['governance_score']}, "
            f"Global: {scores['overall_score']}"
        )
    except Exception as e:
        logger.exception("Erreur lors de la sauvegarde du critere %s", criterion_code)
        return f"Erreur lors de la sauvegarde du critere {criterion_code} : {e}"


@tool(args_schema=FinalizeESGAssessmentArgs)
@with_retry(
    max_retries=1,
    node_name="esg_scoring_node",
    fallback_message=(
        "Je n'arrive pas à finaliser l'évaluation ESG. "
        "Pouvez-vous confirmer à nouveau ou réessayer ?"
    ),
)
async def finalize_esg_assessment(
    assessment_id: str,
    config: RunnableConfig,
) -> str:
    """Finalise l'evaluation ESG (completed) et calcule scores 0-100 + benchmark.

    Use when:
    - l'utilisateur a confirme explicitement la cloture.
    - 30 criteres evalues + confirmation utilisateur.
    Don't use when:
    - pas de confirmation (demander via `ask_interactive_question`).
    - simple consultation (utiliser `get_esg_assessment`).
    Exemple: "Oui, finalise" -> finalize_esg_assessment(assessment_id='...').
    Anti: "Affiche mon score" -> NE PAS appeler.
    """
    from app.modules.esg.service import finalize_assessment_with_benchmark, get_assessment

    try:
        db, user_id = get_db_and_user(config)

        assessment = await get_assessment(
            db=db,
            assessment_id=uuid.UUID(assessment_id),
            user_id=user_id,
        )
        if assessment is None:
            return f"Erreur : evaluation ESG {assessment_id} introuvable."

        criteria_scores = (assessment.assessment_data or {}).get("criteria_scores", {})

        finalized = await finalize_assessment_with_benchmark(
            db=db,
            assessment=assessment,
            criteria_scores=criteria_scores,
        )

        benchmark_info = ""
        if finalized.sector_benchmark:
            position = finalized.sector_benchmark.get("position", "N/A")
            percentile = finalized.sector_benchmark.get("percentile", "N/A")
            benchmark_info = f"- Position sectorielle : {position}\n- Percentile : {percentile}e\n"

        strengths_count = len(finalized.strengths or [])
        gaps_count = len(finalized.gaps or [])
        reco_count = len(finalized.recommendations or [])

        return (
            f"Evaluation ESG finalisee avec succes !\n"
            f"- Score global : {finalized.overall_score}/100\n"
            f"- Environnement : {finalized.environment_score}/100\n"
            f"- Social : {finalized.social_score}/100\n"
            f"- Gouvernance : {finalized.governance_score}/100\n"
            f"{benchmark_info}"
            f"- Points forts : {strengths_count}\n"
            f"- Lacunes identifiees : {gaps_count}\n"
            f"- Recommandations : {reco_count}"
        )
    except Exception as e:
        logger.exception("Erreur lors de la finalisation de l'evaluation ESG")
        return f"Erreur lors de la finalisation de l'evaluation ESG : {e}"


@tool(args_schema=GetESGAssessmentArgs)
async def get_esg_assessment(
    config: RunnableConfig,
    assessment_id: str | None = None,
) -> str:
    """Consulte une evaluation ESG (par id, sinon la plus recente reprenable).

    Use when:
    - l'utilisateur demande son score ou sa progression.
    - verifier qu'une evaluation est reprenable.
    Don't use when:
    - demarrer une nouvelle evaluation (utiliser `create_esg_assessment`).
    - sauvegarder un critere (utiliser `save_esg_criterion_score`).
    Exemple: "Ou en suis-je ?" -> get_esg_assessment().
    Anti: "Cree une evaluation" -> NE PAS appeler.
    """
    from app.modules.esg.service import (
        compute_progress_percent,
        get_assessment,
        get_resumable_assessment,
    )

    try:
        db, user_id = get_db_and_user(config)

        assessment = None
        if assessment_id:
            assessment = await get_assessment(
                db=db,
                assessment_id=uuid.UUID(assessment_id),
                user_id=user_id,
            )
        else:
            assessment = await get_resumable_assessment(db=db, user_id=user_id)

        if assessment is None:
            if assessment_id:
                return f"Aucune evaluation ESG trouvee avec l'ID {assessment_id}."
            return "Aucune evaluation ESG en cours trouvee pour cet utilisateur."

        status = assessment.status.value if hasattr(assessment.status, "value") else assessment.status
        evaluated = assessment.evaluated_criteria or []
        progress = compute_progress_percent(evaluated)

        summary = (
            f"Evaluation ESG trouvee :\n"
            f"- ID : {assessment.id}\n"
            f"- Statut : {status}\n"
            f"- Secteur : {assessment.sector}\n"
            f"- Pilier en cours : {assessment.current_pillar or 'N/A'}\n"
            f"- Criteres evalues : {len(evaluated)}/30\n"
            f"- Progression : {progress}%"
        )

        if status == "completed" and assessment.overall_score is not None:
            summary += (
                f"\n- Score global : {assessment.overall_score}/100\n"
                f"- Environnement : {assessment.environment_score}/100\n"
                f"- Social : {assessment.social_score}/100\n"
                f"- Gouvernance : {assessment.governance_score}/100"
            )

        return summary
    except Exception as e:
        logger.exception("Erreur lors de la recuperation de l'evaluation ESG")
        return f"Erreur lors de la recuperation de l'evaluation ESG : {e}"


@tool(args_schema=BatchSaveESGCriteriaArgs)
@with_retry(
    max_retries=1,
    node_name="esg_scoring_node",
    fallback_message=(
        "Je n'arrive pas à enregistrer cette série de critères ESG. "
        "Pouvez-vous reformuler ou les saisir un par un ?"
    ),
)
async def batch_save_esg_criteria(
    assessment_id: str,
    criteria: list[dict],
    config: RunnableConfig,
) -> str:
    """Enregistre N criteres ESG (1-30) en une seule transaction.

    Use when:
    - notes de plusieurs criteres (pilier complet).
    - eviter timeout de N `save_esg_criterion_score`.
    Don't use when:
    - un seul critere (utiliser `save_esg_criterion_score`).
    - pas d'evaluation (utiliser `create_esg_assessment`).
    Exemple: "Pilier E entier" -> batch_save_esg_criteria(criteria=[...]).
    Anti: "Note S5 a 8" -> NE PAS appeler.
    """
    from app.models.esg import ESGStatusEnum
    from app.modules.esg.service import (
        compute_overall_score,
        compute_progress_percent,
        get_assessment,
        update_assessment,
    )

    try:
        db, user_id = get_db_and_user(config)

        assessment = await get_assessment(
            db=db,
            assessment_id=uuid.UUID(assessment_id),
            user_id=user_id,
        )
        if assessment is None:
            return f"Erreur : evaluation ESG {assessment_id} introuvable."

        if not criteria:
            return "Erreur : la liste de criteres est vide."

        criteria_scores = dict((assessment.assessment_data or {}).get("criteria_scores", {}))
        evaluated_criteria = list(assessment.evaluated_criteria or [])

        # Pydantic v2 + args_schema=BatchSaveESGCriteriaArgs convertit chaque entree
        # en _CriterionItem (BaseModel). Si le tool est appele directement avec un
        # dict (tests, code legacy), on tolere les deux formes.
        normalized: list[dict] = [
            c if isinstance(c, dict) else c.model_dump()
            for c in criteria
        ]

        for item in normalized:
            code = item["criterion_code"]
            criteria_scores[code] = {
                "score": item["score"],
                "justification": item["justification"],
            }
            if code not in evaluated_criteria:
                evaluated_criteria.append(code)

        last_code = normalized[-1]["criterion_code"]
        current_pillar = assessment.current_pillar
        if last_code.startswith("E"):
            current_pillar = "environment"
        elif last_code.startswith("S"):
            current_pillar = "social"
        elif last_code.startswith("G"):
            current_pillar = "governance"

        assessment_data = dict(assessment.assessment_data or {})
        assessment_data["criteria_scores"] = criteria_scores

        await update_assessment(
            db=db,
            assessment=assessment,
            assessment_data=assessment_data,
            evaluated_criteria=evaluated_criteria,
            current_pillar=current_pillar,
            status=ESGStatusEnum.in_progress,
        )

        progress = compute_progress_percent(evaluated_criteria)
        scores = compute_overall_score(criteria_scores, assessment.sector)

        saved_codes = [item["criterion_code"] for item in normalized]
        return (
            f"{len(criteria)} criteres enregistres : {', '.join(saved_codes)}.\n"
            f"- Criteres evalues : {len(evaluated_criteria)}/30\n"
            f"- Progression : {progress}%\n"
            f"- Scores partiels — E: {scores['environment_score']}, "
            f"S: {scores['social_score']}, G: {scores['governance_score']}, "
            f"Global: {scores['overall_score']}"
        )
    except Exception as e:
        logger.exception("Erreur lors de la sauvegarde par lot de %d criteres", len(criteria))
        return f"Erreur lors de la sauvegarde par lot : {e}"


ESG_TOOLS = [
    create_esg_assessment,
    save_esg_criterion_score,
    finalize_esg_assessment,
    get_esg_assessment,
    batch_save_esg_criteria,
]


# ---------------------------------------------------------------------------
# F13 — Tools LangChain pour le scoring multi-référentiels
# ---------------------------------------------------------------------------


class FinalizeESGAssessmentMultiRefArgs(BaseModel):
    """Args strict pour ``finalize_esg_assessment_multi_ref``."""

    model_config = ConfigDict(extra="forbid")

    assessment_id: str = Field(..., min_length=36, max_length=36, pattern=UUID_PATTERN)
    referentials_to_compute: list[str] | None = Field(
        default=None,
        description=(
            "Codes des référentiels à calculer (default: tous les actifs). "
            "Ex: ['mefali', 'ifc_ps']"
        ),
    )


class RecomputeScoreArgs(BaseModel):
    """Args strict pour ``recompute_score``."""

    model_config = ConfigDict(extra="forbid")

    entity_id: str = Field(..., min_length=36, max_length=36, pattern=UUID_PATTERN)
    referentiel_id: str = Field(..., min_length=36, max_length=36, pattern=UUID_PATTERN)


class CompareReferentialsArgs(BaseModel):
    """Args strict pour ``compare_referentials``."""

    model_config = ConfigDict(extra="forbid")

    assessment_id: str = Field(..., min_length=36, max_length=36, pattern=UUID_PATTERN)
    referentials: list[str] = Field(..., min_length=1, max_length=10)


@tool(args_schema=FinalizeESGAssessmentMultiRefArgs)
async def finalize_esg_assessment_multi_ref(
    assessment_id: str,
    config: RunnableConfig,
    referentials_to_compute: list[str] | None = None,
) -> str:
    """Finalise une evaluation ESG en calculant N scores multi-referentiels (F13).

    Use when:
    - l'utilisateur veut un scoring multi-referentiels (ex : Mefali + IFC PS).
    - finalisation atomique avec calcul des N scores en parallele.
    Don't use when:
    - simple score Mefali mono-referentiel (utiliser `finalize_esg_assessment`).
    - aucune evaluation ESG (utiliser `create_esg_assessment`).
    Exemple: 'Finalise mon ESG avec IFC' -> finalize_esg_assessment_multi_ref(assessment_id='...', referentials_to_compute=['mefali','ifc_ps']).
    Anti: 'Affiche mes scores actuels' -> NE PAS appeler ; utiliser `compare_referentials`.
    """
    from app.modules.esg.multi_referential_service import (
        compute_all_referential_scores,
    )
    from app.models.esg import ESGAssessment, ESGStatusEnum
    from app.models.referential import Referential
    from sqlalchemy import select

    try:
        db, user_id = get_db_and_user(config)

        # Charger l'assessment
        assessment = (
            await db.execute(
                select(ESGAssessment).where(
                    ESGAssessment.id == uuid.UUID(assessment_id),
                    ESGAssessment.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if assessment is None:
            return f"Erreur : évaluation ESG {assessment_id} introuvable."

        # Marquer comme finalisée
        assessment.status = ESGStatusEnum.completed
        await db.flush()

        # Filtrer les référentiels par codes si fournis
        only_referential_ids = None
        if referentials_to_compute:
            ref_q = await db.execute(
                select(Referential.id).where(Referential.code.in_(referentials_to_compute))
            )
            only_referential_ids = [r[0] for r in ref_q.all()]

        scores, failures = await compute_all_referential_scores(
            db,
            assessment_id=uuid.UUID(assessment_id),
        )

        if only_referential_ids is not None:
            scores = [s for s in scores if s.referential_id in only_referential_ids]

        score_summary = ", ".join(
            f"{s.referential_id}={float(s.overall_score) if s.overall_score is not None else 'N/A'}"
            for s in scores
        )
        return (
            f"Évaluation ESG finalisée : {len(scores)} référentiel(s) calculé(s).\n"
            f"- Scores : {score_summary}\n"
            f"- Échecs : {len(failures)}"
        )
    except Exception as e:
        logger.exception("Erreur finalize_esg_assessment_multi_ref")
        return f"Erreur lors de la finalisation multi-référentiels : {e}"


@tool(args_schema=RecomputeScoreArgs)
async def recompute_score(
    entity_id: str,
    referentiel_id: str,
    config: RunnableConfig,
) -> str:
    """Recalcule un score ESG cible (1 referentiel pour 1 evaluation) F13.

    Use when:
    - l'utilisateur demande de recalculer un score precis (ex : 'Recalcule mon IFC').
    - verifier l'impact d'une saisie d'indicateur en isolation.
    Don't use when:
    - finalisation initiale multi-referentiels (utiliser `finalize_esg_assessment_multi_ref`).
    - simple consultation (utiliser `compare_referentials`).
    Exemple: 'Recalcule mon score IFC' -> recompute_score(entity_id='asid', referentiel_id='ifcuuid').
    Anti: 'Compare Mefali et IFC' -> NE PAS appeler ; utiliser `compare_referentials`.
    """
    from app.modules.esg.multi_referential_service import (
        compute_score_for_referential,
        _upsert_referential_score,
    )
    from app.models.esg import ESGAssessment
    from app.models.referential import Referential
    from app.models.referential_score import ComputedByEnum
    from sqlalchemy import select

    try:
        db, user_id = get_db_and_user(config)
        assessment_uuid = uuid.UUID(entity_id)
        ref_uuid = uuid.UUID(referentiel_id)

        assessment = (
            await db.execute(
                select(ESGAssessment).where(
                    ESGAssessment.id == assessment_uuid,
                    ESGAssessment.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if assessment is None:
            return f"Erreur : évaluation {entity_id} introuvable."
        if assessment.account_id is None:
            return "Erreur : évaluation sans account_id."

        referential = (
            await db.execute(select(Referential).where(Referential.id == ref_uuid))
        ).scalar_one_or_none()
        if referential is None:
            return f"Erreur : référentiel {referentiel_id} introuvable."

        request_id = uuid.uuid4()
        score_data = await compute_score_for_referential(
            referential, assessment, db,
        )
        score = await _upsert_referential_score(
            db,
            account_id=assessment.account_id,
            assessment_id=assessment_uuid,
            referential=referential,
            score_data=score_data,
            computed_by=ComputedByEnum.LLM,
            computed_request_id=request_id,
        )

        return (
            f"Score {referential.code} recalculé avec succès.\n"
            f"- Overall score : {float(score.overall_score) if score.overall_score is not None else 'N/A'}\n"
            f"- Coverage : {float(score.coverage_rate) * 100:.1f}%\n"
            f"- Recompute request id : {request_id}"
        )
    except Exception as e:
        logger.exception("Erreur recompute_score")
        return f"Erreur lors du recalcul : {e}"


@tool(args_schema=CompareReferentialsArgs)
async def compare_referentials(
    assessment_id: str,
    referentials: list[str],
    config: RunnableConfig,
) -> str:
    """Compare les scores d'une evaluation selon N referentiels (F13).

    Use when:
    - l'utilisateur demande une comparaison Mefali vs IFC, etc.
    - identifier les divergences (gaps) entre referentiels.
    Don't use when:
    - simple consultation d'un score (utiliser `get_esg_assessment`).
    - recalcul d'un score (utiliser `recompute_score`).
    Exemple: 'Compare Mefali et IFC' -> compare_referentials(assessment_id='asid', referentials=['mefali','ifc_ps']).
    Anti: 'Recalcule mon IFC' -> NE PAS appeler ; utiliser `recompute_score`.
    """
    from app.models.esg import ESGAssessment
    from app.models.referential import Referential
    from app.models.referential_score import ReferentialScore
    from sqlalchemy import select

    try:
        db, user_id = get_db_and_user(config)
        assessment_uuid = uuid.UUID(assessment_id)

        assessment = (
            await db.execute(
                select(ESGAssessment).where(
                    ESGAssessment.id == assessment_uuid,
                    ESGAssessment.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if assessment is None:
            return f"Erreur : évaluation {assessment_id} introuvable."

        # Charger les scores correspondants
        rows = (
            await db.execute(
                select(ReferentialScore, Referential)
                .join(Referential, ReferentialScore.referential_id == Referential.id)
                .where(
                    ReferentialScore.assessment_id == assessment_uuid,
                    ReferentialScore.superseded_by.is_(None),
                    Referential.code.in_(referentials),
                )
            )
        ).all()

        if not rows:
            return (
                f"Aucun score calculé pour les référentiels {referentials}. "
                "Utiliser ``finalize_esg_assessment_multi_ref`` pour calculer."
            )

        scores_list = []
        for score, ref in rows:
            ov = (
                float(score.overall_score) if score.overall_score is not None else None
            )
            scores_list.append((ref.code, ref.label, ov))

        # Calculer gap entre paires consécutives
        gaps = []
        if len(scores_list) >= 2:
            for i in range(len(scores_list) - 1):
                a_code, a_label, a_score = scores_list[i]
                b_code, b_label, b_score = scores_list[i + 1]
                if a_score is not None and b_score is not None:
                    gap = abs(a_score - b_score)
                    gaps.append(
                        f"  - {a_code} ({a_score:.1f}) vs {b_code} ({b_score:.1f}) : "
                        f"écart {gap:.1f} points"
                    )

        scores_text = "\n".join(
            f"  - {code} ({label}) : {score:.1f}/100" if score is not None
            else f"  - {code} ({label}) : non calculable (couverture insuffisante)"
            for code, label, score in scores_list
        )

        return (
            f"Comparaison multi-référentiels :\n{scores_text}\n"
            + ("Écarts identifiés :\n" + "\n".join(gaps) if gaps else "")
        )
    except Exception as e:
        logger.exception("Erreur compare_referentials")
        return f"Erreur lors de la comparaison : {e}"


# F13 — Append F13 tools to the global ESG_TOOLS list (idempotent ; éviter
# de re-ajouter en cas de re-import).
_F13_TOOLS = [finalize_esg_assessment_multi_ref, recompute_score, compare_referentials]
for _t in _F13_TOOLS:
    if _t not in ESG_TOOLS:
        ESG_TOOLS.append(_t)
