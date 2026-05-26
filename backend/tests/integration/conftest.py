"""Fixtures partagées pour les tests d'intégration F048 (parcours candidature).

Construit le graphe d'entités minimal nécessaire au parcours « créer un
dossier » : Account → User (PME) → Source vérifiée → Fund + Intermediary →
FundIntermediary → Offer publiée → Project actif.

Réutilise les jeux de champs éprouvés de ``tests/test_offers/conftest.py``.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.financing import (
    AccessType,
    Fund,
    FundIntermediary,
    FundStatus,
    FundType,
    Intermediary,
    IntermediaryType,
    OrganizationType,
)
from app.models.offer import Offer
from app.models.project import Project
from app.models.source import Source
from app.models.user import User


@pytest.fixture
async def f048_account(db_session: AsyncSession) -> Account:
    account = Account(name=f"PME-{uuid.uuid4().hex[:6]}")
    db_session.add(account)
    await db_session.flush()
    return account


@pytest.fixture
async def f048_pme_user(db_session: AsyncSession, f048_account: Account) -> User:
    user = User(
        email=f"pme-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="x",
        full_name="PME Test",
        company_name="PME Test SA",
        role="PME",
        account_id=f048_account.id,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def f048_admins(db_session: AsyncSession) -> tuple[User, User]:
    """2 admins distincts pour le sourçage 4-yeux (F01)."""
    admin1 = User(
        email=f"admin1-{uuid.uuid4().hex[:6]}@mefali.test",
        hashed_password="x",
        full_name="Admin1",
        company_name="Mefali",
        role="ADMIN",
        account_id=None,
    )
    admin2 = User(
        email=f"admin2-{uuid.uuid4().hex[:6]}@mefali.test",
        hashed_password="x",
        full_name="Admin2",
        company_name="Mefali",
        role="ADMIN",
        account_id=None,
    )
    db_session.add_all([admin1, admin2])
    await db_session.flush()
    return admin1, admin2


@pytest.fixture
async def f048_source(db_session: AsyncSession, f048_admins) -> Source:
    captured_by, verified_by = f048_admins
    source = Source(
        url=f"https://example.test/source-{uuid.uuid4().hex[:6]}",
        title="Source vérifiée F048",
        publisher="TestPub",
        version="1.0",
        date_publi=date.today(),
        captured_by=captured_by.id,
        created_by_user_id=captured_by.id,
        verified_by=verified_by.id,
        verified_at=datetime.now(timezone.utc),
        verification_status="verified",
    )
    db_session.add(source)
    await db_session.flush()
    return source


@pytest.fixture
async def f048_fund(db_session: AsyncSession, f048_source: Source) -> Fund:
    fund = Fund(
        name="GCF Test",
        organization="Green Climate Fund",
        fund_type=FundType.multilateral,
        description="Fonds pour adaptation et mitigation",
        eligibility_criteria={"sectors": ["agriculture", "energy"]},
        sectors_eligible=["agriculture", "energy"],
        required_documents=[],
        esg_requirements={},
        status=FundStatus.active,
        access_type=AccessType.intermediary_required,
        application_process=[],
        typical_timeline_months=18,
        min_amount=Decimal("10000000"),
        min_amount_currency="XOF",
        max_amount=Decimal("100000000"),
        max_amount_currency="XOF",
        instruments=["subvention"],
        theme=["mitigation"],
        submission_mode="rolling",
        source_id=f048_source.id,
        publication_status="published",
    )
    db_session.add(fund)
    await db_session.flush()
    return fund


@pytest.fixture
async def f048_intermediary(
    db_session: AsyncSession, f048_source: Source,
) -> Intermediary:
    intermediary = Intermediary(
        name="BOAD",
        intermediary_type=IntermediaryType.accredited_entity,
        organization_type=OrganizationType.development_bank,
        country="SN",
        city="Dakar",
        accreditations=["GCF"],
        services_offered={},
        eligibility_for_sme={},
        required_documents=[],
        fees_structured={},
        processing_time_days_min=90,
        processing_time_days_max=180,
        disbursement_time_days_min=30,
        disbursement_time_days_max=60,
        success_rate=Decimal("0.7500"),
        is_active=True,
        source_id=f048_source.id,
        publication_status="published",
        version="1.0",
        valid_from=date.today(),
    )
    db_session.add(intermediary)
    await db_session.flush()
    return intermediary


@pytest.fixture
async def f048_fund_intermediary(
    db_session: AsyncSession,
    f048_fund: Fund,
    f048_intermediary: Intermediary,
    f048_source: Source,
) -> FundIntermediary:
    fi = FundIntermediary(
        fund_id=f048_fund.id,
        intermediary_id=f048_intermediary.id,
        accredited_from=date.today(),
        accreditation_source_id=f048_source.id,
        version="1.0",
        valid_from=date.today(),
    )
    db_session.add(fi)
    await db_session.flush()
    return fi


@pytest.fixture
async def f048_offer(
    db_session: AsyncSession,
    f048_fund: Fund,
    f048_intermediary: Intermediary,
    f048_fund_intermediary: FundIntermediary,
    f048_source: Source,
) -> Offer:
    offer = Offer(
        fund_id=f048_fund.id,
        intermediary_id=f048_intermediary.id,
        name=f"{f048_fund.name} via {f048_intermediary.name}",
        accepted_languages=["FR"],
        effective_criteria={},
        effective_required_documents=[],
        effective_fees={},
        is_active=True,
        publication_status="published",
        source_id=f048_source.id,
        version="1.0",
        valid_from=date.today(),
    )
    db_session.add(offer)
    await db_session.flush()
    return offer


@pytest.fixture
async def f048_project(db_session: AsyncSession, f048_account: Account) -> Project:
    project = Project(
        account_id=f048_account.id,
        name="Solarisation Boulangerie Dakar",
        status="draft",
        objective_env=["energie_renouvelable"],
    )
    db_session.add(project)
    await db_session.flush()
    return project
