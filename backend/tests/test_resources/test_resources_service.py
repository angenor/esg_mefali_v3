"""F20 — Tests du service ResourceService."""

from __future__ import annotations

import uuid as _uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resource import Resource, ResourcePublicationStatus, ResourceType
from app.modules.resources.exceptions import (
    ResourceFourEyesViolationError,
    ResourceInvalidStatusError,
    ResourceNotFoundError,
    ResourceSlugConflictError,
    ResourceSourceNotVerifiedError,
)
from app.modules.resources.schemas import ResourceCreateAdmin, ResourceUpdateAdmin
from app.modules.resources.service import ResourceService, _bump_patch
from app.models.source import Source, VerificationStatus
from tests.test_resources.conftest import (
    make_admin,
    make_intermediary,
    make_verified_source,
)

pytestmark = pytest.mark.asyncio


def _create_payload(source_id: _uuid.UUID, **overrides) -> ResourceCreateAdmin:
    base = {
        "type": ResourceType.GUIDE,
        "title": "Guide",
        "slug": "service-test-guide",
        "description": "desc",
        "content_md": "# H",
        "category": ["governance"],
        "target_audience": ["pme_small"],
        "language": "fr",
        "source_id": source_id,
        "intermediary_id": None,
    }
    base.update(overrides)
    return ResourceCreateAdmin(**base)


class TestBumpPatch:
    def test_bump_simple(self) -> None:
        assert _bump_patch("1.0.0") == "1.0.1"
        assert _bump_patch("2.3.5") == "2.3.6"

    def test_bump_short_version(self) -> None:
        assert _bump_patch("1.0") == "1.0.1"


class TestResourceServiceCreateUpdate:
    async def test_create_resource_in_draft(self, db_session: AsyncSession) -> None:
        admin, _ = await make_admin(db_session)
        source = await make_verified_source(db_session, admin.id)
        svc = ResourceService(db_session)
        r = await svc.create_resource(
            _create_payload(source.id), creator_id=admin.id
        )
        await db_session.commit()
        assert r.publication_status == ResourcePublicationStatus.DRAFT.value
        assert r.created_by == admin.id

    async def test_slug_conflict(self, db_session: AsyncSession) -> None:
        admin, _ = await make_admin(db_session)
        source = await make_verified_source(db_session, admin.id)
        svc = ResourceService(db_session)
        await svc.create_resource(_create_payload(source.id), creator_id=admin.id)
        await db_session.commit()
        with pytest.raises(ResourceSlugConflictError):
            await svc.create_resource(
                _create_payload(source.id), creator_id=admin.id
            )

    async def test_source_not_verified(self, db_session: AsyncSession) -> None:
        admin, _ = await make_admin(db_session)
        # Source en draft
        source = Source(
            url=f"https://example.com/x-{_uuid.uuid4().hex[:6]}",
            title="Draft source",
            publisher="Test",
            version="v1",
            date_publi=date(2024, 1, 1),
            captured_by=admin.id,
            verification_status=VerificationStatus.DRAFT.value,
            created_by_user_id=admin.id,
        )
        db_session.add(source)
        await db_session.commit()
        svc = ResourceService(db_session)
        with pytest.raises(ResourceSourceNotVerifiedError):
            await svc.create_resource(
                _create_payload(source.id), creator_id=admin.id
            )

    async def test_update_draft_in_place(self, db_session: AsyncSession) -> None:
        admin, _ = await make_admin(db_session)
        source = await make_verified_source(db_session, admin.id)
        svc = ResourceService(db_session)
        r = await svc.create_resource(_create_payload(source.id), creator_id=admin.id)
        await db_session.commit()
        updated = await svc.update_resource(
            r.id,
            ResourceUpdateAdmin(title="New title"),
            editor_id=admin.id,
        )
        await db_session.commit()
        assert updated.id == r.id
        assert updated.title == "New title"

    async def test_update_published_creates_new_draft(
        self, db_session: AsyncSession
    ) -> None:
        admin, _ = await make_admin(db_session)
        source = await make_verified_source(db_session, admin.id)
        svc = ResourceService(db_session)
        r = await svc.create_resource(_create_payload(source.id), creator_id=admin.id)
        # Publier (need different verifier than creator)
        verifier, _ = await make_admin(db_session, "_verif")
        published = await svc.publish_resource(r.id, verifier_id=verifier.id)
        await db_session.commit()
        assert published.publication_status == ResourcePublicationStatus.PUBLISHED.value

        new_draft = await svc.update_resource(
            published.id,
            ResourceUpdateAdmin(title="V1.0.1"),
            editor_id=verifier.id,
        )
        await db_session.commit()
        assert new_draft.id != published.id
        assert new_draft.publication_status == ResourcePublicationStatus.DRAFT.value
        assert new_draft.version == "1.0.1"


