"""Service de matching Project ↔ Offer (F14).

Calcule un score décomposé fund_score / intermediary_score / global_score,
identifie le goulot (bottleneck) et persiste un ``OfferMatch`` UPSERT in-place.

Réutilise :
- F13 ``compute_referential_score_for_offer`` pour la couche ESG.
- F07 ``Offer`` (champs effective_*).
- F06 ``Project``.

Pondération MVP figée (constante ``MATCHING_WEIGHTS``).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.esg import ESGAssessment, ESGStatusEnum
from app.models.match_alert_subscription import MatchAlertSubscription
from app.models.offer import Offer
from app.models.offer_match import OfferMatch
from app.models.project import Project
from app.modules.financing.matching_schemas import (
    BoostAppliedSchema,
    MatchFundsItem,
    MatchFundsResponse,
)

logger = logging.getLogger(__name__)


# Pondération MVP figée. Total = 1.0.
# sector=0.25, esg=0.30, size=0.15, location=0.10, documents=0.10, instrument=0.10
MATCHING_WEIGHTS: dict[str, float] = {
    "sector": 0.25,
    "esg": 0.30,
    "size": 0.15,
    "location": 0.10,
    "documents": 0.10,
    "instrument": 0.10,
}

# TTL des matches : 30 jours.
MATCH_TTL_DAYS: int = 30

# Cap dur : 50 offres par recompute (politique anti-DoS MVP).
RECOMPUTE_OFFER_CAP: int = 50

# Bottleneck : seuil (en points) pour basculer en 'fund' / 'intermediary'.
BOTTLENECK_GAP_THRESHOLD: int = 10


# --- Sub-scores déterministes ---


def _compute_sector_match(project: Project, fund: Any) -> int:
    """Binaire 100/0 selon ``project.objective_env`` ∈ ``fund.sectors_eligible``.

    On utilise ``objective_env`` comme proxy de secteur projet (8 valeurs
    F06). Si ``fund.sectors_eligible`` est vide, on retourne 100 (pas
    de contrainte → match accepté).
    """
    eligible = getattr(fund, "sectors_eligible", None) or []
    if not eligible:
        return 100
    project_objectives = list(project.objective_env or [])
    if not project_objectives:
        return 0
    if any(obj in eligible for obj in project_objectives):
        return 100
    return 0


def _compute_size_match(project: Project, fund: Any) -> tuple[int, bool]:
    """Score graduel ±50 % autour de la fourchette du fonds.

    Retourne (score, currency_mismatch).
    Si conversion devise impossible : (50, True).
    """
    target_amount = project.target_amount_amount
    if target_amount is None:
        return 50, False  # neutre

    # On utilise XOF comme pivot ; si le fond n'a pas de fourchette, neutre.
    # Pour simplifier MVP : si la devise du projet matche la devise du fonds
    # (via min_amount_currency / fallback XOF), comparaison directe ; sinon
    # neutre + flag mismatch.
    project_currency = project.target_amount_currency or "XOF"
    min_money = getattr(fund, "min_amount_money", None)
    max_money = getattr(fund, "max_amount_money", None)

    if min_money is None and max_money is None:
        return 50, False

    # Si l'une des bornes est dans une devise différente : conversion non
    # gérée en MVP F14, on retourne neutre + flag.
    if min_money is not None and min_money.currency != project_currency:
        return 50, True
    if max_money is not None and max_money.currency != project_currency:
        return 50, True

    target = Decimal(target_amount)
    min_amt = min_money.amount if min_money else Decimal(0)
    max_amt = max_money.amount if max_money else Decimal("1e18")

    if min_amt <= target <= max_amt:
        return 100, False

    # Graduel linéaire ±50 % de la fourchette.
    if target < min_amt and min_amt > 0:
        ratio = float(target / min_amt)
        # ratio = 1.0 → 100, ratio = 0.5 → 0
        score = max(0, min(100, int(round((ratio - 0.5) * 200))))
        return score, False
    if target > max_amt and max_amt > 0:
        ratio = float(max_amt / target)
        score = max(0, min(100, int(round((ratio - 0.5) * 200))))
        return score, False

    return 0, False


def _compute_location_match(project: Project, fund: Any) -> int:
    """Binaire 100/0 selon ``project.location_country`` éligibilité fonds.

    En MVP F14, on s'appuie sur ``fund.eligibility_criteria.eligible_countries``
    si présent, sinon sur la présence du fonds (toujours éligible).
    """
    project_country = (project.location_country or "").upper()
    if not project_country:
        return 50  # neutre si pas de pays projet

    eligibility = getattr(fund, "eligibility_criteria", None) or {}
    eligible_countries = eligibility.get("eligible_countries") or []
    if not eligible_countries:
        return 100  # pas de contrainte
    eligible_upper = [c.upper() for c in eligible_countries]
    return 100 if project_country in eligible_upper else 0


def _compute_documents_match(project: Project, offer: Offer) -> int:
    """Ratio ``len(project_documents) / len(effective_required_documents)``.

    Borné à 100. Si la liste required est vide, 100.
    """
    required = offer.effective_required_documents or []
    if not required:
        return 100
    project_docs = getattr(project, "project_documents", []) or []
    if not project_docs:
        return 0
    ratio = len(project_docs) / max(1, len(required))
    return max(0, min(100, int(round(ratio * 100))))


def _compute_instrument_match(project: Project, fund: Any) -> int:
    """Binaire 100/0 selon ``project.financing_structure`` ∈ ``fund.instruments``.

    Si pas de structure projet → 50 (neutre). Si pas d'instruments fonds → 100.
    """
    if not project.financing_structure:
        return 50
    instruments = getattr(fund, "instruments", None) or []
    if not instruments:
        return 100
    return 100 if project.financing_structure in instruments else 0


def _compute_bottleneck(fund_score: int, intermediary_score: int) -> str:
    """Règle déterministe ``fund``/``intermediary``/``balanced``.

    - ``fund`` si fund_score < intermediary_score - 10
    - ``intermediary`` si intermediary_score < fund_score - 10
    - ``balanced`` sinon (écart ≤ 10)
    """
    diff = fund_score - intermediary_score
    if diff < -BOTTLENECK_GAP_THRESHOLD:
        return "fund"
    if diff > BOTTLENECK_GAP_THRESHOLD:
        return "intermediary"
    return "balanced"


def _build_recommended_actions(
    missing_criteria: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Top 3 actions FR à partir des critères manquants."""
    actions: list[dict[str, Any]] = []
    for crit in (missing_criteria or [])[:3]:
        label = crit.get("label") or crit.get("indicator_code") or "Critère manquant"
        ref = crit.get("referential_code") or crit.get("referential_id") or ""
        suffix = f" (référentiel {ref})" if ref else ""
        actions.append(
            {
                "label": f"Renseignez le critère « {label} »{suffix}.",
                "indicator_id": crit.get("indicator_id"),
                "referential_id": crit.get("referential_id"),
                "source_id": crit.get("source_id"),
            }
        )
    return actions


# --- ESG layer (F13 delegation) ---


