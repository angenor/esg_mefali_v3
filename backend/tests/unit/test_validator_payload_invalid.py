"""F11 — Tests validator payload_invalid (Pydantic ValidationError).

Le validator est invoqué par les noeuds LangGraph quand un tool typed échoue
sa validation Pydantic. Politique :
- 1er passage (retry_count=0) : retourner un message d'erreur structuré au LLM
  avec retry demandé.
- 2e passage (retry_count=1) : fallback texte (pas de nouveau retry).

TDD strict : ce test doit FAIL initialement.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.graph.validators.payload_invalid import (
    PayloadInvalidResult,
    build_llm_error_message,
    handle_payload_invalid,
)
from app.schemas.visualization import KPICardArgs


def _build_validation_error() -> ValidationError:
    """Capture une vraie ValidationError sur KPICardArgs."""
    try:
        KPICardArgs(title="X" * 200, value="x")  # title > 120
    except ValidationError as exc:
        return exc
    raise RuntimeError("Should have raised")


class TestBuildLLMErrorMessage:
    def test_message_contient_schema_name(self) -> None:
        exc = _build_validation_error()
        msg = build_llm_error_message(
            tool_name="show_kpi_card",
            schema_name="KPICardArgs",
            error=exc,
        )
        assert "show_kpi_card" in msg
        assert "KPICardArgs" in msg

    def test_message_mentionne_retry(self) -> None:
        """Le message demande explicitement de retenter avec un payload conforme."""
        exc = _build_validation_error()
        msg = build_llm_error_message(
            tool_name="show_kpi_card",
            schema_name="KPICardArgs",
            error=exc,
        )
        # Doit suggérer à la fois retry et fallback texte.
        assert "retente" in msg.lower() or "retry" in msg.lower() or "réessaie" in msg.lower()

    def test_message_lists_invalid_field(self) -> None:
        exc = _build_validation_error()
        msg = build_llm_error_message(
            tool_name="show_kpi_card",
            schema_name="KPICardArgs",
            error=exc,
        )
        # Le champ title figure dans le message
        assert "title" in msg.lower()


class TestHandlePayloadInvalid:
    def test_first_attempt_requires_retry(self) -> None:
        exc = _build_validation_error()
        result = handle_payload_invalid(
            tool_name="show_kpi_card",
            schema_name="KPICardArgs",
            error=exc,
            retry_count=0,
        )
        assert isinstance(result, PayloadInvalidResult)
        assert result.requires_retry is True
        assert result.fallback_text is None
        assert result.llm_error_message is not None

    def test_second_attempt_fallback_text(self) -> None:
        exc = _build_validation_error()
        result = handle_payload_invalid(
            tool_name="show_kpi_card",
            schema_name="KPICardArgs",
            error=exc,
            retry_count=1,
        )
        assert result.requires_retry is False
        assert result.fallback_text is not None
        # Le message d'origine LLM doit mentionner que la visualisation
        # n'a pas pu être générée.
        assert (
            "visualisation" in result.fallback_text.lower()
            or "visualisations" in result.fallback_text.lower()
            or "rendre" in result.fallback_text.lower()
            or "afficher" in result.fallback_text.lower()
        )


class TestPayloadInvalidResult:
    def test_dataclass_frozen(self) -> None:
        """Le résultat est immuable (immutabilité conforme aux règles communes)."""
        result = PayloadInvalidResult(
            requires_retry=False,
            fallback_text="x",
            llm_error_message=None,
        )
        with pytest.raises((AttributeError, TypeError)):
            result.requires_retry = True  # type: ignore[misc]
