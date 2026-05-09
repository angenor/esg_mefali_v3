"""Tests unitaires pour les helpers partagés des tools."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.graph.tools.common import get_db_and_user, log_tool_call, with_retry


class TestGetDbAndUser:
    """Tests pour get_db_and_user()."""

    def test_valid_config(self, mock_config, mock_db, mock_user_id):
        """Config valide retourne (db, user_id)."""
        db, user_id = get_db_and_user(mock_config)
        assert db is mock_db
        assert user_id == mock_user_id

    def test_user_id_as_string(self, mock_db):
        """user_id string est converti en UUID."""
        uid = uuid.UUID("00000000-0000-0000-0000-000000000042")
        config = {"configurable": {"db": mock_db, "user_id": str(uid)}}
        db, user_id = get_db_and_user(config)
        assert user_id == uid

    def test_missing_db_raises(self, mock_config_no_db):
        """Config sans db lève ValueError."""
        with pytest.raises(ValueError, match="Session DB manquante"):
            get_db_and_user(mock_config_no_db)

    def test_missing_user_id_raises(self, mock_config_no_user):
        """Config sans user_id lève ValueError."""
        with pytest.raises(ValueError, match="user_id manquant"):
            get_db_and_user(mock_config_no_user)

    def test_none_config_raises(self):
        """Config None lève ValueError."""
        with pytest.raises(ValueError):
            get_db_and_user(None)

    def test_empty_config_raises(self):
        """Config vide lève ValueError."""
        with pytest.raises(ValueError):
            get_db_and_user({})


class TestLogToolCall:
    """Tests pour log_tool_call()."""

    @pytest.mark.asyncio
    async def test_log_success(self, mock_db, mock_user_id, mock_account_id):
        """Log un appel réussi dans la BDD."""
        await log_tool_call(
            mock_db,
            user_id=mock_user_id,
            account_id=mock_account_id,
            conversation_id=None,
            node_name="esg_scoring_node",
            tool_name="save_esg_criterion_score",
            tool_args={"criterion_code": "E1", "score": 8},
            tool_result={"status": "saved"},
            duration_ms=150,
            status="success",
        )
        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()

        log_entry = mock_db.add.call_args[0][0]
        assert log_entry.tool_name == "save_esg_criterion_score"
        assert log_entry.status == "success"
        assert log_entry.retry_count == 0

    @pytest.mark.asyncio
    async def test_log_error(self, mock_db, mock_user_id, mock_account_id):
        """Log un appel en erreur avec message."""
        await log_tool_call(
            mock_db,
            user_id=mock_user_id,
            account_id=mock_account_id,
            conversation_id=None,
            node_name="profiling_node",
            tool_name="update_company_profile",
            tool_args={"sector": "agriculture"},
            status="error",
            error_message="DB connection failed",
            retry_count=1,
        )
        log_entry = mock_db.add.call_args[0][0]
        assert log_entry.status == "error"
        assert log_entry.error_message == "DB connection failed"
        assert log_entry.retry_count == 1

    @pytest.mark.asyncio
    async def test_log_retry_success(
        self, mock_db, mock_user_id, mock_account_id, mock_conversation_id,
    ):
        """Log un appel réussi après retry."""
        await log_tool_call(
            mock_db,
            user_id=mock_user_id,
            account_id=mock_account_id,
            conversation_id=mock_conversation_id,
            node_name="carbon_node",
            tool_name="save_emission_entry",
            tool_args={"category": "energy"},
            tool_result={"tco2e": 1.5},
            duration_ms=300,
            status="retry_success",
            retry_count=1,
        )
        log_entry = mock_db.add.call_args[0][0]
        assert log_entry.status == "retry_success"
        assert log_entry.conversation_id == mock_conversation_id


class TestWithRetry:
    """Tests pour with_retry()."""

    @pytest.mark.asyncio
    async def test_success_no_retry(self, mock_config):
        """Fonction réussie au premier appel — pas de retry."""
        async def my_tool(config=None):
            return "ok"

        wrapped = with_retry(my_tool, node_name="test_node")
        result = await wrapped(config=mock_config)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, mock_config):
        """Échec puis succès au retry — retourne le résultat du retry."""
        call_count = 0

        async def flaky_tool(config=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Temporary failure")
            return "recovered"

        wrapped = with_retry(flaky_tool, max_retries=1, node_name="test_node")
        result = await wrapped(config=mock_config)
        assert result == "recovered"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self, mock_config):
        """Échec persistant — retourne message d'erreur."""
        async def always_fail(config=None):
            raise ValueError("Permanent failure")

        wrapped = with_retry(always_fail, max_retries=1, node_name="test_node")
        result = await wrapped(config=mock_config)
        assert "Erreur" in result
        assert "Permanent failure" in result

    @pytest.mark.asyncio
    async def test_no_config_still_works(self):
        """Fonctionne sans config (pas de journalisation)."""
        async def simple_tool():
            return "no config ok"

        wrapped = with_retry(simple_tool, node_name="test")
        result = await wrapped()
        assert result == "no config ok"
