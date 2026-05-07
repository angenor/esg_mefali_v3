"""Tests F12 du tool LangChain `recall_history`.

Les tests pgvector réels (HNSW + cosine) sont marqués ``@pytest.mark.postgres``
pour ne s'exécuter que sur PostgreSQL avec extension pgvector. Ici on teste
le contrat du tool (validation Pydantic, formatage, RLS via mocks).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.graph.tools.memory_tools import (
    RecallHistoryArgs,
    _format_relative_time,
    _recall_history_impl,
    _serialize_result,
    recall_history,
)
from app.modules.memory.service import MessageRecallResult


# ─── Validation Pydantic ─────────────────────────────────────────────


def test_recall_args_min_query_length() -> None:
    with pytest.raises(Exception):
        RecallHistoryArgs(query="a")  # < 2 chars


def test_recall_args_max_query_length() -> None:
    with pytest.raises(Exception):
        RecallHistoryArgs(query="x" * 501)


def test_recall_args_max_results_capped() -> None:
    with pytest.raises(Exception):
        RecallHistoryArgs(query="ok", max_results=11)
    with pytest.raises(Exception):
        RecallHistoryArgs(query="ok", max_results=0)


def test_recall_args_defaults() -> None:
    args = RecallHistoryArgs(query="panneaux solaires")
    assert args.max_results == 5
    assert args.since is None
    assert args.include_current_conversation is False


# ─── Helpers (format / serialize) ────────────────────────────────────


def test_format_relative_time_minutes() -> None:
    now = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)
    assert (
        _format_relative_time(now - timedelta(minutes=5), now=now)
        == "il y a 5 minutes"
    )


def test_format_relative_time_absolute() -> None:
    now = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)
    past = now - timedelta(days=40)
    expected_date = past.strftime("%d/%m/%Y")
    assert _format_relative_time(past, now=now) == f"le {expected_date}"


def test_serialize_result_truncates_long_chunks() -> None:
    long_text = "a" * 2000
    result = MessageRecallResult(
        message_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        conversation_title="title",
        role="user",
        chunk_text=long_text,
        created_at=datetime.now(timezone.utc),
        similarity=0.85,
    )
    payload = _serialize_result(result, datetime.now(timezone.utc))
    assert len(payload["chunk_text"]) <= 1500
    assert payload["chunk_text"].endswith("...")
    assert payload["similarity"] == 0.85


# ─── Tool recall_history (avec mock service) ─────────────────────────


@pytest.mark.asyncio
async def test_recall_history_basic_success(monkeypatch) -> None:
    """Le tool sérialise correctement les résultats du service."""
    account_id = uuid.uuid4()
    conv_id = uuid.uuid4()
    msg_id = uuid.uuid4()

    fake_results = [
        MessageRecallResult(
            message_id=msg_id,
            conversation_id=conv_id,
            conversation_title="Test",
            role="user",
            chunk_text="On parlait des panneaux solaires.",
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
            similarity=0.82,
        )
    ]
    fake_search = AsyncMock(return_value=fake_results)
    monkeypatch.setattr("app.graph.tools.memory_tools.search_history", fake_search)

    config = {
        "configurable": {
            "account_id": account_id,
            "conversation_id": conv_id,
            "user_id": uuid.uuid4(),
        }
    }
    out = await _recall_history_impl(
        query="panneaux solaires",
        max_results=5,
        config=config,
    )
    assert isinstance(out, list)
    assert len(out) == 1
    item = out[0]
    assert item["message_id"] == str(msg_id)
    assert item["conversation_id"] == str(conv_id)
    assert "panneaux solaires" in item["chunk_text"]
    assert item["similarity"] == 0.82
    assert "il y a" in item["relative_time"] or "le " in item["relative_time"]


@pytest.mark.asyncio
async def test_recall_history_empty_results(monkeypatch) -> None:
    """Sans résultat, retour [] propre."""
    fake_search = AsyncMock(return_value=[])
    monkeypatch.setattr("app.graph.tools.memory_tools.search_history", fake_search)

    config = {
        "configurable": {
            "account_id": uuid.uuid4(),
            "conversation_id": uuid.uuid4(),
        }
    }
    out = await _recall_history_impl(query="rien à trouver", config=config)
    assert out == []


@pytest.mark.asyncio
async def test_recall_history_no_account_id_returns_empty(monkeypatch) -> None:
    """Sans account_id en configurable, le tool retourne [] (défense en profondeur)."""
    fake_search = AsyncMock(return_value=[])
    monkeypatch.setattr("app.graph.tools.memory_tools.search_history", fake_search)

    config = {"configurable": {}}
    out = await _recall_history_impl(query="panneaux", config=config)
    assert out == []
    # search_history NE doit PAS avoir été appelé
    fake_search.assert_not_called()


@pytest.mark.asyncio
async def test_recall_history_invalid_account_id(monkeypatch) -> None:
    """Si account_id n'est pas un UUID valide, retour [] sans crash."""
    fake_search = AsyncMock(return_value=[])
    monkeypatch.setattr("app.graph.tools.memory_tools.search_history", fake_search)

    config = {"configurable": {"account_id": "not-a-uuid"}}
    out = await _recall_history_impl(query="test", config=config)
    assert out == []


