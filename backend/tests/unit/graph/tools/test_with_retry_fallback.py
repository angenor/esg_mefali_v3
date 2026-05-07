"""Tests TDD pour l'extension F22 du décorateur ``with_retry``.

Vérifie l'ajout des paramètres ``fallback_message`` et la capture spécifique
de ``pydantic.ValidationError`` (sérialisée en JSONB via ``e.errors()``).

Réf : ``specs/032-decision-tree-with-retry-eval/{spec.md, data-model.md}``.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field, ValidationError

from app.graph.tools.common import (
    log_tool_call,
    requires_destructive_confirmation,
    with_retry,
)


pytestmark = pytest.mark.unit


@pytest.fixture
def mock_user_id() -> uuid.UUID:
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def mock_conversation_id() -> uuid.UUID:
    return uuid.UUID("00000000-0000-0000-0000-000000000099")


@pytest.fixture
def mock_db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def mock_config(mock_db, mock_user_id, mock_conversation_id) -> RunnableConfig:
    return {
        "configurable": {
            "db": mock_db,
            "user_id": mock_user_id,
            "conversation_id": mock_conversation_id,
        },
    }


def _trigger_validation_error() -> ValidationError:
    """Génère une vraie ValidationError Pydantic pour les tests."""

    class _S(BaseModel):
        sector: str = Field(..., min_length=1)

    try:
        _S(sector="")
    except ValidationError as exc:
        return exc
    raise AssertionError("La validation aurait dû échouer.")


# ─── 1. Décorateur paramétré ────────────────────────────────────────────────


class TestWithRetryDecoratorSyntax:
    """Le décorateur supporte la double-syntaxe legacy + paramétrée."""

    @pytest.mark.asyncio
    async def test_legacy_syntax_no_paren(self, mock_config):
        """``@with_retry`` sans parenthèses (legacy) → fonctionne."""

        async def my_tool(config=None):
            return "ok"

        wrapped = with_retry(my_tool, node_name="test")
        assert await wrapped(config=mock_config) == "ok"

    @pytest.mark.asyncio
    async def test_paramatrized_syntax(self, mock_config):
        """``@with_retry(max_retries=1, fallback_message="...")`` → fonctionne."""

        @with_retry(max_retries=1, node_name="test", fallback_message="fallback")
        async def my_tool(config=None):
            return "ok"

        assert await my_tool(config=mock_config) == "ok"


# ─── 2. ValidationError → validation_error rempli, errors() ─────────────────


class TestValidationErrorCapture:
    """Pydantic ValidationError est sérialisée via .errors() dans validation_error."""

    @pytest.mark.asyncio
    async def test_validation_error_logged_then_retry_success(
        self, mock_config, mock_db
    ):
        """Échec ValidationError → retry → succès. validation_error peuplé."""
        attempts = {"n": 0}

        async def flaky(config=None):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise _trigger_validation_error()
            return "recovered"

        wrapped = with_retry(flaky, max_retries=1, node_name="test")
        result = await wrapped(config=mock_config)
        assert result == "recovered"
        assert attempts["n"] == 2

        # 2 entrées loggées (retry error + success retry_success).
        assert mock_db.add.call_count == 2
        retry_log = mock_db.add.call_args_list[0][0][0]
        success_log = mock_db.add.call_args_list[1][0][0]

        assert retry_log.status == "error"
        # validation_error doit être peuplé sur l'entrée d'erreur
        assert retry_log.validation_error is not None
        assert isinstance(retry_log.validation_error, list)
        assert len(retry_log.validation_error) >= 1
        assert "loc" in retry_log.validation_error[0]
        assert "msg" in retry_log.validation_error[0]
        assert "type" in retry_log.validation_error[0]

        # Le succès final n'a pas de validation_error
        assert success_log.status == "retry_success"
        assert success_log.retry_count == 1

    @pytest.mark.asyncio
    async def test_runtime_exception_validation_error_null(
        self, mock_config, mock_db
    ):
        """Runtime exception (non-Pydantic) → validation_error null."""

        async def always_fail_runtime(config=None):
            raise RuntimeError("DB down")

        wrapped = with_retry(always_fail_runtime, max_retries=1, node_name="test")
        result = await wrapped(config=mock_config)
        assert "Erreur" in result
        # 2 logs (retry + final), validation_error null sur les deux
        for call in mock_db.add.call_args_list:
            log = call[0][0]
            assert log.validation_error is None


# ─── 3. fallback_message ────────────────────────────────────────────────────


class TestFallbackMessage:
    """Si retry échoue ET fallback_message fourni → JSON structuré."""

    @pytest.mark.asyncio
    async def test_fallback_message_returned_on_persistent_failure(
        self, mock_config
    ):
        """Échec persistant + fallback_message → JSON ``{success: false, fallback_message}``."""

        @with_retry(
            max_retries=1,
            node_name="test",
            fallback_message="Je ne peux pas formaliser. Reformulez ?",
        )
        async def always_fail(config=None):
            raise _trigger_validation_error()

        result = await always_fail(config=mock_config)
        # Le retour DOIT être un JSON sérialisé (parsable).
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert parsed["fallback_message"] == "Je ne peux pas formaliser. Reformulez ?"

    @pytest.mark.asyncio
    async def test_legacy_no_fallback_returns_legacy_error(self, mock_config):
        """Sans fallback_message → comportement legacy ``f"Erreur : {e}"``."""

        async def always_fail(config=None):
            raise ValueError("boom")

        wrapped = with_retry(always_fail, max_retries=1, node_name="test")
        result = await wrapped(config=mock_config)
        assert isinstance(result, str)
        assert result.startswith("Erreur")
        assert "boom" in result


# ─── 4. Premier coup OK → validation_error null ─────────────────────────────


class TestFirstCallSuccess:
    """Succès du premier coup → validation_error null, retry_count=0."""

    @pytest.mark.asyncio
    async def test_success_first_call_no_validation_error(
        self, mock_config, mock_db
    ):
        async def my_tool(config=None):
            return "fast ok"

        wrapped = with_retry(my_tool, node_name="test")
        result = await wrapped(config=mock_config)
        assert result == "fast ok"

        # 1 seul log success, validation_error null
        assert mock_db.add.call_count == 1
        log = mock_db.add.call_args[0][0]
        assert log.status == "success"
        assert log.retry_count == 0
        assert log.validation_error is None


# ─── 5. requires_destructive_confirmation passthrough ───────────────────────


class TestDestructiveConfirmationPassthrough:
    """Le marker destructif est traité comme un succès (pas de retry)."""

    @pytest.mark.asyncio
    async def test_marker_returned_no_retry(self, mock_config, mock_db):
        """Le tool retourne le marker → pas d'exception → pas de retry."""

        @with_retry(max_retries=1, node_name="test", fallback_message="x")
        async def destructive_tool(config=None):
            return requires_destructive_confirmation("delete_project")

        result = await destructive_tool(config=mock_config)
        # Le marker est un JSON sérialisé contenant requires_confirmation.
        parsed = json.loads(result)
        assert parsed["requires_confirmation"] is True

        # 1 seul log (success — pas de retry).
        assert mock_db.add.call_count == 1


# ─── 6. log_tool_call accepte validation_error ──────────────────────────────


class TestLogToolCallSignatureExtended:
    """``log_tool_call`` accepte un nouveau paramètre ``validation_error``."""

    @pytest.mark.asyncio
    async def test_log_with_validation_error(self, mock_db, mock_user_id):
        errors_payload = [
            {
                "type": "missing",
                "loc": ["sector"],
                "msg": "Field required",
                "input": {},
            }
        ]
        await log_tool_call(
            mock_db,
            user_id=mock_user_id,
            conversation_id=None,
            node_name="profiling_node",
            tool_name="update_company_profile",
            tool_args={"company_name": "Acme"},
            status="error",
            error_message="ValidationError",
            retry_count=1,
            validation_error=errors_payload,
        )
        log_entry = mock_db.add.call_args[0][0]
        assert log_entry.validation_error == errors_payload
