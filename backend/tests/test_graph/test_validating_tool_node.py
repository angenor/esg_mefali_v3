"""Tests unitaires pour `ValidatingToolNode` (story 10.4).

Couvre :
- helper `format_pydantic_errors_for_llm` (formatage FR de `exc.errors()`)
- `ValidatingToolNode.__call__` :
  - payload valide → délégation au `ToolNode` interne
  - payload invalide puis valide → 1 retry, log `valid_after_retry`
  - payload invalide deux fois → ToolMessage fallback FR + flag `validation_failed`
  - isolation du compteur de retry par `tool_call_id`
  - défense en profondeur : log_tool_call qui lève ne casse pas la boucle
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.graph.validating_tool_node import (
    PYDANTIC_FALLBACK_MESSAGE,
    ValidatingToolNode,
    format_pydantic_errors_for_llm,
)


# ---------------------------------------------------------------------------
# Helper format_pydantic_errors_for_llm — Tâche 3 / AC3
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_format_pydantic_errors_enum_missing_string():
    errors = [
        {
            "type": "enum",
            "loc": ("legal_form",),
            "msg": "Input should be 'SARL', 'SA', 'SAS'",
            "input": "sarl-incorrect",
            "ctx": {"expected": "'SARL', 'SA', 'SAS'"},
        },
        {
            "type": "missing",
            "loc": ("employee_count",),
            "msg": "Field required",
            "input": {},
        },
        {
            "type": "string_type",
            "loc": ("entity", "name"),
            "msg": "Input should be a valid string",
            "input": 12,
        },
    ]
    output = format_pydantic_errors_for_llm("update_company_profile", errors)
    assert "Le tool update_company_profile a rejeté ton appel." in output
    assert 'field "legal_form"' in output
    assert "enum" in output and "sarl-incorrect" in output
    assert 'field "employee_count": champ requis manquant' in output
    assert 'field "entity.name"' in output and "doit être" in output and "string" in output
    assert "Réessaie avec un payload corrigé." in output


@pytest.mark.unit
def test_format_pydantic_errors_truncates_long_messages():
    long_msg = "X" * 500
    errors = [{"type": "value_error", "loc": ("field",), "msg": long_msg, "input": None}]
    output = format_pydantic_errors_for_llm("tool_x", errors)
    for line in output.splitlines():
        if line.startswith("- field"):
            assert len(line) <= 200
            assert line.endswith("...")


@pytest.mark.unit
def test_format_pydantic_errors_int_and_bool_types():
    errors = [
        {"type": "int_type", "loc": ("count",), "msg": "Input should be a valid integer", "input": "x"},
        {"type": "bool_type", "loc": ("flag",), "msg": "Input should be a valid boolean", "input": "yes"},
    ]
    output = format_pydantic_errors_for_llm("tool_y", errors)
    assert "doit être un integer" in output or "doit être un int" in output
    assert "doit être un boolean" in output or "doit être un bool" in output


@pytest.mark.unit
def test_format_pydantic_errors_unknown_type_falls_back_to_msg():
    errors = [{"type": "exotic_type", "loc": ("foo",), "msg": "Some Pydantic message", "input": None}]
    output = format_pydantic_errors_for_llm("tool_z", errors)
    assert "Some Pydantic message" in output


# ---------------------------------------------------------------------------
# ValidatingToolNode — fixtures
# ---------------------------------------------------------------------------


class _SampleArgs(BaseModel):
    name: str = Field(..., description="Nom requis")
    count: int = Field(..., description="Compteur requis")


@tool(args_schema=_SampleArgs)
async def sample_tool(name: str, count: int) -> str:
    """Outil de test."""
    return f"OK:{name}:{count}"


@pytest.fixture
def validating_node() -> ValidatingToolNode:
    return ValidatingToolNode([sample_tool], node_name="test_node")


def _state_with_tool_call(args: dict[str, Any], tool_call_id: str = "call_1") -> dict:
    ai = AIMessage(
        content="",
        tool_calls=[{"id": tool_call_id, "name": "sample_tool", "args": args}],
    )
    return {"messages": [ai], "tool_call_count": 0}


# ---------------------------------------------------------------------------
# ValidatingToolNode — comportement
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validating_tool_node_valid_payload_passes_through(validating_node):
    state = _state_with_tool_call({"name": "alpha", "count": 3})
    with patch("app.graph.validating_tool_node.log_tool_call", new=AsyncMock()):
        result = await validating_node(state, config=None)
    messages = result.get("messages", [])
    assert len(messages) == 1
    msg = messages[0]
    assert isinstance(msg, ToolMessage)
    assert "OK:alpha:3" in msg.content


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validating_tool_node_invalid_then_valid_retry(validating_node):
    """1er appel invalide → ToolMessage erreur structurée. Pas de fallback."""
    state = _state_with_tool_call({"name": "alpha"})  # count manquant
    with patch("app.graph.validating_tool_node.log_tool_call", new=AsyncMock()):
        result = await validating_node(state, config=None)
    messages = result.get("messages", [])
    assert len(messages) == 1
    msg = messages[0]
    assert isinstance(msg, ToolMessage)
    assert msg.tool_call_id == "call_1"
    assert "a rejeté ton appel" in msg.content
    assert PYDANTIC_FALLBACK_MESSAGE not in msg.content
    assert not result.get("validation_failed")
    assert result.get("pydantic_retries", {}).get("call_1") == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validating_tool_node_invalid_twice_fallback(validating_node):
    """2e appel invalide consécutif → fallback FR + flag terminaison."""
    state = _state_with_tool_call({"name": "alpha"}, tool_call_id="call_2")
    state["pydantic_retries"] = {"call_2": 1}
    with patch("app.graph.validating_tool_node.log_tool_call", new=AsyncMock()):
        result = await validating_node(state, config=None)
    messages = result.get("messages", [])
    assert len(messages) == 1
    msg = messages[0]
    assert isinstance(msg, ToolMessage)
    assert PYDANTIC_FALLBACK_MESSAGE in msg.content
    assert result.get("validation_failed") is True
    from app.graph.graph import MAX_TOOL_CALLS_PER_TURN

    assert result.get("tool_call_count") == MAX_TOOL_CALLS_PER_TURN


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pydantic_retries_state_isolated_per_tool_call_id(validating_node):
    """Plusieurs tool_call_id → compteurs indépendants."""
    ai = AIMessage(
        content="",
        tool_calls=[
            {"id": "call_a", "name": "sample_tool", "args": {"name": "x"}},  # invalide
            {"id": "call_b", "name": "sample_tool", "args": {"name": "y", "count": 2}},  # valide
        ],
    )
    state = {"messages": [ai], "tool_call_count": 0}
    with patch("app.graph.validating_tool_node.log_tool_call", new=AsyncMock()):
        result = await validating_node(state, config=None)
    retries = result.get("pydantic_retries", {})
    assert retries.get("call_a") == 1
    assert retries.get("call_b", 0) == 0
    assert len(result["messages"]) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_log_tool_call_failure_does_not_break_loop(validating_node):
    """log_tool_call qui leve une exception ne casse pas la boucle."""
    state = _state_with_tool_call({"name": "alpha", "count": 3})
    fake_config = {"configurable": {"db": object(), "user_id": "u1", "conversation_id": None}}
    with patch(
        "app.graph.validating_tool_node.log_tool_call",
        side_effect=RuntimeError("boom"),
    ):
        result = await validating_node(state, config=fake_config)
    assert any(isinstance(m, ToolMessage) for m in result.get("messages", []))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_legacy_state_without_pydantic_retries_accepted(validating_node):
    """State sans la clé pydantic_retries (retro-compat) reste accepté."""
    state = _state_with_tool_call({"name": "x"})  # invalide
    state.pop("pydantic_retries", None)
    with patch("app.graph.validating_tool_node.log_tool_call", new=AsyncMock()):
        result = await validating_node(state, config=None)
    assert result.get("pydantic_retries", {}).get("call_1") == 1


# ---------------------------------------------------------------------------
# Tests post-review (couverture des branches P4 / P8 / P10 + chemin _safe_log)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unknown_tool_logs_and_responds(validating_node):
    """Tool inconnu → ToolMessage erreur + log validation_status=unknown_tool (patch P8)."""
    ai = AIMessage(
        content="",
        tool_calls=[{"id": "call_ghost", "name": "ghost_tool", "args": {}}],
    )
    state = {"messages": [ai], "tool_call_count": 0}
    fake_log = AsyncMock()
    fake_config = {"configurable": {"db": object(), "user_id": "u1"}}
    with patch("app.graph.validating_tool_node.log_tool_call", new=fake_log), patch(
        "app.graph.validating_tool_node.get_db_and_user",
        return_value=(fake_config["configurable"]["db"], "u1"),
    ):
        result = await validating_node(state, config=fake_config)
    messages = result["messages"]
    assert len(messages) == 1
    assert isinstance(messages[0], ToolMessage)
    assert "ghost_tool" in messages[0].content and "indisponible" in messages[0].content
    assert result["pydantic_retries"]["call_ghost"] == 1
    fake_log.assert_awaited_once()
    kwargs = fake_log.await_args.kwargs
    assert kwargs["validation_status"] == "unknown_tool"
    assert kwargs["status"] == "error"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_runtime_exception_after_validation_returns_error_message():
    """Exception runtime apres validation OK → ToolMessage 'Erreur :' + status=error (couvre _execute_tool except)."""

    class _A(BaseModel):
        x: int

    @tool(args_schema=_A)
    async def boom_tool(x: int) -> str:
        """Outil qui leve."""
        raise RuntimeError("kaboom")

    node = ValidatingToolNode([boom_tool], node_name="t")
    ai = AIMessage(
        content="",
        tool_calls=[{"id": "c1", "name": "boom_tool", "args": {"x": 1}}],
    )
    state = {"messages": [ai], "tool_call_count": 0}
    with patch("app.graph.validating_tool_node.log_tool_call", new=AsyncMock()):
        result = await node(state, config=None)
    msg = result["messages"][0]
    assert isinstance(msg, ToolMessage)
    assert "Erreur" in msg.content and "kaboom" in msg.content


@pytest.mark.unit
@pytest.mark.asyncio
async def test_safe_log_invokes_log_tool_call_with_real_config(validating_node):
    """Chemin nominal _safe_log : config truthy + db/user_id resolus → log_tool_call appele."""
    state = _state_with_tool_call({"name": "alpha", "count": 3})
    fake_log = AsyncMock()
    fake_config = {
        "configurable": {
            "db": object(),
            "user_id": "u1",
            "conversation_id": "conv1",
            "tools_offered": ["sample_tool"],
        }
    }
    with patch(
        "app.graph.validating_tool_node.get_db_and_user",
        return_value=(fake_config["configurable"]["db"], "u1"),
    ), patch("app.graph.validating_tool_node.log_tool_call", new=fake_log):
        await validating_node(state, config=fake_config)
    fake_log.assert_awaited_once()
    kwargs = fake_log.await_args.kwargs
    assert kwargs["validation_status"] == "valid"
    assert kwargs["tools_offered"] == ["sample_tool"]
    assert kwargs["conversation_id"] == "conv1"
    assert kwargs["node_name"] == "test_node"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stable_fallback_id_when_call_id_missing(validating_node):
    """tool_call sans id → cle pydantic_retries genere via _stable_fallback_id (prefixe 'hash:')."""
    ai = AIMessage(
        content="",
        tool_calls=[{"id": None, "name": "sample_tool", "args": {"name": "x"}}],  # id absent, count manquant
    )
    state = {"messages": [ai], "tool_call_count": 0}
    with patch("app.graph.validating_tool_node.log_tool_call", new=AsyncMock()):
        result = await validating_node(state, config=None)
    retries = result.get("pydantic_retries", {})
    assert len(retries) == 1
    key = next(iter(retries))
    assert key.startswith("hash:")
    assert retries[key] == 1


class _SerArgs(BaseModel):
    v: int


class _SerOut(BaseModel):
    ok: bool
    v: int


@tool(args_schema=_SerArgs)
async def _model_tool(v: int) -> _SerOut:
    """Renvoie un BaseModel."""
    return _SerOut(ok=True, v=v)


@tool(args_schema=_SerArgs)
async def _dict_tool(v: int) -> dict:
    """Renvoie un dict."""
    return {"value": v, "ok": True}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_serialize_tool_result_basemodel_and_dict():
    """_serialize_tool_result couvre BaseModel (model_dump_json) et dict (json.dumps)."""
    node = ValidatingToolNode([_model_tool, _dict_tool], node_name="t")
    ai = AIMessage(
        content="",
        tool_calls=[
            {"id": "m1", "name": "_model_tool", "args": {"v": 7}},
            {"id": "d1", "name": "_dict_tool", "args": {"v": 9}},
        ],
    )
    state = {"messages": [ai], "tool_call_count": 0}
    with patch("app.graph.validating_tool_node.log_tool_call", new=AsyncMock()):
        result = await node(state, config=None)
    contents = [m.content for m in result["messages"]]
    assert any('"ok":true' in c.replace(" ", "") and '"v":7' in c.replace(" ", "") for c in contents)
    assert any('"value": 9' in c or '"value":9' in c for c in contents)
