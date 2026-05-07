"""Tests F17 du tool ``save_emission_entry`` refactore (T017, T026, T034).

Couvre :
    - Lecture du ``country`` depuis le profil entreprise.
    - Appel a ``factor_service.get_emission_factor`` avec country/year.
    - Stockage de ``source_id`` et ``factor_id`` via ``add_entries``.
    - Reponse JSON enrichie : ``factor_used``, ``source_id``, ``is_approximate``,
      ``fallback_reason``.
    - Recategorisation purchases (T034).
    - Source_id retourne pour ``cite_source`` (T026).
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.graph.tools.carbon_tools import save_emission_entry


_CARBON_SVC = "app.modules.carbon.service"
_COMPANY_SVC = "app.modules.company.service"
_FACTOR_SVC = "app.modules.carbon.factor_service.get_emission_factor"


@pytest.fixture
def mock_user_id() -> uuid.UUID:
    """UUID fixe pour les tests."""
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def mock_db() -> AsyncMock:
    """Session DB mockee."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def mock_config(mock_db: AsyncMock, mock_user_id: uuid.UUID):
    """RunnableConfig avec db et user_id injectes."""
    return {
        "configurable": {
            "db": mock_db,
            "user_id": mock_user_id,
            "thread_id": "test-thread-1",
        },
    }


def _make_factor(
    *,
    factor_id: str = "bbbbbbbb-0000-0000-0000-000000000001",
    code: str = "electricity_ci_2024",
    label: str = "Electricite reseau Cote d'Ivoire 2024",
    country: str = "CI",
    year: int = 2024,
    value: float = 0.456,
    unit: str = "kgCO2e/kWh",
    source_id: str = "cccccccc-0000-0000-0000-000000000001",
):
    """Factory MagicMock representant un EmissionFactor."""
    factor = MagicMock()
    factor.id = uuid.UUID(factor_id)
    factor.code = code
    factor.label = label
    factor.country = country
    factor.year = year
    factor.value = value
    factor.unit = unit
    factor.source_id = uuid.UUID(source_id)
    return factor


def _make_resolution(factor, is_approximate=False, fallback_reason=None):
    """Factory pour EmissionFactorResolution."""
    from app.modules.carbon.factor_service import EmissionFactorResolution

    return EmissionFactorResolution(
        factor=factor,
        is_approximate=is_approximate,
        fallback_reason=fallback_reason,
    )


# ---------- T017 : utilise country du profil entreprise ----------------------


@pytest.mark.asyncio
async def test_save_emission_entry_uses_country_from_profile(mock_config):
    """T017 — Le tool lit le country depuis le profil et le passe a get_emission_factor."""
    fake_assessment = MagicMock()
    fake_assessment.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
    fake_assessment.year = 2024
    fake_assessment.status.value = "in_progress"

    fake_profile = MagicMock()
    fake_profile.country = "CI"

    factor = _make_factor()
    resolution = _make_resolution(factor)

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
        patch(_FACTOR_SVC, new_callable=AsyncMock, return_value=resolution) as mock_resolve,
        patch(
            f"{_CARBON_SVC}.add_entries",
            new_callable=AsyncMock,
            return_value=(1, 0.456, []),
        ),
    ):
        result = await save_emission_entry.ainvoke(
            {
                "assessment_id": "aaaaaaaa-0000-0000-0000-000000000001",
                "category": "energy",
                "subcategory": "electricity",
                "quantity": 1000.0,
                "unit": "kWh",
                "source_description": "Electricite siege",
            },
            config=mock_config,
        )

    data = json.loads(result)
    assert data["status"] == "success"
    # Verifier que get_emission_factor a ete appele avec country='CI'.
    call_kwargs = mock_resolve.await_args.kwargs
    assert call_kwargs["country"] == "CI"
    assert call_kwargs["year"] == 2024


@pytest.mark.asyncio
async def test_save_emission_entry_country_normalized_to_upper(mock_config):
    """T017 — Le pays est normalise en majuscules (insensible a la casse)."""
    fake_assessment = MagicMock()
    fake_assessment.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
    fake_assessment.year = 2024

    fake_profile = MagicMock()
    fake_profile.country = "ci"  # minuscule

    factor = _make_factor()
    resolution = _make_resolution(factor)

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
        patch(_FACTOR_SVC, new_callable=AsyncMock, return_value=resolution) as mock_resolve,
        patch(
            f"{_CARBON_SVC}.add_entries",
            new_callable=AsyncMock,
            return_value=(1, 0.456, []),
        ),
    ):
        await save_emission_entry.ainvoke(
            {
                "assessment_id": "aaaaaaaa-0000-0000-0000-000000000001",
                "category": "energy",
                "subcategory": "electricity",
                "quantity": 1000.0,
                "unit": "kWh",
                "source_description": "Test",
            },
            config=mock_config,
        )

    assert mock_resolve.await_args.kwargs["country"] == "CI"


