"""Tests d'integration `ValidatingToolNode` (story 10.4 — AC9).

Mini-graphe LangGraph avec un seul tool et un LLM mock deterministe.
3 scenarios :
- A : payload valide d'emblee -> 1 ToolMessage de resultat
- B : payload invalide puis valide -> ToolMessage erreur structuree puis ToolMessage resultat
- C : payload invalide deux fois -> ToolMessage fallback FR + flag validation_failed

Aucun appel OpenRouter — le LLM est entierement simule.
"""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.graph.validating_tool_node import (
    PYDANTIC_FALLBACK_MESSAGE,
    ValidatingToolNode,
)


class _Args(BaseModel):
    name: str = Field(..., description="Nom requis")
    count: int = Field(..., description="Compteur requis")


@tool(args_schema=_Args)
async def integration_tool(name: str, count: int) -> str:
    """Outil de test integration."""
    return f"DONE name={name} count={count}"


def _ai_with_call(args: dict[str, Any], call_id: str = "intcall_1") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"id": call_id, "name": "integration_tool", "args": args}],
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scenario_a_valid_payload_first_try():
    """A — payload valide d'emblee."""
    node = ValidatingToolNode([integration_tool], node_name="integration_test")
    state = {
        "messages": [HumanMessage(content="hi"), _ai_with_call({"name": "alpha", "count": 5})],
        "tool_call_count": 0,
    }
    result = await node(state, config=None)
    msgs = result["messages"]
    assert len(msgs) == 1
    assert isinstance(msgs[0], ToolMessage)
    assert "DONE name=alpha count=5" in msgs[0].content
    assert not result.get("validation_failed")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scenario_b_invalid_then_valid():
    """B — invalide puis valide en reutilisant le meme tool_call_id.

    Le LLM, en pratique, conserve le meme `tool_call_id` quand il corrige son
    appel suite a un message d'erreur structure — c'est la seule maniere pour
    que le compteur `pydantic_retries` aboutisse au statut `valid_after_retry`.
    """
    node = ValidatingToolNode([integration_tool], node_name="integration_test")

    # Tour 1 : args invalides (count manquant)
    state1 = {
        "messages": [HumanMessage(content="hi"), _ai_with_call({"name": "beta"}, call_id="intcall_b")],
        "tool_call_count": 0,
    }
    result1 = await node(state1, config=None)
    msg1 = result1["messages"][0]
    assert isinstance(msg1, ToolMessage)
    assert "a rejeté ton appel" in msg1.content
    assert PYDANTIC_FALLBACK_MESSAGE not in msg1.content
    assert result1["pydantic_retries"]["intcall_b"] == 1

    # Tour 2 : meme tool_call_id, payload corrige -> doit declencher `valid_after_retry`.
    state2 = {
        "messages": [
            HumanMessage(content="hi"),
            _ai_with_call({"name": "beta"}, call_id="intcall_b"),
            msg1,
            _ai_with_call({"name": "beta", "count": 7}, call_id="intcall_b"),
        ],
        "tool_call_count": 1,
        "pydantic_retries": result1["pydantic_retries"],
    }
    result2 = await node(state2, config=None)
    msg2 = result2["messages"][0]
    assert isinstance(msg2, ToolMessage)
    assert "DONE name=beta count=7" in msg2.content
    assert not result2.get("validation_failed")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scenario_c_invalid_twice_fallback():
    """C — invalide deux fois consecutifs (meme tool_call_id) -> fallback FR."""
    node = ValidatingToolNode([integration_tool], node_name="integration_test")

    state1 = {
        "messages": [HumanMessage(content="hi"), _ai_with_call({"name": "gamma"}, call_id="intcall_c")],
        "tool_call_count": 0,
    }
    result1 = await node(state1, config=None)
    assert result1["pydantic_retries"]["intcall_c"] == 1
    assert not result1.get("validation_failed")

    # Tour 2 : on simule que le LLM persiste avec un payload encore invalide,
    # en reutilisant le meme tool_call_id pour comptabiliser le 2eme echec.
    state2 = {
        "messages": [
            HumanMessage(content="hi"),
            _ai_with_call({"name": "gamma"}, call_id="intcall_c"),
            result1["messages"][0],
            _ai_with_call({"name": "gamma"}, call_id="intcall_c"),
        ],
        "tool_call_count": 1,
        "pydantic_retries": result1["pydantic_retries"],
    }
    result2 = await node(state2, config=None)
    msg = result2["messages"][0]
    assert isinstance(msg, ToolMessage)
    assert PYDANTIC_FALLBACK_MESSAGE in msg.content
    assert result2.get("validation_failed") is True
    from app.graph.graph import MAX_TOOL_CALLS_PER_TURN

    assert result2.get("tool_call_count") == MAX_TOOL_CALLS_PER_TURN
