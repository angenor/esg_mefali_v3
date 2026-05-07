"""Compilation du graphe LangGraph pour la conversation."""

import logging
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from app.graph.checkpointer import create_checkpointer
from app.graph.nodes import action_plan_node, application_node, carbon_node, chat_node, credit_node, document_node, esg_scoring_node, financing_node, router_node
from app.graph.state import ConversationState

logger = logging.getLogger(__name__)

MAX_TOOL_CALLS_PER_TURN = 5


def _import_memory_tools() -> list:
    """Importer MEMORY_TOOLS de manière paresseuse (évite cycles d'import).

    F12 — Le tool recall_history est ajouté au ToolNode de chaque noeud
    spécialiste pour permettre la recherche sémantique dans l'historique
    conversationnel.
    """
    from app.graph.tools.memory_tools import MEMORY_TOOLS

    return MEMORY_TOOLS


def _route_after_router(state: ConversationState) -> str:
    """Décider du prochain nœud après le routeur.

    Priorité : ESG > carbon > financing > application > credit > action_plan > document > chat.
    """
    if state.get("_route_esg"):
        return "esg_scoring"
    if state.get("_route_carbon"):
        return "carbon"
    if state.get("_route_financing"):
        return "financing"
    if state.get("_route_application"):
        return "application"
    if state.get("_route_credit"):
        return "credit"
    if state.get("_route_action_plan"):
        return "action_plan"
    if state.get("has_document"):
        return "document"
    return "chat"


