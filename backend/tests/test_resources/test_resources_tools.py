"""F20 — Tests des tools LangChain Resources (read-only)."""

from __future__ import annotations

import json
import uuid as _uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.tools.resource_tools import (
    RESOURCE_TOOLS,
    get_resource_content,
    recommend_resources_for_user,
    search_resources,
)
from app.modules.resources.schemas import ResourceCreateAdmin
from app.modules.resources.service import ResourceService
from tests.test_resources.conftest import make_admin, make_verified_source

pytestmark = pytest.mark.asyncio


def _build_config(db: AsyncSession, user_id: _uuid.UUID, **extra) -> dict:
    return {
        "configurable": {
            "db": db,
            "user_id": str(user_id),
            **extra,
        }
    }


class TestResourceToolsContract:
    def test_three_tools_registered(self) -> None:
        names = {t.name for t in RESOURCE_TOOLS}
        assert names == {
            "search_resources",
            "get_resource_content",
            "recommend_resources_for_user",
        }


class TestSearchResources:
    async def test_missing_query(self, db_session: AsyncSession) -> None:
        admin, _ = await make_admin(db_session)
        cfg = _build_config(db_session, admin.id)
        result = await search_resources.ainvoke({"query": ""}, config=cfg)
        body = json.loads(result)
        assert body["error"] == "query required"

    async def test_search_returns_published(
        self, db_session: AsyncSession
    ) -> None:
        admin, _ = await make_admin(db_session)
        verifier, _ = await make_admin(db_session, "_v")
        source = await make_verified_source(db_session, admin.id)
        svc = ResourceService(db_session)
        payload = ResourceCreateAdmin(
            type="guide",
            title="Politique anti-corruption",
            slug="search-anti-corrupt",
            description="Guide PME",
            content_md="# h",
            category=["governance"],
            target_audience=["pme_small"],
            language="fr",
            source_id=source.id,
            intermediary_id=None,
        )
        r = await svc.create_resource(payload, creator_id=admin.id)
        await svc.publish_resource(r.id, verifier_id=verifier.id)
        await db_session.commit()
        cfg = _build_config(db_session, admin.id)
        result = await search_resources.ainvoke(
            {"query": "anti-corruption"}, config=cfg
        )
        body = json.loads(result)
        assert any("anti-corruption" in r["title"].lower() for r in body["results"])


class TestGetResourceContent:
    async def test_not_found(self, db_session: AsyncSession) -> None:
        admin, _ = await make_admin(db_session)
        cfg = _build_config(db_session, admin.id)
        res = await get_resource_content.ainvoke({"slug": "nope"}, config=cfg)
        body = json.loads(res)
        assert body["error"] == "resource_not_found"

    async def test_returns_content(self, db_session: AsyncSession) -> None:
        admin, _ = await make_admin(db_session)
        verifier, _ = await make_admin(db_session, "_v")
        source = await make_verified_source(db_session, admin.id)
        svc = ResourceService(db_session)
        payload = ResourceCreateAdmin(
            type="guide",
            title="Test",
            slug="get-content-test",
            description="d",
            content_md="# Hello world",
            category=[],
            target_audience=[],
            language="fr",
            source_id=source.id,
            intermediary_id=None,
        )
        r = await svc.create_resource(payload, creator_id=admin.id)
        await svc.publish_resource(r.id, verifier_id=verifier.id)
        await db_session.commit()
        cfg = _build_config(db_session, admin.id)
        res = await get_resource_content.ainvoke(
            {"slug": "get-content-test"}, config=cfg
        )
        body = json.loads(res)
        assert body["content_md"] == "# Hello world"


class TestRecommendResources:
    async def test_empty_db_returns_empty(self, db_session: AsyncSession) -> None:
        admin, _ = await make_admin(db_session)
        cfg = _build_config(db_session, admin.id)
        res = await recommend_resources_for_user.ainvoke({}, config=cfg)
        body = json.loads(res)
        assert body["results"] == []

    async def test_recommendations_with_score_context(
        self, db_session: AsyncSession
    ) -> None:
        admin, _ = await make_admin(db_session)
        verifier, _ = await make_admin(db_session, "_v")
        source = await make_verified_source(db_session, admin.id)
        svc = ResourceService(db_session)
        payload = ResourceCreateAdmin(
            type="guide",
            title="Gouvernance",
            slug="rec-gouv",
            description="d",
            content_md="# h",
            category=["governance"],
            target_audience=["pme_small"],
            language="fr",
            source_id=source.id,
            intermediary_id=None,
        )
        r = await svc.create_resource(payload, creator_id=admin.id)
        await svc.publish_resource(r.id, verifier_id=verifier.id)
        await db_session.commit()
        cfg = _build_config(
            db_session,
            admin.id,
            scores={"governance_score": 30},
            active_module="esg_scoring",
        )
        res = await recommend_resources_for_user.ainvoke(
            {"limit": 5}, config=cfg
        )
        body = json.loads(res)
        assert len(body["results"]) >= 1
