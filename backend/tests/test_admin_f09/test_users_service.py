"""Tests F09 — service users (reset password + toggle active)."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.core.email_service import NoopEmailService
from app.core.security import hash_password, hash_token, verify_password
from app.models.account import Account
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.modules.admin.users_service import (
    ResetTokenAlreadyUsedError,
    ResetTokenExpiredError,
    ResetTokenInvalidError,
    complete_password_reset,
    initiate_password_reset,
    toggle_user_active,
)


pytestmark = pytest.mark.asyncio


async def _make_admin(db: AsyncSession) -> User:
    user = User(
        email=f"admin-{_uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("admin1234"),
        full_name="Admin",
        company_name="ESG Mefali",
        role=UserRole.ADMIN.value,
        account_id=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _make_pme(db: AsyncSession) -> User:
    account = Account(name="PME Acc")
    db.add(account)
    await db.flush()
    user = User(
        email=f"pme-{_uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("oldpw1234"),
        full_name="PME",
        company_name="PME",
        role=UserRole.PME.value,
        account_id=account.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


class TestInitiatePasswordReset:
    async def test_creates_token_with_1h_expiration(
        self, db_session: AsyncSession
    ) -> None:
        admin = await _make_admin(db_session)
        pme = await _make_pme(db_session)
        token_row, plain = await initiate_password_reset(
            db_session,
            user_id=pme.id,
            admin_id=admin.id,
            email_service=NoopEmailService(),
        )
        await db_session.commit()
        assert token_row.user_id == pme.id
        assert len(plain) >= 32
        # ~1h plus tard
        delta = token_row.expires_at - datetime.now(timezone.utc)
        assert timedelta(minutes=55) < delta < timedelta(minutes=65)
        # Hash stocké correspond
        assert token_row.token_hash == hash_token(plain)
        assert token_row.used_at is None

    async def test_unknown_user_raises(self, db_session: AsyncSession) -> None:
        admin = await _make_admin(db_session)
        with pytest.raises(ResetTokenInvalidError):
            await initiate_password_reset(
                db_session,
                user_id=_uuid.uuid4(),
                admin_id=admin.id,
                email_service=NoopEmailService(),
            )


class TestCompletePasswordReset:
    async def test_valid_token_changes_password(
        self, db_session: AsyncSession
    ) -> None:
        admin = await _make_admin(db_session)
        pme = await _make_pme(db_session)
        token_row, plain = await initiate_password_reset(
            db_session,
            user_id=pme.id,
            admin_id=admin.id,
            email_service=NoopEmailService(),
        )
        await db_session.commit()

        updated = await complete_password_reset(
            db_session,
            plain_token=plain,
            new_password="newPW123!",
        )
        await db_session.commit()
        assert verify_password("newPW123!", updated.hashed_password) is True

        # used_at marqué
        await db_session.refresh(token_row)
        assert token_row.used_at is not None

    async def test_expired_token_raises(self, db_session: AsyncSession) -> None:
        admin = await _make_admin(db_session)
        pme = await _make_pme(db_session)
        token_row, plain = await initiate_password_reset(
            db_session,
            user_id=pme.id,
            admin_id=admin.id,
            email_service=NoopEmailService(),
        )
        # Force expiration au passé
        token_row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await db_session.commit()

        with pytest.raises(ResetTokenExpiredError):
            await complete_password_reset(
                db_session,
                plain_token=plain,
                new_password="newPW123!",
            )

    async def test_already_used_token_raises(
        self, db_session: AsyncSession
    ) -> None:
        admin = await _make_admin(db_session)
        pme = await _make_pme(db_session)
        token_row, plain = await initiate_password_reset(
            db_session,
            user_id=pme.id,
            admin_id=admin.id,
            email_service=NoopEmailService(),
        )
        await db_session.commit()
        await complete_password_reset(
            db_session, plain_token=plain, new_password="firstPW1!",
        )
        await db_session.commit()
        with pytest.raises(ResetTokenAlreadyUsedError):
            await complete_password_reset(
                db_session, plain_token=plain, new_password="secondPW2!",
            )

    async def test_invalid_token_raises(self, db_session: AsyncSession) -> None:
        with pytest.raises(ResetTokenInvalidError):
            await complete_password_reset(
                db_session,
                plain_token="not-a-real-token-xxxxxxxxxxxxxxxxxxxx",
                new_password="newPW123!",
            )


class TestToggleUserActive:
    async def test_toggle_changes_state(self, db_session: AsyncSession) -> None:
        admin = await _make_admin(db_session)
        pme = await _make_pme(db_session)
        assert pme.is_active is True

        updated = await toggle_user_active(
            db_session,
            user_id=pme.id,
            admin_id=admin.id,
            reason="Suspicion d'usage abusif",
        )
        await db_session.commit()
        assert updated.is_active is False

        # Toggle back
        updated2 = await toggle_user_active(
            db_session,
            user_id=pme.id,
            admin_id=admin.id,
            reason="Réactivation après vérification",
        )
        await db_session.commit()
        assert updated2.is_active is True
