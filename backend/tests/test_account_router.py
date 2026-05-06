"""Tests F02 — endpoints account (US3 invitations équipe)."""

from __future__ import annotations

import uuid as _uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.core.security import create_access_token, hash_password
from app.models.account import Account
from app.models.user import User


pytestmark = pytest.mark.asyncio


async def _make_pme_with_account(
    db: AsyncSession, *, email: str | None = None
) -> tuple[User, Account, str]:
    account = Account(name="Test SARL")
    db.add(account)
    await db.flush()
    user = User(
        email=email or f"pme-{_uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pwd1234567"),
        full_name="PME Test",
        company_name="Test SARL",
        role=UserRole.PME.value,
        account_id=account.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, account, create_access_token(str(user.id))


class TestListTeam:
    async def test_pme_can_list_own_team(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _user, _account, token = await _make_pme_with_account(db_session)
        response = await client.get(
            "/api/account/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "members" in body
        assert "pending_invitations" in body
        # Le user lui-meme doit etre listed
        assert any(m["full_name"] == "PME Test" for m in body["members"])

    async def test_anonymous_gets_401(self, client: AsyncClient) -> None:
        response = await client.get("/api/account/users")
        assert response.status_code == 401


class TestInviteMember:
    async def test_pme_can_invite_new_member(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _user, _account, token = await _make_pme_with_account(db_session)
        response = await client.post(
            "/api/account/invite",
            headers={"Authorization": f"Bearer {token}"},
            json={"email": "newmember@test.com"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "newmember@test.com"
        assert body["status"] == "pending"
        assert body["invited_by"]["full_name"] == "PME Test"

    async def test_invalid_email_returns_422(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _user, _account, token = await _make_pme_with_account(db_session)
        response = await client.post(
            "/api/account/invite",
            headers={"Authorization": f"Bearer {token}"},
            json={"email": "pas-un-email"},
        )
        assert response.status_code == 422

    async def test_anonymous_gets_401(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/account/invite", json={"email": "x@y.com"}
        )
        assert response.status_code == 401


class TestRemoveMember:
    async def test_anonymous_gets_401(self, client: AsyncClient) -> None:
        random_uuid = _uuid.uuid4()
        response = await client.delete(f"/api/account/users/{random_uuid}")
        assert response.status_code == 401
