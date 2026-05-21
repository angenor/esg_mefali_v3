"""Tests F25 (feature 044) — endpoint `/api/admin/catalog/summary`.

Couvre :
- 200 ADMIN avec compteurs totaux cohérents,
- 401 anon (pas de token),
- 403 PME (rôle insuffisant).

Suit la convention F09 : SQLite in-memory + ``client``/``db_session`` fixtures.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.core.security import create_access_token, hash_password
from app.models.financing import (
    AccessType,
    Fund,
    FundIntermediary,
    FundType,
    Intermediary,
    IntermediaryType,
    OrganizationType,
)
from app.models.user import User
from tests.conftest import make_account, make_pme_user

pytestmark = pytest.mark.asyncio


async def _make_admin(db: AsyncSession) -> tuple[User, str]:
    user = User(
        email=f"admin-{_uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pw1234567"),
        full_name="Admin",
        company_name="ESG",
        role=UserRole.ADMIN.value,
        account_id=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, create_access_token(str(user.id))


async def _make_fund(
    db: AsyncSession, name: str = "FondTest", status_str: str = "published"
) -> Fund:
    f = Fund(
        name=name,
        organization="Org",
        fund_type=FundType.multilateral,
        description="d",
        eligibility_criteria={},
        sectors_eligible=[],
        required_documents=[],
        esg_requirements={},
        access_type=AccessType.direct,
        application_process=[],
        publication_status=status_str,
    )
    db.add(f)
    await db.flush()
    return f


async def _make_intermediary(
    db: AsyncSession, name: str = "IntermTest", status_str: str = "published"
) -> Intermediary:
    i = Intermediary(
        name=name,
        intermediary_type=IntermediaryType.accredited_entity,
        organization_type=OrganizationType.bank,
        country="SN",
        city="Dakar",
        accreditations=[],
        services_offered={},
        eligibility_for_sme={},
        publication_status=status_str,
    )
    db.add(i)
    await db.flush()
    return i


class TestSummaryAuth:
    async def test_anonymous_returns_401(self, client: AsyncClient) -> None:
        response = await client.get("/api/admin/catalog/summary")
        assert response.status_code == 401

    async def test_pme_returns_403(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        pme = await make_pme_user(db_session)
        await db_session.commit()
        token = create_access_token(str(pme.id))
        response = await client.get(
            "/api/admin/catalog/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestSummaryContent:
    async def test_admin_returns_summary_shape(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, token = await _make_admin(db_session)
        response = await client.get(
            "/api/admin/catalog/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        for key in ("funds", "intermediaries", "offers", "fund_intermediaries"):
            assert key in body
        for k in ("funds", "intermediaries", "offers"):
            assert "total" in body[k]
            assert "by_status" in body[k]
        assert "total" in body["fund_intermediaries"]
        assert "active" in body["fund_intermediaries"]
        assert "expired" in body["fund_intermediaries"]

    async def test_counts_match_db_state(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, token = await _make_admin(db_session)
        f1 = await _make_fund(db_session, "F1", "published")
        f2 = await _make_fund(db_session, "F2", "draft")
        i1 = await _make_intermediary(db_session, "I1", "published")
        # Liaison active.
        fi = FundIntermediary(
            fund_id=f1.id,
            intermediary_id=i1.id,
            accredited_from=date(2024, 1, 1),
            accredited_to=None,
            geographic_coverage=[],
        )
        db_session.add(fi)
        await db_session.commit()

        response = await client.get(
            "/api/admin/catalog/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["funds"]["total"] >= 2
        assert body["intermediaries"]["total"] >= 1
        assert body["fund_intermediaries"]["total"] >= 1
        assert body["fund_intermediaries"]["active"] >= 1
