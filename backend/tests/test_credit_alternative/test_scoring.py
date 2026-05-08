"""F18 — Tests du score combiné dynamique (FR-015 / FR-016 / SC-005)."""

from __future__ import annotations

import pytest

from app.modules.credit.alternative.scoring import (
    DEFAULT_TARGET_WEIGHTS,
    PUBLIC_DATA_CAP,
    CategoryInput,
    compute_combined_score,
)


def test_all_categories_present_returns_valid_combined_score():
    """Toutes les catégories disponibles → score combiné cohérent."""
    inputs = [
        CategoryInput("solvability", 80.0),
        CategoryInput("green_impact", 70.0),
        CategoryInput("mobile_money_flux", 60.0),
        CategoryInput("photos_ia", 50.0),
        CategoryInput("public_data", 90.0),
    ]
    result = compute_combined_score(inputs)
    # Sum of effective weights = 1
    total_w = sum(c.weight for c in result.categories)
    assert abs(total_w - 1.0) < 1e-6
    assert 0.0 <= result.combined_score <= 100.0
    # Public data MUST not exceed cap
    pd = next(c for c in result.categories if c.name == "public_data")
    assert pd.weight <= PUBLIC_DATA_CAP + 1e-9


def test_public_data_cap_strict_below_10pct():
    """FR-015 / SC-005 — même avec un poids cible élevé, public_data ≤ 10 %."""
    inputs = [
        CategoryInput("solvability", 50.0),
        CategoryInput("green_impact", 50.0),
        CategoryInput("public_data", 100.0),
    ]
    # Cible volontairement abusive : public_data = 50 %.
    result = compute_combined_score(
        inputs,
        target_weights={"solvability": 0.30, "green_impact": 0.20, "public_data": 0.50},
    )
    pd = next(c for c in result.categories if c.name == "public_data")
    assert pd.weight == pytest.approx(PUBLIC_DATA_CAP, abs=1e-6)
    assert pd.capped is True
    # Les autres catégories se partagent les 90 % restants au prorata.
    sol = next(c for c in result.categories if c.name == "solvability")
    gi = next(c for c in result.categories if c.name == "green_impact")
    assert sol.weight + gi.weight == pytest.approx(0.90, abs=1e-6)
    # Ratio préservé entre solvability et green_impact (30:20 = 3:2)
    assert sol.weight / gi.weight == pytest.approx(1.5, abs=1e-3)


def test_consent_revoked_excludes_category():
    """FR-016 — consent_active=False exclut la catégorie."""
    inputs = [
        CategoryInput("solvability", 80.0),
        CategoryInput("green_impact", 70.0),
        CategoryInput("mobile_money_flux", 90.0, consent_active=False),
    ]
    result = compute_combined_score(inputs)
    names = [c.name for c in result.categories]
    assert "mobile_money_flux" not in names
    assert "mobile_money_flux" in result.excluded


def test_unavailable_data_excludes_category():
    """available=False exclut la catégorie même avec consent."""
    inputs = [
        CategoryInput("solvability", 80.0),
        CategoryInput("green_impact", 70.0),
        CategoryInput("public_data", 50.0, available=False),
    ]
    result = compute_combined_score(inputs)
    assert "public_data" in result.excluded
    # Restent solvability + green_impact, normalisés sur 1.
    total = sum(c.weight for c in result.categories)
    assert abs(total - 1.0) < 1e-6


def test_only_solvability_and_green_impact_renormalized():
    """Cas legacy : seules les 2 catégories obligatoires → split au prorata."""
    inputs = [
        CategoryInput("solvability", 80.0),
        CategoryInput("green_impact", 60.0),
    ]
    result = compute_combined_score(inputs)
    # 0.40 / 0.30 → ratio 4:3 → poids effectifs 4/7 et 3/7
    sol = next(c for c in result.categories if c.name == "solvability")
    gi = next(c for c in result.categories if c.name == "green_impact")
    assert sol.weight == pytest.approx(4 / 7, abs=1e-3)
    assert gi.weight == pytest.approx(3 / 7, abs=1e-3)
    # Score = 80 * 4/7 + 60 * 3/7 ≈ 71.43
    assert result.combined_score == pytest.approx(71.4, abs=0.1)


def test_empty_inputs_returns_zero():
    """Cas dégénéré : aucune catégorie → score 0."""
    result = compute_combined_score([])
    assert result.combined_score == 0.0
    assert result.categories == ()


def test_confidence_multiplier_applied():
    """Confidence < 1 réduit linéairement le score combiné."""
    inputs = [
        CategoryInput("solvability", 100.0),
        CategoryInput("green_impact", 100.0),
    ]
    result_full = compute_combined_score(inputs, confidence=1.0)
    result_half = compute_combined_score(inputs, confidence=0.5)
    assert result_full.combined_score == 100.0
    assert result_half.combined_score == 50.0


def test_score_clamped_to_100():
    """Aucun score ne peut dépasser 100 même avec confidence > 1 (clamp)."""
    inputs = [CategoryInput("solvability", 100.0), CategoryInput("green_impact", 100.0)]
    # Confidence > 1 est clampé à 1
    result = compute_combined_score(inputs, confidence=2.0)
    assert result.combined_score == 100.0


def test_default_weights_sum_to_one():
    """DEFAULT_TARGET_WEIGHTS doit sommer à 1 (sanity check)."""
    assert sum(DEFAULT_TARGET_WEIGHTS.values()) == pytest.approx(1.0, abs=1e-6)


def test_public_data_alone_renormalizes_to_cap():
    """Edge case : seule public_data disponible → poids = cap, autres = 0."""
    inputs = [CategoryInput("public_data", 80.0)]
    result = compute_combined_score(inputs)
    # Cap appliqué : public_data prend cap, les autres = 0 (aucune autre).
    pd = next(c for c in result.categories if c.name == "public_data")
    # Aucune autre cat → public_data prend tout le poids restant (cas dégénéré)
    assert pd.weight == pytest.approx(1.0, abs=1e-6)


def test_score_breakdown_per_category_score_clamped():
    """Un score d'entrée > 100 est clampé à 100 dans le breakdown."""
    inputs = [
        CategoryInput("solvability", 150.0),  # invalide, doit clamper
        CategoryInput("green_impact", -10.0),  # invalide, doit clamper
    ]
    result = compute_combined_score(inputs)
    sol = next(c for c in result.categories if c.name == "solvability")
    gi = next(c for c in result.categories if c.name == "green_impact")
    assert sol.score == 100.0
    assert gi.score == 0.0
