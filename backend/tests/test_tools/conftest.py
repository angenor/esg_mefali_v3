"""Fixtures de test pour les tools LangChain."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.runnables import RunnableConfig


@pytest.fixture
def mock_user_id() -> uuid.UUID:
    """UUID fixe pour les tests."""
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def mock_conversation_id() -> uuid.UUID:
    """UUID conversation fixe pour les tests."""
    return uuid.UUID("00000000-0000-0000-0000-000000000099")


@pytest.fixture
def mock_account_id() -> uuid.UUID:
    """UUID account fixe pour les tests (F02 multi-tenant)."""
    return uuid.UUID("00000000-0000-0000-0000-0000000000a1")


@pytest.fixture
def mock_db() -> AsyncMock:
    """Session DB mockée avec les méthodes async courantes."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def mock_config(
    mock_db: AsyncMock,
    mock_user_id: uuid.UUID,
    mock_conversation_id: uuid.UUID,
    mock_account_id: uuid.UUID,
) -> RunnableConfig:
    """RunnableConfig avec db et user_id injectés.

    F02 — ``account_id`` est désormais propagé par ``stream_graph_events``
    côté API ; les tests reflètent ce contrat pour que ``log_tool_call``
    puisse persister sans heurter la contrainte NOT NULL en BDD.
    """
    return {
        "configurable": {
            "db": mock_db,
            "user_id": mock_user_id,
            "conversation_id": mock_conversation_id,
            "thread_id": str(mock_conversation_id),
            "account_id": mock_account_id,
        },
    }


@pytest.fixture
def mock_config_no_db(mock_user_id: uuid.UUID) -> RunnableConfig:
    """RunnableConfig sans session DB (pour tester les erreurs)."""
    return {
        "configurable": {
            "user_id": mock_user_id,
        },
    }


@pytest.fixture
def mock_config_no_user(mock_db: AsyncMock) -> RunnableConfig:
    """RunnableConfig sans user_id (pour tester les erreurs)."""
    return {
        "configurable": {
            "db": mock_db,
        },
    }
