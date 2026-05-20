"""Service metier pour le module Plan d'Action."""

import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action_plan import (
    ActionItem,
    ActionItemCategory,
    ActionItemPriority,
    ActionItemStatus,
    ActionPlan,
    PlanStatus,
    VALID_STATUS_TRANSITIONS,
)

logger = logging.getLogger(__name__)


# --- Helpers ---


def _extract_json_array(text: str) -> list:
    """Extraire un tableau JSON depuis une réponse LLM (supporte markdown)."""
    # Tenter extraction depuis bloc markdown ```json ... ```
    md_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if md_match:
        return json.loads(md_match.group(1))

    # Tenter extraction du premier tableau JSON brut (non-greedy)
    bracket_match = re.search(r"\[.*?\]", text, re.DOTALL)
    if bracket_match:
        try:
            return json.loads(bracket_match.group(0))
        except json.JSONDecodeError:
            pass

    # Fallback: trouver le début du tableau et parser progressivement
    start = text.find("[")
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        pass
                    break

    raise ValueError(f"Aucun tableau JSON valide trouvé dans la réponse LLM : {text[:200]}")


def _parse_action_date(raw: str | None, timeframe_months: int) -> date | None:
    """Valider et convertir une date d'action."""
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(str(raw))
        # Borner la date dans l'horizon du plan
        max_date = date.today() + timedelta(days=timeframe_months * 31)
        if parsed > max_date:
            return max_date
        return parsed
    except (ValueError, TypeError):
        return None


def _safe_category(raw: str | None) -> ActionItemCategory:
    """Convertir une chaîne en ActionItemCategory (fallback governance)."""
    try:
        return ActionItemCategory(raw)
    except (ValueError, TypeError):
        return ActionItemCategory.governance


def _safe_priority(raw: str | None) -> ActionItemPriority:
    """Convertir une chaîne en ActionItemPriority (fallback medium)."""
    try:
        return ActionItemPriority(raw)
    except (ValueError, TypeError):
        return ActionItemPriority.medium


def _build_company_context(profile: object) -> str:
    """Construire le contexte entreprise pour le prompt."""
    if profile is None:
        return "Aucun profil disponible."
    lines = []
    for field in ("company_name", "sector", "country", "city", "employee_count", "annual_revenue_xof"):
        value = getattr(profile, field, None)
        if value is not None and value != "":
            lines.append(f"- {field}: {value}")
    return "\n".join(lines) if lines else "Profil incomplet."


def _build_esg_context(assessment: object | None) -> str:
    """Construire le contexte ESG pour le prompt."""
    if assessment is None:
        return "Aucune évaluation ESG disponible."
    parts = [f"Score global : {assessment.overall_score}/100"]
    if assessment.environment_score is not None:
        parts.append(f"Environnement : {assessment.environment_score}/100")
    if assessment.social_score is not None:
        parts.append(f"Social : {assessment.social_score}/100")
    if assessment.governance_score is not None:
        parts.append(f"Gouvernance : {assessment.governance_score}/100")
    return " | ".join(parts)


def _build_carbon_context(assessment: object | None) -> str:
    """Construire le contexte carbone pour le prompt."""
    if assessment is None:
        return "Aucun bilan carbone disponible."
    total = getattr(assessment, "total_tco2e", None)
    year = getattr(assessment, "year", None)
    if total is not None and year is not None:
        return f"Bilan {year} : {total:.1f} tCO2e"
    return "Bilan carbone en cours."


def _build_financing_context(fund_matches: list) -> str:
    """Construire le contexte financement pour le prompt."""
    if not fund_matches:
        return "Aucun matching financement disponible."
    lines = []
    for match in fund_matches[:5]:
        fund = getattr(match, "fund", None)
        if fund:
            score = getattr(match, "compatibility_score", None)
            score_str = f" ({score:.0f}%)" if score is not None else ""
            lines.append(f"- {fund.name}{score_str}")
    return "\n".join(lines) if lines else "Aucun fonds compatible trouvé."


