"""T011 — Tests Pydantic strict des schemas F047."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.modules.esg.project_schemas import (
    ProjectEsgAssessmentCreate,
    ProjectEsgCriterionResponseSave,
)


class TestProjectEsgAssessmentCreate:
    def test_accepts_valid_referential_id(self):
        payload = ProjectEsgAssessmentCreate(referential_id=uuid.uuid4())
        assert payload.referential_id is not None

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError) as exc:
            ProjectEsgAssessmentCreate(
                referential_id=uuid.uuid4(),
                extra_field="boom",  # type: ignore[call-arg]
            )
        assert "extra_field" in str(exc.value) or "extra" in str(exc.value).lower()


class TestProjectEsgCriterionResponseSave:
    def _base_kwargs(self) -> dict:
        return {
            "criterion_id": uuid.uuid4(),
            "response_type": "qcu",
            "response_value": {"choice": "yes"},
        }

    def test_xor_accepts_only_source(self):
        save = ProjectEsgCriterionResponseSave(
            **self._base_kwargs(), source_id=uuid.uuid4(), unsourced=False,
        )
        assert save.source_id is not None and save.unsourced is False

    def test_xor_accepts_only_unsourced(self):
        save = ProjectEsgCriterionResponseSave(
            **self._base_kwargs(), source_id=None, unsourced=True,
        )
        assert save.source_id is None and save.unsourced is True

    def test_xor_rejects_both_set(self):
        with pytest.raises(ValidationError) as exc:
            ProjectEsgCriterionResponseSave(
                **self._base_kwargs(),
                source_id=uuid.uuid4(),
                unsourced=True,
            )
        assert "XOR" in str(exc.value) or "mutuellement" in str(exc.value)

    def test_xor_rejects_both_unset(self):
        with pytest.raises(ValidationError):
            ProjectEsgCriterionResponseSave(
                **self._base_kwargs(), source_id=None, unsourced=False,
            )

    def test_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            ProjectEsgCriterionResponseSave(
                **self._base_kwargs(),
                source_id=uuid.uuid4(),
                forbidden="x",  # type: ignore[call-arg]
            )

    def test_rejects_invalid_response_type(self):
        with pytest.raises(ValidationError):
            ProjectEsgCriterionResponseSave(
                criterion_id=uuid.uuid4(),
                response_type="bogus",  # type: ignore[arg-type]
                response_value={"x": 1},
                source_id=uuid.uuid4(),
            )
