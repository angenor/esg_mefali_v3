"""Tests F09 — router admin /users (reset password + toggle active)."""

from __future__ import annotations

import os
import uuid as _uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.core.security import create_access_token, hash_password
from app.models.account import Account
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def use_noop_email(monkeypatch):
    monkeypatch.setenv("EMAIL_BACKEND", "noop")
    yield


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


async def _make_pme(db: AsyncSession) -> tuple[User, str]:
    account = Account(name="PME")
    db.add(account)
    await db.flush()
    user = User(
        email=f"pme-{_uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pw1234567"),
        full_name="PME",
        company_name="PME",
        role=UserRole.PME.value,
        account_id=account.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, create_access_token(str(user.id))


class TestResetPasswordEndpoint:
    async def test_admin_can_reset_password(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin, token = await _make_admin(db_session)
        pme, _ = await _make_pme(db_session)
        response = await client.post(
            f"/api/admin/users/{pme.id}/reset-password",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["user_id"] == str(pme.id)
        assert body["email_sent"] is True
        assert "expires_at" in body

        # Vérifier qu'un token a été créé en BDD
        res = await db_session.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == pme.id
            )
        )
        rows = res.scalars().all()
        assert len(rows) == 1

    async def test_pme_cannot_reset_password(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _admin, _ = await _make_admin(db_session)
        pme, pme_token = await _make_pme(db_session)
        target_pme, _ = await _make_pme(db_session)
        response = await client.post(
            f"/api/admin/users/{target_pme.id}/reset-password",
            headers={"Authorization": f"Bearer {pme_token}"},
        )
        assert response.status_code == 403

    async def test_anonymous_cannot_reset_password(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        pme, _ = await _make_pme(db_session)
        response = await client.post(
            f"/api/admin/users/{pme.id}/reset-password"
        )
        assert response.status_code == 401


class TestToggleActiveEndpoint:
    async def test_admin_can_toggle(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin, token = await _make_admin(db_session)
        pme, _ = await _make_pme(db_session)
        response = await client.post(
            f"/api/admin/users/{pme.id}/toggle-active",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "Test deactivation reason"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["is_active"] is False

    async def test_reason_required(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin, token = await _make_admin(db_session)
        pme, _ = await _make_pme(db_session)
        response = await client.post(
            f"/api/admin/users/{pme.id}/toggle-active",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert response.status_code == 422

    async def test_reason_too_short(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin, token = await _make_admin(db_session)
        pme, _ = await _make_pme(db_session)
        response = await client.post(
            f"/api/admin/users/{pme.id}/toggle-active",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "short"},
        )
        assert response.status_code == 422
