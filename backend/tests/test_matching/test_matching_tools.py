"""Tests des tools LangChain F14."""

from __future__ import annotations

import json
import uuid

import pytest

from app.graph.tools.matching_tools import (
    MATCHING_READ_TOOLS,
    MATCHING_TOOLS,
    CompareOffersArgs,
    GetMatchDetailsArgs,
    ListMatchesArgs,
    RecomputeMatchesArgs,
    compare_offers_for_fund_v2,
    get_match_details,
    list_matches_for_project,
    recompute_matches_for_project,
)


def test_matching_tools_count():
    assert len(MATCHING_TOOLS) == 4


def test_matching_read_tools_count():
    assert len(MATCHING_READ_TOOLS) == 3


def test_tool_names_unique():
    names = {t.name for t in MATCHING_TOOLS}
    assert len(names) == 4


def test_tool_names_pattern():
    names = {t.name for t in MATCHING_TOOLS}
    assert "list_matches_for_project" in names
    assert "compare_offers_for_fund_v2" in names
    assert "recompute_matches_for_project" in names
    assert "get_match_details" in names


def test_tools_are_langchain_tools():
    for t in MATCHING_TOOLS:
        # langchain_core tool decorator wraps as StructuredTool / BaseTool
        assert hasattr(t, "name")
        assert hasattr(t, "args_schema")


def test_list_matches_args_validation():
    valid = ListMatchesArgs(project_id=uuid.uuid4())
    assert valid.min_score == 60
    assert valid.limit == 10


def test_list_matches_args_extra_forbidden():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ListMatchesArgs(project_id=uuid.uuid4(), unknown="x")  # type: ignore[call-arg]


def test_list_matches_min_score_bounds():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ListMatchesArgs(project_id=uuid.uuid4(), min_score=101)


def test_list_matches_limit_bounds():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ListMatchesArgs(project_id=uuid.uuid4(), limit=51)


def test_compare_offers_args_required():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CompareOffersArgs(project_id=uuid.uuid4())  # type: ignore[call-arg]


def test_recompute_matches_args_extra_forbidden():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        RecomputeMatchesArgs(
            project_id=uuid.uuid4(), unknown=True,  # type: ignore[call-arg]
        )


def test_get_match_details_args_required():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        GetMatchDetailsArgs(project_id=uuid.uuid4())  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_list_matches_returns_error_json_when_no_account(monkeypatch):
    """Sans config valide, retourne JSON {ok: false, error}."""
    out = await list_matches_for_project.ainvoke(
        {"project_id": str(uuid.uuid4()), "min_score": 60, "limit": 10},
        config={"configurable": {}},
    )
    parsed = json.loads(out)
    assert parsed.get("ok") is False
    assert "error" in parsed


@pytest.mark.asyncio
async def test_compare_offers_returns_error_json_when_no_account():
    out = await compare_offers_for_fund_v2.ainvoke(
        {"project_id": str(uuid.uuid4()), "fund_id": str(uuid.uuid4())},
        config={"configurable": {}},
    )
    parsed = json.loads(out)
    assert parsed.get("ok") is False


@pytest.mark.asyncio
async def test_get_match_details_returns_error_json_when_no_account():
    out = await get_match_details.ainvoke(
        {"project_id": str(uuid.uuid4()), "offer_id": str(uuid.uuid4())},
        config={"configurable": {}},
    )
    parsed = json.loads(out)
    assert parsed.get("ok") is False


def test_compare_offers_emits_sse_marker_pattern():
    """Vérifie que le code émet un marker SSE quand ça fonctionne (test de structure)."""
    import inspect
    from app.graph.tools import matching_tools as mt
    src = inspect.getsource(mt)
    assert "__sse_visualization_block__" in src
    assert "comparison_table" in src
    assert "<!--SSE:" in src