@pytest.mark.asyncio
async def test_recall_history_passes_include_current_flag(monkeypatch) -> None:
    """Le flag include_current_conversation est transmis au service."""
    fake_search = AsyncMock(return_value=[])
    monkeypatch.setattr("app.graph.tools.memory_tools.search_history", fake_search)

    config = {
        "configurable": {
            "account_id": uuid.uuid4(),
            "conversation_id": uuid.uuid4(),
        }
    }
    await _recall_history_impl(
        query="test",
        include_current_conversation=True,
        config=config,
    )
    fake_search.assert_awaited_once()
    call_kwargs = fake_search.call_args.kwargs
    assert call_kwargs.get("include_current_conversation") is True


@pytest.mark.asyncio
async def test_recall_history_max_results_capped_at_10(monkeypatch) -> None:
    """Le hard cap server-side limite max_results à 10 (défense en profondeur)."""
    fake_search = AsyncMock(return_value=[])
    monkeypatch.setattr("app.graph.tools.memory_tools.search_history", fake_search)

    config = {
        "configurable": {
            "account_id": uuid.uuid4(),
            "conversation_id": uuid.uuid4(),
        }
    }
    # On peut tester directement la borne dure : 999 → cap 10
    await _recall_history_impl(query="test", max_results=999, config=config)
    fake_search.assert_awaited_once()
    assert fake_search.call_args.kwargs.get("max_results") == 10


@pytest.mark.asyncio
async def test_recall_history_excludes_current_by_default(monkeypatch) -> None:
    """Par défaut, include_current_conversation=False et current_conversation_id transmis."""
    captured = {}

    async def fake(*args, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr("app.graph.tools.memory_tools.search_history", fake)

    conv_id = uuid.uuid4()
    config = {
        "configurable": {
            "account_id": uuid.uuid4(),
            "conversation_id": conv_id,
        }
    }
    await _recall_history_impl(query="test", config=config)
    assert captured.get("include_current_conversation") is False
    assert captured.get("current_conversation_id") == conv_id


@pytest.mark.asyncio
async def test_recall_history_short_query_returns_empty(monkeypatch) -> None:
    """Query trop courte (< 2 chars) retourne [] sans appeler search."""
    fake_search = AsyncMock(return_value=[])
    monkeypatch.setattr("app.graph.tools.memory_tools.search_history", fake_search)

    config = {"configurable": {"account_id": uuid.uuid4()}}
    out = await _recall_history_impl(query="a", config=config)
    assert out == []
    fake_search.assert_not_called()


@pytest.mark.asyncio
async def test_recall_history_tool_invoke_via_runnable(monkeypatch) -> None:
    """Le tool LangChain @tool reste invocable via ainvoke avec args dict."""
    fake_search = AsyncMock(return_value=[])
    monkeypatch.setattr("app.graph.tools.memory_tools.search_history", fake_search)

    # Sans config valide, le tool retourne []
    out = await recall_history.ainvoke({"query": "test"})
    assert out == []
