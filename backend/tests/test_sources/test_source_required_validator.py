"""Tests du validator source_required (F01).

10 cas couvrant : detection, ignored, retry, fallback, multi-paragraphe.
"""

from __future__ import annotations

import pytest

from app.graph.validators.source_required import (
    FALLBACK_TEXT,
    detect_claims,
    validate_response,
)


def test_detect_no_claim() -> None:
    """Texte sans chiffre : 0 grappe detectee."""
    text = "Bonjour, votre profil est complet."
    claims = detect_claims(text)
    assert claims == []


def test_detect_kgco2e_claim() -> None:
    """0,41 kgCO2e/kWh est detecte."""
    text = "Le facteur d'emission est de 0,41 kgCO2e/kWh."
    claims = detect_claims(text)
    assert len(claims) >= 1


def test_detect_percent_claim() -> None:
    """75% est detecte."""
    text = "Votre score atteint 75% sur le pilier social."
    claims = detect_claims(text)
    assert len(claims) >= 1


def test_detect_score_sur_100() -> None:
    """Score 75/100 est detecte."""
    text = "Note globale : 75/100."
    claims = detect_claims(text)
    assert len(claims) >= 1


def test_iso_14001_is_ignored() -> None:
    """ISO 14001 est dans IGNORED_NUMERIC_PATTERNS."""
    text = "L'ISO 14001 est requise pour ce dossier."
    claims = detect_claims(text)
    assert claims == []


def test_iso_9001_and_50001_ignored() -> None:
    text = "Voir ISO 9001 et ISO 50001 pour reference."
    claims = detect_claims(text)
    assert claims == []


def test_article_reference_ignored() -> None:
    """article 4.2 est ignore."""
    text = "Voir article 4.2 du reglement."
    claims = detect_claims(text)
    assert claims == []


def test_validation_passes_with_cite_source() -> None:
    """Texte avec chiffre + tool_call cite_source = valide."""
    text = "Le facteur ADEME est 0,41 kgCO2e/kWh selon la source."
    tool_calls = [{"name": "cite_source", "args": {"source_id": "abc"}}]
    result = validate_response(text, tool_calls=tool_calls)
    assert result.passed is True
    assert result.requires_retry is False


def test_validation_passes_with_flag_unsourced() -> None:
    """Texte avec chiffre + flag_unsourced = valide (signalement explicite)."""
    text = "Estimation indicative : 50% des PME sont concernees."
    tool_calls = [{"name": "flag_unsourced", "args": {"claim": "x", "reason": "y"}}]
    result = validate_response(text, tool_calls=tool_calls)
    assert result.passed is True


def test_validation_fails_first_pass_requires_retry() -> None:
    """Texte avec chiffre sans citation = retry demande au premier passage."""
    text = "Le facteur ADEME est 0,41 kgCO2e/kWh."
    result = validate_response(text, tool_calls=[], retry_count=0)
    assert result.passed is False
    assert result.requires_retry is True


def test_validation_fallback_after_retry() -> None:
    """Apres retry epuise : substitution par fallback texte."""
    text = "Le facteur ADEME est 0,41 kgCO2e/kWh."
    result = validate_response(text, tool_calls=[], retry_count=1)
    assert result.passed is False
    assert result.requires_retry is False
    assert result.substituted_text is not None
    assert FALLBACK_TEXT in result.substituted_text
    assert result.incident_logged is True


def test_validation_no_claim_passes() -> None:
    """Texte sans chiffre passe sans citation."""
    text = "Voici votre profil entreprise complet."
    result = validate_response(text, tool_calls=[])
    assert result.passed is True


def test_iso_14001_no_retry_needed() -> None:
    """ISO 14001 seul, sans citation : passe car aucune grappe detectee."""
    text = "Vous etes certifie ISO 14001."
    result = validate_response(text, tool_calls=[])
    assert result.passed is True


def test_french_decimal_detection() -> None:
    """Format francais 1,5 milliard FCFA est detecte."""
    text = "Plafond PME : 1,5 milliard FCFA selon BCEAO."
    claims = detect_claims(text)
    assert len(claims) >= 1
