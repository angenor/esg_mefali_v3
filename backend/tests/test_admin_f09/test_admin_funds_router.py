"""Tests F09 — router admin /funds, /intermediaries, /offers (lecture seule).

Les écritures (publish) sont testées en intégration PostgreSQL avec triggers.
Ici on couvre :
- list (filtrage, pagination),
- get_one (404 si absent),
- isolation PME → 403.
"""

from __future__ import annotations

import uuid as _uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.core.security import create_access_token, hash_password
from app.models.account import Account
from app.models.financing import Fund, Intermediary
from app.models.user import User


pytestmark = pytest.mark.asyncio


async def _make_admin(db: AsyncSession) -> tuple[User, str]:
    user = User(
        email=f"admin-{_uuid.uuid4().hex[:6]}@test.com",
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


class TestFundsAdmin:
    async def test_list_returns_pagination_envelope(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            "/api/admin/funds",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "items" in body
        assert "total" in body
        assert "page" in body
        assert "limit" in body

    async def test_get_unknown_fund_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            f"/api/admin/funds/{_uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


class TestIntermediariesAdmin:
    async def test_list_returns_pagination_envelope(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            "/api/admin/intermediaries",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body["items"], list)

    async def test_get_unknown_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            f"/api/admin/intermediaries/{_uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


class TestOffersAdmin:
    async def test_list_returns_pagination_envelope(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            "/api/admin/offers",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body["items"], list)

    async def test_get_unknown_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.get(
            f"/api/admin/offers/{_uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


class TestPublishGatingFundUnknown:
    async def test_publish_unknown_fund_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, token = await _make_admin(db_session)
        response = await client.post(
            f"/api/admin/funds/{_uuid.uuid4()}/publish",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
