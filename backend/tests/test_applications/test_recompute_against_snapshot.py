"""F04 — Tests endpoint recompute-against-snapshot et logique de recompute."""

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
)
from app.modules.applications.recompute import recompute_against_snapshot
from app.modules.applications.snapshot import SnapshotMissingError


@pytest.fixture
async def fund_and_user(db_session):
    from tests.conftest import make_pme_user
    user = await make_pme_user(db_session, email=f"rec-{uuid.uuid4().hex[:6]}@t.com")
    fund = Fund(
        name="GCF Reco",
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
async def test_recompute_returns_match_when_score_unchanged(
    db_session, fund_and_user,
) -> None:
    user, fund = fund_and_user
    snapshot = {
        "schema_version": "1.0",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "referential": {
            "id": str(uuid.uuid4()),
            "version": "1.2",
        },
        "fund": {"id": str(fund.id)},
        "intermediary": None,
        "offer": None,
        "scores": {
            "esg_total": 72.5,
            "esg_breakdown": {"E": 80, "S": 70, "G": 65},
            "credit_score": None,
            "carbon_total_tco2e": 12.3,
        },
        "documents_requis_at_submission": [],
        "source_ids_cited": [],
    }
    app = FundApplication(
        user_id=user.id,
        fund_id=fund.id,
        account_id=user.account_id,
        target_type=TargetType.fund_direct,
        status=ApplicationStatus.submitted_to_fund,
        sections={},
        checklist=[],
        snapshot_at=datetime.now(timezone.utc),
        snapshot_data=snapshot,
    )
    db_session.add(app)
    await db_session.flush()

    result = await recompute_against_snapshot(app.id, db_session)
    assert result["application_id"] == str(app.id)
    assert result["comparison_with_origin"]["match"] is True
    assert result["comparison_with_origin"]["delta"] == 0.0
    assert result["referential_version_used"] == "1.2"
    assert result["score"]["esg_total"] == 72.5


@pytest.mark.asyncio
async def test_recompute_raises_409_if_no_snapshot(
    db_session, fund_and_user,
) -> None:
    """Une candidature en draft (snapshot_at=None) → SnapshotMissingError."""
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

    with pytest.raises(SnapshotMissingError):
        await recompute_against_snapshot(app.id, db_session)


@pytest.mark.asyncio
async def test_recompute_raises_when_application_not_found(db_session) -> None:
    fake_id = uuid.uuid4()
    with pytest.raises(ValueError):
        await recompute_against_snapshot(fake_id, db_session)


@pytest.mark.asyncio
async def test_recompute_endpoint_409_on_draft(client, db_session) -> None:
    """L'endpoint retourne HTTP 409 si la candidature n'a pas été soumise."""
    from app.api.deps import get_current_user
    from app.main import app as fastapi_app
    from tests.conftest import make_pme_user

    user = await make_pme_user(
        db_session, email=f"recapi-{uuid.uuid4().hex[:6]}@t.com",
    )
    fund = Fund(
        name="GCF API",
        organization="GCF",
        fund_type=FundType.international,
        description="X",
        eligibility_criteria={},
        sectors_eligible=[],
        required_documents=[],
        esg_requirements={},
        status=FundStatus.active,
        access_type=AccessType.direct,
        application_process=[],
    )
    db_session.add(fund)
    await db_session.flush()
    app_obj = FundApplication(
        user_id=user.id,
        fund_id=fund.id,
        account_id=user.account_id,
        target_type=TargetType.fund_direct,
        status=ApplicationStatus.draft,
        sections={},
        checklist=[],
    )
    db_session.add(app_obj)
    await db_session.commit()

    fastapi_app.dependency_overrides[get_current_user] = lambda: user
    try:
        resp = await client.post(
            f"/api/applications/{app_obj.id}/recompute-against-snapshot",
        )
        assert resp.status_code == 409
        assert "submit" in resp.json()["detail"].lower()
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)