@pytest.mark.asyncio
async def test_save_emission_entry_no_country_in_profile(mock_config):
    """T017 — Profil sans country -> get_emission_factor avec country=None
    (fallback global)."""
    fake_assessment = MagicMock()
    fake_assessment.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
    fake_assessment.year = 2024

    fake_profile = MagicMock()
    fake_profile.country = None

    factor = _make_factor(country="global", code="electricity_global_2024")
    resolution = _make_resolution(
        factor, is_approximate=True, fallback_reason="country_global"
    )

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
        patch(_FACTOR_SVC, new_callable=AsyncMock, return_value=resolution) as mock_resolve,
        patch(
            f"{_CARBON_SVC}.add_entries",
            new_callable=AsyncMock,
            return_value=(1, 0.520, []),
        ),
    ):
        result = await save_emission_entry.ainvoke(
            {
                "assessment_id": "aaaaaaaa-0000-0000-0000-000000000001",
                "category": "energy",
                "subcategory": "electricity",
                "quantity": 1000.0,
                "unit": "kWh",
                "source_description": "Electricite",
            },
            config=mock_config,
        )

    assert mock_resolve.await_args.kwargs["country"] is None
    data = json.loads(result)
    assert data["is_approximate"] is True
    assert data["fallback_reason"] == "country_global"


# ---------- T026 : source_id retourne pour cite_source ----------------------


@pytest.mark.asyncio
async def test_save_emission_entry_returns_source_id_for_cite_source(mock_config):
    """T026 — La reponse JSON contient ``source_id`` UUID valide
    pour permettre l'appel ``cite_source(source_id)`` par le LLM.
    """
    fake_assessment = MagicMock()
    fake_assessment.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
    fake_assessment.year = 2024

    fake_profile = MagicMock()
    fake_profile.country = "CI"

    factor = _make_factor()
    resolution = _make_resolution(factor)

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
        patch(_FACTOR_SVC, new_callable=AsyncMock, return_value=resolution),
        patch(
            f"{_CARBON_SVC}.add_entries",
            new_callable=AsyncMock,
            return_value=(1, 0.456, []),
        ),
    ):
        result = await save_emission_entry.ainvoke(
            {
                "assessment_id": "aaaaaaaa-0000-0000-0000-000000000001",
                "category": "energy",
                "subcategory": "electricity",
                "quantity": 1000.0,
                "unit": "kWh",
                "source_description": "Test",
            },
            config=mock_config,
        )

    data = json.loads(result)
    # Source_id est un UUID string valide.
    assert "source_id" in data
    parsed = uuid.UUID(data["source_id"])
    assert isinstance(parsed, uuid.UUID)
    # factor_used contient le code du facteur et son label.
    assert "factor_used" in data
    assert data["factor_used"]["code"] == "electricity_ci_2024"


@pytest.mark.asyncio
async def test_save_emission_entry_returns_factor_metadata(mock_config):
    """``factor_used`` contient code, label, country, year, value, unit."""
    fake_assessment = MagicMock()
    fake_assessment.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
    fake_assessment.year = 2024

    fake_profile = MagicMock()
    fake_profile.country = "CI"

    factor = _make_factor()
    resolution = _make_resolution(factor)

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
        patch(_FACTOR_SVC, new_callable=AsyncMock, return_value=resolution),
        patch(
            f"{_CARBON_SVC}.add_entries",
            new_callable=AsyncMock,
            return_value=(1, 0.456, []),
        ),
    ):
        result = await save_emission_entry.ainvoke(
            {
                "assessment_id": "aaaaaaaa-0000-0000-0000-000000000001",
                "category": "energy",
                "subcategory": "electricity",
                "quantity": 1000.0,
                "unit": "kWh",
                "source_description": "Test",
            },
            config=mock_config,
        )

    data = json.loads(result)
    factor_data = data["factor_used"]
    assert factor_data["code"] == "electricity_ci_2024"
    assert factor_data["country"] == "CI"
    assert factor_data["year"] == 2024
    assert factor_data["value"] == 0.456
    assert factor_data["unit"] == "kgCO2e/kWh"
    assert "label" in factor_data


