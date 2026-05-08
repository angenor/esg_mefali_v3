"""Tests d'intégration HTTP du router F24 extension.

On utilise le client httpx ASGI fourni par tests/conftest.py.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.user import User
from tests.conftest import make_account


@pytest.mark.asyncio
async def test_endpoints_require_bearer(client: AsyncClient):
    """Tous les endpoints sauf /auth/exchange exigent un bearer token."""
    r = await client.get("/api/extension/v1/me/profile-snapshot")
    assert r.status_code == 401
    r = await client.post(
        "/api/extension/v1/detect", json={"url": "https://x.fr"}
    )
    assert r.status_code == 401
    r = await client.get("/api/extension/v1/applications/active")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_auth_exchange_returns_extension_scope(
    client: AsyncClient, db_session: AsyncSession
):
    """POST /auth/exchange émet un access token + refresh token scope=extension."""
    account = await make_account(db_session, name="ExtCo")
    user = User(
        email="ext@test.fr",
        hashed_password=hash_password("Password1!"),
        full_name="Ext User",
        company_name="ExtCo",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.commit()

    r = await client.post(
        "/api/extension/v1/auth/exchange",
        json={"email": "ext@test.fr", "password": "Password1!"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["scope"] == "extension"
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_auth_exchange_invalid_credentials(
    client: AsyncClient, db_session: AsyncSession
):
    r = await client.post(
        "/api/extension/v1/auth/exchange",
        json={"email": "nope@test.fr", "password": "WrongPassw1!"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_auth_exchange_rejects_short_password(client: AsyncClient):
    r = await client.post(
        "/api/extension/v1/auth/exchange",
        json={"email": "x@y.fr", "password": "abc"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_detect_returns_204_when_no_match(
    client: AsyncClient, db_session: AsyncSession
):
    account = await make_account(db_session, name="DetectCo")
    user = User(
        email="d@test.fr",
        hashed_password=hash_password("Password1!"),
        full_name="D",
        company_name="DetectCo",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(str(user.id))
    headers = {"Authorization": f"Bearer {token}"}
    r = await client.post(
        "/api/extension/v1/detect",
        json={"url": "https://no-match.example.com/"},
        headers=headers,
    )
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_detect_rejects_invalid_url(
    client: AsyncClient, db_session: AsyncSession
):
    account = await make_account(db_session, name="UrlCo")
    user = User(
        email="u@test.fr",
        hashed_password=hash_password("Password1!"),
        full_name="U",
        company_name="UrlCo",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(str(user.id))
    r = await client.post(
        "/api/extension/v1/detect",
        json={"url": "not-a-url"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_applications_active_empty_list(
    client: AsyncClient, db_session: AsyncSession
):
    account = await make_account(db_session, name="EmptyCo")
    user = User(
        email="empty@test.fr",
        hashed_password=hash_password("Password1!"),
        full_name="E",
        company_name="EmptyCo",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(str(user.id))
    r = await client.get(
        "/api/extension/v1/applications/active",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_profile_snapshot_returns_payload(
    client: AsyncClient, db_session: AsyncSession
):
    account = await make_account(db_session, name="ProfCo")
    user = User(
        email="prof@test.fr",
        hashed_password=hash_password("Password1!"),
        full_name="P",
        company_name="ProfCo",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(str(user.id))
    r = await client.get(
        "/api/extension/v1/me/profile-snapshot",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "sector" in body
    assert "country" in body
    assert body["projects"] == []