def _should_continue_tool_loop(state: ConversationState) -> str:
    """Décider si le nœud doit continuer la boucle tool ou terminer.

    Vérifie le dernier message AI :
    - S'il contient des tool_calls ET que le compteur < MAX → continuer vers le ToolNode
    - Sinon → terminer (END)
    """
    messages = state.get("messages", [])
    tool_call_count = state.get("tool_call_count", 0)

    if not messages:
        return "end"

    last_message = messages[-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        if tool_call_count < MAX_TOOL_CALLS_PER_TURN:
            return "continue"

    return "end"


def create_tool_loop(
    graph: StateGraph,
    node_name: str,
    node_fn: Any,
    tools: list,
) -> None:
    """Ajouter un nœud avec sa boucle ToolNode conditionnelle au graphe.

    Pattern : node_fn → should_continue → ToolNode → node_fn (max 5 itérations)
              node_fn → should_continue → END (pas de tool call ou plafond atteint)

    Args:
        graph: Le StateGraph en construction
        node_name: Nom du nœud (ex: "esg_scoring")
        node_fn: La fonction async du nœud spécialiste
        tools: Liste des tools LangChain pour ce nœud
    """
    tool_node_name = f"{node_name}_tools"

    graph.add_node(node_name, node_fn)

    if tools:
        tool_node = ToolNode(tools)
        graph.add_node(tool_node_name, tool_node)

        graph.add_conditional_edges(
            node_name,
            _should_continue_tool_loop,
            {
                "continue": tool_node_name,
                "end": END,
            },
        )
        graph.add_edge(tool_node_name, node_name)
    else:
        graph.add_edge(node_name, END)


def build_graph() -> StateGraph:
    """Construire le graphe de conversation multi-nœuds avec tool calling.

    Structure :
        START → router_node → [esg]          → esg_scoring_node ⟲ esg_tools → END
                             → [carbon]       → carbon_node ⟲ carbon_tools → END
                             → [financing]    → financing_node ⟲ financing_tools → END
                             → [application]  → application_node ⟲ application_tools → END
                             → [credit]       → credit_node ⟲ credit_tools → END
                             → [action_plan]  → action_plan_node ⟲ action_plan_tools → END
                             → [has_document] → document_node → chat_node ⟲ chat_tools → END
                             → [no_document]  → chat_node ⟲ chat_tools → END
    """
    # Importer les tools de chaque module (imports paresseux pour eviter les cycles)
    from app.graph.tools.action_plan_tools import ACTION_PLAN_TOOLS
    from app.graph.tools.application_tools import APPLICATION_TOOLS
    from app.graph.tools.carbon_tools import CARBON_TOOLS
    from app.graph.tools.chat_tools import CHAT_TOOLS
    from app.graph.tools.credit_tools import CREDIT_TOOLS
    from app.graph.tools.document_tools import DOCUMENT_TOOLS
    from app.graph.tools.esg_tools import ESG_TOOLS
    from app.graph.tools.financing_tools import FINANCING_TOOLS
    from app.graph.tools.guided_tour_tools import GUIDED_TOUR_TOOLS
    from app.graph.tools.interactive_tools import INTERACTIVE_TOOLS
    from app.graph.tools.profiling_tools import PROFILING_TOOLS
    # F06 — Tools projets verts (list/get/create/update/delete/duplicate/link)
    from app.graph.tools.project_tools import PROJECT_TOOLS

    graph = StateGraph(ConversationState)

    # Le router n'a pas de tools
    graph.add_node("router", router_node)
    graph.add_node("document", document_node)

    # F12 — recall_history (mémoire sémantique) injecté en transverse dans tous les noeuds.
    MEMORY_TOOLS = _import_memory_tools()

    # Noeuds avec boucle tool calling — INTERACTIVE_TOOLS injecte partout (feature 018),
    # GUIDED_TOUR_TOOLS injecte dans les 6 noeuds eligibles au guidage (feature 019),
    # MEMORY_TOOLS (recall_history) injecte partout (F12).
    # Le tool doit figurer AUSSI dans le ToolNode (et pas seulement bind_tools cote LLM),
    # sinon l'executeur rejette le tool_call et le LLM hallucine "tool indisponible".
    create_tool_loop(graph, "chat", chat_node, tools=PROFILING_TOOLS + CHAT_TOOLS + DOCUMENT_TOOLS + INTERACTIVE_TOOLS + GUIDED_TOUR_TOOLS + MEMORY_TOOLS + PROJECT_TOOLS)
    create_tool_loop(graph, "esg_scoring", esg_scoring_node, tools=ESG_TOOLS + INTERACTIVE_TOOLS + GUIDED_TOUR_TOOLS + MEMORY_TOOLS)
    create_tool_loop(graph, "carbon", carbon_node, tools=CARBON_TOOLS + INTERACTIVE_TOOLS + GUIDED_TOUR_TOOLS + MEMORY_TOOLS)
    create_tool_loop(graph, "financing", financing_node, tools=FINANCING_TOOLS + INTERACTIVE_TOOLS + GUIDED_TOUR_TOOLS + MEMORY_TOOLS)
    create_tool_loop(graph, "application", application_node, tools=APPLICATION_TOOLS + INTERACTIVE_TOOLS + MEMORY_TOOLS)
    create_tool_loop(graph, "credit", credit_node, tools=CREDIT_TOOLS + INTERACTIVE_TOOLS + GUIDED_TOUR_TOOLS + MEMORY_TOOLS)
    create_tool_loop(graph, "action_plan", action_plan_node, tools=ACTION_PLAN_TOOLS + INTERACTIVE_TOOLS + GUIDED_TOUR_TOOLS + MEMORY_TOOLS)

    graph.set_entry_point("router")
    graph.add_conditional_edges(
        "router",
        _route_after_router,
        {
            "esg_scoring": "esg_scoring",
            "carbon": "carbon",
            "financing": "financing",
            "application": "application",
            "credit": "credit",
            "action_plan": "action_plan",
            "document": "document",
            "chat": "chat",
        },
    )
    graph.add_edge("document", "chat")

    return graph


async def create_compiled_graph(checkpointer: Any | None = None):
    """Compiler le graphe avec le checkpointer.

    Appelé dans le lifespan FastAPI. Si ``checkpointer`` est fourni
    (typiquement ``AsyncPostgresSaver`` initialisé par le lifespan), on
    l'utilise pour la persistance des conversations (F12). Sinon on retombe
    sur ``MemorySaver`` (RAM volatile — utile pour scripts CLI/tests).

    Args:
        checkpointer: Instance de checkpointer LangGraph (optionnel).

    Returns:
        Graphe compilé prêt à l'emploi.
    """
    graph = build_graph()
    if checkpointer is None:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
