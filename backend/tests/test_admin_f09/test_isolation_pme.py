"""Tests F09 — isolation PME : aucun accès aux endpoints /api/admin/*."""

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


async def _make_pme(db: AsyncSession) -> tuple[User, str]:
    account = Account(name="PME")
    db.add(account)
    await db.flush()
    user = User(
        email=f"pme-{_uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pw1234567"),
        full_name="PME",
        company_name="P",
        role=UserRole.PME.value,
        account_id=account.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, create_access_token(str(user.id))


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/admin/funds"),
        ("GET", "/api/admin/intermediaries"),
        ("GET", "/api/admin/offers"),
        ("GET", "/api/admin/sources"),
    ],
)
async def test_pme_gets_403(
    client: AsyncClient,
    db_session: AsyncSession,
    method: str,
    path: str,
) -> None:
    _user, token = await _make_pme(db_session)
    response = await client.request(
        method,
        path,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
