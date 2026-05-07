"""F11 — Tests Pydantic stricts pour MatchCardArgs.

TDD strict : ces tests doivent FAIL initialement (avant T010).
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.visualization import MatchCardArgs


def _valid_match_payload(**overrides):
    """Payload MatchCardArgs minimal valide."""
    base = {
        "project_id": uuid.uuid4(),
        "offer_id": uuid.uuid4(),
        "fund_name": "Green Climate Fund",
        "intermediary_name": "BOAD",
        "compatibility_score": 78,
        "amount_range": "1-5 M FCFA",
        "timeline": "12-18 mois",
        "instruments": ["subvention", "blending"],
        "missing_criteria_count": 2,
        "drilldown_url": "/financing/offers/abc",
    }
    base.update(overrides)
    return base


class TestMatchCardArgsValidation:
    """Validation des champs et bornes."""

    def test_valid_minimal(self) -> None:
        args = MatchCardArgs(**_valid_match_payload())
        assert args.fund_name == "Green Climate Fund"
        assert args.compatibility_score == 78
        assert args.cta_label == "Explorer"  # défaut

    def test_valid_full(self) -> None:
        args = MatchCardArgs(**_valid_match_payload(
            fund_logo_url="https://logo.example/fund.png",
            intermediary_logo_url="https://logo.example/inter.png",
            compatibility_breakdown={"fund_score": 80, "intermediary_score": 65},
            cta_label="Voir le détail",
        ))
        assert args.compatibility_breakdown["fund_score"] == 80

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            MatchCardArgs(**_valid_match_payload(hallucinated="x"))

    def test_score_borne_low(self) -> None:
        with pytest.raises(ValidationError):
            MatchCardArgs(**_valid_match_payload(compatibility_score=-1))

    def test_score_borne_high(self) -> None:
        with pytest.raises(ValidationError):
            MatchCardArgs(**_valid_match_payload(compatibility_score=101))

    def test_score_zero_ok(self) -> None:
        args = MatchCardArgs(**_valid_match_payload(compatibility_score=0))
        assert args.compatibility_score == 0

    def test_score_hundred_ok(self) -> None:
        args = MatchCardArgs(**_valid_match_payload(compatibility_score=100))
        assert args.compatibility_score == 100

    def test_instruments_min_length(self) -> None:
        """instruments vide rejeté (min_length=1)."""
        with pytest.raises(ValidationError):
            MatchCardArgs(**_valid_match_payload(instruments=[]))

    def test_instruments_max_length(self) -> None:
        """instruments > 8 rejeté."""
        with pytest.raises(ValidationError):
            MatchCardArgs(**_valid_match_payload(instruments=["x"] * 9))

    def test_missing_criteria_count_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MatchCardArgs(**_valid_match_payload(missing_criteria_count=-1))

    def test_missing_criteria_count_too_high(self) -> None:
        with pytest.raises(ValidationError):
            MatchCardArgs(**_valid_match_payload(missing_criteria_count=100))

    def test_invalid_uuid_project(self) -> None:
        with pytest.raises(ValidationError):
            MatchCardArgs(**_valid_match_payload(project_id="not-a-uuid"))

    def test_drilldown_url_required(self) -> None:
        payload = _valid_match_payload()
        del payload["drilldown_url"]
        with pytest.raises(ValidationError):
            MatchCardArgs(**payload)

    def test_fund_name_max_length(self) -> None:
        with pytest.raises(ValidationError):
            MatchCardArgs(**_valid_match_payload(fund_name="X" * 121))

    def test_amount_range_required(self) -> None:
        payload = _valid_match_payload()
        del payload["amount_range"]
        with pytest.raises(ValidationError):
            MatchCardArgs(**payload)

    def test_cta_label_default(self) -> None:
        args = MatchCardArgs(**_valid_match_payload())
        assert args.cta_label == "Explorer"

    def test_cta_label_max_length(self) -> None:
        with pytest.raises(ValidationError):
            MatchCardArgs(**_valid_match_payload(cta_label="X" * 41))