async def _get_latest_esg_assessment(
    db: AsyncSession, account_id: uuid.UUID,
) -> ESGAssessment | None:
    """Dernier ESGAssessment finalisé du compte, ou None."""
    result = await db.execute(
        select(ESGAssessment)
        .where(
            ESGAssessment.account_id == account_id,
            ESGAssessment.status == ESGStatusEnum.completed,
        )
        .order_by(desc(ESGAssessment.updated_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


# --- compute_offer_match ---


async def compute_offer_match(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    offer_id: uuid.UUID,
) -> OfferMatch:
    """Calcule (ou recalcule) un OfferMatch pour ``(project_id, offer_id)``.

    UPSERT in-place via UNIQUE ``(project_id, offer_id)``.
    """
    project = (
        await db.execute(select(Project).where(Project.id == project_id))
    ).scalar_one_or_none()
    if project is None:
        raise ValueError(f"Project introuvable : {project_id}")

    offer = (
        await db.execute(select(Offer).where(Offer.id == offer_id))
    ).scalar_one_or_none()
    if offer is None:
        raise ValueError(f"Offer introuvable : {offer_id}")

    fund = offer.fund
    if fund is None:
        raise ValueError(f"Offer {offer_id} sans fund chargé")

    # Sub-scores non-ESG.
    sector_match = _compute_sector_match(project, fund)
    size_match, currency_mismatch = _compute_size_match(project, fund)
    location_match = _compute_location_match(project, fund)
    documents_match = _compute_documents_match(project, offer)
    instrument_match = _compute_instrument_match(project, fund)

    # Couche ESG via F13 (best-effort).
    assessment = await _get_latest_esg_assessment(db, project.account_id)
    assessment_missing = assessment is None
    esg_fund_score = 50
    esg_intermediary_score = 50
    fund_missing: list[dict[str, Any]] = []
    intermediary_missing: list[dict[str, Any]] = []

    if not assessment_missing:
        try:
            from app.modules.esg.multi_referential_service import (
                compute_referential_score_for_offer,
            )

            f13_result = await compute_referential_score_for_offer(
                db, assessment_id=assessment.id, offer_id=offer_id,
            )
            fund_score_obj = f13_result.get("fund_score")
            intermediary_score_obj = f13_result.get("intermediary_score")

            if fund_score_obj is not None and fund_score_obj.overall_score is not None:
                esg_fund_score = int(round(float(fund_score_obj.overall_score)))
                fund_missing = list(fund_score_obj.missing_criteria or [])
            if (
                intermediary_score_obj is not None
                and intermediary_score_obj.overall_score is not None
            ):
                esg_intermediary_score = int(
                    round(float(intermediary_score_obj.overall_score))
                )
                intermediary_missing = list(
                    intermediary_score_obj.missing_criteria or []
                )
            else:
                # Si pas de dual view : intermediary = fund (Mefali fallback).
                esg_intermediary_score = esg_fund_score
                intermediary_missing = list(fund_missing)
        except Exception:  # noqa: BLE001 — best-effort
            logger.exception(
                "compute_referential_score_for_offer failed (offer=%s)",
                offer_id,
            )

    # Pondération
    w = MATCHING_WEIGHTS
    base = (
        w["sector"] * sector_match
        + w["size"] * size_match
        + w["location"] * location_match
        + w["documents"] * documents_match
        + w["instrument"] * instrument_match
    )
    fund_score = int(round(base + w["esg"] * esg_fund_score))
    intermediary_score = int(round(base + w["esg"] * esg_intermediary_score))
    fund_score = max(0, min(100, fund_score))
    intermediary_score = max(0, min(100, intermediary_score))
    global_score = min(fund_score, intermediary_score)

    bottleneck = _compute_bottleneck(fund_score, intermediary_score)

    # Pour les actions recommandées, on prend le côté goulot.
    if bottleneck == "fund":
        critical_missing = fund_missing
    elif bottleneck == "intermediary":
        critical_missing = intermediary_missing
    else:
        critical_missing = fund_missing or intermediary_missing
    recommended_actions = _build_recommended_actions(critical_missing)

    score_breakdown: dict[str, Any] = {
        "fund": {
            "sector_match": sector_match,
            "esg_match": esg_fund_score,
            "size_match": size_match,
            "location_match": location_match,
            "documents_match": documents_match,
            "instrument_match": instrument_match,
            "missing_criteria": fund_missing,
        },
        "intermediary": {
            "sector_match": sector_match,
            "esg_match": esg_intermediary_score,
            "size_match": size_match,
            "location_match": location_match,
            "documents_match": documents_match,
            "instrument_match": instrument_match,
            "missing_criteria": intermediary_missing,
        },
        "assessment_missing": assessment_missing,
        "size_match_currency_mismatch": currency_mismatch,
    }

    # UPSERT in-place
    existing_q = await db.execute(
        select(OfferMatch).where(
            OfferMatch.project_id == project_id,
            OfferMatch.offer_id == offer_id,
        )
    )
    existing = existing_q.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=MATCH_TTL_DAYS)

    # F045 : populate aussi les 4 nouvelles colonnes (project_score, company_score,
    # project_score_breakdown, divergence_explanation) pour que les recompute F14
    # existants ne laissent pas ces colonnes a leur DEFAULT 0 / {} / NULL.
    company_score_int, _ = _compute_company_score(
        project, offer, fund, esg_fund_score=esg_fund_score,
    )
    project_score_int, project_breakdown_dict = _compute_project_score(
        project, fund,
    )

    if existing is None:
        match = OfferMatch(
            account_id=project.account_id,
            project_id=project_id,
            offer_id=offer_id,
            global_score=global_score,
            fund_score=fund_score,
            intermediary_score=intermediary_score,
            project_score=project_score_int,
            company_score=company_score_int,
            project_score_breakdown=project_breakdown_dict,
            divergence_explanation=None,
            score_breakdown=score_breakdown,
            bottleneck=bottleneck,
            recommended_actions=recommended_actions,
            status="suggested",
            computed_at=now,
            expires_at=expires_at,
            last_notified_at=None,
        )
        db.add(match)
    else:
        existing.global_score = global_score
        existing.fund_score = fund_score
        existing.intermediary_score = intermediary_score
        existing.project_score = project_score_int
        existing.company_score = company_score_int
        existing.project_score_breakdown = project_breakdown_dict
        existing.score_breakdown = score_breakdown
        existing.bottleneck = bottleneck
        existing.recommended_actions = recommended_actions
        existing.computed_at = now
        existing.expires_at = expires_at
        match = existing

    await db.flush()
    return match


# --- list / get / compare ---


async def list_matches_for_project(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    project_id: uuid.UUID,
    min_score: int = 0,
    bottleneck: str | None = None,
    fund_id: uuid.UUID | None = None,
    page: int = 1,
    limit: int = 25,
) -> tuple[list[OfferMatch], int]:
    """Liste paginée des matches actifs (expires_at > now()) d'un projet."""
    now = datetime.now(timezone.utc)
    base = select(OfferMatch).where(
        OfferMatch.account_id == account_id,
        OfferMatch.project_id == project_id,
        OfferMatch.expires_at > now,
        OfferMatch.global_score >= min_score,
    )
    if bottleneck is not None:
        base = base.where(OfferMatch.bottleneck == bottleneck)
    if fund_id is not None:
        base = base.join(Offer, Offer.id == OfferMatch.offer_id).where(
            Offer.fund_id == fund_id,
        )

    # Total
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Page
    # F045 : tri bascule vers project_score DESC, company_score DESC (R12).
    offset = (page - 1) * limit
    items_q = (
        base.order_by(
            desc(OfferMatch.project_score),
            desc(OfferMatch.company_score),
            desc(OfferMatch.computed_at),
        )
        .offset(offset)
        .limit(limit)
    )
    items = (await db.execute(items_q)).scalars().all()
    return list(items), int(total or 0)


async def get_match_details(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    project_id: uuid.UUID,
    offer_id: uuid.UUID,
) -> OfferMatch | None:
    """Retourne le match pour la paire (project_id, offer_id) du compte."""
    result = await db.execute(
        select(OfferMatch).where(
            OfferMatch.account_id == account_id,
            OfferMatch.project_id == project_id,
            OfferMatch.offer_id == offer_id,
        )
    )
    return result.scalar_one_or_none()


async def recompute_matches_for_project(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    cap: int = RECOMPUTE_OFFER_CAP,
) -> tuple[uuid.UUID, int]:
    """Déclenche un recompute pour toutes les offres publiées (capé).

    Retourne (recompute_request_id, total_offers_to_compute).
    NB : l'exécution effective est faite par le caller via BackgroundTasks
    pour ne pas bloquer la requête HTTP. Cette fonction PEUT être appelée
    en synchrone pour les tests / tools en autonomie.
    """
    project = (
        await db.execute(select(Project).where(Project.id == project_id))
    ).scalar_one_or_none()
    if project is None:
        raise ValueError(f"Project introuvable : {project_id}")

    # Charger les offres publiées + actives.
    offers_q = await db.execute(
        select(Offer.id)
        .where(
            Offer.publication_status == "published",
            Offer.is_active == True,  # noqa: E712 — SQLAlchemy bool compare
        )
        .order_by(Offer.id)
        .limit(cap)
    )
    offer_ids = [row[0] for row in offers_q.all()]
    request_id = uuid.uuid4()

    total = len(offer_ids)
    if total == cap:
        logger.warning(
            "recompute_matches_for_project: cap atteint (%d offres) pour project=%s",
            cap, project_id,
        )

    # Le caller exécute le recompute lui-même pour pouvoir wrapper dans
    # BackgroundTasks ; on retourne juste l'inventaire.
    return request_id, total


async def execute_recompute_batch(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    cap: int = RECOMPUTE_OFFER_CAP,
) -> int:
    """Exécute effectivement un batch de recompute. Retourne le nombre traité."""
    offers_q = await db.execute(
        select(Offer.id)
        .where(
            Offer.publication_status == "published",
            Offer.is_active == True,  # noqa: E712
        )
        .order_by(Offer.id)
        .limit(cap)
    )
    offer_ids = [row[0] for row in offers_q.all()]
    processed = 0
    for offer_id in offer_ids:
        try:
            await compute_offer_match(
                db, project_id=project_id, offer_id=offer_id,
            )
            processed += 1
        except Exception:  # noqa: BLE001
            logger.exception(
                "compute_offer_match failed (project=%s, offer=%s)",
                project_id, offer_id,
            )
    await db.commit()
    return processed


async def compare_offers_for_fund(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    fund_id: uuid.UUID,
) -> dict[str, Any]:
    """Génère un ComparisonResult réutilisable F11 pour un fonds donné."""
    # Charger les offres publiées du fonds.
    offers_q = await db.execute(
        select(Offer).where(
            Offer.fund_id == fund_id,
            Offer.publication_status == "published",
            Offer.is_active == True,  # noqa: E712
        )
    )
    offers = list(offers_q.scalars().all())
    if not offers:
        return {
            "fund_id": fund_id,
            "project_id": project_id,
            "subjects": [],
            "rows": [],
        }

    # S'assurer que les matches sont calculés
    matches: list[OfferMatch] = []
    for offer in offers:
        match = await compute_offer_match(
            db, project_id=project_id, offer_id=offer.id,
        )
        matches.append(match)

    subjects = []
    for match, offer in zip(matches, offers):
        intermediary = offer.intermediary
        subjects.append({
            "id": str(offer.id),
            "label": (
                f"{intermediary.name} ({intermediary.country})"
                if intermediary else "Direct"
            ),
            "metadata": {
                "offer_id": str(offer.id),
                "intermediary_code": intermediary.code if intermediary else None,
            },
        })

    def _row(key: str, label: str, type_: str, values: list[Any]) -> dict[str, Any]:
        # winner = max
        winner_idx = -1
        if values:
            try:
                numeric = [
                    float(v) if isinstance(v, (int, float, Decimal)) else None
                    for v in values
                ]
                non_none = [v for v in numeric if v is not None]
                if non_none:
                    max_v = max(non_none)
                    for i, v in enumerate(numeric):
                        if v == max_v:
                            winner_idx = i
                            break
            except Exception:  # noqa: BLE001
                pass
        return {
            "key": key,
            "label": label,
            "type": type_,
            "values": [
                {
                    "subject_id": str(offers[i].id),
                    "raw": v,
                    "display": str(v) if v is not None else "—",
                    "source_id": None,
                    "is_winner": (i == winner_idx),
                }
                for i, v in enumerate(values)
            ],
        }

    rows = [
        _row(
            "global_score", "Score global", "rating",
            [m.global_score for m in matches],
        ),
        _row(
            "fund_score", "Score fonds", "rating",
            [m.fund_score for m in matches],
        ),
        _row(
            "intermediary_score", "Score intermédiaire", "rating",
            [m.intermediary_score for m in matches],
        ),
        _row(
            "documents_count", "Documents requis", "rating",
            [
                len(o.effective_required_documents or []) for o in offers
            ],
        ),
        _row(
            "processing_time_min", "Délai min (jours)", "duration",
            [
                o.effective_processing_time_days_min or 0 for o in offers
            ],
        ),
    ]

    return {
        "fund_id": fund_id,
        "project_id": project_id,
        "subjects": subjects,
        "rows": rows,
    }


# --- Subscriptions ---


async def subscribe_to_alerts(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    project_id: uuid.UUID,
    min_global_score: int = 60,
) -> MatchAlertSubscription:
    """Souscrit aux alertes (idempotent) pour un projet."""
    existing = (
        await db.execute(
            select(MatchAlertSubscription).where(
                MatchAlertSubscription.project_id == project_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        # Réactivation idempotente
        if not existing.is_active:
            existing.is_active = True
        return existing

    sub = MatchAlertSubscription(
        account_id=account_id,
        project_id=project_id,
        min_global_score=min_global_score,
        is_active=True,
    )
    db.add(sub)
    await db.flush()
    return sub


async def update_subscription(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    project_id: uuid.UUID,
    min_global_score: int | None = None,
    is_active: bool | None = None,
) -> MatchAlertSubscription | None:
    """Mise à jour partielle (PATCH) d'une souscription."""
    result = await db.execute(
        select(MatchAlertSubscription).where(
            MatchAlertSubscription.project_id == project_id,
            MatchAlertSubscription.account_id == account_id,
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        # Créer si absente (UPSERT comportemental)
        sub = await subscribe_to_alerts(
            db, account_id=account_id, project_id=project_id,
            min_global_score=min_global_score or 60,
        )
        if is_active is not None:
            sub.is_active = is_active
        return sub
    if min_global_score is not None:
        sub.min_global_score = min_global_score
    if is_active is not None:
        sub.is_active = is_active
    await db.flush()
    return sub


async def get_subscription(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    project_id: uuid.UUID,
) -> MatchAlertSubscription | None:
    """Retourne la souscription du projet (ou None)."""
    result = await db.execute(
        select(MatchAlertSubscription).where(
            MatchAlertSubscription.project_id == project_id,
            MatchAlertSubscription.account_id == account_id,
        )
    )
    return result.scalar_one_or_none()


# =====================================================================
# F045 - Matching projet-centric : 8 sub-scores + orchestrateur + boost
# Reference : specs/045-matching-projet-centric/research.md R5 + R13
# =====================================================================


# Pondération MVP figée. Total = 1.0. (research.md R5)
PROJECT_SCORE_WEIGHTS: dict[str, float] = {
    "sector": 0.15,
    "taxonomy": 0.20,
    "gcf_themes": 0.20,
    "co2_impact": 0.15,
    "beneficiaries": 0.10,
    "gender": 0.05,
    "vulnerable": 0.05,
    "project_esg": 0.10,
}

# Noms des 3 fonds prioritaires impact (R13 - case-insensitive match)
PRIORITY_IMPACT_FUND_NAMES: frozenset[str] = frozenset({
    "green climate fund",
    "fonds pour l'environnement mondial",
    "fonds d'adaptation",
})

# Seuil tCO2e pour le critere co2_impact "below_threshold" GCF (R13)
CO2_IMPACT_THRESHOLD_GCF: int = 1000


# --- 8 sub-scores projet ---


def _compute_project_score_sector(project: Any, fund: Any) -> int:
    """100 si project.objective_env intersecte fund.sectors_eligible.

    Si fund.sectors_eligible est vide -> 100 (pas de contrainte).
    Si project.objective_env est vide -> 0 (donnee manquante).
    """
    eligible = getattr(fund, "sectors_eligible", None) or []
    if not eligible:
        return 100
    project_objectives = list(getattr(project, "objective_env", None) or [])
    if not project_objectives:
        return 0
    return 100 if any(o in eligible for o in project_objectives) else 0


def _compute_project_score_taxonomy(project: Any, fund: Any) -> int:
    """100 si taxonomie_verte_uemoa_aligned=True, 0 sinon (incl. NULL)."""
    return 100 if getattr(project, "taxonomie_verte_uemoa_aligned", None) is True else 0


def _compute_project_score_gcf_themes(project: Any, fund: Any) -> int:
    """Jaccard project.gcf_priority_themes ∩ fund.theme × 100."""
    project_themes = set(getattr(project, "gcf_priority_themes", None) or [])
    fund_themes = set(getattr(fund, "theme", None) or [])
    if not project_themes or not fund_themes:
        return 0
    intersection = project_themes & fund_themes
    union = project_themes | fund_themes
    return int(round(100 * len(intersection) / len(union)))


def _compute_project_score_co2_impact(project: Any, fund: Any) -> int:
    """Graduel selon expected_impact_tco2e vs fund.min_co2_threshold.

    - Pas de tCO2e renseigne -> 0.
    - Pas de seuil sur le fonds -> 100 si renseigne.
    - tCO2e >= seuil -> 100. Sinon ratio borne 0..100.
    """
    impact = getattr(project, "expected_impact_tco2e", None)
    if impact is None or impact <= 0:
        return 0
    threshold = getattr(fund, "min_co2_threshold", None)
    if threshold is None or threshold <= 0:
        return 100
    try:
        from decimal import Decimal as _D
        ratio = float(_D(str(impact)) / _D(str(threshold)))
        return max(0, min(100, int(round(ratio * 100))))
    except Exception:  # noqa: BLE001
        return 100


def _compute_project_score_beneficiaries(project: Any, fund: Any) -> int:
    """Ratio expected_beneficiaries / fund.target_beneficiaries, borne 0..100.

    Si target_beneficiaries non defini sur le fonds : 100 si renseigne, 50 sinon.
    """
    beneficiaries = getattr(project, "expected_beneficiaries", None)
    if beneficiaries is None or beneficiaries <= 0:
        return 0
    target = getattr(fund, "target_beneficiaries", None)
    if target is None or target <= 0:
        return 100
    return max(0, min(100, int(round(100 * beneficiaries / target))))


def _compute_project_score_gender(project: Any, fund: Any) -> int:
    """100 si gender_inclusion=True, 0 si False, 50 si NULL (neutre).

    Source GCF Gender Policy 2019 mobilisee dans sources_used si > 0.
    """
    gender = getattr(project, "gender_inclusion", None)
    if gender is True:
        return 100
    if gender is False:
        return 0
    return 50


def _compute_project_score_vulnerable(project: Any, fund: Any) -> int:
    """Jaccard project.vulnerable_populations ∩ fund.vulnerable_target × 100.

    Si project ou fund vide -> 0.
    Source ODD 10 mobilisee dans sources_used si > 0.
    """
    project_pops = set(getattr(project, "vulnerable_populations", None) or [])
    fund_target = set(getattr(fund, "vulnerable_target", None) or [])
    if not project_pops:
        return 0
    if not fund_target:
        # Le projet cible des vulnerables mais le fonds ne contraint pas -> 100
        return 100
    intersection = project_pops & fund_target
    union = project_pops | fund_target
    return int(round(100 * len(intersection) / len(union)))


def _compute_project_score_project_esg(project: Any, fund: Any) -> int:
    """project.project_esg_score si renseigne, 50 (neutre) sinon.

    Legacy : utilisé uniquement quand le helper async F047
    :func:`_get_project_esg_subscore` n'est pas disponible (chemins F14 hors
    flow projet-centric). Le matching projet-centric V045 consomme désormais
    le helper async qui consulte `project_esg_assessments` finalisées.
    """
    score = getattr(project, "project_esg_score", None)
    if score is None:
        return 50
    return max(0, min(100, int(score)))


# ---------------------------------------------------------------------
# F047 — Resolver project_esg sub-score depuis project_esg_assessments.
# ---------------------------------------------------------------------


# Mapping fund_name → code référentiel cible (F047 D2/Q4).
_FUND_NAME_TO_REFERENTIAL: tuple[tuple[tuple[str, ...], str], ...] = (
    (("green climate fund", "gcf"), "gcf_ess"),
    (("boad", "banque ouest africaine"), "boad_ess"),
)
# Référentiel universel par défaut (Q4 clarification).
_PROJECT_ESG_FALLBACK_REF_CODE: str = "ifc_ps"


def _detect_target_referential_code(fund: Any) -> tuple[str, bool]:
    """Retourne (ref_code, is_fallback) selon le nom/organisation du fonds.

    Détection case-insensitive. Si aucune ESS dédiée n'est détectée, on
    retombe sur ``ifc_ps`` avec ``is_fallback=True`` (Q4 clarification).
    """
    haystack = " ".join(
        str(getattr(fund, attr, "") or "")
        for attr in ("name", "organization")
    ).lower()
    for needles, code in _FUND_NAME_TO_REFERENTIAL:
        if any(n in haystack for n in needles):
            return code, False
    return _PROJECT_ESG_FALLBACK_REF_CODE, True


async def _load_referential_for_code(
    db: AsyncSession, code: str,
) -> dict[str, Any] | None:
    """Petit lookup sans charger la relation entière — utile pour breakdown."""
    from app.models.referential import Referential
    ref = (
        await db.execute(select(Referential).where(Referential.code == code))
    ).scalar_one_or_none()
    if ref is None:
        return None
    return {
        "id": str(ref.id),
        "code": ref.code,
        "label": ref.label,
        "version": str(getattr(ref, "version", "1.0") or "1.0"),
    }


def _cta_hint_for_referential(ref_meta: dict[str, Any] | None) -> str:
    """Phrase FR courte invitant la PME à démarrer l'évaluation manquante."""
    if ref_meta is None:
        return "Démarrer une évaluation ESG-projet pour augmenter votre score."
    label = ref_meta.get("label") or ref_meta.get("code") or "ESG-projet"
    return (
        f"Démarrer l'évaluation {label} sur ce projet pour améliorer "
        "l'éligibilité auprès de ce fonds."
    )


async def _get_project_esg_subscore(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    project_id: uuid.UUID,
    fund: Any,
) -> tuple[int, dict[str, Any]]:
    """F047 (US2) — Résout le sub-score `project_esg` pour un (projet, fonds).

    Priorité :
      1. Évaluation ``finalized`` active contre le référentiel ciblé du fonds.
      2. Évaluation ``finalized`` IFC PS si fonds sans ESS dédié (Q4 fallback).
      3. ``projects.project_esg_score`` saisi manuellement (legacy F045).
      4. ``score=0, unsourced=True`` + CTA hint.

    Returns:
        Tuple ``(score 0..100, meta_dict)`` où ``meta_dict`` contient :
        ``is_fallback``, ``referential_used`` ({id, code, label, version}),
        ``assessment_id``, ``source_kind`` (``calculated`` /
        ``manual_f045`` / ``unsourced``), ``unsourced``, ``cta_hint``.
    """
    from app.modules.esg.project_models import ProjectEsgAssessment

    target_code, is_fallback = _detect_target_referential_code(fund)
    target_ref = await _load_referential_for_code(db, target_code)

    # 1. Lookup évaluation finalisée active contre le ref cible.
    if target_ref is not None:
        a = (
            await db.execute(
                select(ProjectEsgAssessment).where(
                    ProjectEsgAssessment.account_id == account_id,
                    ProjectEsgAssessment.project_id == project_id,
                    ProjectEsgAssessment.referential_id
                    == uuid.UUID(target_ref["id"]),
                    ProjectEsgAssessment.state == "finalized",
                    ProjectEsgAssessment.superseded_at.is_(None),
                )
                .order_by(desc(ProjectEsgAssessment.finalized_at))
                .limit(1)
            )
        ).scalar_one_or_none()
        if a is not None and a.score is not None:
            return int(a.score), {
                "is_fallback": is_fallback,
                "referential_used": target_ref,
                "assessment_id": str(a.id),
                "source_kind": "calculated",
                "unsourced": False,
                "cta_hint": None,
            }

    # 2. Fallback IFC PS si le ref cible n'est pas déjà IFC PS et qu'il y en a une.
    if target_code != _PROJECT_ESG_FALLBACK_REF_CODE:
        ifc_ref = await _load_referential_for_code(
            db, _PROJECT_ESG_FALLBACK_REF_CODE,
        )
        if ifc_ref is not None:
            a = (
                await db.execute(
                    select(ProjectEsgAssessment).where(
                        ProjectEsgAssessment.account_id == account_id,
                        ProjectEsgAssessment.project_id == project_id,
                        ProjectEsgAssessment.referential_id
                        == uuid.UUID(ifc_ref["id"]),
                        ProjectEsgAssessment.state == "finalized",
                        ProjectEsgAssessment.superseded_at.is_(None),
                    )
                    .order_by(desc(ProjectEsgAssessment.finalized_at))
                    .limit(1)
                )
            ).scalar_one_or_none()
            if a is not None and a.score is not None:
                return int(a.score), {
                    "is_fallback": True,
                    "referential_used": ifc_ref,
                    "assessment_id": str(a.id),
                    "source_kind": "calculated",
                    "unsourced": False,
                    "cta_hint": None,
                }

    # 3. Fallback ``projects.project_esg_score`` (legacy F045).
    project = (
        await db.execute(
            select(Project).where(
                Project.id == project_id, Project.account_id == account_id,
            )
        )
    ).scalar_one_or_none()
    legacy_score = getattr(project, "project_esg_score", None) if project else None
    if legacy_score is not None:
        return max(0, min(100, int(legacy_score))), {
            "is_fallback": is_fallback,
            "referential_used": target_ref,
            "assessment_id": None,
            "source_kind": "manual_f045",
            "unsourced": False,
            "cta_hint": None,
        }

    # 4. Aucune source → 0 + unsourced + CTA hint.
    return 0, {
        "is_fallback": is_fallback,
        "referential_used": target_ref,
        "assessment_id": None,
        "source_kind": "unsourced",
        "unsourced": True,
        "cta_hint": _cta_hint_for_referential(target_ref),
    }


# --- Orchestrateur project_score ---


def _compute_project_score(
    project: Any,
    fund: Any,
    *,
    project_esg_subscore_value: int | None = None,
    project_esg_subscore_meta: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Calcule project_score 0..100 et retourne (score, breakdown_dict).

    Le breakdown contient :
    - sub_scores : dict 8 cles
    - sources_used : list (vide en MVP, alimente par F01 post-impl)
    - missing_criteria : top 5 critères negatifs (kind/key/label_fr)
    - boost_applied : place-holder (rule_triggered=False initial)
    - weights_version, computed_at, factor_status
    - project_esg_subscore : F047 meta {is_fallback, referential_used,
      assessment_id, source_kind, unsourced, cta_hint}

    Args:
        project_esg_subscore_value: si fourni (F047), remplace l'heuristique
            legacy `project.project_esg_score` par le score résolu depuis
            `project_esg_assessments` (voir `_get_project_esg_subscore`).
        project_esg_subscore_meta: meta F047 associée (référentiel utilisé,
            is_fallback, source_kind, etc.) injectée telle quelle dans le
            breakdown sous la clé `project_esg_subscore`.
    """
    if project_esg_subscore_value is not None:
        project_esg = max(0, min(100, int(project_esg_subscore_value)))
    else:
        project_esg = _compute_project_score_project_esg(project, fund)

    sub_scores = {
        "sector": _compute_project_score_sector(project, fund),
        "taxonomy": _compute_project_score_taxonomy(project, fund),
        "gcf_themes": _compute_project_score_gcf_themes(project, fund),
        "co2_impact": _compute_project_score_co2_impact(project, fund),
        "beneficiaries": _compute_project_score_beneficiaries(project, fund),
        "gender": _compute_project_score_gender(project, fund),
        "vulnerable": _compute_project_score_vulnerable(project, fund),
        "project_esg": project_esg,
    }
    weighted = sum(sub_scores[k] * PROJECT_SCORE_WEIGHTS[k] for k in sub_scores)
    score = max(0, min(100, int(round(weighted))))

    # Top 5 missing_criteria : sub_scores triés par score ASC, dérivés en
    # critères negatifs concrets.
    missing: list[dict[str, Any]] = []
    sorted_subs = sorted(sub_scores.items(), key=lambda kv: kv[1])
    for key, value in sorted_subs[:5]:
        if value >= 80:
            break
        missing.append(_build_missing_for_sub_score(key, value, project, fund))

    breakdown: dict[str, Any] = {
        "weights_version": "1.0",
        "sub_scores": sub_scores,
        "sources_used": [],
        "missing_criteria": missing,
        "boost_applied": {"rule_triggered": False, "rule_name": None},
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "factor_status": "ok",
    }
    if project_esg_subscore_meta is not None:
        # F047 — meta exposée à l'UI pour transparence (badge is_fallback,
        # CTA si unsourced, lien fiche évaluation, etc.)
        breakdown["project_esg_subscore"] = {
            "score": project_esg,
            "weight": PROJECT_SCORE_WEIGHTS["project_esg"],
            **project_esg_subscore_meta,
        }
    return score, breakdown


def _build_missing_for_sub_score(
    key: str, value: int, project: Any, fund: Any,
) -> dict[str, Any]:
    """Construit un MissingCriterionSchema dict pour un sub_score deficient."""
    if key == "taxonomy":
        return {
            "key": "taxonomy_not_aligned",
            "label_fr": "Alignement à la taxonomie verte UEMOA non démontré.",
            "source_id": None,
            "kind": "missing" if value == 0 else "wrong_value",
        }
    if key == "gcf_themes":
        return {
            "key": "gcf_themes_empty",
            "label_fr": "Aucun thème prioritaire GCF déclaré pour le projet.",
            "source_id": None,
            "kind": "missing" if value == 0 else "wrong_value",
        }
    if key == "co2_impact":
        return {
            "key": "co2_impact_below_threshold",
            "label_fr": (
                f"Impact CO2 estimé en dessous du seuil GCF ({CO2_IMPACT_THRESHOLD_GCF} tCO2e/an)."
            ),
            "source_id": None,
            "kind": "below_threshold",
            "current_value": float(getattr(project, "expected_impact_tco2e", None) or 0),
            "target_value": CO2_IMPACT_THRESHOLD_GCF,
        }
    if key == "beneficiaries":
        return {
            "key": "beneficiaries_missing",
            "label_fr": "Nombre de bénéficiaires non renseigné ou trop faible.",
            "source_id": None,
            "kind": "missing",
        }
    if key == "gender":
        return {
            "key": "gender_inclusion_missing",
            "label_fr": "Volet genre (GCF Gender Policy 2019) non évalué.",
            "source_id": None,
            "kind": "missing",
        }
    if key == "vulnerable":
        return {
            "key": "vulnerable_populations_empty",
            "label_fr": "Aucune population vulnérable ciblée (ODD 10).",
            "source_id": None,
            "kind": "missing",
        }
    if key == "sector":
        return {
            "key": "sector_not_eligible",
            "label_fr": "Secteur projet hors champ d'éligibilité du fonds.",
            "source_id": None,
            "kind": "wrong_value",
        }
    # project_esg
    return {
        "key": "project_esg_score_missing",
        "label_fr": "Score ESG propre au projet non renseigné.",
        "source_id": None,
        "kind": "missing",
    }


# --- Refactor company_score (heritage F14 isole) ---


def _compute_company_score(
    project: Any,
    offer: Any,
    fund: Any,
    *,
    esg_fund_score: int = 50,
) -> tuple[int, dict[str, Any]]:
    """Score entreprise heritage F14 (sector=0.25, esg=0.30, size=0.15,
    location=0.10, documents=0.10, instrument=0.10).

    Retourne (score 0..100, breakdown dict des sub_scores).
    """
    sector = _compute_sector_match(project, fund)
    size, currency_mismatch = _compute_size_match(project, fund)
    location = _compute_location_match(project, fund)
    documents = _compute_documents_match(project, offer)
    instrument = _compute_instrument_match(project, fund)

    w = MATCHING_WEIGHTS
    score = (
        w["sector"] * sector
        + w["esg"] * esg_fund_score
        + w["size"] * size
        + w["location"] * location
        + w["documents"] * documents
        + w["instrument"] * instrument
    )
    score = max(0, min(100, int(round(score))))
    breakdown = {
        "sector_match": sector,
        "esg_match": esg_fund_score,
        "size_match": size,
        "location_match": location,
        "documents_match": documents,
        "instrument_match": instrument,
        "size_match_currency_mismatch": currency_mismatch,
    }
    return score, breakdown


# --- Boost rule R13 ---


def _project_is_green_strong(project: Any) -> bool:
    """R13 : au moins 2 criteres parmi (taxonomie OK, themes GCF ≥ 1, CO2 ≥ 1000)."""
    criteria_met = 0
    if getattr(project, "taxonomie_verte_uemoa_aligned", None) is True:
        criteria_met += 1
    if len(getattr(project, "gcf_priority_themes", None) or []) >= 1:
        criteria_met += 1
    impact = getattr(project, "expected_impact_tco2e", None)
    if impact is not None and float(impact) >= CO2_IMPACT_THRESHOLD_GCF:
        criteria_met += 1
    return criteria_met >= 2


def _apply_boost_rule_rouge_entreprise_vert_projet(
    matches: list[Any], project: Any,
) -> tuple[list[Any], BoostAppliedSchema]:
    """Promeut les 3 fonds prioritaires impact en tete si conditions remplies.

    Conditions (R13) :
    - Au moins 1 match avec fund_name in PRIORITY_IMPACT_FUND_NAMES
      ET project_score >= 60 ET project_score - company_score > 30
    - ET le projet est "green_strong" (>=2 criteres impact)

    Args:
        matches: liste d'objets/SimpleNamespace avec .fund_name, .project_score,
            .company_score
        project: objet projet

    Returns:
        (nouvelle_liste_triee, BoostAppliedSchema)
    """
    if not matches:
        return list(matches), BoostAppliedSchema(rule_triggered=False)

    if not _project_is_green_strong(project):
        return list(matches), BoostAppliedSchema(rule_triggered=False)

    priority_matches: list[Any] = []
    others: list[Any] = []
    triggered = False

    for m in matches:
        name = (getattr(m, "fund_name", "") or "").strip().lower()
        is_priority = name in PRIORITY_IMPACT_FUND_NAMES
        proj_score = int(getattr(m, "project_score", 0) or 0)
        comp_score = int(getattr(m, "company_score", 0) or 0)

        if is_priority and proj_score >= 60 and (proj_score - comp_score) > 30:
            priority_matches.append(m)
            triggered = True
        else:
            others.append(m)

    if not triggered:
        return list(matches), BoostAppliedSchema(rule_triggered=False)

    new_matches = priority_matches + others
    return new_matches, BoostAppliedSchema(
        rule_triggered=True,
        rule_name="rouge_entreprise_vert_projet",
    )


# --- Refactor compute_offer_match : populate project_score + company_score ---


async def _compute_offer_match_v045(
    db: AsyncSession,
    *,
    project: Project,
    offer: Offer,
    fund: Any,
) -> OfferMatch:
    """Variante 045 : calcule project_score + company_score séparément,
    persiste les 4 nouvelles colonnes en plus des colonnes F14 (rétrocompat).

    Reuse maximalement la logique F14 existante (compute_offer_match) pour
    le score entreprise + ESG, mais ajoute le scoring projet et populate
    project_score / company_score / project_score_breakdown / divergence_explanation.
    """
    # ESG layer F13 (best-effort) — reutilise la logique F14.
    assessment = await _get_latest_esg_assessment(db, project.account_id)
    esg_fund_score = 50
    esg_intermediary_score = 50
    fund_missing: list[dict[str, Any]] = []
    intermediary_missing: list[dict[str, Any]] = []
    assessment_missing = assessment is None

    if assessment is not None:
        try:
            from app.modules.esg.multi_referential_service import (
                compute_referential_score_for_offer,
            )
            f13 = await compute_referential_score_for_offer(
                db, assessment_id=assessment.id, offer_id=offer.id,
            )
            fs = f13.get("fund_score")
            is_ = f13.get("intermediary_score")
            if fs is not None and fs.overall_score is not None:
                esg_fund_score = int(round(float(fs.overall_score)))
                fund_missing = list(fs.missing_criteria or [])
            if is_ is not None and is_.overall_score is not None:
                esg_intermediary_score = int(round(float(is_.overall_score)))
                intermediary_missing = list(is_.missing_criteria or [])
            else:
                esg_intermediary_score = esg_fund_score
                intermediary_missing = list(fund_missing)
        except Exception:  # noqa: BLE001
            logger.exception(
                "F045 - compute_referential_score_for_offer fail offer=%s",
                offer.id,
            )

    # company_score (heritage F14)
    company_score, company_breakdown = _compute_company_score(
        project, offer, fund, esg_fund_score=esg_fund_score,
    )

    # project_esg sub-score F047 (consomme project_esg_assessments)
    try:
        pe_score, pe_meta = await _get_project_esg_subscore(
            db,
            account_id=project.account_id,
            project_id=project.id,
            fund=fund,
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "F047 _get_project_esg_subscore failed (project=%s, offer=%s)",
            project.id, offer.id,
        )
        pe_score, pe_meta = None, None

    # project_score (F045 enrichi F047)
    project_score, project_breakdown = _compute_project_score(
        project, fund,
        project_esg_subscore_value=pe_score,
        project_esg_subscore_meta=pe_meta,
    )

    # Heritage F14 (fund_score / intermediary_score / bottleneck) :
    # on calcule pour preserver la retrocompat.
    w = MATCHING_WEIGHTS
    sector = company_breakdown["sector_match"]
    size = company_breakdown["size_match"]
    location = company_breakdown["location_match"]
    documents = company_breakdown["documents_match"]
    instrument = company_breakdown["instrument_match"]
    base = (
        w["sector"] * sector + w["size"] * size + w["location"] * location
        + w["documents"] * documents + w["instrument"] * instrument
    )
    fund_score = max(0, min(100, int(round(base + w["esg"] * esg_fund_score))))
    intermediary_score = max(
        0, min(100, int(round(base + w["esg"] * esg_intermediary_score))),
    )
    bottleneck = _compute_bottleneck(fund_score, intermediary_score)
    if bottleneck == "fund":
        critical_missing = fund_missing
    elif bottleneck == "intermediary":
        critical_missing = intermediary_missing
    else:
        critical_missing = fund_missing or intermediary_missing
    recommended_actions = _build_recommended_actions(critical_missing)

    # global_score deprecie : backfill = project_score pour rétrocompat tri.
    global_score = project_score

    # divergence_explanation : place-holder MVP (US4 implementera build_divergence_explanation)
    divergence_explanation: str | None = None
    try:
        from app.modules.financing.divergence_templates import (
            build_divergence_explanation,
        )
        if callable(getattr(build_divergence_explanation, "__call__", None)):
            divergence_explanation = build_divergence_explanation(
                project_score=project_score,
                company_score=company_score,
                project_breakdown=project_breakdown,
                company_breakdown=company_breakdown,
            )
    except Exception:  # noqa: BLE001 — US4 pas encore impl
        divergence_explanation = None

    # score_breakdown (F14 format etendu)
    score_breakdown = {
        "fund": {**company_breakdown, "missing_criteria": fund_missing},
        "intermediary": {**company_breakdown, "missing_criteria": intermediary_missing},
        "project": project_breakdown,  # F045
        "company": company_breakdown,  # F045
        "assessment_missing": assessment_missing,
        "size_match_currency_mismatch": company_breakdown.get(
            "size_match_currency_mismatch", False,
        ),
    }

    # UPSERT
    existing_q = await db.execute(
        select(OfferMatch).where(
            OfferMatch.project_id == project.id,
            OfferMatch.offer_id == offer.id,
        )
    )
    existing = existing_q.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=MATCH_TTL_DAYS)

    if existing is None:
        match = OfferMatch(
            account_id=project.account_id,
            project_id=project.id,
            offer_id=offer.id,
            global_score=global_score,
            fund_score=fund_score,
            intermediary_score=intermediary_score,
            project_score=project_score,
            company_score=company_score,
            project_score_breakdown=project_breakdown,
            divergence_explanation=divergence_explanation,
            score_breakdown=score_breakdown,
            bottleneck=bottleneck,
            recommended_actions=recommended_actions,
            status="suggested",
            computed_at=now,
            expires_at=expires_at,
            last_notified_at=None,
        )
        db.add(match)
    else:
        existing.global_score = global_score
        existing.fund_score = fund_score
        existing.intermediary_score = intermediary_score
        existing.project_score = project_score
        existing.company_score = company_score
        existing.project_score_breakdown = project_breakdown
        existing.divergence_explanation = divergence_explanation
        existing.score_breakdown = score_breakdown
        existing.bottleneck = bottleneck
        existing.recommended_actions = recommended_actions
        existing.computed_at = now
        existing.expires_at = expires_at
        match = existing

    await db.flush()
    return match


# --- Service principal match_funds_for_project ---


async def match_funds_for_project(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    project_id: uuid.UUID,
    min_score: int = 60,
    limit: int = 10,
    force_recompute: bool = False,
) -> MatchFundsResponse:
    """Calcule (ou retourne en cache) les matches projet-centric d'un projet.

    Steps :
    1. Charge le projet + verifie l'account_id (RLS).
    2. Charge les offres publiees actives (cap 50).
    3. Pour chaque offre, calcule project_score + company_score via
       _compute_offer_match_v045.
    4. Applique le boost R13 (3 fonds prioritaires impact).
    5. Tri par project_score DESC, company_score DESC.
    6. Persiste (UPSERT) puis retourne MatchFundsResponse.

    Raises:
        ValueError: project introuvable (RLS) -> caller traduit en 404.
    """
    # 1. Charge le projet en respectant l'account_id (RLS applicatif)
    project_q = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.account_id == account_id,
        )
    )
    project = project_q.scalar_one_or_none()
    if project is None:
        raise ValueError(f"Project introuvable (RLS) : {project_id}")

    # 2. Charge les offres publiees actives
    offers_q = await db.execute(
        select(Offer).where(
            Offer.publication_status == "published",
            Offer.is_active == True,  # noqa: E712
        ).limit(RECOMPUTE_OFFER_CAP)
    )
    offers = list(offers_q.scalars().all())

    # 3. Calcul des matches
    matches: list[OfferMatch] = []
    for offer in offers:
        fund = offer.fund
        if fund is None:
            continue
        try:
            m = await _compute_offer_match_v045(
                db, project=project, offer=offer, fund=fund,
            )
            matches.append(m)
        except Exception:  # noqa: BLE001
            logger.exception(
                "F045 match_funds_for_project: fail offer=%s project=%s",
                offer.id, project_id,
            )

    # 4. Tri par project_score DESC, company_score DESC
    matches.sort(
        key=lambda m: (-(m.project_score or 0), -(m.company_score or 0)),
    )

    # Hydrate fund_name / intermediary_name pour le boost (champs non SQL)
    enriched: list[Any] = []
    offer_by_id = {o.id: o for o in offers}
    for m in matches:
        offer_obj = offer_by_id.get(m.offer_id)
        fund_name = ""
        intermediary_name: str | None = None
        if offer_obj is not None:
            fund_name = getattr(offer_obj.fund, "name", "") or ""
            inter = offer_obj.intermediary
            intermediary_name = getattr(inter, "name", None) if inter else None
        # Wrapper enrichi pour le boost (n'altère pas m)
        from types import SimpleNamespace
        enriched.append(SimpleNamespace(
            match=m,
            fund_name=fund_name,
            intermediary_name=intermediary_name,
            project_score=m.project_score,
            company_score=m.company_score,
        ))

    # 5. Boost R13
    enriched, boost = _apply_boost_rule_rouge_entreprise_vert_projet(
        enriched, project,
    )

    # Persiste le boost_applied dans le breakdown des matches concernés
    if boost.rule_triggered:
        for w in enriched:
            m = w.match
            try:
                bd = dict(m.project_score_breakdown or {})
                bd["boost_applied"] = boost.model_dump()
                m.project_score_breakdown = bd
            except Exception:  # noqa: BLE001
                pass
        await db.flush()

    # 6. Filtrage min_score + cap limit
    filtered = [w for w in enriched if (w.project_score or 0) >= min_score][:limit]

    items = [
        MatchFundsItem(
            offer_id=w.match.offer_id,
            fund_id=offer_by_id[w.match.offer_id].fund_id,
            fund_name=w.fund_name,
            intermediary_id=offer_by_id[w.match.offer_id].intermediary_id,
            intermediary_name=w.intermediary_name,
            project_score=w.match.project_score,
            company_score=w.match.company_score,
            project_score_breakdown=dict(w.match.project_score_breakdown or {}),
            divergence_explanation=w.match.divergence_explanation,
            computed_at=w.match.computed_at,
            expires_at=w.match.expires_at,
        )
        for w in filtered
    ]

    no_match_reason: str | None = None
    if not items:
        no_match_reason = _build_no_match_reason_minimal(project)

    return MatchFundsResponse(
        project_id=project.id,
        project_name=project.name,
        matches_count=len(items),
        top_matches=items,
        no_match_reason=no_match_reason,
        recompute_request_id=None,
    )


def _build_no_match_reason_minimal(project: Any) -> str | None:
    """Delegue à _build_no_match_reason(project) - Phase 5 T061."""
    return _build_no_match_reason(project)


# --- F045 Phase 5 : no_match_reason builder enrichi (T061) ---


def _build_no_match_reason(project: Any) -> str | None:
    """Construit un message FR explicatif quand aucun match ne ressort.

    Inspecte 3 attributs critiques (taxonomie verte UEMOA, themes GCF, impact
    CO2 chiffré) + 2 secondaires (gender_inclusion, vulnerable_populations).
    Identifie les 2-3 thèmes manquants prioritaires et génère un gabarit FR.

    Reference : research.md R11 + spec US3 acceptance scenario 1.
    """
    primary_missing: list[str] = []
    secondary_missing: list[str] = []

    if getattr(project, "taxonomie_verte_uemoa_aligned", None) is not True:
        primary_missing.append("alignement à la taxonomie verte UEMOA")
    if not (getattr(project, "gcf_priority_themes", None) or []):
        primary_missing.append("thèmes GCF prioritaires")
    impact = getattr(project, "expected_impact_tco2e", None)
    if impact is None or float(impact or 0) <= 0:
        primary_missing.append("impact CO2 chiffré")

    if getattr(project, "gender_inclusion", None) is not True:
        secondary_missing.append("volet genre (GCF Gender Policy 2019)")
    if not (getattr(project, "vulnerable_populations", None) or []):
        secondary_missing.append("populations vulnérables ciblées (ODD 10)")

    if not primary_missing and not secondary_missing:
        # Cas degenere : projet apparemment complet mais aucun match.
        # Probablement un probleme catalogue (aucune offre publiee).
        return (
            "Aucun fonds ne correspond actuellement aux critères de ce projet. "
            "Le catalogue d'offres publiées est peut-être limité — réessayez "
            "ultérieurement."
        )

    # Prioritaire : 2-3 themes principaux, fallback secondaires si moins de 2 manques.
    themes_to_show = list(primary_missing)
    if len(themes_to_show) < 2 and secondary_missing:
        themes_to_show.extend(secondary_missing[: 2 - len(themes_to_show)])
    themes_to_show = themes_to_show[:3]
    themes_fr = ", ".join(themes_to_show)

    return (
        "Aucun fonds n'aligne ses critères avec ce projet. Pour augmenter "
        f"votre éligibilité, renseignez : {themes_fr}."
    )
