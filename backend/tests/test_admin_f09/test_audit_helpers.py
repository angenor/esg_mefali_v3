"""Tests F09 — helpers audit log admin."""

from __future__ import annotations

import uuid as _uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction, UserRole
from app.core.security import hash_password
from app.models.account import Account
from app.models.audit_log import AuditLog
from app.models.user import User
from app.modules.admin.audit_helpers import (
    log_admin_action,
    log_view_admin_dedup,
)


pytestmark = pytest.mark.asyncio


async def _admin(db: AsyncSession) -> User:
    user = User(
        email=f"admin-{_uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pw1234567"),
        full_name="A",
        company_name="ESG",
        role=UserRole.ADMIN.value,
        account_id=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _account(db: AsyncSession) -> Account:
    a = Account(name="A")
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


class TestLogAdminAction:
    async def test_creates_one_audit_entry(
        self, db_session: AsyncSession
    ) -> None:
        admin = await _admin(db_session)
        entity_id = _uuid.uuid4()
        await log_admin_action(
            db_session,
            admin_id=admin.id,
            action="source_verified",
            entity_type="source",
            entity_id=entity_id,
        )
        await db_session.commit()
        rows = (
            await db_session.execute(
                select(AuditLog).where(AuditLog.entity_id == entity_id)
            )
        ).scalars().all()
        assert len(rows) == 1
        meta = rows[0].actor_metadata or {}
        assert meta.get("admin_action") == "source_verified"


class TestLogViewAdminDedup:
    async def test_first_call_creates_entry(
        self, db_session: AsyncSession
    ) -> None:
        admin = await _admin(db_session)
        account = await _account(db_session)
        log = await log_view_admin_dedup(
            db_session,
            admin_id=admin.id,
            account_id=account.id,
        )
        await db_session.commit()
        assert log is not None
        assert log.action == AuditAction.view_admin

    async def test_second_call_same_day_dedup(
        self, db_session: AsyncSession
    ) -> None:
        admin = await _admin(db_session)
        account = await _account(db_session)
        log1 = await log_view_admin_dedup(
            db_session, admin_id=admin.id, account_id=account.id,
        )
        await db_session.commit()
        log2 = await log_view_admin_dedup(
            db_session, admin_id=admin.id, account_id=account.id,
        )
        await db_session.commit()
        assert log1 is not None
        assert log2 is None  # dedup

    async def test_different_account_creates_distinct_entry(
        self, db_session: AsyncSession
    ) -> None:
        admin = await _admin(db_session)
        account1 = await _account(db_session)
        account2 = await _account(db_session)
        l1 = await log_view_admin_dedup(
            db_session, admin_id=admin.id, account_id=account1.id,
        )
        await db_session.commit()
        l2 = await log_view_admin_dedup(
            db_session, admin_id=admin.id, account_id=account2.id,
        )
        await db_session.commit()
        assert l1 is not None
        assert l2 is not None
