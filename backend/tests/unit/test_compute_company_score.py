"""F045 T022 - Tests refactor de _compute_company_score.

Heritage F14 (sector=0.25, esg=0.30, size=0.15, location=0.10, documents=0.10,
instrument=0.10). Cette fonction encapsule la logique de scoring entreprise
existante apres le refactor F045.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def _fake_project(**kwargs):
    return SimpleNamespace(
        objective_env=kwargs.get("objective_env", ["mitigation"]),
        target_amount_amount=None,
        target_amount_currency=None,
        location_country=kwargs.get("location_country", "TG"),
        financing_structure=kwargs.get("financing_structure", "subvention"),
        project_documents=kwargs.get("project_documents", []),
    )


def _fake_fund(**kwargs):
    return SimpleNamespace(
        sectors_eligible=kwargs.get("sectors_eligible", ["mitigation"]),
        min_amount_money=None,
        max_amount_money=None,
        eligibility_criteria=kwargs.get("eligibility_criteria", {}),
        instruments=kwargs.get("instruments", ["subvention"]),
    )


def _fake_offer(effective_required_documents=None):
    return SimpleNamespace(
        effective_required_documents=effective_required_documents or [],
    )


def test_compute_company_score_returns_int_0_100_no_esg():
    from app.modules.financing.matching_service import _compute_company_score

    p = _fake_project()
    f = _fake_fund()
    o = _fake_offer()
    score, breakdown = _compute_company_score(p, o, f, esg_fund_score=50)
    assert 0 <= score <= 100
    assert isinstance(breakdown, dict)


def test_compute_company_score_high_with_full_alignment():
    from app.modules.financing.matching_service import _compute_company_score

    p = _fake_project()
    f = _fake_fund()
    o = _fake_offer()
    score, _ = _compute_company_score(p, o, f, esg_fund_score=90)
    assert score >= 50


def test_compute_company_score_low_when_sector_misses():
    from app.modules.financing.matching_service import _compute_company_score

    p = _fake_project(objective_env=["water"])  # secteur hors fonds
    f = _fake_fund(sectors_eligible=["mitigation"])
    o = _fake_offer()
    score, _ = _compute_company_score(p, o, f, esg_fund_score=20)
    # Score plus bas qu'avec un secteur aligne
    assert score < 70
