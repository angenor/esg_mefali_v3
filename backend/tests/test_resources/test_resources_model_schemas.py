"""F20 — Tests modèle Resource + schémas Pydantic."""

from __future__ import annotations

import uuid as _uuid
from datetime import date

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resource import (
    Resource,
    ResourceLanguage,
    ResourcePublicationStatus,
    ResourceType,
)
from app.modules.resources.schemas import (
    ResourceCreateAdmin,
    ResourceUpdateAdmin,
)
from tests.test_resources.conftest import (
    make_admin,
    make_intermediary,
    make_verified_source,
)

pytestmark = pytest.mark.asyncio


class TestResourceModel:
    async def test_resource_default_status_draft(self, db_session: AsyncSession) -> None:
        admin, _ = await make_admin(db_session)
        source = await make_verified_source(db_session, admin.id)
        r = Resource(
            type=ResourceType.GUIDE.value,
            title="Test",
            slug="test-guide",
            description="desc",
            content_md="# hi",
            category=["governance"],
            target_audience=["pme_small"],
            language="fr",
            source_id=source.id,
            created_by=admin.id,
        )
        db_session.add(r)
        await db_session.commit()
        await db_session.refresh(r)
        assert r.publication_status == ResourcePublicationStatus.DRAFT.value
        assert r.view_count == 0
        assert r.version == "1.0.0"

    async def test_resource_repr(self, db_session: AsyncSession) -> None:
        admin, _ = await make_admin(db_session)
        source = await make_verified_source(db_session, admin.id)
        r = Resource(
            type=ResourceType.FAQ.value,
            title="Q",
            slug="q-slug",
            description="d",
            content_md="x",
            category=[],
            target_audience=[],
            language="fr",
            source_id=source.id,
            created_by=admin.id,
        )
        db_session.add(r)
        await db_session.flush()
        s = repr(r)
        assert "Resource" in s and "q-slug" in s


class TestResourceSchemas:
    def _payload(self, source_id: _uuid.UUID, **overrides) -> dict:
        base = {
            "type": ResourceType.GUIDE,
            "title": "Guide",
            "slug": "valid-slug",
            "description": "desc",
            "content_md": "# Hello",
            "category": ["governance"],
            "target_audience": ["pme_small"],
            "language": ResourceLanguage.FR,
            "source_id": source_id,
            "intermediary_id": None,
            "file_url": None,
            "video_url": None,
            "duration_seconds": None,
        }
        base.update(overrides)
        return base

    def test_create_admin_valid(self) -> None:
        payload = self._payload(_uuid.uuid4())
        m = ResourceCreateAdmin(**payload)
        assert m.slug == "valid-slug"

    def test_invalid_slug_format(self) -> None:
        with pytest.raises(ValidationError):
            ResourceCreateAdmin(**self._payload(_uuid.uuid4(), slug="Bad Slug!"))

    def test_intermediary_guide_requires_intermediary_id(self) -> None:
        with pytest.raises(ValidationError):
            ResourceCreateAdmin(
                **self._payload(
                    _uuid.uuid4(),
                    type=ResourceType.INTERMEDIARY_GUIDE,
                    intermediary_id=None,
                )
            )

    def test_non_intermediary_guide_rejects_intermediary_id(self) -> None:
        with pytest.raises(ValidationError):
            ResourceCreateAdmin(
                **self._payload(
                    _uuid.uuid4(),
                    type=ResourceType.GUIDE,
                    intermediary_id=_uuid.uuid4(),
                )
            )

    def test_template_doc_requires_file_url(self) -> None:
        with pytest.raises(ValidationError):
            ResourceCreateAdmin(
                **self._payload(_uuid.uuid4(), type=ResourceType.TEMPLATE_DOC)
            )

    def test_template_doc_with_file_url_ok(self) -> None:
        m = ResourceCreateAdmin(
            **self._payload(
                _uuid.uuid4(),
                type=ResourceType.TEMPLATE_DOC,
                file_url="/uploads/resources/x.docx",
            )
        )
        assert m.file_url == "/uploads/resources/x.docx"

    def test_video_requires_video_url(self) -> None:
        with pytest.raises(ValidationError):
            ResourceCreateAdmin(
                **self._payload(_uuid.uuid4(), type=ResourceType.VIDEO)
            )

    def test_video_url_whitelist_youtube_ok(self) -> None:
        m = ResourceCreateAdmin(
            **self._payload(
                _uuid.uuid4(),
                type=ResourceType.VIDEO,
                video_url="https://www.youtube.com/embed/abc123",
            )
        )
        assert "youtube" in m.video_url

    def test_video_url_invalid_provider(self) -> None:
        with pytest.raises(ValidationError):
            ResourceCreateAdmin(
                **self._payload(
                    _uuid.uuid4(),
                    type=ResourceType.VIDEO,
                    video_url="https://example.com/video.mp4",
                )
            )

    def test_invalid_target_audience(self) -> None:
        with pytest.raises(ValidationError):
            ResourceCreateAdmin(
                **self._payload(_uuid.uuid4(), target_audience=["large_corp"])
            )

    def test_content_md_too_long(self) -> None:
        with pytest.raises(ValidationError):
            ResourceCreateAdmin(
                **self._payload(_uuid.uuid4(), content_md="x" * 50_001)
            )

    def test_update_admin_partial_ok(self) -> None:
        m = ResourceUpdateAdmin(title="New title")
        assert m.title == "New title"

    def test_update_admin_video_url_whitelist(self) -> None:
        with pytest.raises(ValidationError):
            ResourceUpdateAdmin(video_url="https://malicious.example.com/v")