class TestResourceServicePublish:
    async def test_publish_4_eyes_violation(self, db_session: AsyncSession) -> None:
        admin, _ = await make_admin(db_session)
        source = await make_verified_source(db_session, admin.id)
        svc = ResourceService(db_session)
        r = await svc.create_resource(_create_payload(source.id), creator_id=admin.id)
        await db_session.commit()
        with pytest.raises(ResourceFourEyesViolationError):
            await svc.publish_resource(r.id, verifier_id=admin.id)

    async def test_publish_only_drafts(self, db_session: AsyncSession) -> None:
        admin, _ = await make_admin(db_session)
        verifier, _ = await make_admin(db_session, "_v")
        source = await make_verified_source(db_session, admin.id)
        svc = ResourceService(db_session)
        r = await svc.create_resource(_create_payload(source.id), creator_id=admin.id)
        await svc.publish_resource(r.id, verifier_id=verifier.id)
        await db_session.commit()
        with pytest.raises(ResourceInvalidStatusError):
            await svc.publish_resource(r.id, verifier_id=verifier.id)

    async def test_publish_intermediary_guide_supersedes_old(
        self, db_session: AsyncSession
    ) -> None:
        admin, _ = await make_admin(db_session)
        verifier, _ = await make_admin(db_session, "_v")
        source = await make_verified_source(db_session, admin.id)
        intermediary = await make_intermediary(db_session)
        svc = ResourceService(db_session)
        # première version publiée
        r1 = await svc.create_resource(
            _create_payload(
                source.id,
                slug="ig-v1",
                type=ResourceType.INTERMEDIARY_GUIDE,
                intermediary_id=intermediary.id,
            ),
            creator_id=admin.id,
        )
        await svc.publish_resource(r1.id, verifier_id=verifier.id)
        await db_session.commit()
        # deuxième version qu'on publie : la première doit être supersédée
        r2 = await svc.create_resource(
            _create_payload(
                source.id,
                slug="ig-v2",
                type=ResourceType.INTERMEDIARY_GUIDE,
                intermediary_id=intermediary.id,
            ),
            creator_id=admin.id,
        )
        await svc.publish_resource(r2.id, verifier_id=verifier.id)
        await db_session.commit()
        await db_session.refresh(r1)
        assert r1.superseded_by == r2.id


