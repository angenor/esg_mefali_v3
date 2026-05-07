"""Tests F09 — router admin /sources (workflow 4-yeux + impact analysis)."""

from __future__ import annotations

import uuid as _uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.core.security import create_access_token, hash_password
from app.models.user import User


pytestmark = pytest.mark.asyncio


async def _make_admin(db: AsyncSession, suffix: str = "") -> tuple[User, str]:
    user = User(
        email=f"admin{suffix}-{_uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pw1234567"),
        full_name=f"Admin{suffix}",
        company_name="ESG",
        role=UserRole.ADMIN.value,
        account_id=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, create_access_token(str(user.id))


def _payload() -> dict:
    return {
        "url": f"https://example.com/doc-{_uuid.uuid4().hex[:6]}",
        "title": "Document Test",
        "publisher": "GCF",
        "version": "v1.0",
        "date_publi": "2024-01-01",
        "page": 1,
        "section": "S1",
    }


class TestSourcesAdmin:
    async def test_create_source_in_pending_status(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin_a, token_a = await _make_admin(db_session, "_a")
        response = await client.post(
            "/api/admin/sources",
            headers={"Authorization": f"Bearer {token_a}"},
            json=_payload(),
        )
        assert response.status_code == 201
        body = response.json()
        assert body["captured_by"] == str(admin_a.id)
        assert body["verification_status"] == "pending"

    async def test_creator_cannot_verify_own_source(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin_a, token_a = await _make_admin(db_session, "_a")
        # Créer
        r_create = await client.post(
            "/api/admin/sources",
            headers={"Authorization": f"Bearer {token_a}"},
            json=_payload(),
        )
        source_id = r_create.json()["id"]
        # Tenter verify par A (créateur) → 400 four_eyes_violation
        r = await client.patch(
            f"/api/admin/sources/{source_id}",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"verification_status": "verified"},
        )
        assert r.status_code == 400
        detail = r.json()["detail"]
        assert isinstance(detail, dict) and detail.get("error") == "four_eyes_violation"

    async def test_other_admin_can_verify(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin_a, token_a = await _make_admin(db_session, "_a")
        admin_b, token_b = await _make_admin(db_session, "_b")
        r_create = await client.post(
            "/api/admin/sources",
            headers={"Authorization": f"Bearer {token_a}"},
            json=_payload(),
        )
        source_id = r_create.json()["id"]
        r = await client.patch(
            f"/api/admin/sources/{source_id}",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"verification_status": "verified"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["verification_status"] == "verified"
        assert body["verified_by"] == str(admin_b.id)

    async def test_list_sources_filter_pending(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin_a, token_a = await _make_admin(db_session, "_a")
        await client.post(
            "/api/admin/sources",
            headers={"Authorization": f"Bearer {token_a}"},
            json=_payload(),
        )
        r = await client.get(
            "/api/admin/sources?verification_status=pending",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total"] >= 1
        assert all(it["verification_status"] == "pending" for it in body["items"])

    async def test_dependents_returns_empty_report(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin_a, token_a = await _make_admin(db_session, "_a")
        r_create = await client.post(
            "/api/admin/sources",
            headers={"Authorization": f"Bearer {token_a}"},
            json=_payload(),
        )
        source_id = r_create.json()["id"]
        r = await client.get(
            f"/api/admin/sources/{source_id}/dependents",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
