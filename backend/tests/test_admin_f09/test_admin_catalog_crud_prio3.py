"""Tests F09 PRIO 3 — chemins write (create + validation errors).

Complète test_admin_catalog_routers_prio3.py. Le PATCH/DELETE après création
est testé via les tests E2E Playwright (F09-prio3-admin-completion.spec.ts)
car SQLAlchemy 2.0 + aiosqlite + Python 3.14 ont une incompatibilité avec
les nested transactions sur la même connexion partagée (cache SQLite).
"""

from __future__ import annotations

import uuid as _uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.core.security import create_access_token, hash_password
from app.models.source import Source
from app.models.user import User


pytestmark = pytest.mark.asyncio


async def _make_admin(db: AsyncSession) -> tuple[User, str]:
    user = User(
        email=f"admin-crud-{_uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pw1234567"),
        full_name="A",
        company_name="ESG",
        role=UserRole.ADMIN.value,
        account_id=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, create_access_token(str(user.id))


async def _make_verified_source(db: AsyncSession, admin: User) -> Source:
    """Crée une Source verified (bypass 4-eyes via UPDATE direct)."""
    admin2 = User(
        email=f"admin-b-{_uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pw1234567"),
        full_name="B",
        company_name="ESG",
        role=UserRole.ADMIN.value,
        account_id=None,
    )
    db.add(admin2)
    await db.commit()
    await db.refresh(admin2)
    source = Source(
        url="https://example.org/doc.pdf",
        title=f"Source {_uuid.uuid4().hex[:6]}",
        publisher="Example",
        version="1.0",
        date_publi=date(2024, 1, 1),
        captured_by=admin.id,
        created_by_user_id=admin.id,
        verified_by=admin2.id,
        verified_at=datetime.now(timezone.utc),
        verification_status="verified",
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


class TestReferentialsCreate:
    async def test_create_returns_201_with_draft_status(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin, token = await _make_admin(db_session)
        source = await _make_verified_source(db_session, admin)

        resp = await client.post(
            "/api/admin/referentials",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "code": f"ref_{_uuid.uuid4().hex[:6]}",
                "label": "Test référentiel",
                "description": "Description du test",
                "source_id": str(source.id),
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["publication_status"] == "draft"
        assert body["label"] == "Test référentiel"

    async def test_create_missing_required_fields_returns_422(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        resp = await client.post(
            "/api/admin/referentials",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": "test"},  # manque label, description, source_id
        )
        assert resp.status_code == 422


class TestIndicatorsCreate:
    async def test_create_with_environment_pillar(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin, token = await _make_admin(db_session)
        source = await _make_verified_source(db_session, admin)

        resp = await client.post(
            "/api/admin/indicators",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "code": f"E{_uuid.uuid4().hex[:4]}",
                "pillar": "environment",
                "label": "Test",
                "description": "Description",
                "question": "Question?",
                "source_id": str(source.id),
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["pillar"] == "environment"

    async def test_create_with_invalid_pillar_returns_422(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        resp = await client.post(
            "/api/admin/indicators",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "code": "X1",
                "pillar": "invalid",
                "label": "x",
                "description": "x",
                "question": "x",
                "source_id": str(_uuid.uuid4()),
            },
        )
        assert resp.status_code == 422


class TestCriteriaCreate:
    async def test_create_with_expression(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin, token = await _make_admin(db_session)
        source = await _make_verified_source(db_session, admin)

        resp = await client.post(
            "/api/admin/criteria",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "code": f"crit_{_uuid.uuid4().hex[:4]}",
                "label": "Test",
                "expression": {"op": "gt", "lhs": "indicator.E1", "rhs": 50},
                "source_id": str(source.id),
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["expression"]["op"] == "gt"


class TestEmissionFactorsCreate:
    async def test_create_with_uemoa_country(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin, token = await _make_admin(db_session)
        source = await _make_verified_source(db_session, admin)

        resp = await client.post(
            "/api/admin/emission-factors",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "code": f"ef_{_uuid.uuid4().hex[:6]}",
                "label": "Test EF",
                "category": "energy",
                "country": "CI",
                "year": 2024,
                "value": 0.456,
                "unit": "kgCO2e/kWh",
                "source_id": str(source.id),
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["country"] == "CI"
        assert body["year"] == 2024

    async def test_create_with_invalid_year_returns_422(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        resp = await client.post(
            "/api/admin/emission-factors",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "code": "test",
                "label": "Test",
                "category": "energy",
                "country": "CI",
                "year": 1500,  # avant 2000
                "value": 0.5,
                "unit": "kgCO2e/kWh",
                "source_id": str(_uuid.uuid4()),
            },
        )
        assert resp.status_code == 422


class TestSimulationFactorsCreate:
    async def test_create_pending_with_null_source(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        resp = await client.post(
            "/api/admin/simulation-factors",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "code": f"sf_{_uuid.uuid4().hex[:6]}",
                "label": "Test SF",
                "value": 0.05,
                "unit": "%",
                "scope": "credit",
                "status": "pending",
                "source_id": None,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "pending"
        assert body["source_id"] is None

    async def test_create_verified_with_source(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin, token = await _make_admin(db_session)
        source = await _make_verified_source(db_session, admin)

        resp = await client.post(
            "/api/admin/simulation-factors",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "code": f"sf_v_{_uuid.uuid4().hex[:6]}",
                "label": "SF verified",
                "value": 0.1,
                "unit": "%",
                "scope": "credit",
                "status": "verified",
                "source_id": str(source.id),
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["status"] == "verified"


class TestCompaniesOverview:
    async def test_overview_returns_full_structure(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        from app.models.account import Account

        _admin, token = await _make_admin(db_session)
        account = Account(name=f"Acc-{_uuid.uuid4().hex[:6]}")
        db_session.add(account)
        await db_session.commit()
        await db_session.refresh(account)

        resp = await client.get(
            f"/api/admin/companies/{account.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["account"]["name"] == account.name
        assert "users" in body
        assert "projects" in body
        assert "applications" in body
        assert "scores" in body
        assert "attestations" in body

    async def test_overview_dedup_view_admin_log(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Le second appel ne crée pas un second audit log view_admin (dédup 1/jour)."""
        from sqlalchemy import select, func
        from app.core.constants import AuditAction
        from app.models.account import Account
        from app.models.audit_log import AuditLog

        admin, token = await _make_admin(db_session)
        account = Account(name=f"Acc-dedup-{_uuid.uuid4().hex[:6]}")
        db_session.add(account)
        await db_session.commit()
        await db_session.refresh(account)

        await client.get(
            f"/api/admin/companies/{account.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        await client.get(
            f"/api/admin/companies/{account.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        count_res = await db_session.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.user_id == admin.id,
                AuditLog.entity_id == account.id,
                AuditLog.action == AuditAction.view_admin,
            )
        )
        count = count_res.scalar_one()
        assert count == 1, f"Expected dedup → 1 entry, got {count}"
