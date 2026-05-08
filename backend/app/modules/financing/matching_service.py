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

    if existing is None:
        match = OfferMatch(
            account_id=project.account_id,
            project_id=project_id,
            offer_id=offer_id,
            global_score=global_score,
            fund_score=fund_score,
            intermediary_score=intermediary_score,
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
    offset = (page - 1) * limit
    items_q = (
        base.order_by(desc(OfferMatch.global_score))
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
