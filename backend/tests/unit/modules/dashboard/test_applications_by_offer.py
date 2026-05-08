"""F21 (US1) — Tests unitaires de _get_applications_by_offer."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.models.account import Account
from app.models.application import ApplicationStatus, FundApplication, TargetType
from app.models.financing import Fund, Intermediary
from app.models.user import User
from app.modules.dashboard.service import _get_applications_by_offer

pytestmark = pytest.mark.asyncio


async def _make_user(db_session) -> User:
    account = Account(name=f"Acc-{uuid.uuid4().hex[:6]}")
    db_session.add(account)
    await db_session.flush()
    u = User(
        email=f"u-{uuid.uuid4().hex[:6]}@t.com",
        hashed_password="x",
        full_name="PME",
        company_name="PME SA",
        is_active=True,
        role="PME",
        account_id=account.id,
    )
    db_session.add(u)
    await db_session.flush()
    return u


async def _make_fund(db_session, name: str = "Fonds Vert") -> Fund:
    """Créer un Fund minimal pour tests SQLite."""
    fund = Fund(
        name=name,
        organization="TestOrg",
        fund_type="multilateral",
        description="...",
        eligibility_criteria={},
        sectors_eligible=["agriculture"],
        required_documents=[],
        esg_requirements={},
        status="active",
        access_type="direct",
        application_process=[],
    )
    db_session.add(fund)
    await db_session.flush()
    return fund


async def _make_application(
    db_session,
    user,
    fund,
    status: ApplicationStatus,
    intermediary=None,
) -> FundApplication:
    target_type = (
        TargetType.intermediary_bank if intermediary else TargetType.fund_direct
    )
    payload: dict = {
        "user_id": user.id,
        "account_id": user.account_id,
        "fund_id": fund.id,
        "status": status,
        "target_type": target_type,
        "sections": {},
        "checklist": [],
    }
    if intermediary is not None:
        payload["intermediary_id"] = intermediary.id
    app = FundApplication(**payload)
    db_session.add(app)
    await db_session.flush()
    return app


class TestGetApplicationsByOffer:
    async def test_empty_returns_empty_list(self, db_session) -> None:
        user = await _make_user(db_session)
        cards = await _get_applications_by_offer(db_session, user.id)
        assert cards == []

    async def test_single_active_application_returns_card(self, db_session) -> None:
        user = await _make_user(db_session)
        fund = await _make_fund(db_session, name="GCF")
        await _make_application(
            db_session, user, fund, ApplicationStatus.preparing_documents
        )

        cards = await _get_applications_by_offer(db_session, user.id)
        assert len(cards) == 1
        card = cards[0]
        assert card["fund_name"] == "GCF"
        assert card["intermediary_name"] == "Accès direct"  # pas d'intermédiaire
        assert card["status"] == "preparing_documents"
        assert "Préparation" in card["current_step"]

    async def test_rejected_excluded(self, db_session) -> None:
        user = await _make_user(db_session)
        fund = await _make_fund(db_session)
        await _make_application(db_session, user, fund, ApplicationStatus.rejected)

        cards = await _get_applications_by_offer(db_session, user.id)
        assert cards == []

    async def test_accepted_excluded(self, db_session) -> None:
        user = await _make_user(db_session)
        fund = await _make_fund(db_session)
        await _make_application(db_session, user, fund, ApplicationStatus.accepted)

        cards = await _get_applications_by_offer(db_session, user.id)
        assert cards == []

    async def test_max_limit_5(self, db_session) -> None:
        user = await _make_user(db_session)
        for i in range(7):
            fund = await _make_fund(db_session, name=f"Fund-{i}")
            await _make_application(
                db_session, user, fund, ApplicationStatus.preparing_documents
            )

        cards = await _get_applications_by_offer(db_session, user.id, limit=5)
        assert len(cards) == 5
