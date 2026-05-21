"""F045 T011 - Tests Pydantic v2 strict pour ProjectScoreBreakdown.

Verifie :
- extra='forbid' refuse les cles inconnues
- sub_scores : ranges 0..100 obligatoires
- MissingCriterionSchema : ``kind`` Literal restreint
- SourceUsedSchema : ``sub_score`` Literal restreint
- ProjectScoreBreakdown : missing_criteria max_length=5
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError


@pytest.mark.unit
def test_project_sub_scores_accepts_valid_range() -> None:
    from app.modules.financing.matching_schemas import ProjectSubScoresSchema

    s = ProjectSubScoresSchema(
        sector=100,
        taxonomy=100,
        gcf_themes=75,
        co2_impact=60,
        beneficiaries=80,
        gender=100,
        vulnerable=50,
        project_esg=70,
    )
    assert s.sector == 100


@pytest.mark.unit
def test_project_sub_scores_rejects_out_of_range() -> None:
    from app.modules.financing.matching_schemas import ProjectSubScoresSchema

    with pytest.raises(ValidationError):
        ProjectSubScoresSchema(
            sector=101, taxonomy=0, gcf_themes=0, co2_impact=0,
            beneficiaries=0, gender=0, vulnerable=0, project_esg=0,
        )


@pytest.mark.unit
def test_project_sub_scores_rejects_extra_key() -> None:
    from app.modules.financing.matching_schemas import ProjectSubScoresSchema

    with pytest.raises(ValidationError):
        ProjectSubScoresSchema(
            sector=0, taxonomy=0, gcf_themes=0, co2_impact=0,
            beneficiaries=0, gender=0, vulnerable=0, project_esg=0,
            extra="nope",  # type: ignore[call-arg]
        )


@pytest.mark.unit
def test_missing_criterion_schema_kind_literal() -> None:
    from app.modules.financing.matching_schemas import MissingCriterionSchema

    c = MissingCriterionSchema(
        key="co2_impact_below_threshold",
        label_fr="Impact CO2 sous seuil",
        kind="below_threshold",
        current_value=450,
        target_value=1000,
    )
    assert c.kind == "below_threshold"

    with pytest.raises(ValidationError):
        MissingCriterionSchema(
            key="x", label_fr="x", kind="unknown",  # type: ignore[arg-type]
        )


@pytest.mark.unit
def test_source_used_schema_sub_score_literal() -> None:
    from app.modules.financing.matching_schemas import SourceUsedSchema

    s = SourceUsedSchema(
        sub_score="taxonomy",
        source_id=uuid.uuid4(),
        source_name="BCEAO Taxonomie 2024",
    )
    assert s.sub_score == "taxonomy"

    with pytest.raises(ValidationError):
        SourceUsedSchema(
            sub_score="invalid",  # type: ignore[arg-type]
            source_id=uuid.uuid4(),
            source_name="x",
        )


@pytest.mark.unit
def test_project_score_breakdown_max_5_missing_criteria() -> None:
    from app.modules.financing.matching_schemas import (
        BoostAppliedSchema,
        MissingCriterionSchema,
        ProjectScoreBreakdown,
        ProjectSubScoresSchema,
    )

    sub = ProjectSubScoresSchema(
        sector=100, taxonomy=100, gcf_themes=100, co2_impact=100,
        beneficiaries=100, gender=100, vulnerable=100, project_esg=100,
    )
    missing = [
        MissingCriterionSchema(key=f"k{i}", label_fr=f"L{i}", kind="missing")
        for i in range(6)
    ]
    with pytest.raises(ValidationError):
        ProjectScoreBreakdown(
            sub_scores=sub,
            missing_criteria=missing,
            boost_applied=BoostAppliedSchema(rule_triggered=False),
            computed_at=datetime.now(timezone.utc),
            factor_status="ok",
        )

    # 5 missing OK
    ProjectScoreBreakdown(
        sub_scores=sub,
        missing_criteria=missing[:5],
        boost_applied=BoostAppliedSchema(rule_triggered=False),
        computed_at=datetime.now(timezone.utc),
        factor_status="ok",
    )


@pytest.mark.unit
def test_match_funds_request_validation() -> None:
    from app.modules.financing.matching_schemas import MatchFundsRequest

    r = MatchFundsRequest(min_score=60, limit=10, force_recompute=False)
    assert r.min_score == 60

    with pytest.raises(ValidationError):
        MatchFundsRequest(min_score=-1)
    with pytest.raises(ValidationError):
        MatchFundsRequest(limit=51)