# ---------- T034 : categorie purchases reconnue ------------------------------


@pytest.mark.asyncio
async def test_save_emission_entry_purchases_cement(mock_config):
    """T034 — Categorie ``purchases`` reconnue avec subcategory ``purchases_cement``."""
    fake_assessment = MagicMock()
    fake_assessment.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
    fake_assessment.year = 2024

    fake_profile = MagicMock()
    fake_profile.country = "CI"

    factor = _make_factor(
        factor_id="dddddddd-0000-0000-0000-000000000001",
        code="purchases_cement_global_2024",
        label="Ciment (matiere premiere)",
        country="global",
        year=2024,
        value=0.9,
        unit="kgCO2e/kg",
    )
    resolution = _make_resolution(factor, is_approximate=True, fallback_reason="country_global")

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
        patch(_FACTOR_SVC, new_callable=AsyncMock, return_value=resolution),
        patch(
            f"{_CARBON_SVC}.add_entries",
            new_callable=AsyncMock,
            return_value=(1, 45.0, []),
        ) as mock_add,
    ):
        result = await save_emission_entry.ainvoke(
            {
                "assessment_id": "aaaaaaaa-0000-0000-0000-000000000001",
                "category": "purchases",
                "subcategory": "purchases_cement",
                "quantity": 50000.0,  # 50 tonnes en kg.
                "unit": "kg",
                "source_description": "Achat ciment",
            },
            config=mock_config,
        )

    data = json.loads(result)
    assert data["status"] == "success"
    assert data["entry"]["subcategory"] == "purchases_cement_global_2024"
    # 50000 kg * 0.9 / 1000 = 45 tCO2e.
    assert data["entry"]["emissions_tco2e"] == 45.0
    # Verifier que add_entries a ete appele avec category='purchases'.
    add_call_args = mock_add.await_args
    entry_data = add_call_args.kwargs["entries_data"][0]
    assert entry_data["category"] == "purchases"


@pytest.mark.asyncio
async def test_save_emission_entry_passes_source_id_and_factor_id_to_service(
    mock_config,
):
    """T021/T022 — ``add_entries`` recoit source_id et factor_id en plus
    des champs legacy."""
    fake_assessment = MagicMock()
    fake_assessment.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
    fake_assessment.year = 2024

    fake_profile = MagicMock()
    fake_profile.country = "CI"

    factor = _make_factor()
    resolution = _make_resolution(factor)

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
        patch(_FACTOR_SVC, new_callable=AsyncMock, return_value=resolution),
        patch(
            f"{_CARBON_SVC}.add_entries",
            new_callable=AsyncMock,
            return_value=(1, 0.456, []),
        ) as mock_add,
    ):
        await save_emission_entry.ainvoke(
            {
                "assessment_id": "aaaaaaaa-0000-0000-0000-000000000001",
                "category": "energy",
                "subcategory": "electricity",
                "quantity": 1000.0,
                "unit": "kWh",
                "source_description": "Test",
            },
            config=mock_config,
        )

    add_call = mock_add.await_args
    entry_data = add_call.kwargs["entries_data"][0]
    assert entry_data["source_id"] == factor.source_id
    assert entry_data["factor_id"] == factor.id
    # subcategory remplace par le code complet du facteur.
    assert entry_data["subcategory"] == "electricity_ci_2024"


# ---------- Approximate flag --------------------------------------------------


@pytest.mark.asyncio
async def test_save_emission_entry_returns_is_approximate_flag(mock_config):
    """``is_approximate`` est propage dans la reponse JSON."""
    fake_assessment = MagicMock()
    fake_assessment.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
    fake_assessment.year = 2030  # annee future, fallback annee anterieure.

    fake_profile = MagicMock()
    fake_profile.country = "CI"

    factor = _make_factor()
    resolution = _make_resolution(
        factor, is_approximate=True, fallback_reason="year_older"
    )

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
        patch(_FACTOR_SVC, new_callable=AsyncMock, return_value=resolution),
        patch(
            f"{_CARBON_SVC}.add_entries",
            new_callable=AsyncMock,
            return_value=(1, 0.456, []),
        ),
    ):
        result = await save_emission_entry.ainvoke(
            {
                "assessment_id": "aaaaaaaa-0000-0000-0000-000000000001",
                "category": "energy",
                "subcategory": "electricity",
                "quantity": 1000.0,
                "unit": "kWh",
                "source_description": "Test 2030",
            },
            config=mock_config,
        )

    data = json.loads(result)
    assert data["is_approximate"] is True
    assert data["fallback_reason"] == "year_older"
