"""F045 T021 - Tests des 8 sub-scores projet + orchestrateur.

Couvre :
- _compute_project_score_sector / taxonomy / gcf_themes / co2_impact /
  beneficiaries / gender / vulnerable / project_esg
- _compute_project_score (orchestrateur) avec PROJECT_SCORE_WEIGHTS
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest


def _fake_project(**kwargs):
    defaults = {
        "objective_env": [],
        "taxonomie_verte_uemoa_aligned": None,
        "gcf_priority_themes": [],
        "gender_inclusion": None,
        "vulnerable_populations": [],
        "project_esg_score": None,
        "expected_impact_tco2e": None,
        "expected_beneficiaries": None,
    }
    return SimpleNamespace(**{**defaults, **kwargs})


def _fake_fund(**kwargs):
    defaults = {
        "sectors_eligible": [],
        "theme": [],
        "name": "Test Fund",
    }
    return SimpleNamespace(**{**defaults, **kwargs})


# ----- sector -----

def test_project_score_sector_hit():
    from app.modules.financing.matching_service import _compute_project_score_sector
    p = _fake_project(objective_env=["mitigation"])
    f = _fake_fund(sectors_eligible=["mitigation"])
    assert _compute_project_score_sector(p, f) == 100


def test_project_score_sector_miss():
    from app.modules.financing.matching_service import _compute_project_score_sector
    p = _fake_project(objective_env=["water"])
    f = _fake_fund(sectors_eligible=["mitigation"])
    assert _compute_project_score_sector(p, f) == 0


# ----- taxonomy -----

def test_project_score_taxonomy_aligned():
    from app.modules.financing.matching_service import _compute_project_score_taxonomy
    p = _fake_project(taxonomie_verte_uemoa_aligned=True)
    assert _compute_project_score_taxonomy(p, _fake_fund()) == 100


def test_project_score_taxonomy_not_aligned():
    from app.modules.financing.matching_service import _compute_project_score_taxonomy
    p = _fake_project(taxonomie_verte_uemoa_aligned=False)
    assert _compute_project_score_taxonomy(p, _fake_fund()) == 0


def test_project_score_taxonomy_null():
    from app.modules.financing.matching_service import _compute_project_score_taxonomy
    p = _fake_project(taxonomie_verte_uemoa_aligned=None)
    # Non evalue : 0 (sans source verified, on ne booste pas)
    assert _compute_project_score_taxonomy(p, _fake_fund()) == 0


# ----- gcf_themes -----

def test_project_score_gcf_themes_full_overlap():
    from app.modules.financing.matching_service import _compute_project_score_gcf_themes
    p = _fake_project(gcf_priority_themes=["adaptation", "REDD+"])
    f = _fake_fund(theme=["adaptation", "REDD+"])
    assert _compute_project_score_gcf_themes(p, f) == 100


def test_project_score_gcf_themes_partial_overlap():
    from app.modules.financing.matching_service import _compute_project_score_gcf_themes
    p = _fake_project(gcf_priority_themes=["adaptation", "REDD+"])
    f = _fake_fund(theme=["adaptation", "eau"])
    # Jaccard = 1 / 3 ≈ 33
    score = _compute_project_score_gcf_themes(p, f)
    assert 30 <= score <= 40


def test_project_score_gcf_themes_no_overlap():
    from app.modules.financing.matching_service import _compute_project_score_gcf_themes
    p = _fake_project(gcf_priority_themes=["agriculture"])
    f = _fake_fund(theme=["eau"])
    assert _compute_project_score_gcf_themes(p, f) == 0


def test_project_score_gcf_themes_empty_project():
    from app.modules.financing.matching_service import _compute_project_score_gcf_themes
    p = _fake_project(gcf_priority_themes=[])
    f = _fake_fund(theme=["adaptation"])
    assert _compute_project_score_gcf_themes(p, f) == 0


# ----- co2_impact -----

def test_project_score_co2_impact_above_threshold():
    from app.modules.financing.matching_service import _compute_project_score_co2_impact
    p = _fake_project(expected_impact_tco2e=Decimal("5000"))
    # Pas de seuil sur le fonds par defaut : 100
    assert _compute_project_score_co2_impact(p, _fake_fund()) == 100


def test_project_score_co2_impact_zero():
    from app.modules.financing.matching_service import _compute_project_score_co2_impact
    p = _fake_project(expected_impact_tco2e=None)
    assert _compute_project_score_co2_impact(p, _fake_fund()) == 0


# ----- beneficiaries -----

def test_project_score_beneficiaries_present():
    from app.modules.financing.matching_service import (
        _compute_project_score_beneficiaries,
    )
    p = _fake_project(expected_beneficiaries=2000)
    assert _compute_project_score_beneficiaries(p, _fake_fund()) >= 50


def test_project_score_beneficiaries_missing():
    from app.modules.financing.matching_service import (
        _compute_project_score_beneficiaries,
    )
    p = _fake_project(expected_beneficiaries=None)
    # Neutre 50 ou 0 selon design ; on accepte 0..50
    score = _compute_project_score_beneficiaries(p, _fake_fund())
    assert 0 <= score <= 50


# ----- gender -----

def test_project_score_gender_true():
    from app.modules.financing.matching_service import _compute_project_score_gender
    p = _fake_project(gender_inclusion=True)
    assert _compute_project_score_gender(p, _fake_fund()) == 100


def test_project_score_gender_false():
    from app.modules.financing.matching_service import _compute_project_score_gender
    p = _fake_project(gender_inclusion=False)
    assert _compute_project_score_gender(p, _fake_fund()) == 0


def test_project_score_gender_null():
    from app.modules.financing.matching_service import _compute_project_score_gender
    p = _fake_project(gender_inclusion=None)
    assert _compute_project_score_gender(p, _fake_fund()) == 50


# ----- vulnerable -----

def test_project_score_vulnerable_overlap():
    from app.modules.financing.matching_service import (
        _compute_project_score_vulnerable,
    )
    p = _fake_project(vulnerable_populations=["femmes", "jeunes"])
    f = _fake_fund(vulnerable_target=["femmes"])
    score = _compute_project_score_vulnerable(p, f)
    assert score > 0


def test_project_score_vulnerable_empty():
    from app.modules.financing.matching_service import (
        _compute_project_score_vulnerable,
    )
    p = _fake_project(vulnerable_populations=[])
    assert _compute_project_score_vulnerable(p, _fake_fund()) == 0


# ----- project_esg -----

def test_project_score_project_esg_set():
    from app.modules.financing.matching_service import _compute_project_score_project_esg
    p = _fake_project(project_esg_score=72)
    assert _compute_project_score_project_esg(p, _fake_fund()) == 72


def test_project_score_project_esg_null_neutral():
    from app.modules.financing.matching_service import _compute_project_score_project_esg
    p = _fake_project(project_esg_score=None)
    assert _compute_project_score_project_esg(p, _fake_fund()) == 50


# ----- Orchestrateur -----

def test_compute_project_score_weights_sum_to_one():
    from app.modules.financing.matching_service import PROJECT_SCORE_WEIGHTS
    assert abs(sum(PROJECT_SCORE_WEIGHTS.values()) - 1.0) < 1e-9
    assert set(PROJECT_SCORE_WEIGHTS.keys()) == {
        "sector", "taxonomy", "gcf_themes", "co2_impact",
        "beneficiaries", "gender", "vulnerable", "project_esg",
    }


def test_compute_project_score_full_aligned():
    """Projet pleinement aligne → score eleve."""
    from app.modules.financing.matching_service import _compute_project_score
    p = _fake_project(
        objective_env=["mitigation"],
        taxonomie_verte_uemoa_aligned=True,
        gcf_priority_themes=["adaptation", "REDD+"],
        gender_inclusion=True,
        vulnerable_populations=["femmes"],
        project_esg_score=85,
        expected_impact_tco2e=Decimal("5000"),
        expected_beneficiaries=2000,
    )
    f = _fake_fund(
        sectors_eligible=["mitigation"],
        theme=["adaptation", "REDD+"],
        vulnerable_target=["femmes"],
    )
    score, breakdown = _compute_project_score(p, f)
    assert score >= 80
    # Breakdown contient les 8 sub_scores
    assert "sub_scores" in breakdown or hasattr(breakdown, "sub_scores")
