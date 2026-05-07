"""Tests pour les tools LangChain du module bilan carbone."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.graph.tools.carbon_tools import (
    create_carbon_assessment,
    finalize_carbon_assessment,
    get_carbon_summary,
    save_emission_entry,
)

# Chemins de patch pour les imports paresseux dans les tools
_CARBON_SVC = "app.modules.carbon.service"
_COMPANY_SVC = "app.modules.company.service"


# ---------- create_carbon_assessment ----------


@pytest.mark.asyncio
async def test_create_carbon_assessment_success(mock_config, mock_user_id):
    """Creer un bilan carbone avec succes."""
    fake_assessment = MagicMock()
    fake_assessment.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
    fake_assessment.year = 2025
    fake_assessment.sector = "agriculture"

    fake_profile = MagicMock()
    fake_profile.sector = "agriculture"

    with (
        patch(
            f"{_CARBON_SVC}.create_assessment",
            new_callable=AsyncMock,
            return_value=fake_assessment,
        ) as mock_create,
        patch(
            f"{_COMPANY_SVC}.get_profile",
            new_callable=AsyncMock,
            return_value=fake_profile,
        ),
    ):
        result = await create_carbon_assessment.ainvoke(
            {"year": 2025}, config=mock_config
        )

    data = json.loads(result)
    assert data["status"] == "success"
    assert data["assessment_id"] == "aaaaaaaa-0000-0000-0000-000000000001"
    assert data["year"] == 2025
    assert data["sector"] == "agriculture"
    mock_create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_carbon_assessment_duplicate_year(mock_config):
    """Erreur si un bilan existe deja pour cette annee."""
    with (
        patch(
            f"{_CARBON_SVC}.create_assessment",
            new_callable=AsyncMock,
            side_effect=ValueError("Un bilan carbone existe deja pour l'annee 2025"),
        ),
        patch(
            f"{_COMPANY_SVC}.get_profile",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        result = await create_carbon_assessment.ainvoke(
            {"year": 2025}, config=mock_config
        )

    data = json.loads(result)
    assert data["status"] == "error"
    assert "existe deja" in data["message"]


@pytest.mark.asyncio
async def test_create_carbon_assessment_no_profile(mock_config):
    """Creer un bilan meme si le profil entreprise n'existe pas."""
    fake_assessment = MagicMock()
    fake_assessment.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000002")
    fake_assessment.year = 2024
    fake_assessment.sector = None

    with (
        patch(
            f"{_CARBON_SVC}.create_assessment",
            new_callable=AsyncMock,
            return_value=fake_assessment,
        ),
        patch(
            f"{_COMPANY_SVC}.get_profile",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        result = await create_carbon_assessment.ainvoke(
            {"year": 2024}, config=mock_config
        )

    data = json.loads(result)
    assert data["status"] == "success"
    assert data["sector"] == "non defini"


# ---------- save_emission_entry ----------


@pytest.mark.asyncio
async def test_save_emission_entry_success(mock_config):
    """F17 — Enregistrer une entree d'emission via factor_service."""
    from app.modules.carbon.factor_service import EmissionFactorResolution

    fake_assessment = MagicMock()
    fake_assessment.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
    fake_assessment.status.value = "in_progress"
    fake_assessment.year = 2024

    fake_factor = MagicMock()
    fake_factor.id = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001")
    fake_factor.code = "electricity_ci_2024"
    fake_factor.label = "Electricite reseau Cote d'Ivoire 2024"
    fake_factor.country = "CI"
    fake_factor.year = 2024
    fake_factor.value = 0.456
    fake_factor.unit = "kgCO2e/kWh"
    fake_factor.source_id = uuid.UUID("cccccccc-0000-0000-0000-000000000001")

    fake_resolution = EmissionFactorResolution(
        factor=fake_factor,
        is_approximate=False,
        fallback_reason=None,
    )

    fake_profile = MagicMock()
    fake_profile.country = "CI"

    with (
        patch(
            f"{_CARBON_SVC}.get_assessment",
            new_callable=AsyncMock,
            return_value=fake_assessment,
        ),
        patch(
            f"{_COMPANY_SVC}.get_profile",
            new_callable=AsyncMock,
            return_value=fake_profile,
        ),
        patch(
            "app.modules.carbon.factor_service.get_emission_factor",
            new_callable=AsyncMock,
            return_value=fake_resolution,
        ),
        patch(
            f"{_CARBON_SVC}.add_entries",
            new_callable=AsyncMock,
            return_value=(1, 0.228, ["energy"]),
        ) as mock_add,
    ):
        result = await save_emission_entry.ainvoke(
            {
                "assessment_id": "aaaaaaaa-0000-0000-0000-000000000001",
                "category": "energy",
                "subcategory": "electricity",
                "quantity": 500.0,
                "unit": "kWh",
                "source_description": "Electricite bureau",
            },
            config=mock_config,
        )

    data = json.loads(result)
    assert data["status"] == "success"
    # F17 : la subcategory finale est le code complet du facteur.
    assert data["entry"]["subcategory"] == "electricity_ci_2024"
    assert data["entry"]["emission_factor_kgco2e"] == 0.456
    # 500 * 0.456 / 1000 = 0.228
    assert data["entry"]["emissions_tco2e"] == 0.228
    assert data["total_emissions_tco2e"] == 0.228
    # F17 : factor_used + source_id sont presents.
    assert data["factor_used"]["code"] == "electricity_ci_2024"
    assert data["factor_used"]["country"] == "CI"
    assert data["source_id"] == "cccccccc-0000-0000-0000-000000000001"
    assert data["is_approximate"] is False
    mock_add.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_emission_entry_fallback_category(mock_config):
    """F17 — Si subcategory n'est pas trouve, fallback sur category."""
    from app.modules.carbon.factor_service import (
        EmissionFactorNotFoundError,
        EmissionFactorResolution,
    )

    fake_assessment = MagicMock()
    fake_assessment.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
    fake_assessment.year = 2024

    fake_factor = MagicMock()
    fake_factor.id = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002")
    fake_factor.code = "fuel_diesel_global_2024"
    fake_factor.label = "Gasoil"
    fake_factor.country = "global"
    fake_factor.year = 2024
    fake_factor.value = 2.68
    fake_factor.unit = "kgCO2e/L"
    fake_factor.source_id = uuid.UUID("cccccccc-0000-0000-0000-000000000002")

    fake_resolution = EmissionFactorResolution(
        factor=fake_factor,
        is_approximate=True,
        fallback_reason="country_global",
    )

    fake_profile = MagicMock()
    fake_profile.country = "ZZ"  # Pays inconnu, fallback global.

    # Simule : 1er appel echoue (lookup avec subcategory='diesel'), 2eme reussit avec category='transport'.
    side_effects = [
        EmissionFactorNotFoundError("diesel", "ZZ", 2024),
        fake_resolution,
    ]

    with (
        patch(
            f"{_CARBON_SVC}.get_assessment",
            new_callable=AsyncMock,
            return_value=fake_assessment,
        ),
        patch(
            f"{_COMPANY_SVC}.get_profile",
            new_callable=AsyncMock,
            return_value=fake_profile,
        ),
        patch(
            "app.modules.carbon.factor_service.get_emission_factor",
            new_callable=AsyncMock,
            side_effect=side_effects,
        ),
        patch(
            f"{_CARBON_SVC}.add_entries",
            new_callable=AsyncMock,
            return_value=(1, 0.268, []),
        ),
    ):
        result = await save_emission_entry.ainvoke(
            {
                "assessment_id": "aaaaaaaa-0000-0000-0000-000000000001",
                "category": "fuel_diesel",
                "subcategory": "diesel",
                "quantity": 100.0,
                "unit": "L",
                "source_description": "Carburant vehicule",
            },
            config=mock_config,
        )

    data = json.loads(result)
    assert data["status"] == "success"
    # F17 : code du facteur retenu apres fallback.
    assert data["entry"]["subcategory"] == "fuel_diesel_global_2024"
    assert data["is_approximate"] is True
    assert data["fallback_reason"] == "country_global"


@pytest.mark.asyncio
async def test_save_emission_entry_assessment_not_found(mock_config):
    """Erreur si le bilan n'existe pas."""
    with patch(
        f"{_CARBON_SVC}.get_assessment",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await save_emission_entry.ainvoke(
            {
                "assessment_id": "aaaaaaaa-0000-0000-0000-000000000099",
                "category": "energy",
                "subcategory": "electricity_ci",
                "quantity": 500.0,
                "unit": "kWh",
                "source_description": "Test",
            },
            config=mock_config,
        )

    data = json.loads(result)
    assert data["status"] == "error"
    assert "introuvable" in data["message"]


@pytest.mark.asyncio
async def test_save_emission_entry_unknown_factor(mock_config):
    """F17 — Erreur si aucun facteur d'emission ne correspond
    (ni subcategory, ni category fallback).
    """
    from app.modules.carbon.factor_service import EmissionFactorNotFoundError

    fake_assessment = MagicMock()
    fake_assessment.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
    fake_assessment.year = 2024

    fake_profile = MagicMock()
    fake_profile.country = None

    # Les 2 appels factor_service echouent (subcategory + category fallback).
    with (
        patch(
            f"{_CARBON_SVC}.get_assessment",
            new_callable=AsyncMock,
            return_value=fake_assessment,
        ),
        patch(
            f"{_COMPANY_SVC}.get_profile",
            new_callable=AsyncMock,
            return_value=fake_profile,
        ),
        patch(
            "app.modules.carbon.factor_service.get_emission_factor",
            new_callable=AsyncMock,
            side_effect=EmissionFactorNotFoundError(
                "unknown_category", None, 2024
            ),
        ),
    ):
        result = await save_emission_entry.ainvoke(
            {
                "assessment_id": "aaaaaaaa-0000-0000-0000-000000000001",
                "category": "unknown_category",
                "subcategory": "unknown_sub",
                "quantity": 100.0,
                "unit": "kg",
                "source_description": "Test inconnu",
            },
            config=mock_config,
        )

    data = json.loads(result)
    assert data["status"] == "error"
    assert data.get("error_code") == "factor_not_found"
    assert "Aucun facteur" in data["message"]


# ---------- finalize_carbon_assessment ----------


@pytest.mark.asyncio
async def test_finalize_carbon_assessment_success(mock_config):
    """Finaliser un bilan avec succes."""
    fake_assessment = MagicMock()
    fake_assessment.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
    fake_assessment.status.value = "in_progress"
    fake_assessment.year = 2025

    fake_completed = MagicMock()
    fake_completed.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
    fake_completed.total_emissions_tco2e = 3.7
    fake_completed.year = 2025

    with (
        patch(
            f"{_CARBON_SVC}.get_assessment",
            new_callable=AsyncMock,
            return_value=fake_assessment,
        ),
        patch(
            f"{_CARBON_SVC}.complete_assessment",
            new_callable=AsyncMock,
            return_value=fake_completed,
        ) as mock_complete,
    ):
        result = await finalize_carbon_assessment.ainvoke(
            {"assessment_id": "aaaaaaaa-0000-0000-0000-000000000001"},
            config=mock_config,
        )

    data = json.loads(result)
    assert data["status"] == "success"
    assert data["total_emissions_tco2e"] == 3.7
    assert data["year"] == 2025
    mock_complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_finalize_carbon_assessment_already_completed(mock_config):
    """Erreur si le bilan est deja finalise."""
    fake_assessment = MagicMock()
    fake_assessment.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
    fake_assessment.status.value = "completed"

    with patch(
        f"{_CARBON_SVC}.get_assessment",
        new_callable=AsyncMock,
        return_value=fake_assessment,
    ):
        result = await finalize_carbon_assessment.ainvoke(
            {"assessment_id": "aaaaaaaa-0000-0000-0000-000000000001"},
            config=mock_config,
        )

    data = json.loads(result)
    assert data["status"] == "error"
    assert "deja finalise" in data["message"]


@pytest.mark.asyncio
async def test_finalize_carbon_assessment_not_found(mock_config):
    """Erreur si le bilan n'existe pas."""
    with patch(
        f"{_CARBON_SVC}.get_assessment",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await finalize_carbon_assessment.ainvoke(
            {"assessment_id": "aaaaaaaa-0000-0000-0000-000000000099"},
            config=mock_config,
        )

    data = json.loads(result)
    assert data["status"] == "error"
    assert "introuvable" in data["message"]


@pytest.mark.asyncio
async def test_finalize_docstring_contains_confirmation_warning():
    """FR-019 : le docstring doit exiger la confirmation utilisateur."""
    docstring = finalize_carbon_assessment.description or ""
    assert "confirme" in docstring.lower() or "confirmation" in docstring.lower()


# ---------- get_carbon_summary ----------


@pytest.mark.asyncio
async def test_get_carbon_summary_with_id(mock_config):
    """Obtenir le resume d'un bilan par son ID."""
    fake_assessment = MagicMock()
    fake_assessment.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")

    fake_summary = {
        "assessment_id": "aaaaaaaa-0000-0000-0000-000000000001",
        "year": 2025,
        "status": "completed",
        "total_emissions_tco2e": 3.7,
        "by_category": {"energy": {"emissions_tco2e": 2.0, "entries_count": 2, "percentage": 54.1}},
        "equivalences": [{"label": "vols Paris-Dakar", "value": 3.1}],
        "reduction_plan": None,
        "sector_benchmark": None,
    }

    with (
        patch(
            f"{_CARBON_SVC}.get_assessment",
            new_callable=AsyncMock,
            return_value=fake_assessment,
        ),
        patch(
            f"{_CARBON_SVC}.get_assessment_summary",
            new_callable=AsyncMock,
            return_value=fake_summary,
        ),
    ):
        result = await get_carbon_summary.ainvoke(
            {"assessment_id": "aaaaaaaa-0000-0000-0000-000000000001"},
            config=mock_config,
        )

    data = json.loads(result)
    assert data["status"] == "success"
    assert data["summary"]["total_emissions_tco2e"] == 3.7
    assert "energy" in data["summary"]["by_category"]


@pytest.mark.asyncio
async def test_get_carbon_summary_without_id_uses_resumable(mock_config):
    """Sans ID, chercher le bilan en cours."""
    fake_assessment = MagicMock()
    fake_assessment.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000002")

    fake_summary = {
        "assessment_id": "aaaaaaaa-0000-0000-0000-000000000002",
        "year": 2025,
        "status": "in_progress",
        "total_emissions_tco2e": 1.5,
        "by_category": {},
        "equivalences": [],
        "reduction_plan": None,
        "sector_benchmark": None,
    }

    with (
        patch(
            f"{_CARBON_SVC}.get_resumable_assessment",
            new_callable=AsyncMock,
            return_value=fake_assessment,
        ) as mock_resumable,
        patch(
            f"{_CARBON_SVC}.get_assessment_summary",
            new_callable=AsyncMock,
            return_value=fake_summary,
        ),
    ):
        result = await get_carbon_summary.ainvoke(
            {},
            config=mock_config,
        )

    data = json.loads(result)
    assert data["status"] == "success"
    assert data["summary"]["total_emissions_tco2e"] == 1.5
    mock_resumable.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_carbon_summary_no_assessment_found(mock_config):
    """Erreur si aucun bilan n'est trouve."""
    with (
        patch(
            f"{_CARBON_SVC}.get_resumable_assessment",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            f"{_CARBON_SVC}.get_latest_assessment",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        result = await get_carbon_summary.ainvoke(
            {},
            config=mock_config,
        )

    data = json.loads(result)
    assert data["status"] == "error"
    assert "Aucun bilan" in data["message"]


@pytest.mark.asyncio
async def test_get_carbon_summary_falls_back_to_latest_completed(mock_config):
    """Regression BUG-CARBON-LECTURE : sans ID et sans bilan in_progress,
    retrouver le dernier bilan completed de l'utilisateur.

    Scenario reproduit : utilisateur Fatou a 1 bilan 2025 completed a 43.041 tCO2e.
    Avant le fix, `get_carbon_summary()` sans id appelait uniquement
    `get_resumable_assessment` (qui filtre in_progress) et retournait
    "Aucun bilan" alors que le bilan completed existe.
    """
    fake_assessment = MagicMock()
    fake_assessment.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000003")

    fake_summary = {
        "assessment_id": "aaaaaaaa-0000-0000-0000-000000000003",
        "year": 2025,
        "status": "completed",
        "total_emissions_tco2e": 43.041,
        "by_category": {
            "energy": {"emissions_tco2e": 20.0, "entries_count": 2, "percentage": 46.5},
        },
        "equivalences": [],
        "reduction_plan": None,
        "sector_benchmark": None,
    }

    with (
        patch(
            f"{_CARBON_SVC}.get_resumable_assessment",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_resumable,
        patch(
            f"{_CARBON_SVC}.get_latest_assessment",
            new_callable=AsyncMock,
            return_value=fake_assessment,
        ) as mock_latest,
        patch(
            f"{_CARBON_SVC}.get_assessment_summary",
            new_callable=AsyncMock,
            return_value=fake_summary,
        ),
    ):
        result = await get_carbon_summary.ainvoke({}, config=mock_config)

    data = json.loads(result)
    assert data["status"] == "success"
    assert data["summary"]["total_emissions_tco2e"] == 43.041
    assert data["summary"]["status"] == "completed"
    mock_resumable.assert_awaited_once()
    mock_latest.assert_awaited_once()
