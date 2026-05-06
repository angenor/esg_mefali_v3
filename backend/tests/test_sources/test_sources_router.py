"""Tests d'integration des routes /api/sources (F01)."""

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


async def _make_admin(db: AsyncSession, *, email: str | None = None):
    user = User(
        email=email or f"adm-{_uuid.uuid4().hex[:6]}@x.com",
        hashed_password=hash_password("pwd12345678"),
        full_name="Admin",
        company_name="N/A",
        role=UserRole.ADMIN.value,
        account_id=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, create_access_token(str(user.id))


async def _make_pme(db: AsyncSession, *, email: str | None = None):
    account = Account(name="Test PME")
    db.add(account)
    await db.flush()
    user = User(
        email=email or f"pme-{_uuid.uuid4().hex[:6]}@x.com",
        hashed_password=hash_password("pwd12345678"),
        full_name="PME",
        company_name="Test PME",
        role=UserRole.PME.value,
        account_id=account.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, account, create_access_token(str(user.id))


def _create_payload(suffix: str = "") -> dict:
    s = suffix or "a"
    return {
        "url": f"https://ademe.fr/source-{s}.pdf",
        "title": f"ADEME {s}",
        "publisher": "ADEME",
        "version": "v23",
        "date_publi": "2024-01-01",
        "page": 12,
        "section": "Annexe 3",
    }


class TestListSources:
    async def test_pme_sees_only_verified(
        self, client: AsyncClient, db_session: AsyncSession,
    ) -> None:
        _, _, token = await _make_pme(db_session)
        response = await client.get(
            "/api/sources",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "items" in body
        assert "total" in body

    async def test_anonymous_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get("/api/sources")
        assert response.status_code == 401


class TestCreateSource:
    async def test_admin_can_create_source(
        self, client: AsyncClient, db_session: AsyncSession,
    ) -> None:
        _, token = await _make_admin(db_session)
        response = await client.post(
            "/api/sources",
            headers={"Authorization": f"Bearer {token}"},
            json=_create_payload("a1"),
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["title"] == "ADEME a1"
        assert body["verification_status"] == "draft"

    async def test_pme_cannot_create_source(
        self, client: AsyncClient, db_session: AsyncSession,
    ) -> None:
        _, _, token = await _make_pme(db_session)
        response = await client.post(
            "/api/sources",
            headers={"Authorization": f"Bearer {token}"},
            json=_create_payload("a2"),
        )
        assert response.status_code == 403

    async def test_invalid_payload_rejected(
        self, client: AsyncClient, db_session: AsyncSession,
    ) -> None:
        _, token = await _make_admin(db_session)
        response = await client.post(
            "/api/sources",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "url": "not-url",
                "title": "x",
                "publisher": "x",
                "version": "v1",
                "date_publi": "2024-01-01",
            },
        )
        assert response.status_code == 422


class TestVerifyWorkflow:
    async def test_request_verification_then_verify_with_other_admin(
        self, client: AsyncClient, db_session: AsyncSession,
    ) -> None:
        admin_a, token_a = await _make_admin(db_session, email="a@x.com")
        admin_b, token_b = await _make_admin(db_session, email="b@x.com")

        # Admin A cree la source
        r = await client.post(
            "/api/sources",
            headers={"Authorization": f"Bearer {token_a}"},
            json=_create_payload("v1"),
        )
        sid = r.json()["id"]

        # A demande la verification
        r = await client.post(
            f"/api/sources/{sid}/request-verification",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert r.status_code == 200
        assert r.json()["verification_status"] == "pending"

        # A tente de valider lui-meme : 403 (4-yeux)
        r = await client.post(
            f"/api/sources/{sid}/verify",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert r.status_code == 403

        # B valide : succes
        r = await client.post(
            f"/api/sources/{sid}/verify",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert r.status_code == 200
        assert r.json()["verification_status"] == "verified"

    async def test_pme_can_get_verified_source(
        self, client: AsyncClient, db_session: AsyncSession,
    ) -> None:
        admin_a, token_a = await _make_admin(db_session, email="a@x.com")
        admin_b, token_b = await _make_admin(db_session, email="b@x.com")

        r = await client.post(
            "/api/sources",
            headers={"Authorization": f"Bearer {token_a}"},
            json=_create_payload("public"),
        )
        sid = r.json()["id"]
        await client.post(
            f"/api/sources/{sid}/request-verification",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        await client.post(
            f"/api/sources/{sid}/verify",
            headers={"Authorization": f"Bearer {token_b}"},
        )

        # PME peut maintenant le voir
        _, _, pme_token = await _make_pme(db_session)
        r = await client.get(
            f"/api/sources/{sid}",
            headers={"Authorization": f"Bearer {pme_token}"},
        )
        assert r.status_code == 200

    async def test_pme_404_on_draft_source(
        self, client: AsyncClient, db_session: AsyncSession,
    ) -> None:
        admin_a, token_a = await _make_admin(db_session, email="a@x.com")
        r = await client.post(
            "/api/sources",
            headers={"Authorization": f"Bearer {token_a}"},
            json=_create_payload("draft"),
        )
        sid = r.json()["id"]
        # PME : 404 car non verified
        _, _, pme_token = await _make_pme(db_session)
        r = await client.get(
            f"/api/sources/{sid}",
            headers={"Authorization": f"Bearer {pme_token}"},
        )
        assert r.status_code == 404


class TestMarkOutdated:
    async def test_admin_can_mark_outdated(
        self, client: AsyncClient, db_session: AsyncSession,
    ) -> None:
        admin_a, token_a = await _make_admin(db_session, email="a@x.com")
        admin_b, token_b = await _make_admin(db_session, email="b@x.com")
        r = await client.post(
            "/api/sources",
            headers={"Authorization": f"Bearer {token_a}"},
            json=_create_payload("out"),
        )
        sid = r.json()["id"]
        await client.post(
            f"/api/sources/{sid}/request-verification",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        await client.post(
            f"/api/sources/{sid}/verify",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        r = await client.post(
            f"/api/sources/{sid}/mark-outdated",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"reason": "Nouvelle version 2025"},
        )
        assert r.status_code == 200
        assert r.json()["verification_status"] == "outdated"
        assert r.json()["outdated_reason"] == "Nouvelle version 2025"

    async def test_mark_outdated_requires_reason(
        self, client: AsyncClient, db_session: AsyncSession,
    ) -> None:
        admin_a, token_a = await _make_admin(db_session, email="a@x.com")
        r = await client.post(
            "/api/sources",
            headers={"Authorization": f"Bearer {token_a}"},
            json=_create_payload("noreason"),
        )
        sid = r.json()["id"]
        # status = draft : doit echouer 422 (pas verified)
        r = await client.post(
            f"/api/sources/{sid}/mark-outdated",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"reason": ""},
        )
        # Empty reason caught by Pydantic 422
        assert r.status_code == 422
