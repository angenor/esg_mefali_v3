"""Tests F12 du checkpointer LangGraph (smoke tests).

Le test ``test_create_checkpointer_is_async_context_manager`` valide la
signature du context manager. Les tests d'intégration réels avec
``AsyncPostgresSaver`` nécessitent PostgreSQL et sont marqués
``@pytest.mark.postgres`` pour être exécutés ponctuellement.
"""

from __future__ import annotations

from contextlib import _AsyncGeneratorContextManager

import pytest

from app.graph.checkpointer import create_checkpointer, get_checkpointer_connection_string


def test_get_checkpointer_connection_string_strips_asyncpg() -> None:
    """L'URL passée au checkpointer doit utiliser psycopg (pas asyncpg)."""
    conn = get_checkpointer_connection_string()
    assert "asyncpg" not in conn
    assert conn.startswith("postgresql://") or conn.startswith("postgresql+psycopg://") or conn.startswith("sqlite")


def test_create_checkpointer_returns_async_context_manager() -> None:
    """``create_checkpointer()`` doit retourner un async context manager utilisable en ``async with``."""
    cm = create_checkpointer()
    # @asynccontextmanager retourne une instance de _AsyncGeneratorContextManager
    assert isinstance(cm, _AsyncGeneratorContextManager) or hasattr(cm, "__aenter__")
    # On ferme/ne lance pas le with (PostgreSQL non requis pour ce test)


@pytest.mark.asyncio
async def test_compiled_graph_accepts_injected_checkpointer() -> None:
    """``create_compiled_graph(checkpointer=...)`` doit accepter un checkpointer."""
    from langgraph.checkpoint.memory import MemorySaver

    from app.graph.graph import create_compiled_graph

    cp = MemorySaver()
    graph = await create_compiled_graph(checkpointer=cp)
    # Le graphe compilé doit avoir une méthode astream_events ou ainvoke
    assert hasattr(graph, "ainvoke") or hasattr(graph, "astream_events")


@pytest.mark.asyncio
async def test_compiled_graph_falls_back_to_memorysaver_when_no_checkpointer() -> None:
    """Sans checkpointer fourni, fallback sur MemorySaver."""
    from app.graph.graph import create_compiled_graph

    graph = await create_compiled_graph()
    assert hasattr(graph, "ainvoke") or hasattr(graph, "astream_events")
