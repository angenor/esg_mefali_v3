"""Tests d'intégration PG — triggers append-only ``audit_log`` (T010)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from app.core.constants import AuditAction, AuditSourceOfChange
from app.models.audit_log import AuditLog


@pytest.mark.postgres
class TestAppendOnlyTriggers:
    @pytest.mark.asyncio
    async def test_insert_then_update_raises(self, pg_session, pg_user_admin):
        account, pme, admin = pg_user_admin

        # Insertion via SQL direct (admin context déjà SET dans la fixture)
        log = AuditLog(
            user_id=admin.id,
            account_id=account.id,
            entity_type="company_profile",
            entity_id=uuid.uuid4(),
            action=AuditAction.create,
            source_of_change=AuditSourceOfChange.admin,
        )
        pg_session.add(log)
        await pg_session.flush()
        log_id = log.id

        # UPDATE → doit échouer via trigger
        with pytest.raises((ProgrammingError, DBAPIError)) as exc_info:
            await pg_session.execute(
                text(
                    "UPDATE audit_log SET source_of_change='manual' "
                    "WHERE id=:id"
                ),
                {"id": log_id},
            )
            await pg_session.flush()
        assert "append-only" in str(exc_info.value).lower() or "forbidden" in str(
            exc_info.value
        ).lower()

    @pytest.mark.asyncio
    async def test_insert_then_delete_raises(self, pg_session, pg_user_admin):
        account, pme, admin = pg_user_admin

        log = AuditLog(
            user_id=admin.id,
            account_id=account.id,
            entity_type="company_profile",
            entity_id=uuid.uuid4(),
            action=AuditAction.create,
            source_of_change=AuditSourceOfChange.admin,
        )
        pg_session.add(log)
        await pg_session.flush()
        log_id = log.id

        with pytest.raises((ProgrammingError, DBAPIError)) as exc_info:
            await pg_session.execute(
                text("DELETE FROM audit_log WHERE id=:id"),
                {"id": log_id},
            )
            await pg_session.flush()
        assert "append-only" in str(exc_info.value).lower() or "forbidden" in str(
            exc_info.value
        ).lower()

    @pytest.mark.asyncio
    async def test_invalid_enum_value_raises(self, pg_session, pg_user_admin):
        account, pme, admin = pg_user_admin

        # Tentative d'insertion avec une valeur ENUM invalide
        with pytest.raises((ProgrammingError, DBAPIError)):
            await pg_session.execute(
                text(
                    "INSERT INTO audit_log "
                    "(id, user_id, account_id, entity_type, entity_id, action, source_of_change) "
                    "VALUES (gen_random_uuid(), :u, :a, 'x', gen_random_uuid(), 'create', 'invalid')"
                ),
                {"u": admin.id, "a": account.id},
            )
            await pg_session.flush()


async def _is_superuser(session) -> bool:
    """Détecte si la session est connectée comme superuser (RLS bypass)."""
    r = await session.execute(
        text("SELECT rolsuper FROM pg_roles WHERE rolname=current_user")
    )
    return bool(r.scalar_one_or_none())


@pytest.mark.postgres
class TestRLSIsolation:
    """Tests RLS — skipés si la session est superuser (cas MVP F02/F03 où le
    rôle applicatif est superuser/owner et bypass RLS en PG).

    Les policies sont vérifiées par leur seule présence + structure dans
    ``test_alembic_021_upgrade_downgrade``. La validation fonctionnelle
    nécessitera un rôle non-superuser post-MVP (cf. limites documentées).
    """

    @pytest.mark.asyncio
    async def test_pme_can_read_own_logs_only(self, pg_session, pg_user_admin):
        if await _is_superuser(pg_session):
            pytest.skip(
                "RLS test skipped : current PG role is superuser (bypass RLS). "
                "Requires non-superuser application role (post-MVP)."
            )

        account, pme, admin = pg_user_admin

        # Créer un AuditLog pour le compte PME
        log = AuditLog(
            user_id=admin.id,
            account_id=account.id,
            entity_type="account",
            entity_id=account.id,
            action=AuditAction.view_admin,
            source_of_change=AuditSourceOfChange.admin,
        )
        pg_session.add(log)
        await pg_session.flush()
        my_id = log.id

        # Créer un autre compte + log
        from app.models.account import Account

        other_account = Account(name=f"other-{uuid.uuid4().hex[:6]}")
        pg_session.add(other_account)
        await pg_session.flush()
        other_log = AuditLog(
            user_id=admin.id,
            account_id=other_account.id,
            entity_type="account",
            entity_id=other_account.id,
            action=AuditAction.view_admin,
            source_of_change=AuditSourceOfChange.admin,
        )
        pg_session.add(other_log)
        await pg_session.flush()

        # Switch au contexte PME du compte 1
        await pg_session.execute(
            text("SELECT set_config('app.current_role', 'PME', true)")
        )
        await pg_session.execute(
            text("SELECT set_config('app.current_account_id', :v, true)"),
            {"v": str(account.id)},
        )

        result = await pg_session.execute(text("SELECT id FROM audit_log"))
        ids = {row[0] for row in result.fetchall()}
        assert my_id in ids
        assert other_log.id not in ids

    @pytest.mark.asyncio
    async def test_admin_sees_all_accounts(self, pg_session, pg_user_admin):
        # Ce test fonctionne avec OU sans superuser (admin_full_access matche
        # OU bypass RLS).
        account, pme, admin = pg_user_admin

        log = AuditLog(
            user_id=admin.id,
            account_id=account.id,
            entity_type="account",
            entity_id=account.id,
            action=AuditAction.view_admin,
            source_of_change=AuditSourceOfChange.admin,
        )
        pg_session.add(log)
        await pg_session.flush()

        from app.models.account import Account

        other_account = Account(name=f"other-admin-{uuid.uuid4().hex[:6]}")
        pg_session.add(other_account)
        await pg_session.flush()
        other_log = AuditLog(
            user_id=admin.id,
            account_id=other_account.id,
            entity_type="account",
            entity_id=other_account.id,
            action=AuditAction.view_admin,
            source_of_change=AuditSourceOfChange.admin,
        )
        pg_session.add(other_log)
        await pg_session.flush()

        # Reste en contexte ADMIN (déjà SET dans fixture)
        result = await pg_session.execute(text("SELECT id FROM audit_log"))
        ids = {row[0] for row in result.fetchall()}
        assert log.id in ids
        assert other_log.id in ids
