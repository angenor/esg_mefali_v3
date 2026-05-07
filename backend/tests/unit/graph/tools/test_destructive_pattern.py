"""Tests F10 — Helper requires_destructive_confirmation (T006).

Vérifie le format JSON retourné, la liste DESTRUCTIVE_ACTIONS, et le
garde-fou contre les actions non enregistrées.

Couvre FR-011, FR-012, contracts/destructive_pattern.md.
"""

from __future__ import annotations

import json

import pytest

from app.graph.tools.common import (
    DESTRUCTIVE_ACTIONS,
    requires_destructive_confirmation,
)


class TestRequiresDestructiveConfirmation:
    def test_returns_marker_for_known_action(self) -> None:
        result = requires_destructive_confirmation("delete_project")
        parsed = json.loads(result)
        assert parsed["requires_confirmation"] is True
        assert parsed["destructive_action"] == "delete_project"
        assert "ask_yes_no" in parsed["message"]

    def test_destructive_actions_includes_minimum_set(self) -> None:
        # FR-013 : minimum requis
        for action in (
            "delete_project",
            "delete_application",
            "delete_assessment",
            "delete_carbon_assessment",
            "revoke_attestation",
            "cancel_application",
        ):
            assert action in DESTRUCTIVE_ACTIONS, (
                f"{action} doit être dans DESTRUCTIVE_ACTIONS"
            )

    def test_rejects_unregistered_action(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            requires_destructive_confirmation("not_a_destructive_action")
        assert "DESTRUCTIVE_ACTIONS" in str(exc_info.value)

    def test_message_mentions_confirm_true(self) -> None:
        result = requires_destructive_confirmation("delete_project")
        parsed = json.loads(result)
        assert "confirm=True" in parsed["message"]

    def test_returns_valid_json(self) -> None:
        # Le retour doit être un JSON sérialisable interprétable par le LLM.
        result = requires_destructive_confirmation("revoke_attestation")
        parsed = json.loads(result)
        assert isinstance(parsed, dict)
        assert {"requires_confirmation", "message", "destructive_action"} <= parsed.keys()