class TestResourceServiceRead:
    async def test_get_by_slug_only_published(
        self, db_session: AsyncSession
    ) -> None:
        admin, _ = await make_admin(db_session)
        verifier, _ = await make_admin(db_session, "_v")
        source = await make_verified_source(db_session, admin.id)
        svc = ResourceService(db_session)
        r = await svc.create_resource(
            _create_payload(source.id), creator_id=admin.id
        )
        await db_session.commit()
        # draft → invisible
        assert await svc.get_by_slug(r.slug) is None
        await svc.publish_resource(r.id, verifier_id=verifier.id)
        await db_session.commit()
        assert (await svc.get_by_slug(r.slug)).id == r.id

    async def test_increment_view_count_atomic(
        self, db_session: AsyncSession
    ) -> None:
        admin, _ = await make_admin(db_session)
        verifier, _ = await make_admin(db_session, "_v")
        source = await make_verified_source(db_session, admin.id)
        svc = ResourceService(db_session)
        r = await svc.create_resource(_create_payload(source.id), creator_id=admin.id)
        await svc.publish_resource(r.id, verifier_id=verifier.id)
        await db_session.commit()
        n1 = await svc.increment_view_count(r.slug)
        await db_session.commit()
        n2 = await svc.increment_view_count(r.slug)
        await db_session.commit()
        assert n1 == 1
        assert n2 == 2

    async def test_increment_view_count_404(self, db_session: AsyncSession) -> None:
        svc = ResourceService(db_session)
        with pytest.raises(ResourceNotFoundError):
            await svc.increment_view_count("nonexistent")

    async def test_list_published_filters(self, db_session: AsyncSession) -> None:
        admin, _ = await make_admin(db_session)
        verifier, _ = await make_admin(db_session, "_v")
        source = await make_verified_source(db_session, admin.id)
        svc = ResourceService(db_session)
        for i in range(3):
            r = await svc.create_resource(
                _create_payload(
                    source.id,
                    slug=f"l-{i}",
                    type=ResourceType.GUIDE if i < 2 else ResourceType.FAQ,
                ),
                creator_id=admin.id,
            )
            await svc.publish_resource(r.id, verifier_id=verifier.id)
        await db_session.commit()
        items, total = await svc.list_published(type_=ResourceType.GUIDE.value)
        assert total == 2
        assert all(r.type == ResourceType.GUIDE.value for r in items)

    async def test_recommendations_empty(self, db_session: AsyncSession) -> None:
        svc = ResourceService(db_session)
        results = await svc.get_recommendations(limit=5)
        assert results == []

    async def test_delete_only_drafts(self, db_session: AsyncSession) -> None:
        admin, _ = await make_admin(db_session)
        verifier, _ = await make_admin(db_session, "_v")
        source = await make_verified_source(db_session, admin.id)
        svc = ResourceService(db_session)
        r = await svc.create_resource(_create_payload(source.id), creator_id=admin.id)
        await db_session.commit()
        # draft → ok
        await svc.delete_resource(r.id)
        await db_session.commit()
        # republie → tente delete → erreur
        r2 = await svc.create_resource(
            _create_payload(source.id, slug="other-slug"), creator_id=admin.id
        )
        await svc.publish_resource(r2.id, verifier_id=verifier.id)
        await db_session.commit()
        with pytest.raises(ResourceInvalidStatusError):
            await svc.delete_resource(r2.id)

    async def test_archive_resource(self, db_session: AsyncSession) -> None:
        admin, _ = await make_admin(db_session)
        verifier, _ = await make_admin(db_session, "_v")
        source = await make_verified_source(db_session, admin.id)
        svc = ResourceService(db_session)
        r = await svc.create_resource(_create_payload(source.id), creator_id=admin.id)
        await svc.publish_resource(r.id, verifier_id=verifier.id)
        archived = await svc.archive_resource(r.id, editor_id=verifier.id)
        await db_session.commit()
        assert archived.publication_status == ResourcePublicationStatus.ARCHIVED.value
        assert archived.valid_to is not None

    async def test_get_intermediary_guide(self, db_session: AsyncSession) -> None:
        admin, _ = await make_admin(db_session)
        verifier, _ = await make_admin(db_session, "_v")
        source = await make_verified_source(db_session, admin.id)
        intermediary = await make_intermediary(db_session)
        svc = ResourceService(db_session)
        r = await svc.create_resource(
            _create_payload(
                source.id,
                slug="ig-only",
                type=ResourceType.INTERMEDIARY_GUIDE,
                intermediary_id=intermediary.id,
            ),
            creator_id=admin.id,
        )
        await svc.publish_resource(r.id, verifier_id=verifier.id)
        await db_session.commit()
        found = await svc.get_intermediary_guide(intermediary.id)
        assert found is not None and found.id == r.id
