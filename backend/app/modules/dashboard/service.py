"""Service d'agrégation des données pour le tableau de bord."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession


# --- Helpers calcul de grade ---


def _esg_grade(score: float) -> str:
    """Convertir un score ESG /100 en grade (A/B/C/D)."""
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    return "D"


def _credit_grade(score: float) -> str:
    """Convertir un score crédit /100 en grade (A+/A/B+/B/C/D)."""
    if score >= 90:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B+"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    return "D"


# --- Sous-fonctions d'agrégation ---


async def _get_esg_summary(db: AsyncSession, user_id: uuid.UUID) -> dict | None:
    """Récupérer le résumé ESG pour l'utilisateur."""
    from app.models.esg import ESGAssessment, ESGStatusEnum

    # Récupérer les deux dernières évaluations complètes
    stmt = (
        select(ESGAssessment)
        .where(
            and_(
                ESGAssessment.user_id == user_id,
                ESGAssessment.status == ESGStatusEnum.completed,
                ESGAssessment.overall_score.is_not(None),
            )
        )
        .order_by(ESGAssessment.created_at.desc())
        .limit(2)
    )
    result = await db.execute(stmt)
    assessments = result.scalars().all()

    if not assessments:
        return None

    latest = assessments[0]
    trend: str | None = None

    if len(assessments) == 2:
        previous = assessments[1]
        if latest.overall_score > previous.overall_score:
            trend = "up"
        elif latest.overall_score < previous.overall_score:
            trend = "down"
        else:
            trend = None

    pillar_scores: dict[str, float] = {}
    if latest.environment_score is not None:
        pillar_scores["environment"] = latest.environment_score
    if latest.social_score is not None:
        pillar_scores["social"] = latest.social_score
    if latest.governance_score is not None:
        pillar_scores["governance"] = latest.governance_score

    return {
        "score": latest.overall_score,
        "grade": _esg_grade(latest.overall_score),
        "trend": trend,
        "last_assessment_date": latest.created_at.isoformat() if latest.created_at else None,
        "pillar_scores": pillar_scores,
    }


async def _get_carbon_summary(db: AsyncSession, user_id: uuid.UUID) -> dict | None:
    """Récupérer le résumé carbone pour l'utilisateur."""
    from app.models.carbon import CarbonAssessment, CarbonStatusEnum, CarbonEmissionEntry

    # Deux derniers bilans complétés (ordonnés par année desc)
    stmt = (
        select(CarbonAssessment)
        .where(
            and_(
                CarbonAssessment.user_id == user_id,
                CarbonAssessment.status == CarbonStatusEnum.completed,
                CarbonAssessment.total_emissions_tco2e.is_not(None),
            )
        )
        .order_by(CarbonAssessment.year.desc())
        .limit(2)
    )
    result = await db.execute(stmt)
    assessments = result.scalars().all()

    if not assessments:
        return None

    latest = assessments[0]
    variation_percent: float | None = None

    if len(assessments) == 2:
        previous = assessments[1]
        if previous.total_emissions_tco2e and previous.total_emissions_tco2e != 0:
            variation_percent = round(
                (latest.total_emissions_tco2e - previous.total_emissions_tco2e)
                / previous.total_emissions_tco2e
                * 100,
                1,
            )

    # Catégories depuis les entrées d'émission
    stmt_entries = (
        select(
            CarbonEmissionEntry.category,
            func.sum(CarbonEmissionEntry.emissions_tco2e).label("total"),
        )
        .where(CarbonEmissionEntry.assessment_id == latest.id)
        .group_by(CarbonEmissionEntry.category)
        .order_by(func.sum(CarbonEmissionEntry.emissions_tco2e).desc())
    )
    entry_result = await db.execute(stmt_entries)
    rows = entry_result.all()

    categories: dict[str, float] = {row.category: round(row.total, 3) for row in rows}
    top_category: str | None = rows[0].category if rows else None

    return {
        "total_tco2e": latest.total_emissions_tco2e,
        "year": latest.year,
        "variation_percent": variation_percent,
        "top_category": top_category,
        "categories": categories,
    }


