"""Tests F02 — protection des endpoints admin.

US2 — Accès admin protégé : les routes /api/admin/* sont réservées aux
utilisateurs avec ``role='ADMIN'``. Un PME reçoit 403, un anonyme 401.
"""

from __future__ import annotations

import pytest
import uuid as _uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.core.security import create_access_token, hash_password
from app.models.account import Account
from app.models.user import User


pytestmark = pytest.mark.asyncio


async def _make_admin(db: AsyncSession) -> tuple[User, str]:
    user = User(
        email=f"admin-{_uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pwd1234567"),
        full_name="Admin Test",
        company_name="ESG Mefali",
        role=UserRole.ADMIN.value,
        account_id=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, create_access_token(str(user.id))


async def _make_pme(db: AsyncSession) -> tuple[User, str]:
    account = Account(name="PME Test")
    db.add(account)
    await db.flush()
    user = User(
        email=f"pme-{_uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pwd1234567"),
        full_name="PME Test",
        company_name="PME Test",
        role=UserRole.PME.value,
        account_id=account.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, create_access_token(str(user.id))


class TestAdminHealth:
    async def test_admin_can_access_health(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _user, token = await _make_admin(db_session)
        response = await client.get(
            "/api/admin/health",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["role"] == "ADMIN"

    async def test_pme_gets_403_on_admin_health(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _user, token = await _make_pme(db_session)
        response = await client.get(
            "/api/admin/health",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    async def test_anonymous_gets_401_on_admin_health(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/api/admin/health")
        assert response.status_code == 401
