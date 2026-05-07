"""Tests F09 — modèle PasswordResetToken (round-trip ORM + contraintes)."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.core.constants import UserRole
from app.models.account import Account
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User


pytestmark = pytest.mark.asyncio


async def _make_user(db: AsyncSession) -> User:
    account = Account(name="Test Acc")
    db.add(account)
    await db.flush()
    user = User(
        email=f"u-{_uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pw1234567"),
        full_name="U",
        company_name="C",
        role=UserRole.PME.value,
        account_id=account.id,
    )
    db.add(user)
    await db.flush()
    return user


async def test_create_minimal_fields_ok(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    tok = PasswordResetToken(
        user_id=user.id,
        token_hash="a" * 64,
        expires_at=expires,
    )
    db_session.add(tok)
    await db_session.commit()
    await db_session.refresh(tok)
    assert tok.id is not None
    assert tok.created_at is not None
    assert tok.used_at is None


async def test_unique_token_hash(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    h = "deadbeef" * 8
    db_session.add(PasswordResetToken(
        user_id=user.id, token_hash=h, expires_at=expires,
    ))
    await db_session.commit()

    db_session.add(PasswordResetToken(
        user_id=user.id, token_hash=h, expires_at=expires,
    ))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_round_trip_persists_correctly(
    db_session: AsyncSession,
) -> None:
    """Vérifie le round-trip complet d'un token."""
    user = await _make_user(db_session)
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    tok = PasswordResetToken(
        user_id=user.id,
        token_hash="cafe" * 16,
        expires_at=expires,
    )
    db_session.add(tok)
    await db_session.commit()

    # Reload
    res = await db_session.execute(
        select(PasswordResetToken).where(PasswordResetToken.id == tok.id)
    )
    loaded = res.scalar_one()
    assert loaded.user_id == user.id
    assert loaded.token_hash == "cafe" * 16
    assert loaded.used_at is None
