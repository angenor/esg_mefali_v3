"""Tests intégration migration Alembic 021 (T009)."""

from __future__ import annotations

import pytest
from sqlalchemy import text


@pytest.mark.postgres
class TestSchemaPresent:
    @pytest.mark.asyncio
    async def test_table_audit_log_exists(self, pg_session) -> None:
        r = await pg_session.execute(
            text(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name = 'audit_log' "
                "ORDER BY ordinal_position"
            )
        )
        rows = r.fetchall()
        col_names = [row[0] for row in rows]
        # 12 colonnes attendues
        for expected in (
            "id",
            "user_id",
            "account_id",
            "timestamp",
            "entity_type",
            "entity_id",
            "action",
            "field",
            "old_value",
            "new_value",
            "source_of_change",
            "actor_metadata",
        ):
            assert expected in col_names, f"colonne {expected!r} absente"

    @pytest.mark.asyncio
    async def test_indexes_present(self, pg_session) -> None:
        r = await pg_session.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename='audit_log' ORDER BY indexname"
            )
        )
        idx = {row[0] for row in r.fetchall()}
        expected = {
            "idx_audit_log_account_timestamp",
            "idx_audit_log_account_entity",
            "idx_audit_log_user_timestamp",
            "idx_audit_log_source_timestamp",
        }
        missing = expected - idx
        assert not missing, f"indexes manquants : {missing}"

    @pytest.mark.asyncio
    async def test_enums_present(self, pg_session) -> None:
        r = await pg_session.execute(
            text(
                "SELECT typname FROM pg_type "
                "WHERE typname IN ('audit_action','audit_source')"
            )
        )
        types = {row[0] for row in r.fetchall()}
        assert "audit_action" in types
        assert "audit_source" in types

    @pytest.mark.asyncio
    async def test_triggers_present(self, pg_session) -> None:
        r = await pg_session.execute(
            text(
                "SELECT tgname FROM pg_trigger "
                "WHERE tgrelid='audit_log'::regclass AND NOT tgisinternal"
            )
        )
        triggers = {row[0] for row in r.fetchall()}
        assert "audit_log_no_update" in triggers
        assert "audit_log_no_delete" in triggers

    @pytest.mark.asyncio
    async def test_rls_enabled_and_forced(self, pg_session) -> None:
        r = await pg_session.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity "
                "FROM pg_class WHERE relname='audit_log'"
            )
        )
        row = r.fetchone()
        assert row is not None
        assert row[0] is True  # ENABLE
        assert row[1] is True  # FORCE

    @pytest.mark.asyncio
    async def test_policies_present(self, pg_session) -> None:
        r = await pg_session.execute(
            text(
                "SELECT policyname FROM pg_policies WHERE tablename='audit_log' "
                "ORDER BY policyname"
            )
        )
        policies = {row[0] for row in r.fetchall()}
        assert "pme_access_own_account" in policies
        assert "pme_insert_own_account" in policies
        assert "admin_full_access" in policies
        assert "admin_insert_anywhere" in policies
