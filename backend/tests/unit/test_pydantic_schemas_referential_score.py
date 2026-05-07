"""F13 — Tests unitaires des schémas Pydantic pour referential_score (T006)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.referential_score import (
    BottleneckInfo,
    ComparisonResult,
    ComputedBy,
    CoveredCriterion,
    DualReferentialResponse,
    FinalizeAssessmentResult,
    GenerateReportRequest,
    MissingCriterion,
    MissingReason,
    PillarScore,
    RecomputeRequestResponse,
    ReferentialScoreCreate,
    ReferentialScoreRead,
)


def test_pillar_score_valid():
    p = PillarScore(score=Decimal("75.5"), weight=Decimal("0.33"), criteria_count=10, **{"criteria_renseignés": 8})
    assert p.score == Decimal("75.5")
    assert p.criteria_renseignes == 8


def test_pillar_score_score_out_of_bounds_raises():
    with pytest.raises(ValidationError):
        PillarScore(score=Decimal("101"), weight=Decimal("0.5"), criteria_count=10, **{"criteria_renseignés": 5})


def test_pillar_score_weight_out_of_bounds_raises():
    with pytest.raises(ValidationError):
        PillarScore(score=Decimal("50"), weight=Decimal("1.5"), criteria_count=10, **{"criteria_renseignés": 5})


def test_pillar_score_negative_count_raises():
    with pytest.raises(ValidationError):
        PillarScore(score=Decimal("50"), weight=Decimal("0.5"), criteria_count=-1, **{"criteria_renseignés": 0})


def test_covered_criterion_valid():
    c = CoveredCriterion(
        indicator_id=uuid.uuid4(),
        indicator_code="E1",
        score=Decimal("80"),
        weight=Decimal("0.2"),
        source_id=uuid.uuid4(),
    )
    assert c.indicator_code == "E1"


def test_covered_criterion_source_id_optional():
    """Permet ``source_id=None`` pour les indicateurs legacy F05 sans Source F01."""
    c = CoveredCriterion(
        indicator_id=uuid.uuid4(),
        indicator_code="E1",
        score=Decimal("80"),
        weight=Decimal("0.2"),
    )
    assert c.source_id is None


def test_missing_criterion_with_reason():
    m = MissingCriterion(
        indicator_id=uuid.uuid4(),
        indicator_code="S5",
        reason=MissingReason.NON_RENSEIGNE,
    )
    assert m.reason == MissingReason.NON_RENSEIGNE


def test_missing_criterion_invalid_reason_raises():
    with pytest.raises(ValidationError):
        MissingCriterion(
            indicator_id=uuid.uuid4(),
            indicator_code="S5",
            reason="invalid_reason",
        )


def test_referential_score_read_minimal():
    rs = ReferentialScoreRead(
        id=uuid.uuid4(),
        assessment_id=uuid.uuid4(),
        referential_id=uuid.uuid4(),
        referential_code="mefali",
        referential_name="ESG Mefali",
        referential_version="1.0",
        overall_score=Decimal("75"),
        pillar_scores={},
        coverage_rate=Decimal("0.85"),
        covered_criteria=[],
        missing_criteria=[],
        gap_to_threshold=Decimal("25"),
        eligibility=True,
        computed_at=datetime.now(timezone.utc),
        computed_by=ComputedBy.AUTO,
    )
    assert rs.is_fallback is False


def test_referential_score_create_validates_coverage_range():
    """coverage_rate doit être dans [0, 1]."""
    with pytest.raises(ValidationError):
        ReferentialScoreCreate(
            account_id=uuid.uuid4(),
            assessment_id=uuid.uuid4(),
            referential_id=uuid.uuid4(),
            referential_version="1.0",
            overall_score=Decimal("70"),
            pillar_scores={},
            coverage_rate=Decimal("1.5"),
            covered_criteria=[],
            missing_criteria=[],
            gap_to_threshold=None,
            eligibility=None,
            computed_by=ComputedBy.AUTO,
        )


def test_comparison_result_structure():
    cr = ComparisonResult(scores=[], gaps={"mefali_vs_ifc_ps": Decimal("26")}, divergent_criteria={})
    assert cr.gaps["mefali_vs_ifc_ps"] == Decimal("26")


def test_recompute_request_response_default():
    r = RecomputeRequestResponse(recompute_request_id=uuid.uuid4())
    assert r.status == "accepted"
    assert r.estimated_duration_seconds == 5


def test_finalize_assessment_result():
    fr = FinalizeAssessmentResult(
        assessment_id=uuid.uuid4(),
        finalized_at=datetime.now(timezone.utc),
        referential_scores=[],
        failures=[],
    )
    assert fr.failures == []


def test_bottleneck_info_structure():
    b = BottleneckInfo(
        bottleneck_referential_code="gcf",
        bottleneck_referential_name="Green Climate Fund",
        bottleneck_score=Decimal("45"),
        other_referential_code="boad_ess",
        other_referential_score=Decimal("68"),
        gap=Decimal("23"),
        eligibility_min=False,
        top_3_critical_indicators=["E1", "S2", "G3"],
    )
    assert b.eligibility_min is False
    assert len(b.top_3_critical_indicators) == 3


def test_dual_referential_response_no_intermediary():
    rs = ReferentialScoreRead(
        id=uuid.uuid4(),
        assessment_id=uuid.uuid4(),
        referential_id=uuid.uuid4(),
        referential_code="mefali",
        referential_name="ESG Mefali",
        referential_version="1.0",
        overall_score=Decimal("70"),
        pillar_scores={},
        coverage_rate=Decimal("0.5"),
        covered_criteria=[],
        missing_criteria=[],
        gap_to_threshold=Decimal("20"),
        eligibility=True,
        computed_at=datetime.now(timezone.utc),
        computed_by=ComputedBy.AUTO,
    )
    d = DualReferentialResponse(
        fund_score=rs,
        intermediary_score=None,
        bottleneck=None,
        is_dual_view=False,
    )
    assert d.is_dual_view is False
    assert d.intermediary_score is None


def test_generate_report_request_defaults():
    r = GenerateReportRequest()
    assert r.referentials == ["mefali"]
    assert r.include_appendix_sources is True
    assert r.format == "pdf"


def test_generate_report_request_extra_forbid():
    with pytest.raises(ValidationError):
        GenerateReportRequest(unknown_field="x")
