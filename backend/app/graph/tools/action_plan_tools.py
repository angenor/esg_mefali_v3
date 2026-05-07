"""Tools LangChain pour le noeud plan d'action.

Trois tools exposes au LLM :
- generate_action_plan : generer un plan d'action ESG
- update_action_item : mettre a jour le statut d'une action
- get_action_plan : consulter le plan d'action actif
"""

import logging
import uuid

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.graph.tools.common import get_db_and_user, with_retry

logger = logging.getLogger(__name__)


@tool
@with_retry(
    max_retries=1,
    node_name="action_plan_node",
    fallback_message=(
        "Je n'arrive pas à générer le plan d'action. "
        "Pouvez-vous me préciser l'horizon souhaité (6, 12 ou 24 mois) ?"
    ),
)
async def generate_action_plan(timeframe: int, config: RunnableConfig) -> str:
    """Genere un plan d'action ESG personnalise (feuille de route 6/12/24 mois).

    Use when:
    - "feuille de route", "plan d'action", "que faire en priorite".
    - apres evaluation ESG ou bilan carbone, transformer en actions concretes.
    Don't use when:
    - plan deja actif (utiliser `get_action_plan`).
    - mise a jour d'une action precise (utiliser `update_action_item`).
    Exemple: "Donne-moi un plan 12 mois" -> generate_action_plan(timeframe=12).
    Anti: "Mes actions du moment ?" -> NE PAS appeler (utiliser `get_action_plan`).

    Args:
        timeframe: Horizon du plan en mois (6, 12 ou 24).
    """
    from app.modules.action_plan.service import generate_action_plan as gen_plan

    try:
        db, user_id = get_db_and_user(config)

        plan = await gen_plan(db=db, user_id=user_id, timeframe=timeframe)

        items_preview = []
        for item in (plan.items or [])[:5]:
            status = item.status.value if hasattr(item.status, "value") else item.status
            items_preview.append(f"  - {item.title} ({item.category}, {status})")
        items_text = "\n".join(items_preview) if items_preview else "  Aucune action generee."

        return (
            f"Plan d'action genere avec succes !\n"
            f"- Titre : {plan.title}\n"
            f"- Horizon : {plan.timeframe} mois\n"
            f"- Nombre d'actions : {plan.total_actions}\n"
            f"- Premieres actions :\n{items_text}\n\n"
            f"Le plan complet est visible sur la page /action-plan."
        )
    except Exception as e:
        logger.exception("Erreur lors de la generation du plan d'action")
        return f"Erreur lors de la generation du plan d'action : {e}"


@tool
@with_retry(
    max_retries=1,
    node_name="action_plan_node",
    fallback_message=(
        "Je n'arrive pas à mettre à jour cette action. "
        "Pouvez-vous me redonner l'identifiant et le statut visé ?"
    ),
)
async def update_action_item(
    action_id: str,
    config: RunnableConfig,
    status: str | None = None,
    completion_percentage: int | None = None,
) -> str:
    """Met a jour le statut ou la progression d'une action du plan (in_progress, completed, %).

    Use when:
    - l'utilisateur signale une progression ou completion d'action.
    - changement de statut explicite (cancelled, in_progress).
    Don't use when:
    - generation initiale (utiliser `generate_action_plan`).
    - simple consultation (utiliser `get_action_plan`).
    Exemple: "J'ai fait l'action XYZ" -> update_action_item(action_id=..., status='completed').
    Anti: "Comment va mon plan ?" -> NE PAS appeler (utiliser `get_action_plan`).

    Args:
        action_id: Identifiant UUID de l'action a mettre a jour.
        status: Nouveau statut (pending, in_progress, completed, cancelled).
        completion_percentage: Pourcentage de completion (0-100).
    """
    from app.modules.action_plan.service import update_action_item as update_item

    try:
        db, user_id = get_db_and_user(config)

        updates: dict = {}
        if status is not None:
            updates["status"] = status
        if completion_percentage is not None:
            updates["completion_percentage"] = completion_percentage

        if not updates:
            return "Aucune modification fournie. Precisez le statut ou le pourcentage de completion."

        item = await update_item(
            db=db,
            item_id=uuid.UUID(action_id),
            user_id=user_id,
            updates=updates,
        )

        item_status = item.status.value if hasattr(item.status, "value") else item.status

        return (
            f"Action mise a jour avec succes :\n"
            f"- Titre : {item.title}\n"
            f"- Statut : {item_status}\n"
            f"- Completion : {item.completion_percentage}%"
        )
    except Exception as e:
        logger.exception("Erreur lors de la mise a jour de l'action %s", action_id)
        return f"Erreur lors de la mise a jour de l'action : {e}"


@tool
async def get_action_plan(config: RunnableConfig) -> str:
    """Consulte le plan d'action actif et sa progression (lecture seule).

    Use when:
    - "mon plan d'action", "progression", "prochaines etapes".
    - decision sur l'action a prioriser.
    Don't use when:
    - generation initiale (utiliser `generate_action_plan`).
    - mise a jour d'une action (utiliser `update_action_item`).
    Exemple: "Mon plan ?" -> get_action_plan().
    Anti: "Genere un nouveau plan" -> NE PAS appeler (utiliser `generate_action_plan`).
    """
    from app.modules.action_plan.service import get_active_plan

    try:
        db, user_id = get_db_and_user(config)

        plan = await get_active_plan(db=db, user_id=user_id)

        if plan is None:
            return (
                "Aucun plan d'action actif trouve. "
                "Proposez a l'utilisateur de generer un plan d'action "
                "en precisant l'horizon souhaite (6, 12 ou 24 mois)."
            )

        completed = plan.completed_actions
        total = plan.total_actions
        pct = int((completed / total) * 100) if total > 0 else 0

        # Lister les actions non completees
        pending_items = []
        for item in (plan.items or []):
            item_status = item.status.value if hasattr(item.status, "value") else item.status
            if item_status != "completed":
                pending_items.append(
                    f"  - {item.title} ({item.category}, {item_status}, {item.completion_percentage}%)"
                )

        pending_text = "\n".join(pending_items[:5]) if pending_items else "  Toutes les actions sont completees !"

        return (
            f"Plan d'action actif :\n"
            f"- Titre : {plan.title}\n"
            f"- Horizon : {plan.timeframe} mois\n"
            f"- Progression : {completed}/{total} actions ({pct}%)\n"
            f"- Prochaines actions :\n{pending_text}"
        )
    except Exception as e:
        logger.exception("Erreur lors de la consultation du plan d'action")
        return f"Erreur lors de la consultation du plan d'action : {e}"


ACTION_PLAN_TOOLS = [generate_action_plan, update_action_item, get_action_plan]
