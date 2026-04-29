"""Test E2E : un noeud LangGraph (esg_scoring) bind exactement la liste
filtree par select_tools_for_node (story 10.2 — AC7)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.graph.tool_selector import select_tools_for_node
from app.graph.tools.esg_tools import ESG_TOOLS
from app.graph.tools.guided_tour_tools import GUIDED_TOUR_TOOLS
from app.graph.tools.interactive_tools import INTERACTIVE_TOOLS

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_esg_scoring_node_binds_filtered_tools_only() -> None:
    """Le noeud esg_scoring doit appeler bind_tools avec EXACTEMENT la
    liste filtree par select_tools_for_node."""
    captured: dict[str, Any] = {}

    fake_response = AIMessage(content="ok")
    fake_llm_with_tools = MagicMock()
    fake_llm_with_tools.ainvoke = AsyncMock(return_value=fake_response)

    fake_llm = MagicMock()

    def _capture_bind(tools: list, *args: Any, **kwargs: Any) -> Any:
        captured["bind_tools_arg"] = tools
        return fake_llm_with_tools

    fake_llm.bind_tools = _capture_bind

    from app.graph import nodes as nodes_module

    state = {
        "messages": [HumanMessage(content="J'aimerais lancer mon evaluation ESG.")],
        "user_id": None,
        "user_profile": {"sector": "services"},
        "context_memory": [],
        "esg_assessment": None,
        "current_page": "/esg/results",
        "tool_call_count": 0,
    }

    config: dict[str, Any] = {"configurable": {}}

    with patch.object(nodes_module, "get_llm", return_value=fake_llm):
        await nodes_module.esg_scoring_node(state, config=config)

    assert "bind_tools_arg" in captured, "bind_tools n'a pas ete appele"
    bound_names = {t.name for t in captured["bind_tools_arg"]}

    expected_tools, debug = select_tools_for_node(
        node_name="esg_scoring",
        current_page="/esg/results",
        all_tools=ESG_TOOLS + INTERACTIVE_TOOLS + GUIDED_TOUR_TOOLS,
    )
    expected_names = {t.name for t in expected_tools}

    assert bound_names == expected_names, (
        f"Tools binds {bound_names} != attendu {expected_names}"
    )
    assert len(captured["bind_tools_arg"]) <= 10, "Plus de 10 tools binds"
    assert debug["page_slug"] == "esg"
    assert debug["fallback_used"] is False

    # tools_offered doit etre propage dans le RunnableConfig pour le logging.
    assert config["configurable"].get("tools_offered") == debug["tools_offered"]
