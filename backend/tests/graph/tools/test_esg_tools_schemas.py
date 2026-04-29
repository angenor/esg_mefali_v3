"""Tests unitaires des schemas Pydantic des tools ESG (story 10.1)."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.graph.tools.esg_tools import (
    BatchSaveESGCriteriaArgs,
    CreateESGAssessmentArgs,
    FinalizeESGAssessmentArgs,
    GetESGAssessmentArgs,
    SaveESGCriterionScoreArgs,
)


pytestmark = pytest.mark.unit

VALID_UUID = str(uuid.uuid4())


def test_create_empty_accepted():
    args = CreateESGAssessmentArgs()
    assert args is not None


def test_create_extra_forbidden():
    with pytest.raises(ValidationError) as exc:
        CreateESGAssessmentArgs(extra="x")
    assert any(e["type"] == "extra_forbidden" for e in exc.value.errors())


def _save_payload(**ov) -> dict:
    base = {
        "assessment_id": VALID_UUID,
        "criterion_code": "E1",
        "score": 8,
        "justification": "Politique de gestion des dechets en place.",
    }
    base.update(ov)
    return base


def test_save_valid():
    args = SaveESGCriterionScoreArgs(**_save_payload())
    assert args.criterion_code == "E1"
    assert args.score == 8


@pytest.mark.parametrize(
    "field,value",
    [
        ("assessment_id", "not-a-uuid"),
        ("criterion_code", "X1"),
        ("criterion_code", "e1"),
        ("criterion_code", "E"),
        ("score", -1),
        ("score", 11),
        ("justification", ""),
    ],
)
def test_save_invalid_rejected(field, value):
    with pytest.raises(ValidationError):
        SaveESGCriterionScoreArgs(**_save_payload(**{field: value}))


def test_save_extra_forbidden():
    with pytest.raises(ValidationError) as exc:
        SaveESGCriterionScoreArgs(**_save_payload(unknown="x"))
    assert any(e["type"] == "extra_forbidden" for e in exc.value.errors())


def _batch_payload(**ov) -> dict:
    base = {
        "assessment_id": VALID_UUID,
        "criteria": [
            {"criterion_code": "E1", "score": 7, "justification": "ok"},
            {"criterion_code": "E2", "score": 5, "justification": "moyen"},
        ],
    }
    base.update(ov)
    return base


def test_batch_valid():
    args = BatchSaveESGCriteriaArgs(**_batch_payload())
    assert len(args.criteria) == 2


@pytest.mark.parametrize(
    "criteria",
    [
        [],
        [{"criterion_code": "X1", "score": 5, "justification": "x"}],
        [{"criterion_code": "E1", "score": 99, "justification": "x"}],
        [{"criterion_code": "E1", "score": 5, "justification": ""}],
    ],
)
def test_batch_invalid_criteria(criteria):
    with pytest.raises(ValidationError):
        BatchSaveESGCriteriaArgs(**_batch_payload(criteria=criteria))


def test_batch_item_extra_forbidden():
    payload = _batch_payload(criteria=[
        {"criterion_code": "E1", "score": 5, "justification": "x", "junk": True},
    ])
    with pytest.raises(ValidationError) as exc:
        BatchSaveESGCriteriaArgs(**payload)
    assert any(e["type"] == "extra_forbidden" for e in exc.value.errors())


def test_batch_extra_forbidden():
    with pytest.raises(ValidationError) as exc:
        BatchSaveESGCriteriaArgs(**_batch_payload(unknown="x"))
    assert any(e["type"] == "extra_forbidden" for e in exc.value.errors())


def test_finalize_valid():
    args = FinalizeESGAssessmentArgs(assessment_id=VALID_UUID)
    assert args.assessment_id == VALID_UUID


def test_finalize_invalid_uuid():
    with pytest.raises(ValidationError):
        FinalizeESGAssessmentArgs(assessment_id="abc")


def test_finalize_extra_forbidden():
    with pytest.raises(ValidationError) as exc:
        FinalizeESGAssessmentArgs(assessment_id=VALID_UUID, junk=1)
    assert any(e["type"] == "extra_forbidden" for e in exc.value.errors())


def test_get_optional_id():
    args_none = GetESGAssessmentArgs()
    args_id = GetESGAssessmentArgs(assessment_id=VALID_UUID)
    assert args_none.assessment_id is None
    assert args_id.assessment_id == VALID_UUID


def test_get_invalid_uuid():
    with pytest.raises(ValidationError):
        GetESGAssessmentArgs(assessment_id="bad")


def test_get_extra_forbidden():
    with pytest.raises(ValidationError) as exc:
        GetESGAssessmentArgs(extra=1)
    assert any(e["type"] == "extra_forbidden" for e in exc.value.errors())
