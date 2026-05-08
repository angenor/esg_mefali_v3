"""Tests unitaires des schemas Pydantic F14."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.modules.financing.matching_schemas import (
    ComparisonResult,
    ComparisonRow,
    ComparisonSubject,
    ComparisonValue,
    MatchAlertSubscriptionUpdate,
    MatchSubBreakdown,
    MissingCriterion,
    OfferMatchRead,
    RecomputeMatchesResponse,
    ScoreBreakdown,
)


def test_missing_criterion_minimal():
    mc = MissingCriterion(label="Critère X")
    assert mc.label == "Critère X"


def test_missing_criterion_frozen():
    mc = MissingCriterion(label="X")
    with pytest.raises(ValidationError):
        mc.label = "Y"  # type: ignore[misc]


def test_match_sub_breakdown_score_bounds():
    """Tous les sub-scores doivent être dans [0, 100]."""
    breakdown = MatchSubBreakdown(
        sector_match=100,
        esg_match=50,
        size_match=0,
        location_match=80,
        documents_match=40,
        instrument_match=70,
    )
    assert breakdown.sector_match == 100


def test_match_sub_breakdown_rejects_out_of_bounds():
    with pytest.raises(ValidationError):
        MatchSubBreakdown(
            sector_match=101,
            esg_match=0, size_match=0, location_match=0,
            documents_match=0, instrument_match=0,
        )


def test_score_breakdown_assembly():
    sub = MatchSubBreakdown(
        sector_match=80, esg_match=60, size_match=50,
        location_match=40, documents_match=30, instrument_match=20,
    )
    breakdown = ScoreBreakdown(
        fund=sub, intermediary=sub, assessment_missing=False,
    )
    assert breakdown.fund.sector_match == 80
    assert breakdown.assessment_missing is False


def test_offer_match_read_validates_bottleneck():
    payload = {
        "id": uuid.uuid4(),
        "account_id": uuid.uuid4(),
        "project_id": uuid.uuid4(),
        "offer_id": uuid.uuid4(),
        "global_score": 50, "fund_score": 50, "intermediary_score": 50,
        "score_breakdown": {},
        "bottleneck": "balanced",
        "recommended_actions": [],
        "status": "suggested",
        "computed_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc),
    }
    m = OfferMatchRead.model_validate(payload)
    assert m.bottleneck == "balanced"


def test_offer_match_read_rejects_bad_bottleneck():
    payload = {
        "id": uuid.uuid4(),
        "account_id": uuid.uuid4(),
        "project_id": uuid.uuid4(),
        "offer_id": uuid.uuid4(),
        "global_score": 50, "fund_score": 50, "intermediary_score": 50,
        "score_breakdown": {},
        "bottleneck": "invalid",
        "recommended_actions": [],
        "status": "suggested",
        "computed_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc),
    }
    with pytest.raises(ValidationError):
        OfferMatchRead.model_validate(payload)


def test_recompute_matches_response():
    r = RecomputeMatchesResponse(
        recompute_request_id=uuid.uuid4(),
        total_offers_to_compute=10,
    )
    assert r.total_offers_to_compute == 10


def test_recompute_matches_rejects_negative():
    with pytest.raises(ValidationError):
        RecomputeMatchesResponse(
            recompute_request_id=uuid.uuid4(),
            total_offers_to_compute=-1,
        )


def test_match_alert_subscription_update_partial():
    upd = MatchAlertSubscriptionUpdate(is_active=False)
    assert upd.is_active is False
    assert upd.min_global_score is None


def test_match_alert_subscription_update_score_bounds():
    with pytest.raises(ValidationError):
        MatchAlertSubscriptionUpdate(min_global_score=101)


def test_comparison_result_minimal():
    c = ComparisonResult(
        fund_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        subjects=[
            ComparisonSubject(id="o1", label="Offer 1"),
        ],
        rows=[
            ComparisonRow(
                key="score",
                label="Score",
                values=[
                    ComparisonValue(
                        subject_id="o1", raw=80, display="80", is_winner=True,
                    ),
                ],
            ),
        ],
    )
    assert len(c.subjects) == 1
    assert c.rows[0].values[0].is_winner is True
