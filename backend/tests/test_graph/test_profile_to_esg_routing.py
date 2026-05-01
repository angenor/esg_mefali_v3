"""Tests d'intégration multi-tours profilage → ESG (spec fix-profile-and-routing-regression).

Vérifie qu'après un tour de chat (qui aurait pu fixer active_module='chat' via
continuation), un message d'intention ESG explicite au tour suivant déclenche
correctement `_route_esg=True` et réinitialise `active_module`.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.graph.nodes import router_node
from app.graph.state import ConversationState


def _state_with_history(messages: list, **overrides) -> ConversationState:
    """Construire un ConversationState avec un historique multi-tours."""
    base: dict = {
        "messages": messages,
        "user_id": "test-user",
        "user_profile": {
            "company_name": "Moussa SARL",
            "sector": "agroalimentaire",
            "city": "Dakar",
            "country": "Senegal",
            "employee_count": 18,
            "annual_revenue_xof": 85_000_000,
        },
        "context_memory": [],
        "profile_updates": None,
        "profiling_instructions": None,
        "document_upload": None,
        "document_analysis_summary": None,
        "has_document": False,
        "esg_assessment": None,
        "_route_esg": False,
        "carbon_data": None,
        "_route_carbon": False,
        "financing_data": None,
        "_route_financing": False,
        "application_data": None,
        "_route_application": False,
        "credit_data": None,
        "_route_credit": False,
        "action_plan_data": None,
        "_route_action_plan": False,
        "tool_call_count": 0,
        "active_module": None,
        "active_module_data": None,
        "current_page": None,
        "guidance_stats": None,
        "active_entities": None,
    }
    base.update(overrides)
    return base  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_profile_to_esg_two_turn_routing() -> None:
    """Séquence : tour 1 profilage dense → tour 2 « lance mon évaluation ESG ».

    AC3 : au tour 2, `_route_esg=True` quand bien même `active_module` aurait
    été fixé à 'chat' par un tour précédent (séquelle classifier continuation).

    NOTE (acceptance auditor) : ce test couvre la décision de routage uniquement.
    L'assertion runtime sur le contenu de `tool_call_logs` (deux entrées :
    `update_company_profile` puis `create_esg_assessment`) est portée par le
    replay E2E `agent-browser` documenté dans le Spec Change Log — non
    exécutable ici sans LLM réel + persistance DB.
    """
    messages = [
        HumanMessage(
            content="Moussa SARL, agroalimentaire, Dakar, 18 personnes, "
            "85 M FCFA, ODD 8/12/13",
        ),
        AIMessage(content="Merci, j'ai noté ces informations !"),
        HumanMessage(content="lance mon évaluation ESG"),
    ]
    # Simuler la séquelle d'un tour précédent : active_module='chat'
    state = _state_with_history(messages, active_module="chat")

    with patch(
        "app.graph.nodes._is_topic_continuation",
        new=AsyncMock(return_value=True),
    ):
        result = await router_node(state)

    assert result.get("_route_esg") is True, (
        "Au tour 2, l'intention ESG explicite doit forcer _route_esg=True ; "
        f"resultat={result}"
    )
    assert result.get("active_module") is None, (
        "active_module doit être réinitialisé pour permettre la transition "
        "vers esg_scoring_node"
    )


@pytest.mark.asyncio
async def test_esg_request_clean_slate() -> None:
    """Cas de base : message ESG sans active_module préalable → routage direct."""
    messages = [HumanMessage(content="lance mon évaluation ESG")]
    state = _state_with_history(messages, active_module=None)

    with patch(
        "app.graph.nodes._is_topic_continuation",
        new=AsyncMock(return_value=True),
    ):
        result = await router_node(state)

    assert result.get("_route_esg") is True
    assert result.get("active_module") is None
