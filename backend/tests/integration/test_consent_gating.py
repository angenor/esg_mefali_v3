"""F05 — Tests d'intégration du gating ``consent_dependency`` (T091-T092).

Vérifie via l'endpoint stub ``/api/credit/mobile-money/preview`` que le
helper bloque correctement sans grant et passe avec.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.security import create_access_token, hash_password
from app.models.user import User
from tests.conftest import make_account


async def _make_user(db_session) -> User:
    account = await make_account(db_session, name="GatingCo")
    user = User(
        email=f"gate-{uuid.uuid4().hex[:8]}@x.com",
        hashed_password=hash_password("p"),
        full_name="G",
        company_name="GatingCo",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


def _bearer(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


@pytest.mark.asyncio
async def test_endpoint_blocked_without_grant(client, db_session) -> None:
    user = await _make_user(db_session)
    res = await client.post(
        "/api/credit/mobile-money/preview", headers=_bearer(user)
    )
    assert res.status_code == 403
    body = res.json()
    assert body["detail"]["consent_type"] == "mobile_money_analysis"
    assert body["detail"]["settings_url"] == "/mes-donnees/consentements"
    assert "Mobile Money" in body["detail"]["detail"]


@pytest.mark.asyncio
async def test_endpoint_passes_after_grant(client, db_session) -> None:
    user = await _make_user(db_session)
    res_grant = await client.post(
        "/api/me/consents/mobile_money_analysis/grant",
        headers=_bearer(user),
    )
    assert res_grant.status_code == 200
    res = await client.post(
        "/api/credit/mobile-money/preview", headers=_bearer(user)
    )
    # 501 (stub renvoie ce code) — pas 403.
    assert res.status_code == 501


@pytest.mark.asyncio
async def test_endpoint_blocked_after_revoke(client, db_session) -> None:
    user = await _make_user(db_session)
    await client.post(
        "/api/me/consents/mobile_money_analysis/grant",
        headers=_bearer(user),
    )
    await client.post(
        "/api/me/consents/mobile_money_analysis/revoke",
        headers=_bearer(user),
    )
    res = await client.post(
        "/api/credit/mobile-money/preview", headers=_bearer(user)
    )
    assert res.status_code == 403
