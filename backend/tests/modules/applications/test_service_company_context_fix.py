"""F15 BUG-001 — Garde-fou : ``generate_section`` utilise le profil PME réel.

Avant F15, ``company_context`` était hardcodé à
``"Aucun profil d'entreprise disponible."``. Le LLM ne recevait jamais
les données entreprise (secteur, pays, CA, effectif). F15 refactorise
``generate_section`` pour appeler ``get_or_create_profile`` et injecter
les vrais champs via :func:`build_company_context`.

Régression bloquée par ces tests.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.modules.applications.service import build_company_context

pytestmark = pytest.mark.unit


def _profile(**overrides) -> MagicMock:
    """Construit un MagicMock de CompanyProfile avec valeurs par défaut."""
    profile = MagicMock()
    profile.company_name = overrides.get("company_name", "Acme SA")
    sector = overrides.get("sector", "agriculture")
    profile.sector = MagicMock(value=sector) if isinstance(sector, str) else sector
    profile.country = overrides.get("country", "Sénégal")
    profile.city = overrides.get("city", "Dakar")
    profile.employee_count = overrides.get("employee_count", 25)
    profile.year_founded = overrides.get("year_founded", 2018)
    profile.annual_revenue_xof = overrides.get("annual_revenue_xof", 150_000_000)
    profile.annual_revenue_money = overrides.get("annual_revenue_money", None)
    return profile


def test_company_context_contains_critical_fields() -> None:
    """SC-001 : 100 % des contextes contiennent secteur, pays, taille."""
    profile = _profile()
    ctx = build_company_context(profile)

    assert "Acme SA" in ctx
    assert "agriculture" in ctx
    assert "Sénégal" in ctx
    assert "25" in ctx
    assert "150,000,000" in ctx or "150000000" in ctx


def test_company_context_no_legacy_hardcoded_text() -> None:
    """Le texte hardcoded ne doit plus jamais apparaître."""
    profile = _profile()
    ctx = build_company_context(profile)
    assert "Aucun profil d'entreprise disponible" not in ctx


def test_company_context_raises_when_profile_is_none() -> None:
    """Profil manquant → erreur explicite (pas de string fallback fantôme)."""
    with pytest.raises(ValueError, match="Profil entreprise introuvable"):
        build_company_context(None)


def test_company_context_raises_when_profile_is_empty() -> None:
    """Profil vide → erreur listant l'incomplétude."""
    profile = MagicMock(
        company_name=None, sector=None, country=None, city=None,
        employee_count=None, year_founded=None, annual_revenue_xof=None,
        annual_revenue_money=None,
    )
    with pytest.raises(ValueError, match="Profil entreprise incomplet"):
        build_company_context(profile)


def test_company_context_uses_money_typed_when_available() -> None:
    """F04 — Money typed prioritaire sur le legacy ``annual_revenue_xof``."""
    money = MagicMock()
    money.amount = Decimal("250000000")
    money.currency = "XOF"
    profile = _profile(annual_revenue_money=money)
    ctx = build_company_context(profile)
    assert "250000000" in ctx
    assert "XOF" in ctx


def test_company_context_minimum_viable() -> None:
    """Profil minimal (juste secteur) → contexte non-vide acceptable."""
    profile = MagicMock(
        company_name=None, country=None, city=None, employee_count=None,
        year_founded=None, annual_revenue_xof=None, annual_revenue_money=None,
    )
    profile.sector = MagicMock(value="energy")
    ctx = build_company_context(profile)
    assert "energy" in ctx
