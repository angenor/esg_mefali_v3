"""Tests unitaires modèle SQLAlchemy ``AuditLog`` (T007)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.constants import AuditAction, AuditSourceOfChange
from app.models.audit_log import AuditLog
from tests.conftest import make_pme_user


class TestAuditLogModel:
    @pytest.mark.asyncio
    async def test_create_minimal(self, db_session) -> None:
        user = await make_pme_user(db_session)
        await db_session.commit()

        log = AuditLog(
            user_id=user.id,
            account_id=user.account_id,
            entity_type="company_profile",
            entity_id=uuid.uuid4(),
            action=AuditAction.create,
            source_of_change=AuditSourceOfChange.manual,
        )
        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)
        assert log.id is not None
        assert log.timestamp is not None  # défaut serveur
        assert log.field is None
        assert log.old_value is None
        assert log.new_value is None
        assert log.actor_metadata is None

    @pytest.mark.asyncio
    async def test_jsonb_fields_accept_arbitrary_json(self, db_session) -> None:
        user = await make_pme_user(db_session)
        await db_session.commit()

        log = AuditLog(
            user_id=user.id,
            account_id=user.account_id,
            entity_type="fund_application",
            entity_id=uuid.uuid4(),
            action=AuditAction.update,
            field="sections",
            old_value={"intro": "old text"},
            new_value={"intro": "new text", "items": [1, 2, 3]},
            source_of_change=AuditSourceOfChange.llm,
            actor_metadata={"tool_name": "create_fund_application"},
        )
        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)
        assert log.old_value == {"intro": "old text"}
        assert log.new_value == {"intro": "new text", "items": [1, 2, 3]}
        assert log.actor_metadata == {"tool_name": "create_fund_application"}

    @pytest.mark.asyncio
    async def test_user_id_nullable_after_f05(self, db_session) -> None:
        """F05 — user_id devient nullable pour permettre l'anonymisation RGPD."""
        user = await make_pme_user(db_session)
        await db_session.commit()
        log = AuditLog(
            user_id=None,  # accepté depuis F05
            account_id=user.account_id,
            entity_type="company_profile",
            entity_id=uuid.uuid4(),
            action=AuditAction.create,
            source_of_change=AuditSourceOfChange.manual,
        )
        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)
        assert log.user_id is None

    @pytest.mark.asyncio
    async def test_account_id_nullable_after_f05(self, db_session) -> None:
        """F05 — account_id devient nullable pour permettre l'anonymisation RGPD."""
        user = await make_pme_user(db_session)
        await db_session.commit()
        log = AuditLog(
            user_id=user.id,
            account_id=None,  # accepté depuis F05
            entity_type="company_profile",
            entity_id=uuid.uuid4(),
            action=AuditAction.create,
            source_of_change=AuditSourceOfChange.manual,
        )
        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)
        assert log.account_id is None

    @pytest.mark.asyncio
    async def test_field_nullable(self, db_session) -> None:
        user = await make_pme_user(db_session)
        await db_session.commit()
        # Champ field=NULL pour create
        log = AuditLog(
            user_id=user.id,
            account_id=user.account_id,
            entity_type="company_profile",
            entity_id=uuid.uuid4(),
            action=AuditAction.create,
            field=None,
            source_of_change=AuditSourceOfChange.manual,
        )
        db_session.add(log)
        await db_session.commit()
        assert log.field is None

    @pytest.mark.asyncio
    async def test_select_back(self, db_session) -> None:
        user = await make_pme_user(db_session)
        await db_session.commit()
        log = AuditLog(
            user_id=user.id,
            account_id=user.account_id,
            entity_type="company_profile",
            entity_id=uuid.uuid4(),
            action=AuditAction.update,
            field="sector",
            old_value="agriculture",
            new_value="energie",
            source_of_change=AuditSourceOfChange.manual,
        )
        db_session.add(log)
        await db_session.commit()
        result = await db_session.execute(select(AuditLog).where(AuditLog.id == log.id))
        row = result.scalar_one()
        assert row.field == "sector"
        assert row.action == AuditAction.update or row.action == "update"
        assert row.source_of_change == AuditSourceOfChange.manual or row.source_of_change == "manual"
