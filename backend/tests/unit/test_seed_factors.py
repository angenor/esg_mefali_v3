"""Tests unitaires du seed des facteurs d'emission F17 (T006).

Couvre :
- ``SEED_DATA`` contient suffisamment de facteurs (~33+ pour les 8 pays UEMOA
  electricite x2 annees + global + 14 autres).
- 8 facteurs ``electricity`` UEMOA en 2024 (un par pays).
- 6 facteurs ``purchases_*`` (steel, cement, paper, food, plastic, other).
- 3 facteurs combustibles (diesel, gasoline, butane).
- Idempotence : second run -> 0 inserted, total inchange.
- Resolution publisher -> source_id correcte (ADEME, IEA, IPCC).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import func, select

from app.core.constants import UserRole
from app.models.emission_factor import EmissionFactor
from app.models.source import PublicationStatus, Source, VerificationStatus
from app.models.user import User
from app.modules.carbon.seed_factors import (
    SEED_DATA,
    SeedFactor,
    seed_emission_factors,
)


async def _make_admin_user(db_session, name: str = "admin") -> User:
    """Cree un user admin pour les tests."""
    user = User(
        email=f"{name}-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="x",
        full_name=name,
        company_name="ESG Mefali",
        is_active=False,
        role=UserRole.ADMIN.value,
        account_id=None,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _seed_minimal_sources(db_session) -> dict[str, Source]:
    """Cree 3 sources minimales (ADEME, IEA, IPCC) pour le seed des facteurs."""
    curator = await _make_admin_user(db_session, "curator")
    validator = await _make_admin_user(db_session, "validator")

    sources_to_seed = [
        {
            "url": "https://base-empreinte.ademe.fr/",
            "title": "ADEME Base Carbone v23",
            "publisher": "ADEME",
            "version": "v23",
            "date_publi": date(2024, 1, 15),
        },
        {
            "url": "https://www.iea.org/reports/africa-energy-outlook-2024",
            "title": "IEA Africa Energy Outlook 2024",
            "publisher": "IEA",
            "version": "2024",
            "date_publi": date(2024, 6, 15),
        },
        {
            "url": "https://www.ipcc.ch/report/ar6/wg3/",
            "title": "IPCC AR6 Working Group III - Mitigation",
            "publisher": "IPCC",
            "version": "AR6",
            "date_publi": date(2022, 4, 4),
        },
    ]

    sources_by_publisher: dict[str, Source] = {}
    for src_data in sources_to_seed:
        src = Source(
            url=src_data["url"],
            title=src_data["title"],
            publisher=src_data["publisher"],
            version=src_data["version"],
            date_publi=src_data["date_publi"],
            captured_by=curator.id,
            verified_by=validator.id,
            verification_status=VerificationStatus.VERIFIED.value,
            verified_at=datetime.now(timezone.utc),
            created_by_user_id=curator.id,
        )
        db_session.add(src)
        sources_by_publisher[src.publisher] = src
    await db_session.flush()
    return sources_by_publisher


# ---------- SEED_DATA structure ---------------------------------------------


def test_seed_data_is_non_empty() -> None:
    """SEED_DATA contient des entrees."""
    assert len(SEED_DATA) > 0


def test_seed_data_count_at_least_30() -> None:
    """SEED_DATA contient au moins 30 facteurs."""
    assert len(SEED_DATA) >= 30


def test_seed_data_all_codes_unique() -> None:
    """Tous les codes sont uniques (pre-condition pour l'idempotence)."""
    codes = [s.code for s in SEED_DATA]
    assert len(codes) == len(set(codes))


def test_seed_data_8_uemoa_electricity_factors_2024() -> None:
    """Les 8 pays UEMOA ont chacun un facteur electricity 2024."""
    expected_countries = ["CI", "SN", "BF", "ML", "NE", "BJ", "TG", "GW"]
    for country in expected_countries:
        match = [
            s for s in SEED_DATA
            if s.category == "electricity"
            and s.country == country
            and s.year == 2024
        ]
        assert len(match) == 1, (
            f"Manque facteur electricity {country} 2024 (trouve {len(match)})"
        )


def test_seed_data_global_electricity_fallback() -> None:
    """Un facteur electricity global 2024 existe pour fallback."""
    match = [
        s for s in SEED_DATA
        if s.category == "electricity"
        and s.country == "global"
        and s.year == 2024
    ]
    assert len(match) == 1


def test_seed_data_uemoa_2023_variants_exist() -> None:
    """Variantes 2023 existent pour les 8 pays UEMOA (fallback annee)."""
    expected_countries = ["CI", "SN", "BF", "ML", "NE", "BJ", "TG", "GW"]
    for country in expected_countries:
        match = [
            s for s in SEED_DATA
            if s.category == "electricity"
            and s.country == country
            and s.year == 2023
        ]
        assert len(match) == 1


def test_seed_data_3_fuel_factors() -> None:
    """3 facteurs combustibles : diesel, gasoline, butane."""
    fuel_categories = {
        s.category for s in SEED_DATA if s.category.startswith("fuel_")
    }
    assert fuel_categories == {"fuel_diesel", "fuel_gasoline", "fuel_butane"}


def test_seed_data_6_purchases_factors() -> None:
    """6 facteurs ``purchases_*`` : steel, cement, paper, food, plastic, other."""
    purchase_categories = {
        s.category for s in SEED_DATA if s.category.startswith("purchases_")
    }
    assert purchase_categories == {
        "purchases_steel",
        "purchases_cement",
        "purchases_paper",
        "purchases_food",
        "purchases_plastic",
        "purchases_other",
    }


def test_seed_data_3_waste_factors() -> None:
    """3 facteurs dechets : landfill, incineration, compost."""
    waste_categories = {
        s.category for s in SEED_DATA if s.category.startswith("waste_")
    }
    assert waste_categories == {
        "waste_landfill",
        "waste_incineration",
        "waste_compost",
    }


def test_seed_data_transport_factors_4_personal_3_freight() -> None:
    """Transport : 4 personnels (gasoline, diesel, hybrid, electric) +
    3 fret (light truck, heavy truck, river).

    Note : les categories sont distinctes pour respecter la contrainte
    UNIQUE ``(category, country, year)`` (ex. ``transport_personal_gasoline``).
    """
    personal = [
        s for s in SEED_DATA
        if s.category.startswith("transport_personal_")
    ]
    freight = [
        s for s in SEED_DATA
        if s.category.startswith("transport_freight_")
    ]
    assert len(personal) == 4
    assert len(freight) == 3


def test_seed_data_uses_only_known_publishers() -> None:
    """Tous les facteurs referencent ADEME, IEA ou IPCC."""
    publishers = {s.publisher for s in SEED_DATA}
    assert publishers <= {"ADEME", "IEA", "IPCC"}


def test_seed_data_ci_2024_value_close_to_iea_estimate() -> None:
    """electricity_ci_2024 a une valeur ~0.456 (IEA estimate)."""
    match = [
        s for s in SEED_DATA
        if s.code == "electricity_ci_2024"
    ]
    assert len(match) == 1
    assert abs(match[0].value - 0.456) < 0.05  # Tolerance ±0.05.


def test_seed_data_purchases_cement_value() -> None:
    """purchases_cement a une valeur proche de 0.9 kgCO2e/kg (ADEME)."""
    match = [s for s in SEED_DATA if s.code == "purchases_cement_global_2024"]
    assert len(match) == 1
    assert abs(match[0].value - 0.9) < 0.1


# ---------- Seed function ----------------------------------------------------


async def test_seed_emission_factors_first_run(db_session) -> None:
    """First run : tous les facteurs sont inseres."""
    await _seed_minimal_sources(db_session)
    admin = await _make_admin_user(db_session, "seedadmin")

    result = await seed_emission_factors(db_session, admin.id)
    assert result.inserted == len(SEED_DATA)
    assert result.skipped == 0
    assert result.total_in_db == len(SEED_DATA)


async def test_seed_emission_factors_idempotent(db_session) -> None:
    """Second run : 0 nouveaux inserts, tous skippes."""
    await _seed_minimal_sources(db_session)
    admin = await _make_admin_user(db_session, "seedadmin")

    # First run.
    await seed_emission_factors(db_session, admin.id)

    # Second run.
    result2 = await seed_emission_factors(db_session, admin.id)
    assert result2.inserted == 0
    assert result2.skipped == len(SEED_DATA)
    assert result2.total_in_db == len(SEED_DATA)


async def test_seed_emission_factors_links_correct_sources(db_session) -> None:
    """Les facteurs IEA sont lies a la source IEA, IPCC a IPCC, etc."""
    sources = await _seed_minimal_sources(db_session)
    admin = await _make_admin_user(db_session, "seedadmin")

    await seed_emission_factors(db_session, admin.id)

    # electricity_ci_2024 (IEA) doit pointer vers la source IEA.
    stmt = select(EmissionFactor).where(
        EmissionFactor.code == "electricity_ci_2024"
    )
    factor = (await db_session.execute(stmt)).scalar_one()
    assert factor.source_id == sources["IEA"].id

    # waste_landfill_global_2024 (IPCC) doit pointer vers IPCC.
    stmt2 = select(EmissionFactor).where(
        EmissionFactor.code == "waste_landfill_global_2024"
    )
    factor_landfill = (await db_session.execute(stmt2)).scalar_one()
    assert factor_landfill.source_id == sources["IPCC"].id

    # purchases_cement_global_2024 (ADEME) doit pointer vers ADEME.
    stmt3 = select(EmissionFactor).where(
        EmissionFactor.code == "purchases_cement_global_2024"
    )
    factor_cement = (await db_session.execute(stmt3)).scalar_one()
    assert factor_cement.source_id == sources["ADEME"].id


async def test_seed_emission_factors_no_sources_returns_empty(db_session) -> None:
    """Si aucune source ADEME/IEA/IPCC verifiee : seed log un warning et
    retourne 0/0."""
    admin = await _make_admin_user(db_session, "seedadmin")

    result = await seed_emission_factors(db_session, admin.id)
    assert result.inserted == 0


async def test_seed_emission_factors_invalid_admin_raises(db_session) -> None:
    """Admin user inconnu -> ValueError explicite."""
    await _seed_minimal_sources(db_session)
    bogus_id = uuid.uuid4()

    with pytest.raises(ValueError, match="Admin user .* introuvable"):
        await seed_emission_factors(db_session, bogus_id)


async def test_seed_emission_factors_all_are_published(db_session) -> None:
    """Tous les facteurs seedes sont en publication_status='published'."""
    await _seed_minimal_sources(db_session)
    admin = await _make_admin_user(db_session, "seedadmin")

    await seed_emission_factors(db_session, admin.id)

    stmt = select(func.count()).select_from(EmissionFactor).where(
        EmissionFactor.publication_status == PublicationStatus.PUBLISHED.value
    )
    count = (await db_session.execute(stmt)).scalar() or 0
    assert count == len(SEED_DATA)


async def test_seed_emission_factors_account_id_null_for_catalog(db_session) -> None:
    """Les facteurs catalogue ont account_id=NULL (lecture publique F02)."""
    await _seed_minimal_sources(db_session)
    admin = await _make_admin_user(db_session, "seedadmin")

    await seed_emission_factors(db_session, admin.id)

    stmt = select(func.count()).select_from(EmissionFactor).where(
        EmissionFactor.account_id.is_(None)
    )
    count = (await db_session.execute(stmt)).scalar() or 0
    assert count == len(SEED_DATA)


def test_seed_factor_dataclass_frozen() -> None:
    """SeedFactor est un dataclass immuable."""
    f = SEED_DATA[0]
    with pytest.raises(Exception):
        f.value = 99.0  # type: ignore[misc]
