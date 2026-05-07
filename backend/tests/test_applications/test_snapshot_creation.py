"""F04 — Tests création automatique du snapshot lors de la transition submitted_*."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.models.application import (
    ApplicationStatus,
    FundApplication,
    TargetType,
)
from app.models.financing import (
    AccessType,
    Fund,
    FundType,
    FundStatus,
    Intermediary,
    IntermediaryType,
    OrganizationType,
)
from app.modules.applications.service import update_application_status


@pytest.fixture
async def fund_and_user(db_session):
    """Crée un Account, un User, un Fund et une Application en draft."""
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session, email=f"snap-{uuid.uuid4().hex[:6]}@t.com")
    await db_session.flush()
    fund = Fund(
        name="GCF Test",
        organization="GCF",
        fund_type=FundType.international,
        description="Fonds test",
        eligibility_criteria={},
        sectors_eligible=["agriculture"],
        required_documents=[],
        esg_requirements={},
        status=FundStatus.active,
        access_type=AccessType.direct,
        application_process=[],
    )
    db_session.add(fund)
    await db_session.flush()
    return user, fund


@pytest.mark.asyncio
async def test_snapshot_created_on_submit_to_intermediary(
    db_session, fund_and_user,
) -> None:
    user, fund = fund_and_user
    inter = Intermediary(
        name="BOAD",
        intermediary_type=IntermediaryType.partner_bank,
        organization_type=OrganizationType.bank,
        country="SN",
        city="Dakar",
    )
    db_session.add(inter)
    await db_session.flush()

    app = FundApplication(
        user_id=user.id,
        fund_id=fund.id,
        intermediary_id=inter.id,
        account_id=user.account_id,
        target_type=TargetType.intermediary_bank,
        status=ApplicationStatus.ready_for_intermediary,
        sections={},
        checklist=[],
    )
    db_session.add(app)
    await db_session.flush()

    assert app.snapshot_at is None
    assert app.snapshot_data is None

    # Transition vers submitted_to_intermediary → snapshot créé.
    await update_application_status(db_session, app, "submitted_to_intermediary")

    assert app.snapshot_at is not None
    assert app.snapshot_data is not None
    assert app.snapshot_data["schema_version"] == "1.0"
    assert app.snapshot_data["fund"]["id"] == str(fund.id)
    assert app.snapshot_data["fund"]["name"] == "GCF Test"
    assert app.snapshot_data["intermediary"]["id"] == str(inter.id)
    assert "scores" in app.snapshot_data
    assert "captured_at" in app.snapshot_data


@pytest.mark.asyncio
async def test_snapshot_created_on_submit_to_fund(
    db_session, fund_and_user,
) -> None:
    user, fund = fund_and_user
    app = FundApplication(
        user_id=user.id,
        fund_id=fund.id,
        account_id=user.account_id,
        target_type=TargetType.fund_direct,
        status=ApplicationStatus.ready_for_fund,
        sections={},
        checklist=[],
    )
    db_session.add(app)
    await db_session.flush()

    await update_application_status(db_session, app, "submitted_to_fund")

    assert app.snapshot_at is not None
    assert app.snapshot_data is not None
    assert app.snapshot_data["fund"]["id"] == str(fund.id)
    assert app.snapshot_data["intermediary"] is None


@pytest.mark.asyncio
async def test_snapshot_not_created_on_other_transitions(
    db_session, fund_and_user,
) -> None:
    """Transitions non-submit ne créent pas de snapshot."""
    user, fund = fund_and_user
    app = FundApplication(
        user_id=user.id,
        fund_id=fund.id,
        account_id=user.account_id,
        target_type=TargetType.fund_direct,
        status=ApplicationStatus.draft,
        sections={},
        checklist=[],
    )
    db_session.add(app)
    await db_session.flush()

    # draft → preparing_documents : pas de snapshot.
    await update_application_status(db_session, app, "preparing_documents")
    assert app.snapshot_at is None
    assert app.snapshot_data is None


@pytest.mark.asyncio
async def test_snapshot_idempotent_on_resubmit(
    db_session, fund_and_user,
) -> None:
    """Un second submit ne réécrase pas le snapshot d'origine."""
    user, fund = fund_and_user
    app = FundApplication(
        user_id=user.id,
        fund_id=fund.id,
        account_id=user.account_id,
        target_type=TargetType.fund_direct,
        status=ApplicationStatus.ready_for_intermediary,
        sections={},
        checklist=[],
    )
    db_session.add(app)
    await db_session.flush()

    await update_application_status(db_session, app, "submitted_to_intermediary")
    first_snapshot_at = app.snapshot_at
    first_snapshot_data = dict(app.snapshot_data)
    assert first_snapshot_at is not None

    # Transition submit→submit (e.g. submitted_to_intermediary → submitted_to_fund)
    await update_application_status(db_session, app, "submitted_to_fund")
    # Le snapshot reste IDENTIQUE (immuable, FR-012)
    assert app.snapshot_at == first_snapshot_at
    assert app.snapshot_data == first_snapshot_data


@pytest.mark.asyncio
async def test_snapshot_data_contains_required_keys(
    db_session, fund_and_user,
) -> None:
    user, fund = fund_and_user
    app = FundApplication(
        user_id=user.id,
        fund_id=fund.id,
        account_id=user.account_id,
        target_type=TargetType.fund_direct,
        status=ApplicationStatus.ready_for_intermediary,
        sections={},
        checklist=[],
    )
    db_session.add(app)
    await db_session.flush()

    await update_application_status(db_session, app, "submitted_to_intermediary")

    expected_keys = {
        "schema_version", "captured_at", "referential", "fund",
        "intermediary", "offer", "scores",
        "documents_requis_at_submission", "source_ids_cited",
    }
    assert expected_keys <= set(app.snapshot_data.keys())
