"""Tests F25 (feature 044) — Filtres statut + versioning des 3 onglets primaires.

US2 P2 : vérifie que les routers F09 existants exposent `version`,
`valid_from`, `valid_to`, `superseded_by` quand non NULL, et que les
filtres `publication_status` continuent à fonctionner après l'enrichissement
de la sérialisation.
"""

from __future__ import annotations

import uuid as _uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.core.security import create_access_token, hash_password
from app.models.financing import (
    AccessType,
    Fund,
    FundType,
    Intermediary,
    IntermediaryType,
    OrganizationType,
)
from app.models.user import User

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


class TestFundsVersioningExposed:
    async def test_funds_list_exposes_versioning_fields(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, token = await _make_admin(db_session)
        # Crée 2 fonds : v1 déprécié remplacé par v2 published.
        v2 = Fund(
            name="FundV2",
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
            version="2.0",
        )
        db_session.add(v2)
        await db_session.flush()
        v1 = Fund(
            name="FundV1",
            organization="Org",
            fund_type=FundType.multilateral,
            description="d",
            eligibility_criteria={},
            sectors_eligible=[],
            required_documents=[],
            esg_requirements={},
            access_type=AccessType.direct,
            application_process=[],
            publication_status="draft",
            version="1.0",
            superseded_by=v2.id,
        )
        db_session.add(v1)
        await db_session.commit()

        response = await client.get(
            "/api/admin/funds",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        for item in body["items"]:
            assert "version" in item
            assert "valid_from" in item
            assert "valid_to" in item
            assert "superseded_by" in item
        v1_item = next(it for it in body["items"] if it["name"] == "FundV1")
        assert v1_item["superseded_by"] is not None
        assert v1_item["version"] == "1.0"

    async def test_filter_publication_status_published_only(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, token = await _make_admin(db_session)
        for n, st in (("Pub1", "published"), ("Draft1", "draft")):
            db_session.add(
                Fund(
                    name=n,
                    organization="Org",
                    fund_type=FundType.multilateral,
                    description="d",
                    eligibility_criteria={},
                    sectors_eligible=[],
                    required_documents=[],
                    esg_requirements={},
                    access_type=AccessType.direct,
                    application_process=[],
                    publication_status=st,
                )
            )
        await db_session.commit()
        response = await client.get(
            "/api/admin/funds?publication_status=published",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        names = [it["name"] for it in response.json()["items"]]
        assert "Pub1" in names
        assert "Draft1" not in names


class TestIntermediariesVersioningExposed:
    async def test_intermediaries_list_exposes_versioning(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, token = await _make_admin(db_session)
        db_session.add(
            Intermediary(
                name="Inter1",
                intermediary_type=IntermediaryType.accredited_entity,
                organization_type=OrganizationType.bank,
                country="SN",
                city="Dakar",
                accreditations=[],
                services_offered={},
                eligibility_for_sme={},
                publication_status="draft",
                version="1.0",
            )
        )
        await db_session.commit()
        response = await client.get(
            "/api/admin/intermediaries",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["items"]
        first = body["items"][0]
        assert "version" in first
        assert "valid_from" in first
        assert "valid_to" in first
        assert "superseded_by" in first
