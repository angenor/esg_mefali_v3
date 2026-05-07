"""Tests F09 — endpoint public /api/auth/reset-password."""

from __future__ import annotations

import os
import uuid as _uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.core.email_service import NoopEmailService
from app.models.account import Account
from app.models.user import User
from app.modules.admin.users_service import initiate_password_reset


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def use_noop_email(monkeypatch):
    monkeypatch.setenv("EMAIL_BACKEND", "noop")
    yield


async def _setup(db: AsyncSession) -> tuple[User, User, str]:
    """Crée un admin, un PME et déclenche un reset → retourne (admin, pme, plain_token)."""
    admin = User(
        email=f"admin-{_uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("admin1234"),
        full_name="A",
        company_name="ESG",
        role=UserRole.ADMIN.value,
        account_id=None,
    )
    db.add(admin)
    await db.flush()

    account = Account(name="PME")
    db.add(account)
    await db.flush()
    pme = User(
        email=f"pme-{_uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("oldpw1234"),
        full_name="P",
        company_name="P",
        role=UserRole.PME.value,
        account_id=account.id,
    )
    db.add(pme)
    await db.commit()
    await db.refresh(admin)
    await db.refresh(pme)

    _row, plain = await initiate_password_reset(
        db,
        user_id=pme.id,
        admin_id=admin.id,
        email_service=NoopEmailService(),
    )
    await db.commit()
    return admin, pme, plain


async def test_valid_token_resets_password(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _admin, pme, plain = await _setup(db_session)
    response = await client.post(
        "/api/auth/reset-password",
        json={"token": plain, "new_password": "brandNewPW1!"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Reload user et vérifie
    await db_session.refresh(pme)
    assert verify_password("brandNewPW1!", pme.hashed_password) is True


async def test_invalid_token_returns_400(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(
        "/api/auth/reset-password",
        json={
            "token": "fake-token-xxxxxxxxxxxxxxxxxxxxx",
            "new_password": "newPW1234!",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "token_invalid"


async def test_short_password_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _admin, _pme, plain = await _setup(db_session)
    response = await client.post(
        "/api/auth/reset-password",
        json={"token": plain, "new_password": "short"},
    )
    assert response.status_code == 422


async def test_already_used_returns_400(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _admin, _pme, plain = await _setup(db_session)
    # Première utilisation OK
    r1 = await client.post(
        "/api/auth/reset-password",
        json={"token": plain, "new_password": "firstPW1!"},
    )
    assert r1.status_code == 200
    # Deuxième → 400
    r2 = await client.post(
        "/api/auth/reset-password",
        json={"token": plain, "new_password": "secondPW2!"},
    )
    assert r2.status_code == 400
    assert r2.json()["detail"] == "token_already_used"
