"""Tests unitaires du service ``get_emission_factor`` (F17 — T005).

Couvre 7+ scenarios :
    - Match exact (country + year).
    - Pays exact + annee anterieure recente (diff <= 3) -> approximate=False.
    - Pays exact + annee tres anterieure (diff > 3) -> approximate=True.
    - Pays non couvert -> fallback global, approximate=True.
    - country=None -> fallback global directement.
    - country=None, year donne mais aucun global -> LookupError.
    - Categorie inconnue -> LookupError.
    - Filtre uniquement les facteurs ``published`` (ignore les drafts).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.emission_factor import EmissionFactor
from app.models.source import PublicationStatus, Source, VerificationStatus
from app.models.user import User
from app.modules.carbon.factor_service import (
    EmissionFactorNotFoundError,
    get_emission_factor,
)
from app.core.constants import UserRole


pytestmark = pytest.mark.asyncio


async def _create_admin(db_session, suffix: str = "") -> User:
    """Cree un user admin pour servir de captured_by/verified_by/created_by."""
    user = User(
        email=f"admin-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="x",
        full_name=f"Admin {suffix}",
        company_name="ESG Mefali",
        is_active=False,
        role=UserRole.ADMIN.value,
        account_id=None,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _create_source(db_session, captured_by, verified_by) -> Source:
    """Cree une Source verifiee pour les tests."""
    src = Source(
        url=f"https://test.example/{uuid.uuid4().hex[:8]}",
        title="ADEME Base Carbone v23",
        publisher="ADEME",
        version="v23",
        date_publi=date(2024, 1, 15),
        captured_by=captured_by.id,
        verified_by=verified_by.id,
        verification_status=VerificationStatus.VERIFIED.value,
        verified_at=datetime.now(timezone.utc),
        created_by_user_id=captured_by.id,
    )
    db_session.add(src)
    await db_session.flush()
    return src


async def _create_factor(
    db_session,
    *,
    code: str,
    category: str,
    country: str,
    year: int,
    value: float,
    source: Source,
    creator: User,
    published: bool = True,
) -> EmissionFactor:
    """Cree un EmissionFactor de test."""
    factor = EmissionFactor(
        code=code,
        label=f"Facteur {code}",
        category=category,
        country=country,
        year=year,
        value=value,
        unit="kgCO2e/kWh",
        source_id=source.id,
        publication_status=(
            PublicationStatus.PUBLISHED.value
            if published
            else PublicationStatus.DRAFT.value
        ),
        created_by_user_id=creator.id,
    )
    db_session.add(factor)
    await db_session.flush()
    return factor


@pytest.fixture
async def setup_factors(db_session):
    """Setup standard : 1 source ADEME + plusieurs facteurs electricity."""
    curator = await _create_admin(db_session, "curator")
    validator = await _create_admin(db_session, "validator")
    source = await _create_source(db_session, curator, validator)

    # CI 2024 : facteur exact courant.
    factor_ci_2024 = await _create_factor(
        db_session,
        code="electricity_ci_2024",
        category="electricity",
        country="CI",
        year=2024,
        value=0.456,
        source=source,
        creator=curator,
    )
    # CI 2023 : facteur anterieur (pour fallback annee anterieure).
    factor_ci_2023 = await _create_factor(
        db_session,
        code="electricity_ci_2023",
        category="electricity",
        country="CI",
        year=2023,
        value=0.470,
        source=source,
        creator=curator,
    )
    # CI 2020 : facteur tres ancien (pour test approximate=True quand diff > 3).
    factor_ci_2020 = await _create_factor(
        db_session,
        code="electricity_ci_2020",
        category="electricity",
        country="CI",
        year=2020,
        value=0.500,
        source=source,
        creator=curator,
    )
    # Global 2024 : fallback country.
    factor_global_2024 = await _create_factor(
        db_session,
        code="electricity_global_2024",
        category="electricity",
        country="global",
        year=2024,
        value=0.520,
        source=source,
        creator=curator,
    )
    # Draft (not published).
    factor_draft = await _create_factor(
        db_session,
        code="electricity_sn_2024",
        category="electricity",
        country="SN",
        year=2024,
        value=0.540,
        source=source,
        creator=curator,
        published=False,
    )

    return {
        "ci_2024": factor_ci_2024,
        "ci_2023": factor_ci_2023,
        "ci_2020": factor_ci_2020,
        "global_2024": factor_global_2024,
        "draft": factor_draft,
        "source": source,
    }


# ---------- Cas de match -----------------------------------------------------


async def test_get_emission_factor_exact_match_country_year(setup_factors, db_session):
    """CI 2024 demande -> CI 2024 retourne, exact match."""
    result = await get_emission_factor(db_session, "electricity", "CI", 2024)
    assert result.factor.code == "electricity_ci_2024"
    assert result.is_approximate is False
    assert result.fallback_reason is None


async def test_get_emission_factor_exact_country_recent_older_year(
    setup_factors, db_session
):
    """CI 2026 demande, mais seul CI 2024 existe (diff=2 <= 3) -> approximate=False."""
    result = await get_emission_factor(db_session, "electricity", "CI", 2026)
    assert result.factor.code == "electricity_ci_2024"
    assert result.is_approximate is False
    assert result.fallback_reason == "year_older"


async def test_get_emission_factor_exact_country_very_old_year(
    setup_factors, db_session
):
    """CI 2030 demande, seul CI 2024 disponible (diff=6 > 3) -> approximate=True."""
    result = await get_emission_factor(db_session, "electricity", "CI", 2030)
    assert result.factor.code == "electricity_ci_2024"
    assert result.is_approximate is True
    assert result.fallback_reason == "year_older"


async def test_get_emission_factor_country_global_fallback(setup_factors, db_session):
    """XX 2024 (pays inexistant) -> global 2024, approximate=True."""
    result = await get_emission_factor(db_session, "electricity", "XX", 2024)
    assert result.factor.code == "electricity_global_2024"
    assert result.is_approximate is True
    assert result.fallback_reason == "country_global"


async def test_get_emission_factor_no_country_provided(setup_factors, db_session):
    """country=None -> global, approximate=True."""
    result = await get_emission_factor(db_session, "electricity", None, 2024)
    assert result.factor.code == "electricity_global_2024"
    assert result.is_approximate is True
    assert result.fallback_reason == "country_global"


async def test_get_emission_factor_global_explicit(setup_factors, db_session):
    """country='global' explicite -> global."""
    result = await get_emission_factor(db_session, "electricity", "global", 2024)
    assert result.factor.code == "electricity_global_2024"
    assert result.is_approximate is True


# ---------- Cas non trouve ---------------------------------------------------


async def test_get_emission_factor_not_found_unknown_category(
    setup_factors, db_session
):
    """Categorie inconnue -> EmissionFactorNotFoundError."""
    with pytest.raises(EmissionFactorNotFoundError):
        await get_emission_factor(db_session, "unknown_category", "CI", 2024)


async def test_get_emission_factor_not_found_no_global_fallback(db_session):
    """Aucun facteur du tout -> EmissionFactorNotFoundError."""
    with pytest.raises(EmissionFactorNotFoundError) as exc_info:
        await get_emission_factor(db_session, "fuel_diesel", "CI", 2024)
    assert "fuel_diesel" in str(exc_info.value)
    assert "CI" in str(exc_info.value)
    assert "2024" in str(exc_info.value)


# ---------- Filtres publication_status --------------------------------------


async def test_get_emission_factor_filter_published_only(setup_factors, db_session):
    """SN 2024 existe en draft -> non retourne, fallback sur global 2024."""
    result = await get_emission_factor(db_session, "electricity", "SN", 2024)
    # Le draft SN 2024 est ignore -> fallback sur global 2024.
    assert result.factor.code == "electricity_global_2024"
    assert result.is_approximate is True
    assert result.fallback_reason == "country_global"


async def test_get_emission_factor_year_anterior_when_recent_year_unpublished(
    setup_factors, db_session
):
    """CI 2024 publie, demande pour annee anterieure 2023 -> CI 2023 retourne (exact)."""
    result = await get_emission_factor(db_session, "electricity", "CI", 2023)
    assert result.factor.code == "electricity_ci_2023"
    assert result.is_approximate is False
    assert result.fallback_reason is None


async def test_get_emission_factor_resolution_dataclass_frozen(
    setup_factors, db_session
):
    """EmissionFactorResolution est immuable (frozen dataclass)."""
    result = await get_emission_factor(db_session, "electricity", "CI", 2024)
    with pytest.raises(Exception):
        result.is_approximate = True  # type: ignore[misc]
