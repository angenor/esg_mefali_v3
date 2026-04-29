"""Tests unitaires des schemas Pydantic du tool ask_interactive_question (story 10.1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.graph.tools.interactive_tools import AskInteractiveQuestionArgs


pytestmark = pytest.mark.unit


def _valid_payload(**overrides) -> dict:
    base = {
        "question_type": "qcu",
        "prompt": "Quel est ton secteur ?",
        "options": [
            {"id": "agri", "label": "Agriculture"},
            {"id": "energie", "label": "Energie"},
        ],
        "min_selections": 1,
        "max_selections": 1,
        "requires_justification": False,
    }
    base.update(overrides)
    return base


def test_valid_qcu_payload_accepted():
    args = AskInteractiveQuestionArgs(**_valid_payload())
    assert args.question_type.value == "qcu"
    assert len(args.options) == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("question_type", "invalid_type"),
        ("prompt", ""),
        ("prompt", "x" * 501),
        ("options", []),
        ("options", [{"id": "only", "label": "x"}]),
        ("min_selections", 0),
        ("max_selections", 9),
    ],
)
def test_invalid_field_rejected(field, value):
    payload = _valid_payload(**{field: value})
    with pytest.raises(ValidationError):
        AskInteractiveQuestionArgs(**payload)


def test_extra_field_forbidden():
    payload = _valid_payload(unknown_extra="boom")
    with pytest.raises(ValidationError) as exc:
        AskInteractiveQuestionArgs(**payload)
    errors = exc.value.errors()
    assert any(e["type"] == "extra_forbidden" for e in errors)