async def _get_credit_summary(db: AsyncSession, user_id: uuid.UUID) -> dict | None:
    """Récupérer le résumé de crédit vert pour l'utilisateur."""
    from app.models.credit import CreditScore

    stmt = (
        select(CreditScore)
        .where(CreditScore.user_id == user_id)
        .order_by(CreditScore.version.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    credit_score = result.scalar_one_or_none()

    if credit_score is None:
        return None

    return {
        "score": credit_score.combined_score,
        "grade": _credit_grade(credit_score.combined_score),
        "last_calculated": credit_score.generated_at.isoformat() if credit_score.generated_at else None,
    }


# --- F21 — Mapping statut FundApplication → libellé d'étape humain FR ---


_STATUS_STEP_FR: dict[str, str] = {
    "draft": "Brouillon",
    "preparing_documents": "Préparation des documents",
    "in_progress": "Rédaction en cours",
    "review": "Relecture interne",
    "ready_for_intermediary": "Prêt à soumettre à l'intermédiaire",
    "ready_for_fund": "Prêt à soumettre au fonds",
    "submitted_to_intermediary": "Instruction par l'intermédiaire",
    "submitted_to_fund": "Dossier déposé auprès du fonds",
    "under_review": "En cours d'évaluation",
    "accepted": "Accepté",
    "rejected": "Rejeté",
}


def _status_to_step_fr(status: str, intermediary_name: str | None = None) -> str:
    """Mapper un statut technique vers un libellé d'étape français.

    Si l'intermédiaire est connu, le libellé est enrichi pour les statuts
    `submitted_to_intermediary` (« Instruction par {nom} »).
    """
    base = _STATUS_STEP_FR.get(status, status)
    if status == "submitted_to_intermediary" and intermediary_name:
        return f"Instruction par {intermediary_name}"
    return base


async def _get_applications_by_offer(
    db: AsyncSession, user_id: uuid.UUID, limit: int = 5
) -> list[dict]:
    """F21 (US1) — Lister jusqu'à `limit` cards de candidatures actives par Offre.

    Joint FundApplication + Offer + Fund + Intermediary. Tri par
    `last_activity_at` desc (= updated_at en l'absence d'événement plus précis).
    """
    from app.models.application import FundApplication, ApplicationStatus
    from sqlalchemy.orm import selectinload

    inactive = {
        ApplicationStatus.rejected,
        ApplicationStatus.accepted,
    }

    stmt = (
        select(FundApplication)
        .options(
            selectinload(FundApplication.fund),
            selectinload(FundApplication.intermediary),
            selectinload(FundApplication.offer),
        )
        .where(FundApplication.user_id == user_id)
        .order_by(FundApplication.updated_at.desc())
    )
    result = await db.execute(stmt)
    apps = result.scalars().all()

    cards: list[dict] = []
    for app in apps:
        if app.status in inactive:
            continue

        fund = getattr(app, "fund", None)
        intermediary = getattr(app, "intermediary", None)

        fund_name = (fund.name if fund else None) or "Fonds inconnu"
        intermediary_name = (
            intermediary.name if intermediary else "Accès direct"
        )

        status_val = app.status.value if hasattr(app.status, "value") else str(app.status)

        cards.append(
            {
                "application_id": app.id,
                "offer_id": getattr(app, "offer_id", None),
                "fund_name": fund_name,
                "intermediary_name": intermediary_name,
                "fund_logo_url": getattr(fund, "logo_url", None) if fund else None,
                "intermediary_logo_url": getattr(intermediary, "logo_url", None) if intermediary else None,
                "status": status_val,
                "current_step": _status_to_step_fr(
                    status_val,
                    intermediary.name if intermediary else None,
                ),
                "next_deadline": getattr(app, "next_deadline", None),
                "next_reminder": None,  # alimenté par F11 reminders à terme
                "last_activity_at": app.updated_at or app.created_at,
            }
        )
        if len(cards) >= limit:
            break

    return cards


async def _get_active_intermediaries(
    db: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID | None = None
) -> list[dict]:
    """F21 (US3) — Intermédiaires liés à au moins une candidature non clôturée.

    Le fallback capitale est appliqué quand l'intermédiaire n'a pas de
    coordonnées (cas le plus fréquent dans l'état actuel du modèle).
    """
    from app.models.application import FundApplication, ApplicationStatus
    from sqlalchemy.orm import selectinload
    from app.core.uemoa_capitals import get_capital_coordinates

    inactive = {ApplicationStatus.rejected, ApplicationStatus.accepted}

    stmt = (
        select(FundApplication)
        .options(
            selectinload(FundApplication.intermediary),
            selectinload(FundApplication.fund),
        )
        .where(FundApplication.user_id == user_id)
    )
    result = await db.execute(stmt)
    apps = result.scalars().all()

    grouped: dict[uuid.UUID, dict] = {}
    for app in apps:
        if app.status in inactive:
            continue
        intermediary = getattr(app, "intermediary", None)
        if intermediary is None:
            continue

        existing = grouped.get(intermediary.id)
        fund = getattr(app, "fund", None)
        fund_name = fund.name if fund else None

        if existing is None:
            # Coordonnées : pas de lat/lon natifs sur Intermediary —
            # fallback systématique sur la capitale du country.
            capital = get_capital_coordinates(getattr(intermediary, "country", None))
            if capital is None:
                # Skipper intermédiaires sans country reconnu (avertissement loggé).
                continue
            lat, lon = capital
            grouped[intermediary.id] = {
                "intermediary_id": intermediary.id,
                "name": intermediary.name,
                "type": (
                    intermediary.intermediary_type.value
                    if hasattr(intermediary.intermediary_type, "value")
                    else str(intermediary.intermediary_type)
                ),
                "country": intermediary.country,
                "lat": lat,
                "lon": lon,
                "is_fallback_capital": True,
                "accreditations": [fund_name] if fund_name else [],
                "applications_count": 1,
            }
        else:
            existing["applications_count"] += 1
            if fund_name and fund_name not in existing["accreditations"]:
                existing["accreditations"].append(fund_name)

    return list(grouped.values())


async def _collect_score_sources(
    db: AsyncSession, user_id: uuid.UUID, score_type: str
) -> list[dict]:
    """F21 (US4) — Collecter les sources mobilisées pour un score (ESG/carbon/credit).

    Stratégie : best-effort lecture des `tool_call_logs(tool_name='cite_source')`
    rattachés à la conversation racine du score. Best-effort silencieux si la
    table n'est pas disponible.
    """
    try:
        from app.models.tool_call_log import ToolCallLog
        from app.models.source import Source, VerificationStatus
    except Exception:
        return []

    try:
        result = await db.execute(
            select(ToolCallLog)
            .where(ToolCallLog.tool_name == "cite_source")
            .order_by(ToolCallLog.created_at.desc())
            .limit(20)
        )
        logs = result.scalars().all()
    except Exception:
        return []

    source_ids: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for log in logs:
        args = getattr(log, "arguments", None) or {}
        sid = args.get("source_id") if isinstance(args, dict) else None
        if not sid:
            continue
        try:
            sid_uuid = uuid.UUID(sid)
        except (ValueError, TypeError):
            continue
        if sid_uuid in seen:
            continue
        seen.add(sid_uuid)
        source_ids.append(sid_uuid)

    if not source_ids:
        return []

    src_result = await db.execute(
        select(Source).where(
            Source.id.in_(source_ids),
            Source.verification_status == VerificationStatus.VERIFIED.value,
        )
    )
    sources = src_result.scalars().all()
    out: list[dict] = []
    for src in sources:
        out.append(
            {
                "source_id": src.id,
                "title": src.title,
                "publisher": src.publisher,
                "version": src.version,
                "url": src.url,
            }
        )
    return out[:5]


async def _get_financing_summary(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Récupérer le résumé financements pour l'utilisateur."""
    from app.models.financing import FundMatch
    from app.models.application import FundApplication

    # Nombre de fonds recommandés (matchés)
    count_stmt = select(func.count(FundMatch.id)).where(FundMatch.user_id == user_id)
    count_result = await db.execute(count_stmt)
    recommended_funds_count = count_result.scalar() or 0

    # Candidatures actives (hors rejected)
    apps_stmt = (
        select(FundApplication.status, func.count(FundApplication.id).label("cnt"))
        .where(FundApplication.user_id == user_id)
        .group_by(FundApplication.status)
    )
    apps_result = await db.execute(apps_stmt)
    app_rows = apps_result.all()

    application_statuses: dict[str, int] = {}
    active_count = 0
    inactive_statuses = {"rejected"}

    for row in app_rows:
        status_val = row.status.value if hasattr(row.status, "value") else str(row.status)
        application_statuses[status_val] = row.cnt
        if status_val not in inactive_statuses:
            active_count += row.cnt

    # Vérifier s'il existe des chemins via intermédiaires (action de type intermediary_contact)
    from app.models.action_plan import ActionItem, ActionItemCategory, ActionItemStatus

    intermediary_stmt = (
        select(ActionItem)
        .join(ActionItem.plan)
        .where(
            and_(
                ActionItem.category == ActionItemCategory.intermediary_contact,
                ActionItem.status.in_([ActionItemStatus.todo, ActionItemStatus.in_progress]),
            )
        )
        .limit(1)
    )
    intermediary_result = await db.execute(intermediary_stmt)
    next_intermediary_item = intermediary_result.scalar_one_or_none()

    next_intermediary_action: dict | None = None
    has_intermediary_paths = False

    if next_intermediary_item is not None:
        has_intermediary_paths = True
        next_intermediary_action = {
            "title": next_intermediary_item.title,
            "intermediary_name": next_intermediary_item.intermediary_name,
            "intermediary_address": next_intermediary_item.intermediary_address,
            "due_date": next_intermediary_item.due_date.isoformat() if next_intermediary_item.due_date else None,
        }

    # F21 (US1, US3) — Cards par offre + intermédiaires actifs.
    applications_by_offer = await _get_applications_by_offer(db, user_id, limit=5)
    active_intermediaries = await _get_active_intermediaries(db, user_id)

    return {
        "recommended_funds_count": recommended_funds_count,
        "active_applications_count": active_count,
        "application_statuses": application_statuses,
        "next_intermediary_action": next_intermediary_action,
        "has_intermediary_paths": has_intermediary_paths,
        "applications_by_offer": applications_by_offer,
        "active_intermediaries": active_intermediaries,
    }


async def _get_next_actions(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    """Récupérer les 5 prochaines actions (triées par due_date ASC NULLS LAST)."""
    from app.models.action_plan import ActionItem, ActionPlan, ActionItemStatus

    stmt = (
        select(ActionItem)
        .join(ActionPlan, ActionItem.plan_id == ActionPlan.id)
        .where(
            and_(
                ActionPlan.user_id == user_id,
                ActionItem.status.in_([ActionItemStatus.todo, ActionItemStatus.in_progress]),
            )
        )
        .order_by(ActionItem.due_date.asc().nulls_last())
        .limit(5)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()

    return [
        {
            "id": item.id,
            "title": item.title,
            "category": item.category.value if hasattr(item.category, "value") else str(item.category),
            "due_date": item.due_date.isoformat() if item.due_date else None,
            "status": item.status.value if hasattr(item.status, "value") else str(item.status),
            "intermediary_name": item.intermediary_name,
            "intermediary_address": item.intermediary_address,
        }
        for item in items
    ]


async def _get_recent_activity(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    """Récupérer les 10 événements d'activité récente, toutes sources confondues."""
    events: list[dict] = []

    # --- Évaluations ESG complétées ---
    try:
        from app.models.esg import ESGAssessment, ESGStatusEnum

        esg_stmt = (
            select(ESGAssessment)
            .where(
                and_(
                    ESGAssessment.user_id == user_id,
                    ESGAssessment.status == ESGStatusEnum.completed,
                )
            )
            .order_by(ESGAssessment.updated_at.desc())
            .limit(10)
        )
        esg_result = await db.execute(esg_stmt)
        for assessment in esg_result.scalars().all():
            ts = assessment.updated_at or assessment.created_at
            events.append(
                {
                    "type": "esg_completed",
                    "title": "Évaluation ESG complétée",
                    "description": f"Score : {assessment.overall_score:.0f}/100" if assessment.overall_score else None,
                    "timestamp": ts,
                    "related_entity_type": "esg_assessment",
                    "related_entity_id": assessment.id,
                }
            )
    except Exception:
        pass

    # --- Bilans carbone complétés ---
    try:
        from app.models.carbon import CarbonAssessment, CarbonStatusEnum

        carbon_stmt = (
            select(CarbonAssessment)
            .where(
                and_(
                    CarbonAssessment.user_id == user_id,
                    CarbonAssessment.status == CarbonStatusEnum.completed,
                )
            )
            .order_by(CarbonAssessment.updated_at.desc())
            .limit(10)
        )
        carbon_result = await db.execute(carbon_stmt)
        for assessment in carbon_result.scalars().all():
            ts = assessment.updated_at or assessment.created_at
            events.append(
                {
                    "type": "carbon_completed",
                    "title": "Bilan carbone complété",
                    "description": f"{assessment.year} — {assessment.total_emissions_tco2e:.1f} tCO₂e" if assessment.total_emissions_tco2e else None,
                    "timestamp": ts,
                    "related_entity_type": "carbon_assessment",
                    "related_entity_id": assessment.id,
                }
            )
    except Exception:
        pass

    # --- Changements de statut de candidatures ---
    try:
        from app.models.application import FundApplication

        app_stmt = (
            select(FundApplication)
            .where(FundApplication.user_id == user_id)
            .order_by(FundApplication.updated_at.desc())
            .limit(10)
        )
        app_result = await db.execute(app_stmt)
        for application in app_result.scalars().all():
            ts = application.updated_at or application.created_at
            status_val = application.status.value if hasattr(application.status, "value") else str(application.status)
            events.append(
                {
                    "type": "application_status_change",
                    "title": "Candidature mise à jour",
                    "description": f"Statut : {status_val}",
                    "timestamp": ts,
                    "related_entity_type": "fund_application",
                    "related_entity_id": application.id,
                }
            )
    except Exception:
        pass

    # --- Badges débloqués ---
    try:
        from app.models.action_plan import Badge

        badge_stmt = (
            select(Badge)
            .where(Badge.user_id == user_id)
            .order_by(Badge.unlocked_at.desc())
            .limit(10)
        )
        badge_result = await db.execute(badge_stmt)
        for badge in badge_result.scalars().all():
            badge_type_val = badge.badge_type.value if hasattr(badge.badge_type, "value") else str(badge.badge_type)
            events.append(
                {
                    "type": "badge_unlocked",
                    "title": "Badge débloqué",
                    "description": badge_type_val,
                    "timestamp": badge.unlocked_at,
                    "related_entity_type": "badge",
                    "related_entity_id": badge.id,
                }
            )
    except Exception:
        pass

    # --- Actions mises à jour ---
    try:
        from app.models.action_plan import ActionItem, ActionPlan

        action_stmt = (
            select(ActionItem)
            .join(ActionPlan, ActionItem.plan_id == ActionPlan.id)
            .where(ActionPlan.user_id == user_id)
            .order_by(ActionItem.updated_at.desc())
            .limit(10)
        )
        action_result = await db.execute(action_stmt)
        for item in action_result.scalars().all():
            ts = item.updated_at or item.created_at
            status_val = item.status.value if hasattr(item.status, "value") else str(item.status)
            events.append(
                {
                    "type": "action_status_change",
                    "title": f"Action : {item.title[:50]}",
                    "description": f"Statut : {status_val}",
                    "timestamp": ts,
                    "related_entity_type": "action_item",
                    "related_entity_id": item.id,
                }
            )
    except Exception:
        pass

    # Trier tous les événements par timestamp décroissant et limiter à 10
    def _sort_key(ev: dict) -> datetime:
        ts = ev.get("timestamp")
        if ts is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if isinstance(ts, datetime):
            if ts.tzinfo is None:
                return ts.replace(tzinfo=timezone.utc)
            return ts
        return datetime.min.replace(tzinfo=timezone.utc)

    events.sort(key=_sort_key, reverse=True)
    return events[:10]


async def _get_badges(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    """Récupérer tous les badges de l'utilisateur."""
    from app.models.action_plan import Badge

    stmt = select(Badge).where(Badge.user_id == user_id).order_by(Badge.unlocked_at.desc())
    result = await db.execute(stmt)
    badges = result.scalars().all()

    return [
        {
            "id": b.id,
            "user_id": b.user_id,
            "badge_type": b.badge_type.value if hasattr(b.badge_type, "value") else str(b.badge_type),
            "unlocked_at": b.unlocked_at,
        }
        for b in badges
    ]


# --- Fonction principale ---


async def get_dashboard_summary(db: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    """Agréger toutes les données du dashboard pour un utilisateur.

    Interroge directement les modèles SQLAlchemy de chaque module
    pour éviter les dépendances circulaires entre services.
    """
    esg = await _get_esg_summary(db, user_id)
    carbon = await _get_carbon_summary(db, user_id)
    credit = await _get_credit_summary(db, user_id)
    financing = await _get_financing_summary(db, user_id)
    next_actions = await _get_next_actions(db, user_id)
    recent_activity = await _get_recent_activity(db, user_id)
    badges = await _get_badges(db, user_id)

    # F21 (US4) — Injecter les sources F01 dans chaque ScoreBlock (best-effort).
    if esg is not None:
        esg["sources"] = await _collect_score_sources(db, user_id, "esg")
    if carbon is not None:
        carbon["sources"] = await _collect_score_sources(db, user_id, "carbon")
    if credit is not None:
        credit["sources"] = await _collect_score_sources(db, user_id, "credit")

    return {
        "esg": esg,
        "carbon": carbon,
        "credit": credit,
        "financing": financing,
        "next_actions": next_actions,
        "recent_activity": recent_activity,
        "badges": badges,
    }
