"""État de la conversation LangGraph."""

from typing import Annotated, Any

from langgraph.graph.message import add_messages
from typing_extensions import NotRequired, TypedDict


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
    # Identifiant conversation injecte cote tests/anti-boucle widget (Patch G).
    conversation_id: NotRequired[str]
