"""État de la conversation LangGraph."""

from typing import Annotated, Any

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


def _merge_pydantic_retries(
    left: dict[str, int] | None,
    right: dict[str, int] | None,
) -> dict[str, int] | None:
    """Reducer dict-merge pour `pydantic_retries` (story 10.4).

    Fusion cle-par-cle (last-write-wins par tool_call_id) au lieu de l'overwrite
    par defaut. Empeche un noeud concurrent ecrivant un autre tool_call_id
    d'effacer les compteurs des autres.
    """
    if not left and not right:
        return None
    return {**(left or {}), **(right or {})}


class ConversationState(TypedDict):
    """État partagé entre les nœuds du graphe de conversation."""

    messages: Annotated[list, add_messages]
    user_id: str | None
    user_profile: dict | None
    context_memory: list[str]
    profile_updates: list[dict] | None
    profiling_instructions: str | None
    document_upload: dict | None
    document_analysis_summary: str | None
    has_document: bool
    esg_assessment: dict | None
    _route_esg: bool
    carbon_data: dict | None
    _route_carbon: bool
    financing_data: dict | None
    _route_financing: bool
    application_data: dict | None
    _route_application: bool
    credit_data: dict | None
    _route_credit: bool
    action_plan_data: dict | None
    _route_action_plan: bool
    tool_call_count: int
    active_module: str | None
    active_module_data: dict | None
    current_page: str | None
    # Compteurs frontend transmis pour moduler la frequence des propositions de guidage (FR17)
    guidance_stats: dict | None
    # Entites actives (story 10.2) — cabled-only backend, ignore par le selecteur en V1
    active_entities: dict[str, Any] | None
    # Story 10.4 : compteur de retries Pydantic par tool_call_id (max 1 retry).
    # Disjoint de tool_call_count qui mesure les iterations de boucle tool entiere.
    # Reducer dict-merge pour eviter l'ecrasement en cas d'ecritures concurrentes.
    pydantic_retries: Annotated[dict[str, int] | None, _merge_pydantic_retries]
    # Flag positionne quand le fallback Pydantic est declenche pour forcer la sortie.
    validation_failed: bool | None
