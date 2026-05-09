"""Tool LangChain trigger_guided_tour (feature 019).

Permet au LLM de declencher un parcours guide visuel pour l'utilisateur.
Un marker SSE est embarque dans le retour du tool, intercepte par stream_graph_events.
"""

from __future__ import annotations

import json
import logging
import re
import uuid

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.graph.tools.common import _tools_offered_from_config, get_db_and_user, log_tool_call

logger = logging.getLogger(__name__)

# Format attendu pour un tour_id : identifiant snake_case, evite l'injection de
# sequences `-->` / `<!--` qui casseraient le marker SSE `<!--SSE:...-->`
_VALID_TOUR_ID = re.compile(r"^[a-z][a-z0-9_]*$")


@tool
async def trigger_guided_tour(
    tour_id: str,
    context: dict | None = None,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> str:
    """Declenche un parcours guide visuel (overlay) sur l'interface utilisateur.

    Use when:
    - "montre-moi", "guide-moi", apres une action a explication visuelle.
    - apres un resultat ESG/carbone/credit, proposer un tour des elements.
    Don't use when:
    - simple consultation textuelle (utiliser les `get_*` tools de chat).
    - sans `tour_id` valide (snake_case, lowercase).
    Exemple: "Montre-moi mes resultats ESG" -> trigger_guided_tour(tour_id='show_esg_results').
    Anti: "Donne mon score" -> NE PAS appeler (utiliser `get_esg_assessment_chat`).

    Args:
        tour_id: Identifiant du parcours (ex: show_esg_results, show_carbon_results).
        context: Donnees contextuelles optionnelles pour personnaliser le parcours.
    """
    # Validation du tour_id (format + non vide) pour eviter l'injection SSE
    if not tour_id or not _VALID_TOUR_ID.match(tour_id):
        logger.warning("trigger_guided_tour: tour_id invalide (%r)", tour_id)
        return "Erreur : tour_id invalide (format attendu : snake_case minuscule)."

    try:
        db, user_id = get_db_and_user(config)
    except ValueError as exc:
        logger.warning("trigger_guided_tour: config manquante (%s)", exc)
        return "Erreur : contexte technique indisponible, retente."

    configurable = (config or {}).get("configurable", {})
    conversation_id_raw = configurable.get("conversation_id")
    conversation_id: uuid.UUID | None
    if isinstance(conversation_id_raw, str):
        try:
            conversation_id = uuid.UUID(conversation_id_raw)
        except ValueError:
            logger.warning(
                "trigger_guided_tour: conversation_id non-UUID (%r)",
                conversation_id_raw,
            )
            conversation_id = None
    else:
        conversation_id = conversation_id_raw

    active_module_data = configurable.get("active_module_data") or {}
    module_name = (
        configurable.get("active_module")
        or active_module_data.get("module")
        or "chat"
    )

    sse_payload = {
        "__sse_guided_tour__": True,
        "type": "guided_tour",
        "tour_id": tour_id,
        "context": context or {},
    }
    # Serialisation defensive :
    #   - default=str pour tolerer datetime / bytes / UUID dans context sans crasher
    #   - remplacement `-->` → `--\u003e` pour empecher qu'une valeur de context
    #     contenant cette sequence ne tronque le marker SSE `<!--SSE:...-->`.
    #     Le decodeur JSON cote client restituera `>` correctement.
    sse_marker = json.dumps(sse_payload, default=str).replace("-->", "--\\u003e")

    try:
        await log_tool_call(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            node_name=module_name,
            tool_name="trigger_guided_tour",
            tool_args={"tour_id": tour_id, "context": context},
            tool_result={"tour_id": tour_id, "status": "triggered"},
            status="success",
            tools_offered=_tools_offered_from_config(config),
            config=config,
        )
    except Exception:  # pragma: no cover - journalisation defensive
        logger.debug("Echec journalisation tool trigger_guided_tour", exc_info=True)

    return f"Parcours guide '{tour_id}' declenche pour l'utilisateur.\n\n<!--SSE:{sse_marker}-->"


GUIDED_TOUR_TOOLS = [trigger_guided_tour]
