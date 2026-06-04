"""050 — Garde-fou : la génération de sections reflète le PROJET lié, pas
seulement le profil entreprise.

Un dossier de candidature est lié 1:1 à un projet vert (``FundApplication.project``,
F06). Avant 050, ``generate_section`` n'injectait que ``build_company_context`` +
le contexte fonds : la section « Description du projet » était donc inventée par
le LLM à partir de données génériques d'entreprise.

050 ajoute :func:`build_project_context` et l'injecte dans
:func:`build_section_prompt` (bloc « CONTEXTE PROJET »). Ces tests bloquent la
régression : le contexte projet réel DOIT atteindre le prompt.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.applications.service import (
    build_project_context,
    build_section_prompt,
)

pytestmark = pytest.mark.unit


def _project(**overrides) -> MagicMock:
    """Construit un MagicMock de Project avec des valeurs réalistes."""
    project = MagicMock()
    project.id = overrides.get("id", uuid.uuid4())
    project.name = overrides.get("name", "Ferme Solaire de Kaolack")
    project.description = overrides.get(
        "description",
        "Installation de 200 kWc de panneaux solaires pour l'irrigation "
        "maraîchère de 40 hectares.",
    )
    project.objective_env = overrides.get("objective_env", ["renewable_energy"])
    project.maturity = overrides.get("maturity", "pilot")
    project.status = overrides.get("status", "seeking_funding")
    # Valeurs à l'échelle réelle des colonnes Numeric (asyncpg renvoie des
    # Decimal échelonnés : Numeric(20,2) → Decimal('75000000.00'), etc.).
    project.target_amount_amount = overrides.get(
        "target_amount_amount", Decimal("75000000.00"),
    )
    project.target_amount_currency = overrides.get("target_amount_currency", "XOF")
    project.duration_months = overrides.get("duration_months", 24)
    project.financing_structure = overrides.get("financing_structure", "blending")
    project.location_country = overrides.get("location_country", "SN")
    project.location_region = overrides.get("location_region", "Kaolack")
    project.expected_impact_tco2e = overrides.get(
        "expected_impact_tco2e", Decimal("1200.0000"),
    )
    project.expected_jobs_created = overrides.get("expected_jobs_created", 30)
    project.expected_beneficiaries = overrides.get("expected_beneficiaries", 500)
    project.expected_hectares_restored = overrides.get(
        "expected_hectares_restored", Decimal("12.50"),
    )
    return project


# --- build_project_context -------------------------------------------------


def test_project_context_contains_real_project_fields() -> None:
    """Le contexte projet expose les VRAIES données du projet ciblé."""
    ctx = build_project_context(_project())

    assert "Ferme Solaire de Kaolack" in ctx
    assert "panneaux solaires" in ctx
    # Objectif environnemental traduit en français.
    assert "Énergie renouvelable" in ctx
    # Budget Money typé (F04) : formaté proprement (séparateur de milliers,
    # sans zéros décimaux parasites du Numeric(20,2)).
    assert "75 000 000 XOF" in ctx
    assert "75000000.00" not in ctx


def test_project_context_includes_impacts_and_localisation() -> None:
    """Impacts attendus + localisation injectés quand disponibles."""
    ctx = build_project_context(_project())

    # tCO2e : Numeric(20,4) → Decimal('1200.0000') formaté '1 200', sans zéros.
    assert "1 200 tCO2e" in ctx
    assert "1200.0000" not in ctx
    assert "30 emplois" in ctx
    # Hectares : Numeric(10,2) → Decimal('12.50') formaté '12.5'.
    assert "12.5 ha" in ctx
    assert "Kaolack" in ctx


def test_project_context_returns_empty_when_project_is_none() -> None:
    """Cas legacy : ``project_id`` NULL (SQLite test / pré-migration 025).

    Aucun crash : le contexte projet est simplement vide.
    """
    assert build_project_context(None) == ""


def test_project_context_minimal_project() -> None:
    """Projet minimal (nom seul) → contexte non-vide contenant le nom."""
    project = MagicMock()
    project.name = "Projet minimal"
    project.description = None
    project.objective_env = []
    project.maturity = None
    project.status = None
    project.target_amount_amount = None
    project.target_amount_currency = None
    project.duration_months = None
    project.financing_structure = None
    project.location_country = None
    project.location_region = None
    project.expected_impact_tco2e = None
    project.expected_jobs_created = None
    project.expected_beneficiaries = None
    project.expected_hectares_restored = None

    ctx = build_project_context(project)
    assert "Projet minimal" in ctx


# --- build_section_prompt --------------------------------------------------


def test_build_section_prompt_includes_project_block() -> None:
    """Le bloc « CONTEXTE PROJET » apparaît dans le prompt quand fourni."""
    prompt = build_section_prompt(
        target_type="fund_direct",
        section_key="project_description",
        section_config={"title": "Description du projet", "description": "", "tone": ""},
        company_context="Entreprise ABC",
        fund_context="GCF",
        project_context="Nom du projet : Ferme Solaire de Kaolack",
    )
    assert "CONTEXTE PROJET" in prompt
    assert "Ferme Solaire de Kaolack" in prompt


def test_build_section_prompt_omits_project_block_when_absent() -> None:
    """Sans contexte projet (legacy), pas de bloc « CONTEXTE PROJET » vide."""
    prompt = build_section_prompt(
        target_type="fund_direct",
        section_key="company_presentation",
        section_config={"title": "Présentation", "description": "", "tone": ""},
        company_context="Entreprise ABC",
        fund_context="GCF",
        project_context="",
    )
    assert "CONTEXTE PROJET" not in prompt


# --- generate_section (injection bout-en-bout) -----------------------------


def _application_with_project(project) -> MagicMock:
    """Dossier mock minimal pour ``generate_section`` (section unique)."""
    from app.models.application import FundApplication

    app = MagicMock(spec=FundApplication)
    app.id = uuid.uuid4()
    app.user_id = uuid.uuid4()
    app.target_type = MagicMock(value="fund_direct")
    app.sections = {
        "project_description": {
            "title": "Description du projet",
            "content": None,
            "status": "not_generated",
            "updated_at": None,
        },
    }
    fund = MagicMock()
    fund.name = "Green Climate Fund"
    fund.organization = "GCF"
    fund.description = "Fonds climat"
    fund.sectors_eligible = ["energie"]
    app.fund = fund
    app.project = project
    return app


@pytest.mark.asyncio
async def test_generate_section_injects_project_context_into_prompt() -> None:
    """SC-050 : le prompt envoyé au LLM contient les données réelles du projet.

    Sans cette injection, la section « Description du projet » serait générée
    à partir du seul profil entreprise (données génériques).
    """
    from app.modules.applications.service import generate_section

    project = _project(name="Ferme Solaire de Kaolack")
    app = _application_with_project(project)
    db = AsyncMock()

    mock_response = MagicMock()
    mock_response.content = "<p>Section générée</p>"

    mock_profile = MagicMock(
        company_name="Coopérative Agricole", country="Sénégal", city=None,
        employee_count=12, year_founded=2019, annual_revenue_xof=80_000_000,
        annual_revenue_money=None,
    )
    mock_profile.sector = MagicMock(value="agriculture")

    captured: dict = {}

    async def _capture_ainvoke(messages):
        # Le 1er message est le SystemMessage portant le prompt complet.
        captured["system_prompt"] = messages[0].content
        return mock_response

    with (
        patch("app.graph.nodes.get_llm") as mock_get_llm,
        patch(
            "app.graph.nodes._fetch_rag_context_for_financing",
            new_callable=AsyncMock,
            return_value="",
        ),
        patch(
            "app.modules.company.service.get_or_create_profile",
            new_callable=AsyncMock,
            return_value=mock_profile,
        ),
    ):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = _capture_ainvoke
        mock_get_llm.return_value = mock_llm

        await generate_section(db, app, "project_description")

    prompt = captured["system_prompt"]
    assert "CONTEXTE PROJET" in prompt
    assert "Ferme Solaire de Kaolack" in prompt
    # Le contexte entreprise reste présent (non régressé).
    assert "Coopérative Agricole" in prompt
