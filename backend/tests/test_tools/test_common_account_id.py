"""Tests TDD pour le fix tool_call_logs.account_id NULL (Bug #1).

Contexte :
- F02 mig 019 a marqué tool_call_logs.account_id NOT NULL en BDD.
- Le wrapper ``log_tool_call`` n'avait pas connaissance de ``account_id``,
  ce qui provoquait NotNullViolationError sur PostgreSQL et abortait la
  transaction (cascade : tous les tool calls suivants échouent).

Pattern miroir du fix F18 (2026-05-08) sur ``interactive_questions.account_id`` :
- priorité 1 : ``config['configurable']['account_id']`` (propagé par
  ``stream_graph_events`` côté API).
- priorité 2 : fallback DB ``SELECT account_id FROM conversations``.
- échec total : SKIP l'INSERT (le log est observabilité, jamais bloquant).
"""

from __future__ import annotations

import logging
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.graph.tools.common import log_tool_call


@pytest.fixture
def mock_account_id() -> uuid.UUID:
    """UUID account fixe pour les tests."""
    return uuid.UUID("00000000-0000-0000-0000-0000000000a1")


@pytest.fixture
def mock_db_with_conversation(mock_account_id: uuid.UUID) -> AsyncMock:
    """Session DB qui retourne ``mock_account_id`` lors d'un SELECT
    sur ``conversations.account_id``.

    Simule le filet de sécurité côté BDD quand le config n'a pas l'account_id.
    """
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=mock_account_id)
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.fixture
def mock_db_no_conversation() -> AsyncMock:
    """Session DB qui retourne None pour le SELECT account_id (conversation
    inexistante ou account_id NULL en BDD test SQLite)."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=result)
    return db


class TestLogToolCallAccountId:
    """log_tool_call doit hydrater ``account_id`` pour respecter NOT NULL en BDD."""

    @pytest.mark.asyncio
    async def test_account_id_kwarg_persisted(
        self, mock_db, mock_user_id, mock_account_id, mock_conversation_id
    ):
        """Quand ``account_id`` est passé en kwarg, il est stocké sur ToolCallLog."""
        await log_tool_call(
            mock_db,
            user_id=mock_user_id,
            account_id=mock_account_id,
            conversation_id=mock_conversation_id,
            node_name="chat",
            tool_name="ask_interactive_question",
            tool_args={"question_type": "qcu"},
            status="success",
        )

        mock_db.add.assert_called_once()
        log_entry = mock_db.add.call_args[0][0]
        assert log_entry.account_id == mock_account_id

    @pytest.mark.asyncio
    async def test_account_id_resolved_from_config(
        self,
        mock_db,
        mock_user_id,
        mock_account_id,
        mock_conversation_id,
    ):
        """Quand ``account_id`` est dans config['configurable'], il est extrait
        automatiquement par le wrapper ``with_retry``.

        Vérifie via le helper public ``log_tool_call`` qu'on supporte au moins
        l'extraction kwarg explicite (le wrapper avec config est testé via
        ``with_retry`` ailleurs).
        """
        # Simuler ce que ``with_retry`` doit faire : extraire account_id du config
        # et le passer à log_tool_call.
        await log_tool_call(
            mock_db,
            user_id=mock_user_id,
            account_id=mock_account_id,
            conversation_id=mock_conversation_id,
            node_name="chat",
            tool_name="get_company_profile",
            tool_args={},
        )
        log_entry = mock_db.add.call_args[0][0]
        assert log_entry.account_id == mock_account_id

    @pytest.mark.asyncio
    async def test_account_id_fallback_to_db_when_missing(
        self,
        mock_db_with_conversation,
        mock_user_id,
        mock_account_id,
        mock_conversation_id,
    ):
        """Quand account_id absent, le helper doit faire SELECT FROM conversations."""
        await log_tool_call(
            mock_db_with_conversation,
            user_id=mock_user_id,
            conversation_id=mock_conversation_id,
            node_name="chat",
            tool_name="some_tool",
            tool_args={},
        )

        mock_db_with_conversation.add.assert_called_once()
        log_entry = mock_db_with_conversation.add.call_args[0][0]
        assert log_entry.account_id == mock_account_id

    @pytest.mark.asyncio
    async def test_skip_insert_when_account_id_unresolvable(
        self,
        mock_db_no_conversation,
        mock_user_id,
        mock_conversation_id,
        caplog,
    ):
        """Quand ni kwarg ni fallback DB ne résolvent account_id, l'INSERT
        est skippé (sans exception) — le log est purement observabilité.

        Vital : un log raté ne doit JAMAIS faire échouer le graph.
        """
        with caplog.at_level(logging.WARNING):
            await log_tool_call(
                mock_db_no_conversation,
                user_id=mock_user_id,
                conversation_id=mock_conversation_id,
                node_name="chat",
                tool_name="some_tool",
                tool_args={},
            )

        # AUCUN INSERT ne doit avoir été tenté.
        mock_db_no_conversation.add.assert_not_called()
        mock_db_no_conversation.flush.assert_not_called()

        # Un warning doit être loggé pour observabilité.
        warnings = [
            r for r in caplog.records
            if r.levelno == logging.WARNING and "account_id" in r.getMessage()
        ]
        assert len(warnings) >= 1, (
            "Un warning doit être loggé quand account_id est non-résolvable"
        )

    @pytest.mark.asyncio
    async def test_no_exception_raised_when_account_id_missing(
        self,
        mock_db_no_conversation,
        mock_user_id,
        mock_conversation_id,
    ):
        """L'absence d'account_id NE DOIT PAS lever d'exception (filet sécurité).

        Si log_tool_call lève, la transaction LangGraph est avortée et tous
        les tool calls suivants échouent en cascade — comportement observé
        dans le bug E2E.
        """
        # Aucune exception attendue.
        await log_tool_call(
            mock_db_no_conversation,
            user_id=mock_user_id,
            conversation_id=mock_conversation_id,
            node_name="chat",
            tool_name="cascading_tool",
            tool_args={},
        )

    @pytest.mark.asyncio
    async def test_skip_when_no_conversation_id_at_all(
        self, mock_db, mock_user_id, caplog,
    ):
        """Sans conversation_id ni account_id, on skippe (cas extrême)."""
        with caplog.at_level(logging.WARNING):
            await log_tool_call(
                mock_db,
                user_id=mock_user_id,
                conversation_id=None,
                node_name="chat",
                tool_name="orphan_tool",
                tool_args={},
            )

        mock_db.add.assert_not_called()


class TestWithRetryPropagatesAccountId:
    """``with_retry`` doit propager account_id du config vers log_tool_call."""

    @pytest.mark.asyncio
    async def test_with_retry_extracts_account_id_from_config(
        self,
        mock_db,
        mock_user_id,
        mock_account_id,
        mock_conversation_id,
    ):
        """Quand config['configurable']['account_id'] est présent, le succès
        log_tool_call doit le propager sur ToolCallLog (sans fallback DB)."""
        from app.graph.tools.common import with_retry

        async def my_tool(config=None):
            return "ok"

        wrapped = with_retry(my_tool, node_name="chat")

        config = {
            "configurable": {
                "db": mock_db,
                "user_id": mock_user_id,
                "account_id": mock_account_id,
                "conversation_id": mock_conversation_id,
                "thread_id": str(mock_conversation_id),
            }
        }

        result = await wrapped(config=config)
        assert result == "ok"

        # log_tool_call doit avoir été appelé avec account_id propagé.
        mock_db.add.assert_called()
        log_entry = mock_db.add.call_args[0][0]
        assert log_entry.account_id == mock_account_id

    @pytest.mark.asyncio
    async def test_with_retry_no_account_id_no_crash(
        self,
        mock_db_no_conversation,
        mock_user_id,
        mock_conversation_id,
    ):
        """Sans account_id ni dans config ni en BDD, with_retry ne crash pas
        et l'INSERT est skippé silencieusement."""
        from app.graph.tools.common import with_retry

        async def my_tool(config=None):
            return "ok"

        wrapped = with_retry(my_tool, node_name="chat")
        config = {
            "configurable": {
                "db": mock_db_no_conversation,
                "user_id": mock_user_id,
                "conversation_id": mock_conversation_id,
                "thread_id": str(mock_conversation_id),
                # PAS d'account_id ici, et le fallback DB renvoie None.
            }
        }

        # Aucune exception ne doit remonter.
        result = await wrapped(config=config)
        assert result == "ok"
        mock_db_no_conversation.add.assert_not_called()
