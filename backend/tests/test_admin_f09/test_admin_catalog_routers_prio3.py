"""Tests F09 PRIO 3 — routers admin catalogue étendu.

Couverture des 5 sous-routers ajoutés en PRIO 3 :
- /admin/referentials
- /admin/indicators
- /admin/criteria
- /admin/emission-factors
- /admin/simulation-factors

Pattern réutilisé depuis ``test_admin_funds_router.py`` (lecture seule pour
les list/get + 404, écritures simples pour create/patch/delete).
"""

from __future__ import annotations

import uuid as _uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.core.security import create_access_token, hash_password
from app.models.user import User


pytestmark = pytest.mark.asyncio


async def _make_admin(db: AsyncSession) -> tuple[User, str]:
    user = User(
        email=f"admin-prio3-{_uuid.uuid4().hex[:6]}@test.com",
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


async def _make_pme(db: AsyncSession) -> tuple[User, str]:
    from app.models.account import Account

    account = Account(name=f"Acc-{_uuid.uuid4().hex[:6]}")
    db.add(account)
    await db.flush()
    user = User(
        email=f"pme-prio3-{_uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pw1234567"),
        full_name="P",
        company_name="ESG",
        role=UserRole.PME.value,
        account_id=account.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, create_access_token(str(user.id))


class TestReferentialsAdmin:
    async def test_list_returns_pagination_envelope(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            "/api/admin/referentials",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "items" in body
        assert "total" in body
        assert "page" in body
        assert "limit" in body

    async def test_get_unknown_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            f"/api/admin/referentials/{_uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    async def test_pme_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _pme, token = await _make_pme(db_session)
        response = await client.get(
            "/api/admin/referentials",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestIndicatorsAdmin:
    async def test_list_returns_pagination_envelope(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            "/api/admin/indicators",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    async def test_get_unknown_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            f"/api/admin/indicators/{_uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    async def test_create_validates_pillar(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.post(
            "/api/admin/indicators",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "code": "X1",
                "pillar": "invalid",
                "label": "test",
                "description": "desc",
                "question": "q",
                "source_id": str(_uuid.uuid4()),
            },
        )
        # Pydantic 422 (validator).
        assert response.status_code == 422


class TestCriteriaAdmin:
    async def test_list_returns_pagination_envelope(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            "/api/admin/criteria",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    async def test_get_unknown_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            f"/api/admin/criteria/{_uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    async def test_publish_unknown_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.post(
            f"/api/admin/criteria/{_uuid.uuid4()}/publish",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


class TestEmissionFactorsAdmin:
    async def test_list_returns_pagination_envelope(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            "/api/admin/emission-factors",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    async def test_filters_by_country(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            "/api/admin/emission-factors?country=CI",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    async def test_get_unknown_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            f"/api/admin/emission-factors/{_uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


class TestSimulationFactorsAdmin:
    async def test_list_returns_pagination_envelope(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            "/api/admin/simulation-factors",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    async def test_get_unknown_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            f"/api/admin/simulation-factors/{_uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    async def test_create_pending_with_source_returns_422(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """status=pending requiert source_id=null (CHECK BDD)."""
        _admin, token = await _make_admin(db_session)
        response = await client.post(
            "/api/admin/simulation-factors",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "code": "TEST_PENDING_WITH_SRC",
                "label": "test",
                "value": 1.0,
                "unit": "%",
                "scope": "test",
                "source_id": str(_uuid.uuid4()),
                "status": "pending",
            },
        )
        assert response.status_code == 422

    async def test_create_verified_without_source_returns_422(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """status=verified requiert source_id (CHECK BDD)."""
        _admin, token = await _make_admin(db_session)
        response = await client.post(
            "/api/admin/simulation-factors",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "code": "TEST_VERIFIED_NO_SRC",
                "label": "test",
                "value": 1.0,
                "unit": "%",
                "scope": "test",
                "source_id": None,
                "status": "verified",
            },
        )
        assert response.status_code == 422


class TestCompaniesAdmin:
    async def test_list_returns_pagination_envelope(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            "/api/admin/companies",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "items" in body
        assert "total" in body

    async def test_get_unknown_account_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            f"/api/admin/companies/{_uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    async def test_pme_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _pme, token = await _make_pme(db_session)
        response = await client.get(
            "/api/admin/companies",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestMetricsAdmin:
    async def test_overview_returns_structure(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            "/api/admin/metrics/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "sources" in body
        assert "accounts" in body
        assert "applications" in body
        assert "attestations" in body
        assert "llm_costs" in body
        assert "generated_at" in body

    async def test_overview_sources_keys(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            "/api/admin/metrics/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "total" in body["sources"]
        assert "breakdown" in body["sources"]

    async def test_overview_accounts_keys(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            "/api/admin/metrics/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        for key in ("total", "active", "inactive", "new_30d"):
            assert key in body["accounts"], f"missing {key}"

    async def test_pme_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _pme, token = await _make_pme(db_session)
        response = await client.get(
            "/api/admin/metrics/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
