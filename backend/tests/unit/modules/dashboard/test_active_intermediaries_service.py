"""F21 (US3) — Tests unitaires de _get_active_intermediaries (fallback capitale)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import inspect

from app.models.account import Account
from app.models.application import ApplicationStatus, FundApplication, TargetType
from app.models.financing import Fund, Intermediary
from app.models.user import User
from app.modules.dashboard.service import _get_active_intermediaries

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


async def _make_intermediary(db_session, country: str, name: str = "BOAD") -> Intermediary:
    payload: dict = {
        "name": name,
        "country": country,
        "city": "Capital",
        "intermediary_type": "accredited_entity",
        "organization_type": "development_bank",
        "accreditations": [],
    }
    cols = set(inspect(Intermediary).columns.keys())
    payload = {k: v for k, v in payload.items() if k in cols}
    intermediary = Intermediary(**payload)
    db_session.add(intermediary)
    await db_session.flush()
    return intermediary


def _new_app(user, fund, status, intermediary=None) -> FundApplication:
    target_type = (
        TargetType.intermediary_bank if intermediary else TargetType.fund_direct
    )
    return FundApplication(
        user_id=user.id,
        account_id=user.account_id,
        fund_id=fund.id,
        intermediary_id=intermediary.id if intermediary else None,
        status=status,
        target_type=target_type,
        sections={},
        checklist=[],
    )


async def _make_fund(db_session, name: str = "Fonds Vert") -> Fund:
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


class TestGetActiveIntermediaries:
    async def test_empty_returns_empty(self, db_session) -> None:
        user = await _make_user(db_session)
        result = await _get_active_intermediaries(db_session, user.id)
        assert result == []

    async def test_dedup_by_intermediary(self, db_session) -> None:
        """Plusieurs candidatures via le même intermédiaire = 1 entrée."""
        user = await _make_user(db_session)
        intermediary = await _make_intermediary(db_session, country="SEN", name="BOAD")
        fund1 = await _make_fund(db_session, name="GCF")
        fund2 = await _make_fund(db_session, name="FEM")
        for fund in (fund1, fund2):
            db_session.add(
                _new_app(
                    user, fund, ApplicationStatus.preparing_documents, intermediary
                )
            )
        await db_session.flush()

        result = await _get_active_intermediaries(db_session, user.id)
        assert len(result) == 1
        assert result[0]["name"] == "BOAD"
        assert result[0]["applications_count"] == 2
        assert "GCF" in result[0]["accreditations"]
        assert "FEM" in result[0]["accreditations"]

    async def test_fallback_capital_when_no_lat_lon(self, db_session) -> None:
        user = await _make_user(db_session)
        intermediary = await _make_intermediary(db_session, country="SEN")
        fund = await _make_fund(db_session)
        db_session.add(
            _new_app(user, fund, ApplicationStatus.preparing_documents, intermediary)
        )
        await db_session.flush()

        result = await _get_active_intermediaries(db_session, user.id)
        assert len(result) == 1
        # Capitale Sénégal = Dakar (~14.7167, -17.4677).
        assert result[0]["is_fallback_capital"] is True
        assert 14.0 < result[0]["lat"] < 15.0

    async def test_skip_unknown_country(self, db_session) -> None:
        user = await _make_user(db_session)
        intermediary = await _make_intermediary(db_session, country="USA")
        fund = await _make_fund(db_session)
        db_session.add(
            _new_app(user, fund, ApplicationStatus.preparing_documents, intermediary)
        )
        await db_session.flush()

        result = await _get_active_intermediaries(db_session, user.id)
        # Sans capitale UEMOA, l'intermédiaire est ignoré.
        assert result == []

    async def test_rejected_application_excluded(self, db_session) -> None:
        user = await _make_user(db_session)
        intermediary = await _make_intermediary(db_session, country="CIV")
        fund = await _make_fund(db_session)
        db_session.add(_new_app(user, fund, ApplicationStatus.rejected, intermediary))
        await db_session.flush()

        result = await _get_active_intermediaries(db_session, user.id)
        assert result == []
