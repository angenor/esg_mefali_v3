"""Tests d'integration de la chaine carbone F17 (T018-T020bis, T033, T035, T045).

Couvre :
    - Pipeline complet CI -> facteur electricity_ci_2024 (T018).
    - Pipeline SN -> factor distinct de CI (T019).
    - Pipeline sans country -> fallback global (T020).
    - Pipeline parametrize 8 pays UEMOA (T020bis / SC-004).
    - Pipeline ``purchases_cement`` reconnu (T033).
    - Bilan avec ``purchases`` -> apparait dans by_category (T035).
    - Validation reduction_plan a la finalisation (T045).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

from app.core.constants import UserRole
from app.models.account import Account
from app.models.carbon import CarbonAssessment, CarbonStatusEnum
from app.models.company import CompanyProfile
from app.models.emission_factor import EmissionFactor
from app.models.source import PublicationStatus, Source, VerificationStatus
from app.models.user import User
from app.modules.carbon.factor_service import (
    EmissionFactorNotFoundError,
    get_emission_factor,
)
from app.modules.carbon.seed_factors import seed_emission_factors


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


async def _seed_three_sources(db_session) -> None:
    """Seed les 3 sources minimales (ADEME, IEA, IPCC)."""
    curator = await _create_admin(db_session, "curator")
    validator = await _create_admin(db_session, "validator")

    sources = [
        ("https://base-empreinte.ademe.fr/", "ADEME Base Carbone v23", "ADEME"),
        (
            "https://www.iea.org/reports/africa-energy-outlook-2024",
            "IEA Africa Energy Outlook 2024",
            "IEA",
        ),
        (
            "https://www.ipcc.ch/report/ar6/wg3/",
            "IPCC AR6 Working Group III - Mitigation",
            "IPCC",
        ),
    ]
    for url, title, publisher in sources:
        src = Source(
            url=url,
            title=title,
            publisher=publisher,
            version="2024" if "2024" in url else "v23",
            date_publi=date(2024, 1, 1),
            captured_by=curator.id,
            verified_by=validator.id,
            verification_status=VerificationStatus.VERIFIED.value,
            verified_at=datetime.now(timezone.utc),
            created_by_user_id=curator.id,
        )
        db_session.add(src)
    await db_session.flush()


@pytest.fixture
async def seeded_factors(db_session):
    """Setup : sources F01 + facteurs F17 seedes en BDD."""
    await _seed_three_sources(db_session)
    admin = await _create_admin(db_session, "seedadmin")
    result = await seed_emission_factors(db_session, admin.id)
    assert result.inserted > 0
    return admin


# ---------- T018 : pipeline CI ----------------------------------------------


async def test_pipeline_ci_electricity_factor(seeded_factors, db_session):
    """T018 — country='CI', year=2024 -> factor.code='electricity_ci_2024',
    value~=0.456."""
    resolution = await get_emission_factor(
        db_session, category="electricity", country="CI", year=2024,
    )
    assert resolution.factor.code == "electricity_ci_2024"
    assert abs(float(resolution.factor.value) - 0.456) < 0.001
    assert resolution.is_approximate is False
    assert resolution.factor.source_id is not None


# ---------- T019 : pipeline SN distinct CI -----------------------------------


async def test_pipeline_sn_electricity_different_from_ci(seeded_factors, db_session):
    """T019 — SN -> factor.code='electricity_sn_2024', value distincte de CI."""
    resolution_ci = await get_emission_factor(
        db_session, category="electricity", country="CI", year=2024,
    )
    resolution_sn = await get_emission_factor(
        db_session, category="electricity", country="SN", year=2024,
    )
    assert resolution_sn.factor.code == "electricity_sn_2024"
    assert resolution_sn.factor.id != resolution_ci.factor.id
    assert float(resolution_sn.factor.value) != float(resolution_ci.factor.value)


# ---------- T020 : pipeline sans country -> fallback global -----------------


async def test_pipeline_no_country_falls_back_to_global(seeded_factors, db_session):
    """T020 — country=None -> facteur global, is_approximate=True."""
    resolution = await get_emission_factor(
        db_session, category="electricity", country=None, year=2024,
    )
    assert resolution.factor.country == "global"
    assert resolution.is_approximate is True
    assert resolution.fallback_reason == "country_global"


# ---------- T020bis : pipeline parametrize 8 pays UEMOA ---------------------


@pytest.mark.parametrize(
    "country_code", ["CI", "SN", "BF", "ML", "NE", "BJ", "TG", "GW"]
)
async def test_pipeline_all_uemoa_countries_use_correct_factor(
    seeded_factors, db_session, country_code
):
    """T020bis / SC-004 — Pour chaque pays UEMOA, le facteur correspondant
    est retourne avec un code qui contient le country lowercase."""
    resolution = await get_emission_factor(
        db_session, category="electricity", country=country_code, year=2024,
    )
    expected_prefix = f"electricity_{country_code.lower()}_"
    assert resolution.factor.code.startswith(expected_prefix), (
        f"Pour pays {country_code}, attendu prefixe '{expected_prefix}' mais "
        f"obtenu '{resolution.factor.code}'"
    )
    assert resolution.is_approximate is False


async def test_pipeline_8_uemoa_factors_are_distinct(seeded_factors, db_session):
    """SC-004 (suite) — Les 8 facteurs UEMOA ont des IDs distincts."""
    countries = ["CI", "SN", "BF", "ML", "NE", "BJ", "TG", "GW"]
    factor_ids = []
    for code in countries:
        resolution = await get_emission_factor(
            db_session, category="electricity", country=code, year=2024,
        )
        factor_ids.append(resolution.factor.id)
    assert len(set(factor_ids)) == 8


# ---------- T033 : pipeline purchases_cement ---------------------------------


async def test_pipeline_purchases_cement_recognized(seeded_factors, db_session):
    """T033 — purchases_cement -> factor.code='purchases_cement_global_2024'."""
    resolution = await get_emission_factor(
        db_session, category="purchases_cement", country=None, year=2024,
    )
    assert resolution.factor.code == "purchases_cement_global_2024"
    assert abs(float(resolution.factor.value) - 0.9) < 0.05
    assert resolution.factor.unit == "kgCO2e/kg"


async def test_pipeline_purchases_steel_recognized(seeded_factors, db_session):
    """T033 (variante) — purchases_steel resolved."""
    resolution = await get_emission_factor(
        db_session, category="purchases_steel", country=None, year=2024,
    )
    assert resolution.factor.code == "purchases_steel_global_2024"


# ---------- T035 : ventilation purchases dans le summary ---------------------


async def test_assessment_summary_includes_purchases_category(
    seeded_factors, db_session
):
    """T035 — Un bilan avec entries purchases voit la categorie apparaitre
    dans by_category du summary."""
    from app.modules.carbon.service import (
        add_entries,
        complete_assessment,
        get_assessment_summary,
    )

    # Cree un account pour le PME.
    account = Account(name=f"TestCo-{uuid.uuid4().hex[:6]}")
    db_session.add(account)
    await db_session.flush()
    user = User(
        email=f"pme-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="x",
        full_name="Test User",
        company_name="TestCo",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()

    # Cree un bilan in_progress.
    assessment = CarbonAssessment(
        user_id=user.id,
        account_id=account.id,
        year=2024,
        sector="manufacturing",
        status=CarbonStatusEnum.in_progress,
        completed_categories=[],
    )
    db_session.add(assessment)
    await db_session.flush()

    # Resoudre les facteurs.
    purchases_resolution = await get_emission_factor(
        db_session, category="purchases_cement", country=None, year=2024,
    )
    energy_resolution = await get_emission_factor(
        db_session, category="electricity", country="CI", year=2024,
    )

    # Ajouter 2 entries (energy CI + purchases cement).
    entries = [
        {
            "category": "energy",
            "subcategory": energy_resolution.factor.code,
            "quantity": 1000.0,
            "unit": "kWh",
            "emission_factor": float(energy_resolution.factor.value),
            "emissions_tco2e": 0.456,
            "source_description": "Electricite test",
            "source_id": energy_resolution.factor.source_id,
            "factor_id": energy_resolution.factor.id,
        },
        {
            "category": "purchases",
            "subcategory": purchases_resolution.factor.code,
            "quantity": 50000.0,  # 50t en kg
            "unit": "kg",
            "emission_factor": float(purchases_resolution.factor.value),
            "emissions_tco2e": 45.0,
            "source_description": "Achat ciment",
            "source_id": purchases_resolution.factor.source_id,
            "factor_id": purchases_resolution.factor.id,
        },
    ]
    await add_entries(db_session, assessment, entries)

    # Generer le summary.
    summary = await get_assessment_summary(db_session, assessment)
    assert "by_category" in summary
    by_cat = summary["by_category"]
    assert "energy" in by_cat
    assert "purchases" in by_cat, (
        f"Attendu 'purchases' dans by_category, vu : {list(by_cat.keys())}"
    )
    # Verifier les valeurs.
    assert by_cat["purchases"]["entries_count"] == 1
    assert abs(by_cat["purchases"]["emissions_tco2e"] - 45.0) < 0.01


# ---------- T045 : validation reduction_plan a la finalisation ---------------


async def test_finalize_assessment_reduction_plan_validates(
    seeded_factors, db_session
):
    """T045 — complete_assessment valide le schema F17 du reduction_plan
    avant attribution."""
    from app.modules.carbon.service import complete_assessment

    # Setup minimum.
    account = Account(name="TestCo")
    db_session.add(account)
    await db_session.flush()
    user = User(
        email=f"pme-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="x",
        full_name="Test User",
        company_name="TestCo",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()

    assessment = CarbonAssessment(
        user_id=user.id,
        account_id=account.id,
        year=2024,
        status=CarbonStatusEnum.in_progress,
        completed_categories=[],
    )
    db_session.add(assessment)
    await db_session.flush()

    valid_plan = {
        "actions": [
            {
                "title": "Passer au solaire",
                "description": "Installation 5 kWc panneaux photovoltaiques.",
                "estimated_reduction_tco2e": 1.2,
                "cost_estimate_fcfa": 4_500_000,
                "timeline": "6-12 mois",
                "source_id": str(uuid.uuid4()),
                "unsourced": False,
            },
            {
                "title": "Optimiser tournees",
                "description": "Reorganisation des tournees.",
                "estimated_reduction_tco2e": 0.5,
                "cost_estimate_fcfa": None,
                "timeline": "0-3 mois",
                "source_id": None,
                "unsourced": True,
            },
        ],
    }
    completed = await complete_assessment(
        db_session, assessment, reduction_plan=valid_plan,
    )
    assert completed.status == CarbonStatusEnum.completed
    assert completed.reduction_plan is not None
    assert len(completed.reduction_plan["actions"]) == 2


async def test_finalize_assessment_invalid_reduction_plan_raises(
    seeded_factors, db_session
):
    """T045 — Un reduction_plan incoherent (source_id + unsourced=True)
    leve ValidationError."""
    from app.modules.carbon.service import complete_assessment
    from pydantic import ValidationError

    account = Account(name="TestCo")
    db_session.add(account)
    await db_session.flush()
    user = User(
        email=f"pme-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="x",
        full_name="Test User",
        company_name="TestCo",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()

    assessment = CarbonAssessment(
        user_id=user.id,
        account_id=account.id,
        year=2024,
        status=CarbonStatusEnum.in_progress,
        completed_categories=[],
    )
    db_session.add(assessment)
    await db_session.flush()

    invalid_plan = {
        "actions": [
            {
                "title": "Action incoherente",
                "description": "Test",
                "estimated_reduction_tco2e": 1.0,
                "cost_estimate_fcfa": None,
                "timeline": "0-3 mois",
                "source_id": str(uuid.uuid4()),
                "unsourced": True,  # incoherent : source_id + unsourced=True.
            },
        ],
    }
    with pytest.raises(ValidationError):
        await complete_assessment(
            db_session, assessment, reduction_plan=invalid_plan,
        )


async def test_finalize_assessment_legacy_reduction_plan_accepted(
    seeded_factors, db_session
):
    """T046 — Plan legacy (sans 'actions') accepte sans validation Pydantic
    pour retro-compatibilite."""
    from app.modules.carbon.service import complete_assessment

    account = Account(name="TestCo")
    db_session.add(account)
    await db_session.flush()
    user = User(
        email=f"pme-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="x",
        full_name="Test User",
        company_name="TestCo",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()

    assessment = CarbonAssessment(
        user_id=user.id,
        account_id=account.id,
        year=2024,
        status=CarbonStatusEnum.in_progress,
        completed_categories=[],
    )
    db_session.add(assessment)
    await db_session.flush()

    legacy_plan = {
        "quick_wins": [
            {"action": "Passer au solaire", "reduction_tco2e": 1.2, "savings_fcfa": 800_000},
        ],
        "long_term": [
            {"action": "Vehicules electriques", "reduction_tco2e": 2.5, "savings_fcfa": 5_000_000},
        ],
    }
    completed = await complete_assessment(
        db_session, assessment, reduction_plan=legacy_plan,
    )
    assert completed.reduction_plan == legacy_plan
