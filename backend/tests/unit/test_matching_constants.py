"""F045 T007 - Tests des whitelists FR matching_constants.

Verifie les 8 valeurs FR de PROJECT_GCF_PRIORITY_THEMES_VALUES et les 5
valeurs FR de PROJECT_VULNERABLE_POPULATIONS_VALUES avec les accents
obligatoires (é è ê à ç ô).
"""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_gcf_priority_themes_has_8_values_with_accents() -> None:
    from app.core.matching_constants import PROJECT_GCF_PRIORITY_THEMES_VALUES

    expected = {
        "atténuation",
        "adaptation",
        "cross_cutting",
        "REDD+",
        "forêts",
        "eau",
        "agriculture",
        "énergie",
    }
    assert PROJECT_GCF_PRIORITY_THEMES_VALUES == expected
    assert isinstance(PROJECT_GCF_PRIORITY_THEMES_VALUES, frozenset)
    # accents preserves
    assert "atténuation" in PROJECT_GCF_PRIORITY_THEMES_VALUES
    assert "forêts" in PROJECT_GCF_PRIORITY_THEMES_VALUES
    assert "énergie" in PROJECT_GCF_PRIORITY_THEMES_VALUES


@pytest.mark.unit
def test_vulnerable_populations_has_5_values_with_accents() -> None:
    from app.core.matching_constants import PROJECT_VULNERABLE_POPULATIONS_VALUES

    expected = {
        "femmes",
        "jeunes",
        "handicapés",
        "réfugiés",
        "déplacés_internes",
    }
    assert PROJECT_VULNERABLE_POPULATIONS_VALUES == expected
    assert isinstance(PROJECT_VULNERABLE_POPULATIONS_VALUES, frozenset)
    assert "handicapés" in PROJECT_VULNERABLE_POPULATIONS_VALUES
    assert "réfugiés" in PROJECT_VULNERABLE_POPULATIONS_VALUES
    assert "déplacés_internes" in PROJECT_VULNERABLE_POPULATIONS_VALUES


@pytest.mark.unit
def test_whitelists_are_immutable_frozensets() -> None:
    from app.core.matching_constants import (
        PROJECT_GCF_PRIORITY_THEMES_VALUES,
        PROJECT_VULNERABLE_POPULATIONS_VALUES,
    )

    with pytest.raises(AttributeError):
        PROJECT_GCF_PRIORITY_THEMES_VALUES.add("invalid")  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        PROJECT_VULNERABLE_POPULATIONS_VALUES.add("invalid")  # type: ignore[attr-defined]
