"""Fixtures partagées pour les tests F07 Offers."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.models.source import Source
from app.models.user import User
from tests.conftest import make_account, make_pme_user


@pytest.fixture
async def two_admins(db_session: AsyncSession) -> tuple[User, User]:
    """Crée 2 admins distincts (4-eyes)."""
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
    await db_session.commit()
    return admin1, admin2


@pytest.fixture
async def verified_source(
    db_session: AsyncSession, two_admins,
) -> Source:
    """Crée une Source verified (4-eyes respecté)."""
    captured_by, verified_by = two_admins
    source = Source(
        url=f"https://example.test/source-{uuid.uuid4().hex[:6]}",
        title="Test Source Verified",
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
    await db_session.commit()
    return source


@pytest.fixture
async def draft_source(
    db_session: AsyncSession, two_admins,
) -> Source:
    """Crée une Source en draft (verification_status='draft')."""
    captured_by, _ = two_admins
    source = Source(
        url=f"https://example.test/draft-{uuid.uuid4().hex[:6]}",
        title="Test Source Draft",
        publisher="TestPub",
        version="1.0",
        date_publi=date.today(),
        captured_by=captured_by.id,
        created_by_user_id=captured_by.id,
        verification_status="draft",
    )
    db_session.add(source)
    await db_session.commit()
    return source


@pytest.fixture
async def basic_fund(
    db_session: AsyncSession, verified_source: Source,
) -> Fund:
    """Crée un Fund basique en publication_status='published'."""
    fund = Fund(
        name="GCF Test",
        organization="Green Climate Fund",
        fund_type=FundType.multilateral,
        description="Fonds pour adaptation et mitigation",
        eligibility_criteria={
            "min_company_age": 3,
            "max_company_revenue": 1_000_000_000,
            "sectors": ["agriculture", "energy"],
        },
        sectors_eligible=["agriculture", "energy"],
        required_documents=[
            {"title": "Statuts", "source_id": str(verified_source.id), "mandatory": True},
            {"title": "Audit financier", "source_id": str(verified_source.id), "mandatory": False},
        ],
        esg_requirements={},
        status=FundStatus.active,
        access_type=AccessType.intermediary_required,
        application_process=[],
        typical_timeline_months=18,
        # Money typed
        min_amount=Decimal("10000000"),
        min_amount_currency="XOF",
        max_amount=Decimal("100000000"),
        max_amount_currency="XOF",
        # F07
        instruments=["subvention"],
        theme=["mitigation"],
        submission_mode="rolling",
        source_id=verified_source.id,
        publication_status="published",
    )
    db_session.add(fund)
    await db_session.commit()
    return fund


@pytest.fixture
async def basic_intermediary(
    db_session: AsyncSession, verified_source: Source,
) -> Intermediary:
    """Crée un Intermediary basique en publication_status='published'."""
    intermediary = Intermediary(
        name="BOAD",
        intermediary_type=IntermediaryType.accredited_entity,
        organization_type=OrganizationType.development_bank,
        country="SN",
        city="Dakar",
        accreditations=["GCF"],
        services_offered={},
        eligibility_for_sme={
            "min_company_age": 5,
            "max_company_revenue": 800_000_000,
        },
        required_documents=[
            {"title": "Statuts", "source_id": str(verified_source.id), "mandatory": False},
            {"title": "Plan d'affaires", "source_id": str(verified_source.id), "mandatory": True},
        ],
        fees_structured={
            "doc_fee_amount": {"amount": "50000.00", "currency": "XOF"},
            "fee_rate_min": 0.02,
            "fee_rate_max": 0.05,
        },
        processing_time_days_min=90,
        processing_time_days_max=180,
        disbursement_time_days_min=30,
        disbursement_time_days_max=60,
        success_rate=Decimal("0.7500"),
        is_active=True,
        source_id=verified_source.id,
        publication_status="published",
        version="1.0",
        valid_from=date.today(),
    )
    db_session.add(intermediary)
    await db_session.commit()
    return intermediary


@pytest.fixture
async def basic_fund_intermediary(
    db_session: AsyncSession,
    basic_fund: Fund,
    basic_intermediary: Intermediary,
    verified_source: Source,
) -> FundIntermediary:
    """Lie le fond et l'intermédiaire."""
    fi = FundIntermediary(
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
        accredited_from=date.today(),
        accreditation_source_id=verified_source.id,
        version="1.0",
        valid_from=date.today(),
    )
    db_session.add(fi)
    await db_session.commit()
    return fi


@pytest.fixture
async def published_offer(
    db_session: AsyncSession,
    basic_fund: Fund,
    basic_intermediary: Intermediary,
    basic_fund_intermediary: FundIntermediary,
    verified_source: Source,
) -> Offer:
    """Crée une offre publiée + active liée au couple basic."""
    offer = Offer(
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
        name=f"{basic_fund.name} via {basic_intermediary.name}",
        accepted_languages=["FR"],
        effective_criteria={"min_company_age": 5},
        effective_required_documents=[
            {"title": "Statuts", "mandatory": True},
        ],
        effective_fees={
            "total_min": {"amount": "550000.00", "currency": "XOF"},
            "total_max": {"amount": "550000.00", "currency": "XOF"},
        },
        effective_processing_time_days_min=630,
        effective_processing_time_days_max=720,
        is_active=True,
        publication_status="published",
        source_id=verified_source.id,
        version="1.0",
        valid_from=date.today(),
    )
    db_session.add(offer)
    await db_session.commit()
    return offer


@pytest.fixture
async def draft_offer(
    db_session: AsyncSession,
    basic_fund: Fund,
    basic_intermediary: Intermediary,
    basic_fund_intermediary: FundIntermediary,
    verified_source: Source,
) -> Offer:
    """Crée une offre en draft (is_active=False, publication_status='draft')."""
    offer = Offer(
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
        name=f"{basic_fund.name} via {basic_intermediary.name} - Draft",
        accepted_languages=["FR"],
        effective_criteria={},
        effective_required_documents=[],
        effective_fees={},
        is_active=False,
        publication_status="draft",
        source_id=verified_source.id,
        version="2.0",  # version distincte pour éviter unique constraint
        valid_from=date.today(),
    )
    db_session.add(offer)
    await db_session.commit()
    return offer
