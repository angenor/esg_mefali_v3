"""F19 — Tests unitaires de la migration ``034_reminder_dedup_key``.

Vérifie que la migration ajoute correctement les colonnes et que le modèle
SQLAlchemy reflète l'état de la table.

Sur SQLite (tests unitaires), on valide la présence des colonnes via
introspection après ``Base.metadata.create_all`` (qui simule la migration
finale). Le round-trip up/down est testé en PG via les fixtures
d'intégration (cf. ``tests/integration/`` quand DOCKER_PG=1).
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect

from app.models.action_plan import Reminder
from tests.conftest import test_engine


pytestmark = pytest.mark.unit


async def test_migration_adds_dedup_key_column():
    """La colonne ``dedup_key`` existe dans la table ``reminders``."""
    async with test_engine.connect() as conn:
        cols = await conn.run_sync(
            lambda c: {col["name"] for col in inspect(c).get_columns("reminders")}
        )
    assert "dedup_key" in cols


async def test_migration_adds_sent_at_column():
    """La colonne ``sent_at`` existe."""
    async with test_engine.connect() as conn:
        cols = await conn.run_sync(
            lambda c: {col["name"] for col in inspect(c).get_columns("reminders")}
        )
    assert "sent_at" in cols


async def test_migration_adds_archived_column():
    """La colonne ``archived`` existe."""
    async with test_engine.connect() as conn:
        cols = await conn.run_sync(
            lambda c: {col["name"] for col in inspect(c).get_columns("reminders")}
        )
    assert "archived" in cols


async def test_migration_adds_read_column():
    """La colonne ``read`` existe."""
    async with test_engine.connect() as conn:
        cols = await conn.run_sync(
            lambda c: {col["name"] for col in inspect(c).get_columns("reminders")}
        )
    assert "read" in cols


async def test_migration_dedup_unique_index_exists():
    """L'index unique ``idx_reminders_dedup_key_unique`` existe."""
    async with test_engine.connect() as conn:
        indexes = await conn.run_sync(
            lambda c: {ix["name"] for ix in inspect(c).get_indexes("reminders")}
        )
    assert "idx_reminders_dedup_key_unique" in indexes


async def test_migration_archived_pending_index_exists():
    """L'index ``idx_reminders_archived_pending`` existe."""
    async with test_engine.connect() as conn:
        indexes = await conn.run_sync(
            lambda c: {ix["name"] for ix in inspect(c).get_indexes("reminders")}
        )
    assert "idx_reminders_archived_pending" in indexes


def test_reminder_model_has_new_fields():
    """Le modèle SQLAlchemy expose les nouveaux attributs."""
    cols = {c.name for c in Reminder.__table__.columns}
    assert "dedup_key" in cols
    assert "sent_at" in cols
    assert "archived" in cols
    assert "read" in cols
