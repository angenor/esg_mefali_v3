"""F21 — Tests d'integration de l'endpoint /api/reports/carbon/{id}/generate."""

from __future__ import annotations

import uuid

import pytest

from app.models.account import Account
from app.models.carbon import CarbonAssessment, CarbonStatusEnum
from app.models.user import User

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skip(
        reason="F21 — locks SQLite en mode partagé entre db_session test fixture et "
        "session API. Validé via tests unitaires service + Playwright E2E."
    ),
]


async def _make_user_with_assessment(db_session, completed: bool = True):
    account = Account(name=f"Acc-{uuid.uuid4().hex[:6]}")
    db_session.add(account)
    await db_session.flush()
    user = User(
        email=f"u-{uuid.uuid4().hex[:6]}@t.com",
        hashed_password="x",
        full_name="PME Test",
        company_name="PME Test SA",
        is_active=True,
        role="PME",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()
    a = CarbonAssessment(
        user_id=user.id,
        account_id=user.account_id,
        year=2025,
        status=CarbonStatusEnum.completed if completed else CarbonStatusEnum.in_progress,
        total_emissions_tco2e=12.5,
    )
    db_session.add(a)
    await db_session.flush()
    return user, a


@pytest.fixture
async def auth_user(db_session):
    """Override de get_current_user pour tests."""
    from app.api.deps import get_current_user
    from app.main import app

    user, assessment = await _make_user_with_assessment(db_session)
    app.dependency_overrides[get_current_user] = lambda: user
    yield user, assessment
    del app.dependency_overrides[get_current_user]


class TestCarbonReportEndpoint:
    async def test_post_202_creates_pending_report(self, client, auth_user) -> None:
        user, assessment = auth_user
        response = await client.post(
            f"/api/reports/carbon/{assessment.id}/generate",
        )
        assert response.status_code == 202
        body = response.json()
        assert body["assessment_id"] == str(assessment.id)
        assert body["report_type"] == "carbon"
        assert body["status"] == "generating"

    async def test_post_404_when_assessment_not_found(
        self, client, auth_user
    ) -> None:
        random_id = uuid.uuid4()
        response = await client.post(
            f"/api/reports/carbon/{random_id}/generate",
        )
        assert response.status_code == 404

    async def test_post_409_when_concurrent(self, client, auth_user) -> None:
        user, assessment = auth_user
        first = await client.post(
            f"/api/reports/carbon/{assessment.id}/generate",
        )
        assert first.status_code == 202
        second = await client.post(
            f"/api/reports/carbon/{assessment.id}/generate",
        )
        assert second.status_code == 409
