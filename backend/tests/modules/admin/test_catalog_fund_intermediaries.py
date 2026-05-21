"""Tests F25 (feature 044) — endpoints liaisons fonds × intermédiaires.

Couvre :
- list complet (mode liste complète, total < 2000),
- list paginé (monkeypatch du seuil),
- filtres ``q``, ``status``, ``fund_id``,
- tri,
- détail 200 + format composite id,
- 404 id introuvable,
- 422 format composite invalide,
- 403 PME.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import date, timedelta

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
from tests.conftest import make_pme_user

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


async def _seed_pair(
    db: AsyncSession,
    fund_name: str = "GCF",
    inter_name: str = "BOAD",
    *,
    accredited_to: date | None = None,
) -> tuple[Fund, Intermediary, FundIntermediary]:
    f = Fund(
        name=fund_name,
        organization="Org",
        fund_type=FundType.multilateral,
        description="d",
        eligibility_criteria={},
        sectors_eligible=[],
        required_documents=[],
        esg_requirements={},
        access_type=AccessType.direct,
        application_process=[],
        publication_status="published",
    )
    i = Intermediary(
        name=inter_name,
        intermediary_type=IntermediaryType.accredited_entity,
        organization_type=OrganizationType.bank,
        country="SN",
        city="Dakar",
        accreditations=[],
        services_offered={},
        eligibility_for_sme={},
        publication_status="published",
    )
    db.add_all([f, i])
    await db.flush()
    fi = FundIntermediary(
        fund_id=f.id,
        intermediary_id=i.id,
        accredited_from=date(2024, 1, 1),
        accredited_to=accredited_to,
        geographic_coverage=[],
    )
    db.add(fi)
    await db.commit()
    return f, i, fi


class TestListAuth:
    async def test_pme_returns_403(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        pme = await make_pme_user(db_session)
        await db_session.commit()
        token = create_access_token(str(pme.id))
        response = await client.get(
            "/api/admin/catalog/fund-intermediaries",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestListContent:
    async def test_empty_returns_zero_total(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, token = await _make_admin(db_session)
        response = await client.get(
            "/api/admin/catalog/fund-intermediaries",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 0
        assert body["paginated"] is False
        assert body["items"] == []

    async def test_full_list_under_threshold(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, token = await _make_admin(db_session)
        await _seed_pair(db_session, "GCF", "BOAD")
        await _seed_pair(db_session, "FEM", "Ecobank")
        response = await client.get(
            "/api/admin/catalog/fund-intermediaries",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert body["paginated"] is False
        assert len(body["items"]) == 2
        ids = [it["id"] for it in body["items"]]
        for cid in ids:
            assert ":" in cid

    async def test_filter_q_by_fund_name(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, token = await _make_admin(db_session)
        await _seed_pair(db_session, "GCF", "BOAD")
        await _seed_pair(db_session, "FEM", "Ecobank")
        response = await client.get(
            "/api/admin/catalog/fund-intermediaries?q=GCF",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["fund_name"] == "GCF"

    async def test_filter_status_active(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, token = await _make_admin(db_session)
        await _seed_pair(db_session, "GCF", "BOAD")  # active (accredited_to=None)
        await _seed_pair(
            db_session, "OLD", "OldBank",
            accredited_to=date.today() - timedelta(days=10),
        )
        response = await client.get(
            "/api/admin/catalog/fund-intermediaries?status=active",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1

    async def test_filter_status_expired(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, token = await _make_admin(db_session)
        await _seed_pair(db_session, "GCF", "BOAD")
        await _seed_pair(
            db_session, "OLD", "OldBank",
            accredited_to=date.today() - timedelta(days=10),
        )
        response = await client.get(
            "/api/admin/catalog/fund-intermediaries?status=expired",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["fund_name"] == "OLD"

    async def test_filter_fund_id(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, token = await _make_admin(db_session)
        f, _, _ = await _seed_pair(db_session, "GCF", "BOAD")
        await _seed_pair(db_session, "FEM", "Ecobank")
        response = await client.get(
            f"/api/admin/catalog/fund-intermediaries?fund_id={f.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["fund_id"] == str(f.id)


class TestDetail:
    async def test_get_detail_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, token = await _make_admin(db_session)
        f, i, fi = await _seed_pair(db_session, "GCF", "BOAD")
        composite = f"{f.id}:{i.id}"
        response = await client.get(
            f"/api/admin/catalog/fund-intermediaries/{composite}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == composite
        assert body["fund_link"] == f"/admin/catalog/funds/{f.id}"
        assert body["intermediary_link"] == f"/admin/catalog/intermediaries/{i.id}"

    async def test_get_detail_404_unknown(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, token = await _make_admin(db_session)
        composite = f"{_uuid.uuid4()}:{_uuid.uuid4()}"
        response = await client.get(
            f"/api/admin/catalog/fund-intermediaries/{composite}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    async def test_get_detail_422_bad_format(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, token = await _make_admin(db_session)
        response = await client.get(
            "/api/admin/catalog/fund-intermediaries/not-a-composite",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422


class TestPaginationConditional:
    """T011 — vérifie le basculement liste complète → paginée via seuil."""

    async def test_paginated_when_threshold_lowered(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        monkeypatch,
    ) -> None:
        """Monkeypatch ``FULL_LIST_THRESHOLD`` à 1 pour forcer la pagination."""
        from app.modules.admin import fund_intermediaries_router

        _, token = await _make_admin(db_session)
        await _seed_pair(db_session, "A", "X")
        await _seed_pair(db_session, "B", "Y")

        monkeypatch.setattr(
            fund_intermediaries_router, "FULL_LIST_THRESHOLD", 1, raising=True,
        )
        response = await client.get(
            "/api/admin/catalog/fund-intermediaries?page=1&page_size=25",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["paginated"] is True
        assert body["page"] == 1
        assert body["page_size"] == 25
        assert len(body["items"]) <= 25
