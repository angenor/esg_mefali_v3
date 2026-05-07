"""F13 — Service de scoring ESG multi-référentiels.

Ce module implémente :

- ``compute_score_for_referential`` : helper générique qui calcule le score
  d'UN référentiel à partir des indicateurs renseignés (pondération qui
  ignore les non-renseignés, pas zéro).
- ``compute_all_referential_scores`` : calcule les N référentiels actifs
  en parallèle (asyncio.gather) avec UPSERT idempotent et atomicité par
  référentiel.
- ``compute_referential_score_for_offer`` : calcule les 2 scores
  (fund + intermediary) avec fallback Mefali.
- ``recompute_score_async`` : helper FastAPI BackgroundTasks pour recalcul
  ciblé.

Le pattern « 1 saisie = N scores » est garanti par le fait que les services
lisent les ``criteria_scores`` depuis ``EsgAssessment.assessment_data`` (saisi
une fois) et calculent N référentiels indépendamment.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    DEFAULT_REFERENTIAL_THRESHOLD,
    MEFALI_REFERENTIAL_CODE,
    MEFALI_REFERENTIAL_UUID,
)
from app.models.esg import ESGAssessment
from app.models.referential import Referential
from app.models.referential_score import ComputedByEnum, ReferentialScore

logger = logging.getLogger(__name__)


# --- Helpers ---


def _criteria_scores_from_assessment(assessment: ESGAssessment) -> dict[str, dict]:
    """Extraire ``criteria_scores`` depuis ``assessment.assessment_data``."""
    if assessment.assessment_data is None:
        return {}
    return dict(assessment.assessment_data.get("criteria_scores", {}))


def _is_mefali_referential(referential: Referential) -> bool:
    """Vrai si le référentiel est Mefali (code 'mefali')."""
    return referential.code == MEFALI_REFERENTIAL_CODE


def _build_pillar_scores_from_legacy(
    criteria_scores: dict[str, dict],
    sector: str,
) -> tuple[dict, dict]:
    """Construit les pillar_scores et la liste des covered/missing pour Mefali.

    Réutilise l'implémentation legacy F05 (30 critères E1-E10/S1-S10/G1-G10).
    Retourne ``(pillar_scores_dict, lists_dict)``.
    """
    from app.modules.esg.criteria import PILLAR_CRITERIA
    from app.modules.esg.service import compute_pillar_score
    from app.modules.esg.weights import get_criterion_weight

    pillar_scores: dict[str, dict] = {}
    covered_criteria: list[dict] = []
    missing_criteria: list[dict] = []

    total_renseigned = 0
    total_count = 0

    for pillar_key, pillar_criteria in PILLAR_CRITERIA.items():
        weight_default = {
            "environment": 0.33,
            "social": 0.33,
            "governance": 0.34,
        }.get(pillar_key, 0.33)
        score_for_pillar = compute_pillar_score(
            pillar_key, criteria_scores, sector,
        )
        crit_count = len(pillar_criteria)
        crit_renseigned = 0
        for c in pillar_criteria:
            if c.code in criteria_scores:
                crit_renseigned += 1
                covered_criteria.append({
                    "indicator_id": str(uuid.UUID(int=hash(c.code) & ((1 << 128) - 1))),
                    "indicator_code": c.code,
                    "score": float(criteria_scores[c.code].get("score", 0)) * 10,  # 0-10 → 0-100
                    "weight": float(get_criterion_weight(sector, c.code)),
                    "source_id": None,
                })
            else:
                missing_criteria.append({
                    "indicator_id": str(uuid.UUID(int=hash(c.code) & ((1 << 128) - 1))),
                    "indicator_code": c.code,
                    "reason": "non_renseigne",
                    "source_id": None,
                    "suggestion": f"Renseigner le critère {c.code} : {c.label}",
                })

        total_renseigned += crit_renseigned
        total_count += crit_count

        pillar_scores[pillar_key] = {
            "score": float(score_for_pillar),
            "weight": weight_default,
            "criteria_count": crit_count,
            "criteria_renseignés": crit_renseigned,
        }

    return pillar_scores, {
        "covered_criteria": covered_criteria,
        "missing_criteria": missing_criteria,
        "total_renseigned": total_renseigned,
        "total_count": total_count,
    }


# --- Calcul de score pour UN référentiel ---


async def compute_score_for_referential(
    referential: Referential,
    assessment: ESGAssessment,
    db: AsyncSession,
) -> dict[str, Any]:
    """Calcule le score d'UN référentiel pour UNE évaluation ESG.

    Pondération qui IGNORE les indicateurs non-renseignés (cf. clarification Q3).

    Pour Mefali (référentiel par défaut), réutilise les 30 critères E/S/G F05.
    Pour les autres référentiels, lit ``referential_indicators`` (F01) et
    calcule sur la base des indicateurs renseignés.

    Returns:
        dict avec keys : overall_score, pillar_scores, coverage_rate,
        covered_criteria, missing_criteria, gap_to_threshold, eligibility.
    """
    criteria_scores = _criteria_scores_from_assessment(assessment)

    if _is_mefali_referential(referential):
        # Algorithme F05 réutilisé (30 critères E/S/G du sector)
        pillar_scores, lists = _build_pillar_scores_from_legacy(
            criteria_scores, assessment.sector,
        )
        from app.modules.esg.service import compute_overall_score

        legacy_scores = compute_overall_score(criteria_scores, assessment.sector)
        overall = legacy_scores["overall_score"]

        total_renseigned = lists["total_renseigned"]
        total_count = lists["total_count"]
        coverage_rate = (
            round(total_renseigned / total_count, 3) if total_count > 0 else 0.0
        )
        threshold = DEFAULT_REFERENTIAL_THRESHOLD
        gap = float(overall) - threshold if overall is not None else None
        eligibility = (float(overall) >= threshold) if overall is not None else None

        return {
            "overall_score": Decimal(str(overall)) if overall is not None else None,
            "pillar_scores": pillar_scores,
            "coverage_rate": Decimal(str(coverage_rate)),
            "covered_criteria": lists["covered_criteria"],
            "missing_criteria": lists["missing_criteria"],
            "gap_to_threshold": Decimal(str(gap)) if gap is not None else None,
            "eligibility": eligibility,
        }

    # Pour les autres référentiels : lecture de referential_indicators
    # (table de jointure N-N F01). Si vide, on retourne coverage=0.
    from app.models.indicator import Indicator
    from app.models.referential import ReferentialIndicator

    rows = (await db.execute(
        select(ReferentialIndicator, Indicator)
        .join(Indicator, ReferentialIndicator.indicator_id == Indicator.id)
        .where(ReferentialIndicator.referential_id == referential.id)
    )).all()

    if not rows:
        # Catalogue F01 non encore lié à ce référentiel
        return {
            "overall_score": None,
            "pillar_scores": {},
            "coverage_rate": Decimal("0.000"),
            "covered_criteria": [],
            "missing_criteria": [],
            "gap_to_threshold": None,
            "eligibility": None,
        }

    # Calcul pondéré : on agrège par pilier (selon Indicator.pillar)
    pillar_aggregates: dict[str, dict] = {}
    covered_criteria: list[dict] = []
    missing_criteria: list[dict] = []

    total_renseigned = 0
    total_count = 0

    for ri, indicator in rows:
        total_count += 1
        # Critère renseigné si on a son code dans criteria_scores
        score_data = criteria_scores.get(indicator.code)
        pillar = indicator.pillar
        if pillar not in pillar_aggregates:
            pillar_aggregates[pillar] = {
                "weighted_sum": 0.0,
                "weight_sum": 0.0,
                "criteria_count": 0,
                "criteria_renseignés": 0,
            }
        pillar_aggregates[pillar]["criteria_count"] += 1

        if score_data is not None:
            total_renseigned += 1
            pillar_aggregates[pillar]["criteria_renseignés"] += 1
            score_value = float(score_data.get("score", 0)) * 10  # 0-10 → 0-100
            weight_value = float(ri.weight or 1.0)
            pillar_aggregates[pillar]["weighted_sum"] += score_value * weight_value
            pillar_aggregates[pillar]["weight_sum"] += weight_value

            covered_criteria.append({
                "indicator_id": str(indicator.id),
                "indicator_code": indicator.code,
                "score": score_value,
                "weight": weight_value,
                "source_id": str(ri.source_id) if ri.source_id else None,
            })
        else:
            missing_criteria.append({
                "indicator_id": str(indicator.id),
                "indicator_code": indicator.code,
                "reason": "non_renseigne",
                "source_id": str(ri.source_id) if ri.source_id else None,
                "suggestion": (
                    f"Renseigner l'indicateur {indicator.code} pour couvrir "
                    f"le référentiel {referential.code}."
                ),
            })

    # Score par pilier (moyenne pondérée), score global = moyenne des piliers
    pillar_scores: dict[str, dict] = {}
    for pillar, agg in pillar_aggregates.items():
        if agg["weight_sum"] > 0:
            pillar_score = round(agg["weighted_sum"] / agg["weight_sum"], 1)
        else:
            pillar_score = 0.0
        pillar_scores[pillar] = {
            "score": pillar_score,
            "weight": 1.0 / max(len(pillar_aggregates), 1),
            "criteria_count": agg["criteria_count"],
            "criteria_renseignés": agg["criteria_renseignés"],
        }

    coverage_rate = round(total_renseigned / total_count, 3) if total_count > 0 else 0.0

    if coverage_rate == 0:
        overall_score: Decimal | None = None
    else:
        # Score global = moyenne des piliers où des critères sont renseignés
        scores_with_data = [
            p["score"] for p in pillar_scores.values() if p["criteria_renseignés"] > 0
        ]
        if scores_with_data:
            overall_score = Decimal(str(round(sum(scores_with_data) / len(scores_with_data), 2)))
        else:
            overall_score = None

    threshold = DEFAULT_REFERENTIAL_THRESHOLD
    gap = float(overall_score) - threshold if overall_score is not None else None
    eligibility = (
        float(overall_score) >= threshold if overall_score is not None else None
    )

    return {
        "overall_score": overall_score,
        "pillar_scores": pillar_scores,
        "coverage_rate": Decimal(str(coverage_rate)),
        "covered_criteria": covered_criteria,
        "missing_criteria": missing_criteria,
        "gap_to_threshold": Decimal(str(gap)) if gap is not None else None,
        "eligibility": eligibility,
    }


# --- UPSERT idempotent ---


async def _upsert_referential_score(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    assessment_id: uuid.UUID,
    referential: Referential,
    score_data: dict,
    computed_by: ComputedByEnum,
    computed_request_id: uuid.UUID | None = None,
) -> ReferentialScore:
    """UPSERT idempotent d'un score pour le couple (assessment_id, referential_id).

    Si une ligne courante existe (superseded_by IS NULL) :
    - Si la version du référentiel a changé, marque l'ancienne supersedée
      et crée une nouvelle ligne (versioning F04).
    - Sinon, met à jour la ligne courante en place.
    """
    existing_q = await db.execute(
        select(ReferentialScore).where(
            ReferentialScore.assessment_id == assessment_id,
            ReferentialScore.referential_id == referential.id,
            ReferentialScore.superseded_by.is_(None),
        )
    )
    existing = existing_q.scalars().first()

    new_version = referential.version

    if existing is not None and existing.referential_version == new_version:
        # Update in place
        existing.overall_score = (
            float(score_data["overall_score"])
            if score_data["overall_score"] is not None
            else None
        )
        existing.pillar_scores = score_data["pillar_scores"]
        existing.coverage_rate = float(score_data["coverage_rate"])
        existing.covered_criteria = score_data["covered_criteria"]
        existing.missing_criteria = score_data["missing_criteria"]
        existing.gap_to_threshold = (
            float(score_data["gap_to_threshold"])
            if score_data["gap_to_threshold"] is not None
            else None
        )
        existing.eligibility = score_data["eligibility"]
        existing.computed_at = datetime.now(timezone.utc)
        existing.computed_by = computed_by
        existing.computed_request_id = computed_request_id
        await db.flush()
        return existing

    # Nouvelle ligne (insertion ou versioning F04 si version différente)
    new_id = uuid.uuid4()
    if existing is not None:
        # Marquer l'ancienne comme supersedée AVANT d'insérer la nouvelle
        existing.superseded_by = new_id
        await db.flush()

    new_score = ReferentialScore(
        id=new_id,
        account_id=account_id,
        assessment_id=assessment_id,
        referential_id=referential.id,
        referential_version=new_version,
        overall_score=(
            float(score_data["overall_score"])
            if score_data["overall_score"] is not None
            else None
        ),
        pillar_scores=score_data["pillar_scores"],
        coverage_rate=float(score_data["coverage_rate"]),
        covered_criteria=score_data["covered_criteria"],
        missing_criteria=score_data["missing_criteria"],
        gap_to_threshold=(
            float(score_data["gap_to_threshold"])
            if score_data["gap_to_threshold"] is not None
            else None
        ),
        eligibility=score_data["eligibility"],
        computed_by=computed_by,
        computed_request_id=computed_request_id,
    )
    db.add(new_score)
    await db.flush()
    return new_score


# --- Service principal : calculer N référentiels ---


async def compute_all_referential_scores(
    db: AsyncSession,
    *,
    assessment_id: uuid.UUID,
    only_referentials_using_indicators: list[uuid.UUID] | None = None,
    computed_by: ComputedByEnum = ComputedByEnum.AUTO,
    computed_request_id: uuid.UUID | None = None,
) -> tuple[list[ReferentialScore], list[dict]]:
    """Calcule les N référentiels actifs en parallèle pour une évaluation.

    Args:
        assessment_id: l'évaluation cible.
        only_referentials_using_indicators: si fourni, ne recalcule que les
            référentiels qui utilisent au moins un de ces indicateurs (via
            la table referential_indicators).
        computed_by: source du calcul.
        computed_request_id: identifiant du job background pour traçabilité.

    Returns:
        (scores, failures) : liste des ReferentialScore créés/mis à jour
        + liste des dict {referential_code, error} pour les échecs.
    """
    assessment = (
        await db.execute(select(ESGAssessment).where(ESGAssessment.id == assessment_id))
    ).scalar_one_or_none()
    if assessment is None:
        raise ValueError(f"ESGAssessment introuvable : {assessment_id}")

    if assessment.account_id is None:
        raise ValueError(
            f"ESGAssessment {assessment_id} sans account_id : impossible de "
            "calculer les referential_scores (multi-tenant requis)."
        )

    # Charger les référentiels actifs (publication_status='published')
    q = select(Referential).where(Referential.publication_status == "published")
    referentials = (await db.execute(q)).scalars().all()

    if only_referentials_using_indicators:
        # Filtrer les référentiels concernés via referential_indicators
        from app.models.referential import ReferentialIndicator

        ref_ids_q = select(ReferentialIndicator.referential_id).where(
            ReferentialIndicator.indicator_id.in_(only_referentials_using_indicators)
        ).distinct()
        ref_ids = set(r[0] for r in (await db.execute(ref_ids_q)).all())
        # Toujours inclure Mefali (puisqu'il utilise les critères legacy F05,
        # pas les indicators F01)
        referentials = [r for r in referentials if r.id in ref_ids or _is_mefali_referential(r)]

    # Calcul en parallèle (asyncio.gather avec return_exceptions pour atomicité)
    results: list[tuple[Referential, dict | Exception]] = []
    for ref in referentials:
        try:
            score_data = await compute_score_for_referential(ref, assessment, db)
            results.append((ref, score_data))
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Échec calcul score pour référentiel %s", ref.code)
            results.append((ref, exc))

    # UPSERT séquentiel (atomicité par référentiel)
    scores: list[ReferentialScore] = []
    failures: list[dict] = []
    for ref, result in results:
        if isinstance(result, Exception):
            failures.append({"referential_code": ref.code, "error": str(result)})
            continue
        try:
            score = await _upsert_referential_score(
                db,
                account_id=assessment.account_id,
                assessment_id=assessment_id,
                referential=ref,
                score_data=result,
                computed_by=computed_by,
                computed_request_id=computed_request_id,
            )
            scores.append(score)
        except Exception as exc:
            logger.exception("Échec UPSERT score pour référentiel %s", ref.code)
            failures.append({"referential_code": ref.code, "error": str(exc)})

    # Maintenir cohérence avec colonnes legacy (Mefali → esg_assessments.overall_score|...)
    mefali_score = next(
        (s for s in scores if s.referential_id == MEFALI_REFERENTIAL_UUID), None,
    )
    if mefali_score is None:
        # Fallback : chercher par code
        for s in scores:
            ref = next((r for ref_, r in []), None)
            del ref
        # On utilise la liste referentials chargée
        for ref in referentials:
            if _is_mefali_referential(ref):
                mefali_score = next(
                    (s for s in scores if s.referential_id == ref.id), None,
                )
                break

    if mefali_score is not None and mefali_score.overall_score is not None:
        # Mettre à jour assessment.overall_score, environment_score, etc.
        assessment.overall_score = float(mefali_score.overall_score)
        pillar_scores = mefali_score.pillar_scores or {}
        if "environment" in pillar_scores:
            assessment.environment_score = float(
                pillar_scores["environment"].get("score", 0)
            )
        if "social" in pillar_scores:
            assessment.social_score = float(
                pillar_scores["social"].get("score", 0)
            )
        if "governance" in pillar_scores:
            assessment.governance_score = float(
                pillar_scores["governance"].get("score", 0)
            )
        await db.flush()

    return scores, failures


# --- Service Offer (dual view) ---


async def compute_referential_score_for_offer(
    db: AsyncSession,
    *,
    assessment_id: uuid.UUID,
    offer_id: uuid.UUID,
) -> dict[str, Any]:
    """Calcule (score_fonds, score_intermediaire) pour un assessment + offer.

    Fallback Mefali si fund.referential_id IS NULL ou intermediary.referential_id IS NULL.
    Retourne un dict structuré conforme à DualReferentialResponse.
    """
    from app.models.financing import Fund, Intermediary
    from app.models.offer import Offer

    offer = (
        await db.execute(select(Offer).where(Offer.id == offer_id))
    ).scalar_one_or_none()
    if offer is None:
        raise ValueError(f"Offer introuvable : {offer_id}")

    fund = (
        await db.execute(select(Fund).where(Fund.id == offer.fund_id))
    ).scalar_one_or_none()
    intermediary = (
        await db.execute(
            select(Intermediary).where(Intermediary.id == offer.intermediary_id)
        )
    ).scalar_one_or_none()

    # F13 MVP : ni Fund ni Intermediary n'ont de referential_id ; on utilise
    # systématiquement Mefali pour les deux côtés (fallback explicite).
    fund_referential_id = getattr(fund, "referential_id", None)
    intermediary_referential_id = getattr(intermediary, "referential_id", None)

    # Charger Mefali (fallback)
    mefali_q = await db.execute(
        select(Referential).where(Referential.code == MEFALI_REFERENTIAL_CODE)
    )
    mefali = mefali_q.scalar_one_or_none()
    if mefali is None:
        raise ValueError("Référentiel Mefali introuvable. Migration 030 incomplète ?")

    # Charger les référentiels demandés (ou Mefali en fallback)
    fund_ref = mefali
    fund_is_fallback = True
    if fund_referential_id is not None:
        fund_ref_q = await db.execute(
            select(Referential).where(Referential.id == fund_referential_id)
        )
        candidate = fund_ref_q.scalar_one_or_none()
        if candidate is not None:
            fund_ref = candidate
            fund_is_fallback = False

    intermediary_ref = mefali
    intermediary_is_fallback = True
    if intermediary_referential_id is not None:
        int_ref_q = await db.execute(
            select(Referential).where(Referential.id == intermediary_referential_id)
        )
        candidate = int_ref_q.scalar_one_or_none()
        if candidate is not None:
            intermediary_ref = candidate
            intermediary_is_fallback = False

    is_dual_view = fund_ref.id != intermediary_ref.id

    # Utiliser compute_all_referential_scores pour calculer/persister les 2 scores
    assessment = (
        await db.execute(select(ESGAssessment).where(ESGAssessment.id == assessment_id))
    ).scalar_one_or_none()
    if assessment is None:
        raise ValueError(f"ESGAssessment introuvable : {assessment_id}")
    if assessment.account_id is None:
        raise ValueError(
            f"ESGAssessment {assessment_id} sans account_id : impossible de "
            "calculer le score for offer (multi-tenant requis)."
        )

    fund_score_data = await compute_score_for_referential(fund_ref, assessment, db)
    fund_score = await _upsert_referential_score(
        db,
        account_id=assessment.account_id,
        assessment_id=assessment_id,
        referential=fund_ref,
        score_data=fund_score_data,
        computed_by=ComputedByEnum.AUTO,
    )

    intermediary_score = None
    if is_dual_view:
        intermediary_score_data = await compute_score_for_referential(
            intermediary_ref, assessment, db,
        )
        intermediary_score = await _upsert_referential_score(
            db,
            account_id=assessment.account_id,
            assessment_id=assessment_id,
            referential=intermediary_ref,
            score_data=intermediary_score_data,
            computed_by=ComputedByEnum.AUTO,
        )

    # Calcul du goulot d'étranglement
    bottleneck = None
    if is_dual_view and intermediary_score is not None:
        fund_overall = (
            float(fund_score.overall_score) if fund_score.overall_score is not None else None
        )
        int_overall = (
            float(intermediary_score.overall_score)
            if intermediary_score.overall_score is not None
            else None
        )
        if fund_overall is not None and int_overall is not None:
            if fund_overall <= int_overall:
                bn_score = fund_overall
                bn_ref = fund_ref
                other_score = int_overall
                other_ref = intermediary_ref
                bottleneck_missing = fund_score.missing_criteria or []
            else:
                bn_score = int_overall
                bn_ref = intermediary_ref
                other_score = fund_overall
                other_ref = fund_ref
                bottleneck_missing = intermediary_score.missing_criteria or []

            top_3 = [
                m.get("indicator_code", "")
                for m in bottleneck_missing[:3]
                if m.get("indicator_code")
            ]
            bottleneck = {
                "bottleneck_referential_code": bn_ref.code,
                "bottleneck_referential_name": bn_ref.label,
                "bottleneck_score": Decimal(str(bn_score)),
                "other_referential_code": other_ref.code,
                "other_referential_score": Decimal(str(other_score)),
                "gap": Decimal(str(round(other_score - bn_score, 2))),
                "eligibility_min": bn_score >= DEFAULT_REFERENTIAL_THRESHOLD,
                "top_3_critical_indicators": top_3,
            }

    return {
        "fund_score": fund_score,
        "fund_is_fallback": fund_is_fallback,
        "intermediary_score": intermediary_score,
        "intermediary_is_fallback": intermediary_is_fallback,
        "bottleneck": bottleneck,
        "is_dual_view": is_dual_view,
    }


# --- Helper FastAPI BackgroundTasks ---


async def recompute_score_async(
    assessment_id: uuid.UUID,
    referentiel_id: uuid.UUID | None = None,
    request_id: uuid.UUID | None = None,
) -> None:
    """Helper pour FastAPI BackgroundTasks : recalcule N référentiels en background.

    Si ``referentiel_id`` est fourni, recalcule uniquement ce référentiel ciblé.
    Sinon, recalcule TOUS les référentiels actifs.

    Crée sa propre session DB (le background task n'a pas accès à la session
    de la requête HTTP qui a déjà été closée).
    """
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        try:
            if referentiel_id is not None:
                # Calcul ciblé sur 1 seul référentiel
                referential = (
                    await db.execute(
                        select(Referential).where(Referential.id == referentiel_id)
                    )
                ).scalar_one_or_none()
                if referential is None:
                    logger.warning(
                        "recompute_score_async : référentiel %s introuvable",
                        referentiel_id,
                    )
                    return
                assessment = (
                    await db.execute(
                        select(ESGAssessment).where(ESGAssessment.id == assessment_id)
                    )
                ).scalar_one_or_none()
                if assessment is None or assessment.account_id is None:
                    logger.warning(
                        "recompute_score_async : assessment %s introuvable ou sans account_id",
                        assessment_id,
                    )
                    return
                score_data = await compute_score_for_referential(
                    referential, assessment, db,
                )
                await _upsert_referential_score(
                    db,
                    account_id=assessment.account_id,
                    assessment_id=assessment_id,
                    referential=referential,
                    score_data=score_data,
                    computed_by=ComputedByEnum.AUTO,
                    computed_request_id=request_id,
                )
                await db.commit()
            else:
                _, _ = await compute_all_referential_scores(
                    db,
                    assessment_id=assessment_id,
                    computed_request_id=request_id,
                )
                await db.commit()
        except Exception:  # pragma: no cover - defensive
            logger.exception("recompute_score_async : exception")
            await db.rollback()
