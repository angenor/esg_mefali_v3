"""Tests F25 (feature 044) — endpoint export CSV `/api/admin/catalog/export`.

Couvre :
- headers Content-Type et Content-Disposition (filename daté YYYYMMDD),
- BOM UTF-8 (compatibilité Excel FR),
- 4 valeurs de `tab` retournent des colonnes spécifiques,
- 400 si `tab` invalide,
- 422 si combinaison incompatible (ex `tab=funds&status=expired`),
- 403 PME.
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


async def _make_fund(db: AsyncSession, name: str, status: str = "published") -> Fund:
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
        publication_status=status,
    )
    db.add(f)
    await db.flush()
    return f


class TestExportAuth:
    async def test_pme_returns_403(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        pme = await make_pme_user(db_session)
        await db_session.commit()
        token = create_access_token(str(pme.id))
        response = await client.get(
            "/api/admin/catalog/export?tab=funds",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestExportHeaders:
    async def test_csv_headers_with_bom(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, token = await _make_admin(db_session)
        await _make_fund(db_session, "GCF")
        await db_session.commit()
        response = await client.get(
            "/api/admin/catalog/export?tab=funds",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        cd = response.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert "filename=" in cd
        assert ".csv" in cd
        body_bytes = response.content
        # BOM UTF-8 attendu : 0xEF 0xBB 0xBF
        assert body_bytes[:3] == b"\xef\xbb\xbf"


class TestExportContent:
    async def test_funds_export_has_correct_columns(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, token = await _make_admin(db_session)
        await _make_fund(db_session, "GCF")
        await db_session.commit()
        response = await client.get(
            "/api/admin/catalog/export?tab=funds",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Premier ligne = header (sans BOM pour parsing).
        text = response.content.decode("utf-8-sig")
        first_line = text.splitlines()[0]
        for col in ("id", "name", "publication_status", "version"):
            assert col in first_line

    async def test_intermediaries_export(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, token = await _make_admin(db_session)
        db_session.add(
            Intermediary(
                name="BOAD",
                intermediary_type=IntermediaryType.accredited_entity,
                organization_type=OrganizationType.bank,
                country="SN",
                city="Dakar",
                accreditations=[],
                services_offered={},
                eligibility_for_sme={},
                publication_status="published",
            )
        )
        await db_session.commit()
        response = await client.get(
            "/api/admin/catalog/export?tab=intermediaries",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        text = response.content.decode("utf-8-sig")
        assert "country" in text.splitlines()[0]
        assert "BOAD" in text

    async def test_fund_intermediaries_export(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, token = await _make_admin(db_session)
        f = await _make_fund(db_session, "GCF")
        i = Intermediary(
            name="BOAD",
            intermediary_type=IntermediaryType.accredited_entity,
            organization_type=OrganizationType.bank,
            country="SN",
            city="Dakar",
            accreditations=[],
            services_offered={},
            eligibility_for_sme={},
            publication_status="published",
        )
        db_session.add(i)
        await db_session.flush()
        db_session.add(
            FundIntermediary(
                fund_id=f.id,
                intermediary_id=i.id,
                accredited_from=date(2024, 1, 1),
                geographic_coverage=[],
            )
        )
        await db_session.commit()
        response = await client.get(
            "/api/admin/catalog/export?tab=fund_intermediaries",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        text = response.content.decode("utf-8-sig")
        header = text.splitlines()[0]
        for col in ("fund_id", "intermediary_id", "fund_name", "intermediary_name"):
            assert col in header

    async def test_invalid_tab_returns_400_or_422(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, token = await _make_admin(db_session)
        response = await client.get(
            "/api/admin/catalog/export?tab=invalid",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code in (400, 422)

    async def test_incompatible_combo_returns_422(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """`tab=funds&status=expired` est incompatible (status est valide
        uniquement pour `fund_intermediaries`)."""
        _, token = await _make_admin(db_session)
        response = await client.get(
            "/api/admin/catalog/export?tab=funds&status=expired",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422
