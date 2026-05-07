"""F04 — Tests du service versioning (bump_version, supersede, cycles)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.modules.versioning.exceptions import (
    NotPublishedError,
    SupersedeCycleError,
    VersioningError,
)
from app.modules.versioning.service import (
    bump_version,
    create_new_version,
    is_published,
    supersede,
)


class TestBumpVersion:
    def test_bump_minor_default(self) -> None:
        assert bump_version("1.0") == "1.1"

    def test_bump_minor_increments(self) -> None:
        assert bump_version("1.5") == "1.6"
        assert bump_version("3.42") == "3.43"

    def test_bump_major_force(self) -> None:
        assert bump_version("1.0", force_major=True) == "2.0"
        assert bump_version("1.5", force_major=True) == "2.0"
        assert bump_version("9.99", force_major=True) == "10.0"

    def test_bump_invalid_format_raises(self) -> None:
        with pytest.raises(VersioningError):
            bump_version("invalid")
        with pytest.raises(VersioningError):
            bump_version("1.2.3")  # 3 composantes
        with pytest.raises(VersioningError):
            bump_version("1")
        with pytest.raises(VersioningError):
            bump_version("v1.0")

    def test_bump_non_string_raises(self) -> None:
        with pytest.raises(VersioningError):
            bump_version(1.0)  # type: ignore[arg-type]


class TestIsPublished:
    """Tests de la fonction is_published."""

    def test_published_via_publication_status(self) -> None:
        class _E:
            publication_status = "published"
            valid_to = None
        assert is_published(_E())

    def test_draft_via_publication_status(self) -> None:
        class _E:
            publication_status = "draft"
            valid_to = None
        assert not is_published(_E())

    def test_published_via_valid_to_none(self) -> None:
        class _E:
            valid_to = None
            # pas de publication_status
        assert is_published(_E())

    def test_archived_via_valid_to_set(self) -> None:
        class _E:
            valid_to = date(2025, 1, 1)
        assert not is_published(_E())


@pytest.mark.asyncio
async def test_supersede_self_raises(db_session) -> None:
    """Impossible de superseder une ligne par elle-même."""
    from app.models.exchange_rate import ExchangeRate
    fake_id = uuid.uuid4()
    with pytest.raises(SupersedeCycleError):
        await supersede(db_session, ExchangeRate, fake_id, fake_id)


@pytest.mark.asyncio
async def test_create_new_version_returns_bumped_version(db_session) -> None:
    """create_new_version retourne le bump version + valid_from."""
    today = date(2026, 5, 7)

    class _E:
        id = uuid.uuid4()
        version = "1.5"
        valid_to = None
        publication_status = "published"

    entity = _E()
    plan = await create_new_version(db_session, entity, today=today)
    assert plan["old_id"] == entity.id
    assert plan["new_version"] == "1.6"
    assert plan["new_valid_from"] == today


@pytest.mark.asyncio
async def test_create_new_version_force_major(db_session) -> None:
    today = date(2026, 5, 7)

    class _E:
        id = uuid.uuid4()
        version = "1.5"
        valid_to = None
        publication_status = "published"

    plan = await create_new_version(db_session, _E(), force_major=True, today=today)
    assert plan["new_version"] == "2.0"


@pytest.mark.asyncio
async def test_create_new_version_rejects_unpublished(db_session) -> None:
    """Une entité non publiée ne peut pas être versionnée."""
    class _E:
        id = uuid.uuid4()
        version = "1.0"
        valid_to = None
        publication_status = "draft"

    with pytest.raises(NotPublishedError):
        await create_new_version(db_session, _E())
