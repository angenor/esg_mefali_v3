"""F20 — Tests routers public + admin Resources."""

from __future__ import annotations

import uuid as _uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resources.schemas import ResourceCreateAdmin
from app.modules.resources.service import ResourceService
from tests.test_resources.conftest import (
    make_admin,
    make_intermediary,
    make_pme,
    make_verified_source,
)

pytestmark = pytest.mark.asyncio


def _payload(source_id: _uuid.UUID, **overrides) -> dict:
    base = {
        "type": "guide",
        "title": "Guide",
        "slug": "router-test-guide",
        "description": "desc",
        "content_md": "# h",
        "category": ["governance"],
        "target_audience": ["pme_small"],
        "language": "fr",
        "source_id": str(source_id),
        "intermediary_id": None,
    }
    base.update(overrides)
    return base


class TestPublicRouter:
    async def test_list_resources_empty(self, client: AsyncClient) -> None:
        r = await client.get("/api/resources")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["items"] == []

    async def test_get_resource_404(self, client: AsyncClient) -> None:
        r = await client.get("/api/resources/nonexistent-slug")
        assert r.status_code == 404

    async def test_publish_then_list(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin, _ = await make_admin(db_session)
        verifier, _ = await make_admin(db_session, "_v")
        source = await make_verified_source(db_session, admin.id)
        svc = ResourceService(db_session)
        r = await svc.create_resource(
            ResourceCreateAdmin(**_payload(source.id, slug="public-list-1")),
            creator_id=admin.id,
        )
        await svc.publish_resource(r.id, verifier_id=verifier.id)
        await db_session.commit()
        resp = await client.get("/api/resources")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1

    async def test_view_count_increment(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin, _ = await make_admin(db_session)
        verifier, _ = await make_admin(db_session, "_v")
        source = await make_verified_source(db_session, admin.id)
        svc = ResourceService(db_session)
        r = await svc.create_resource(
            ResourceCreateAdmin(**_payload(source.id, slug="view-count-test")),
            creator_id=admin.id,
        )
        await svc.publish_resource(r.id, verifier_id=verifier.id)
        await db_session.commit()
        resp = await client.post(f"/api/resources/{r.slug}/view")
        assert resp.status_code == 200
        assert resp.json()["view_count"] == 1
        resp2 = await client.post(f"/api/resources/{r.slug}/view")
        assert resp2.json()["view_count"] == 2

    async def test_intermediary_guide_404(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        intermediary = await make_intermediary(db_session)
        resp = await client.get(f"/api/intermediaries/{intermediary.id}/guide")
        assert resp.status_code == 404


class TestAdminRouter:
    async def test_create_admin_only(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        # PME interdit
        _, pme_token = await make_pme(db_session)
        admin, _ = await make_admin(db_session)
        source = await make_verified_source(db_session, admin.id)
        body = _payload(source.id, slug="admin-only-test")
        r = await client.post(
            "/api/admin/resources",
            headers={"Authorization": f"Bearer {pme_token}"},
            json=body,
        )
        assert r.status_code == 403

    async def test_admin_can_create(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin, token = await make_admin(db_session)
        source = await make_verified_source(db_session, admin.id)
        body = _payload(source.id, slug="admin-create-1")
        r = await client.post(
            "/api/admin/resources",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
        assert r.status_code == 201, r.text
        assert r.json()["publication_status"] == "draft"

    async def test_admin_publish_4_eyes(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin, token = await make_admin(db_session)
        source = await make_verified_source(db_session, admin.id)
        body = _payload(source.id, slug="admin-publish-test")
        r = await client.post(
            "/api/admin/resources",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
        rid = r.json()["id"]
        # Same admin tries to publish → 400 four_eyes
        r2 = await client.post(
            f"/api/admin/resources/{rid}/publish",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 400
        assert r2.json()["detail"]["code"] == "four_eyes_violation"

        # Second admin publishes
        _, token2 = await make_admin(db_session, "_v")
        r3 = await client.post(
            f"/api/admin/resources/{rid}/publish",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert r3.status_code == 200
        assert r3.json()["publication_status"] == "published"

    async def test_admin_delete_drafts_only(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin, token = await make_admin(db_session)
        source = await make_verified_source(db_session, admin.id)
        body = _payload(source.id, slug="admin-del-1")
        r = await client.post(
            "/api/admin/resources",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
        rid = r.json()["id"]
        # Delete draft → 204
        r2 = await client.delete(
            f"/api/admin/resources/{rid}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 204

    async def test_admin_archive(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin, token = await make_admin(db_session)
        source = await make_verified_source(db_session, admin.id)
        body = _payload(source.id, slug="admin-arch-1")
        r = await client.post(
            "/api/admin/resources",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
        rid = r.json()["id"]
        r2 = await client.post(
            f"/api/admin/resources/{rid}/archive",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 200
        assert r2.json()["publication_status"] == "archived"

    async def test_admin_list(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        admin, token = await make_admin(db_session)
        r = await client.get(
            "/api/admin/resources",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert "items" in r.json()