def _build_intermediaries_context(intermediaries: list) -> str:
    """Construire le contexte intermédiaires pour le prompt."""
    if not intermediaries:
        return "Aucun intermédiaire identifié."
    lines = []
    for inter in intermediaries[:8]:
        name = getattr(inter, "name", "Inconnu")
        # Champs réels du modèle Intermediary
        address = getattr(inter, "physical_address", None)
        phone = getattr(inter, "contact_phone", None)
        email = getattr(inter, "contact_email", None)
        inter_id = str(getattr(inter, "id", ""))
        line = f"- {name} (id:{inter_id})"
        if address:
            line += f" | Adresse: {address}"
        if phone:
            line += f" | Tel: {phone}"
        if email:
            line += f" | Email: {email}"
        lines.append(line)
    return "\n".join(lines)


# --- Fonctions principales ---


async def generate_action_plan(
    db: AsyncSession,
    user_id: uuid.UUID,
    timeframe: int,
) -> ActionPlan:
    """Générer un plan d'action personnalisé via LLM.

    1. Vérifier que le profil entreprise existe (sinon 428)
    2. Collecter le contexte ESG, carbone, financement, intermédiaires
    3. Appeler le LLM pour générer les actions
    4. Archiver l'ancien plan actif
    5. Créer le nouveau plan avec ses items
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    from app.core.config import settings
    from app.models.carbon import CarbonAssessment, CarbonStatusEnum
    from app.models.company import CompanyProfile
    from app.models.esg import ESGAssessment, ESGStatusEnum
    from app.models.financing import FundMatch, Intermediary
    from app.prompts.action_plan import build_action_plan_json_prompt

    # 1. Vérifier profil entreprise
    result = await db.execute(select(CompanyProfile).where(CompanyProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=428,
            detail="Profil entreprise requis pour générer un plan d'action. Complétez votre profil d'abord.",
        )

    # 2. Collecter contexte ESG (dernière évaluation complète)
    esg_result = await db.execute(
        select(ESGAssessment)
        .where(ESGAssessment.user_id == user_id)
        .where(ESGAssessment.status == ESGStatusEnum.completed)
        .order_by(ESGAssessment.created_at.desc())
        .limit(1)
    )
    esg_assessment = esg_result.scalar_one_or_none()

    # 3. Collecter contexte carbone (dernier bilan complété)
    carbon_result = await db.execute(
        select(CarbonAssessment)
        .where(CarbonAssessment.user_id == user_id)
        .where(CarbonAssessment.status == CarbonStatusEnum.completed)
        .order_by(CarbonAssessment.created_at.desc())
        .limit(1)
    )
    carbon_assessment = carbon_result.scalar_one_or_none()

    # 4. Collecter fonds matchés et intermédiaires
    from sqlalchemy.orm import selectinload

    matches_result = await db.execute(
        select(FundMatch)
        .options(selectinload(FundMatch.fund))
        .where(FundMatch.user_id == user_id)
        .order_by(FundMatch.compatibility_score.desc())
        .limit(5)
    )
    fund_matches = list(matches_result.scalars().all())

    intermediaries_result = await db.execute(
        select(Intermediary).limit(8)
    )
    intermediaries = list(intermediaries_result.scalars().all())

    # 5. Construire le prompt (variante JSON brut, sans tool calling)
    prompt = build_action_plan_json_prompt(
        company_context=_build_company_context(profile),
        esg_context=_build_esg_context(esg_assessment),
        carbon_context=_build_carbon_context(carbon_assessment),
        financing_context=_build_financing_context(fund_matches),
        intermediaries_context=_build_intermediaries_context(intermediaries),
        timeframe=timeframe,
    )

    # 6. Appel LLM
    llm = ChatOpenAI(
        model=settings.openrouter_model,
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        streaming=False,
    )
    response = await llm.ainvoke([
        SystemMessage(content=prompt),
        HumanMessage(content=f"Génère le plan d'action pour {timeframe} mois."),
    ])
    raw_text = response.content if hasattr(response, "content") else str(response)

    # 7. Parser le JSON
    try:
        actions_data = _extract_json_array(raw_text)
    except (ValueError, json.JSONDecodeError) as exc:
        # Log de la sortie LLM brute pour faciliter le debug en cas de
        # format non conforme (markdown sans backticks, JSON encapsule
        # dans un objet, etc.).
        logger.error(
            "Erreur parsing JSON LLM action_plan: %s\n--- raw LLM output (truncated) ---\n%s",
            exc, (raw_text or "")[:2000],
        )
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la génération du plan d'action. Réessayez.",
        ) from exc

    if not isinstance(actions_data, list) or not actions_data:
        logger.error(
            "Plan d'action LLM retourne vide ou format invalide. Raw: %s",
            (raw_text or "")[:500],
        )
        raise HTTPException(
            status_code=500,
            detail="Le LLM n'a pas retourné d'actions exploitables. Réessayez.",
        )

    # 8. Archiver l'ancien plan actif et committer avant d'insérer le nouveau
    # (nécessaire en SQLite qui n'applique pas les index partiels PostgreSQL)
    await db.execute(
        update(ActionPlan)
        .where(ActionPlan.user_id == user_id)
        .where(ActionPlan.status == PlanStatus.active)
        .values(status=PlanStatus.archived)
    )
    await db.commit()

    # Construire un mapping id -> intermédiaire pour les snapshots
    intermediary_map = {str(inter.id): inter for inter in intermediaries}

    # 9. Créer le nouveau plan (F02 multi-tenant : account_id propagé via user)
    company_name = getattr(profile, "company_name", None) or "votre entreprise"
    account_id = getattr(profile, "account_id", None)
    if account_id is None:
        from app.models.user import User as _User
        user_res = await db.execute(select(_User).where(_User.id == user_id))
        user_obj = user_res.scalar_one_or_none()
        if user_obj is None or user_obj.account_id is None:
            raise HTTPException(
                status_code=500,
                detail="account_id introuvable pour l'utilisateur (F02 requis).",
            )
        account_id = user_obj.account_id

    plan = ActionPlan(
        user_id=user_id,
        account_id=account_id,
        title=f"Plan d'action ESG {timeframe} mois — {company_name}",
        timeframe=timeframe,
        status=PlanStatus.active,
        total_actions=len(actions_data),
        completed_actions=0,
    )
    db.add(plan)
    await db.flush()  # Obtenir l'id du plan

    # 10. Créer les items
    for idx, action in enumerate(actions_data):
        # Snapshot coordonnées intermédiaire
        inter_id_raw = action.get("intermediary_id")
        intermediary_name = action.get("intermediary_name")
        intermediary_address = action.get("intermediary_address")
        intermediary_phone = action.get("intermediary_phone")
        intermediary_email = action.get("intermediary_email")

        # Si un intermediary_id est fourni, chercher dans le mapping pour snapshot
        inter_uuid = None
        if inter_id_raw:
            try:
                inter_uuid = uuid.UUID(str(inter_id_raw))
                inter = intermediary_map.get(str(inter_id_raw))
                if inter:
                    intermediary_name = intermediary_name or getattr(inter, "name", None)
                    # Utiliser les champs réels du modèle Intermediary
                    intermediary_address = intermediary_address or getattr(inter, "physical_address", None)
                    intermediary_phone = intermediary_phone or getattr(inter, "contact_phone", None)
                    intermediary_email = intermediary_email or getattr(inter, "contact_email", None)
            except (ValueError, TypeError):
                inter_uuid = None

        # fund_id
        fund_id_raw = action.get("fund_id")
        fund_uuid = None
        if fund_id_raw:
            try:
                fund_uuid = uuid.UUID(str(fund_id_raw))
            except (ValueError, TypeError):
                fund_uuid = None

        item = ActionItem(
            plan_id=plan.id,
            account_id=account_id,
            title=str(action.get("title", "Action sans titre"))[:500],
            description=action.get("description"),
            category=_safe_category(action.get("category")),
            priority=_safe_priority(action.get("priority")),
            status=ActionItemStatus.todo,
            due_date=_parse_action_date(action.get("due_date"), timeframe),
            estimated_cost_xof=action.get("estimated_cost_xof"),
            estimated_benefit=action.get("estimated_benefit"),
            completion_percentage=0,
            related_fund_id=fund_uuid,
            related_intermediary_id=inter_uuid,
            intermediary_name=intermediary_name,
            intermediary_address=intermediary_address,
            intermediary_phone=intermediary_phone,
            intermediary_email=intermediary_email,
            sort_order=idx,
        )
        db.add(item)

    await db.commit()
    await db.refresh(plan)
    return plan


async def get_active_plan(db: AsyncSession, user_id: uuid.UUID) -> ActionPlan | None:
    """Récupérer le plan d'action actif d'un utilisateur."""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(ActionPlan)
        .options(selectinload(ActionPlan.items))
        .where(ActionPlan.user_id == user_id)
        .where(ActionPlan.status == PlanStatus.active)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_plan_items(
    db: AsyncSession,
    plan_id: uuid.UUID,
    user_id: uuid.UUID,
    category: str | None = None,
    status: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[ActionItem], int, dict]:
    """Récupérer les items d'un plan avec filtres et pagination.

    Returns:
        (items, total, progress) où progress contient la progression globale et par catégorie.
    """
    from sqlalchemy import func as sqlfunc

    # Vérifier que le plan appartient à l'utilisateur
    plan_result = await db.execute(
        select(ActionPlan)
        .where(ActionPlan.id == plan_id)
        .where(ActionPlan.user_id == user_id)
    )
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan d'action introuvable.")

    # Requête items avec filtres
    query = select(ActionItem).where(ActionItem.plan_id == plan_id)
    if category:
        query = query.where(ActionItem.category == category)
    if status:
        query = query.where(ActionItem.status == status)

    # Compter le total
    count_query = select(sqlfunc.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Pagination
    offset = (page - 1) * limit
    query = query.order_by(ActionItem.sort_order).offset(offset).limit(limit)
    items_result = await db.execute(query)
    items = list(items_result.scalars().all())

    # Calculer la progression (sur tous les items du plan, pas juste la page)
    all_items_result = await db.execute(
        select(ActionItem).where(ActionItem.plan_id == plan_id)
    )
    all_items = list(all_items_result.scalars().all())

    progress = _compute_progress(all_items)

    return items, total, progress


def _compute_progress(items: list[ActionItem]) -> dict:
    """Calculer la progression globale et par catégorie."""
    if not items:
        return {"global_percentage": 0}

    total_count = len(items)
    completed_count = sum(1 for i in items if i.status == ActionItemStatus.completed)
    global_pct = int((completed_count / total_count) * 100) if total_count > 0 else 0

    progress: dict = {"global_percentage": global_pct}

    # Par catégorie
    categories: dict[str, dict] = {}
    for item in items:
        cat = item.category.value if hasattr(item.category, "value") else str(item.category)
        if cat not in categories:
            categories[cat] = {"total": 0, "completed": 0}
        categories[cat]["total"] += 1
        if item.status == ActionItemStatus.completed:
            categories[cat]["completed"] += 1

    for cat, data in categories.items():
        pct = int((data["completed"] / data["total"]) * 100) if data["total"] > 0 else 0
        progress[cat] = {"total": data["total"], "completed": data["completed"], "percentage": pct}

    return progress


async def update_action_item(
    db: AsyncSession,
    item_id: uuid.UUID,
    user_id: uuid.UUID,
    updates: dict,
) -> ActionItem:
    """Mettre à jour une action du plan.

    Valide les transitions de statut, met à jour l'item et les compteurs du plan.
    """
    # Charger l'item en jointure avec le plan pour vérifier l'appartenance
    result = await db.execute(
        select(ActionItem)
        .join(ActionPlan, ActionItem.plan_id == ActionPlan.id)
        .where(ActionItem.id == item_id)
        .where(ActionPlan.user_id == user_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Action introuvable.")

    # Valider la transition de statut si fournie
    new_status_raw = updates.get("status")
    if new_status_raw is not None:
        try:
            new_status = ActionItemStatus(new_status_raw)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Statut invalide : {new_status_raw}",
            ) from exc

        current_status = item.status
        allowed = VALID_STATUS_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Transition de statut invalide : {current_status.value} → {new_status.value}. "
                    f"Transitions autorisées : {[s.value for s in allowed]}"
                ),
            )
        item.status = new_status

        # Si l'action est complétée, mettre la progression à 100%
        if new_status == ActionItemStatus.completed:
            item.completion_percentage = 100

    # Autres champs
    if "completion_percentage" in updates and updates["completion_percentage"] is not None:
        pct = int(updates["completion_percentage"])
        item.completion_percentage = max(0, min(100, pct))

    if "due_date" in updates and updates["due_date"] is not None:
        raw_date = updates["due_date"]
        if isinstance(raw_date, date):
            item.due_date = raw_date
        else:
            try:
                item.due_date = date.fromisoformat(str(raw_date))
            except (ValueError, TypeError):
                pass

    # Mettre à jour les compteurs du plan
    await _update_plan_counters(db, item.plan_id)

    await db.commit()
    await db.refresh(item)

    # Vérifier les badges après mise à jour (fire-and-forget)
    try:
        from app.modules.action_plan.badges import check_and_award_badges
        await check_and_award_badges(db, user_id)
    except Exception:
        logger.warning("Erreur lors de la vérification des badges", exc_info=True)

    return item


async def _update_plan_counters(db: AsyncSession, plan_id: uuid.UUID) -> None:
    """Recalculer et mettre à jour les compteurs total/completed du plan."""
    from sqlalchemy import func as sqlfunc

    count_result = await db.execute(
        select(sqlfunc.count()).where(ActionItem.plan_id == plan_id)
    )
    total = count_result.scalar() or 0

    completed_result = await db.execute(
        select(sqlfunc.count())
        .where(ActionItem.plan_id == plan_id)
        .where(ActionItem.status == ActionItemStatus.completed)
    )
    completed = completed_result.scalar() or 0

    await db.execute(
        update(ActionPlan)
        .where(ActionPlan.id == plan_id)
        .values(total_actions=total, completed_actions=completed)
    )


# --- Rappels ---


async def create_reminder(
    db: AsyncSession,
    user_id: uuid.UUID,
    action_item_id: uuid.UUID | None,
    reminder_type: str,
    message: str,
    scheduled_at: datetime,
) -> "Reminder":
    """Créer un rappel pour un utilisateur."""
    from app.models.action_plan import Reminder, ReminderType

    reminder = Reminder(
        user_id=user_id,
        action_item_id=action_item_id,
        type=ReminderType(reminder_type),
        message=message,
        scheduled_at=scheduled_at,
    )
    db.add(reminder)
    await db.commit()
    await db.refresh(reminder)
    return reminder


async def get_upcoming_reminders(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 10,
    reminder_type: str | None = None,
) -> list["Reminder"]:
    """Récupérer les prochains rappels non envoyés, triés par date."""
    from app.models.action_plan import Reminder, ReminderType

    query = (
        select(Reminder)
        .where(Reminder.user_id == user_id)
        .where(Reminder.sent == False)  # noqa: E712
        .order_by(Reminder.scheduled_at.asc())
    )

    if reminder_type:
        query = query.where(Reminder.type == ReminderType(reminder_type))

    query = query.limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def mark_reminder_sent(
    db: AsyncSession,
    reminder_id: uuid.UUID,
    user_id: uuid.UUID,
) -> "Reminder":
    """Marquer un rappel comme envoyé."""
    from app.models.action_plan import Reminder

    result = await db.execute(
        select(Reminder)
        .where(Reminder.id == reminder_id)
        .where(Reminder.user_id == user_id)
    )
    reminder = result.scalar_one_or_none()
    if reminder is None:
        raise HTTPException(status_code=404, detail="Rappel introuvable.")

    reminder.sent = True
    await db.commit()
    await db.refresh(reminder)
    return reminder
