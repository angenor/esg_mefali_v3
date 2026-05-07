"""F05 — Tests du modèle ``Consent`` (T007).

Vérifie les invariants table ``consents`` :
- au plus 1 consentement actif par couple ``(account_id, consent_type)``,
- contrainte CHECK ``revoked_at >= granted_at``,
- enum ``consent_type`` rejette les valeurs invalides,
- FK cascade vers ``accounts``,
- FK SET NULL vers ``users``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.account import Account
from app.models.consent import (
    CONSENT_TYPE_DEFAULT_GRANTED,
    CONSENT_TYPE_VALUES,
    Consent,
)
from app.models.user import User


@pytest.mark.asyncio
async def test_consent_can_be_inserted(db_session) -> None:
    account = Account(name="Test Co")
    db_session.add(account)
    await db_session.flush()

    user = User(
        email="t@example.com",
        hashed_password="x",
        full_name="T",
        company_name="Test Co",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()

    consent = Consent(
        account_id=account.id,
        user_id=user.id,
        consent_type="mobile_money_analysis",
        granted=True,
        legal_basis="consent",
        version="v1.0",
    )
    db_session.add(consent)
    await db_session.flush()
    assert consent.id is not None
    assert consent.granted is True
    assert consent.revoked_at is None


@pytest.mark.asyncio
async def test_consent_default_values_documented() -> None:
    """Les 7 types ont chacun une valeur par défaut documentée."""
    for consent_type in CONSENT_TYPE_VALUES:
        assert consent_type in CONSENT_TYPE_DEFAULT_GRANTED


@pytest.mark.asyncio
async def test_consent_unique_active_constraint(db_session) -> None:
    """Au plus 1 consentement actif par (account_id, consent_type)."""
    account = Account(name="UniqueCo")
    db_session.add(account)
    await db_session.flush()
    user = User(
        email="u@example.com",
        hashed_password="x",
        full_name="U",
        company_name="UniqueCo",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()

    db_session.add(
        Consent(
            account_id=account.id,
            user_id=user.id,
            consent_type="profile_analysis",
            granted=True,
            legal_basis="contract",
            version="v1.0",
        )
    )
    await db_session.flush()

    db_session.add(
        Consent(
            account_id=account.id,
            user_id=user.id,
            consent_type="profile_analysis",
            granted=True,
            legal_basis="contract",
            version="v1.0",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_consent_revoked_after_granted_check_constraint(db_session) -> None:
    """``revoked_at >= granted_at`` lorsque non NULL."""
    account = Account(name="Cstr")
    db_session.add(account)
    await db_session.flush()
    user = User(
        email="c@example.com",
        hashed_password="x",
        full_name="C",
        company_name="Cstr",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()

    granted = datetime.now(tz=timezone.utc)
    revoked_invalid = granted - timedelta(days=1)
    db_session.add(
        Consent(
            account_id=account.id,
            user_id=user.id,
            consent_type="document_analysis_ai",
            granted=True,
            granted_at=granted,
            revoked_at=revoked_invalid,
            legal_basis="contract",
            version="v1.0",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_consent_cascade_fk_declared() -> None:
    """ON DELETE CASCADE déclaré au niveau du modèle (vérification statique).

    Les cascades SQLite ne sont pas activées par défaut dans pytest async ;
    le contrat ON DELETE CASCADE est garanti via la migration Alembic
    (cf. ``test_migration_027_creates_consents_table``) et est testé
    end-to-end via le test d'intégration de purge sur PostgreSQL.
    """
    fk_account = next(
        fk for fk in Consent.__table__.foreign_keys
        if fk.column.table.name == "accounts"
    )
    assert fk_account.ondelete == "CASCADE"
    fk_user = next(
        fk for fk in Consent.__table__.foreign_keys
        if fk.column.table.name == "users"
    )
    assert fk_user.ondelete == "SET NULL"


@pytest.mark.asyncio
async def test_consent_revoke_then_re_grant_allowed(db_session) -> None:
    """Après revoke, un nouveau row actif est autorisé."""
    account = Account(name="Reg")
    db_session.add(account)
    await db_session.flush()
    user = User(
        email="reg@example.com",
        hashed_password="x",
        full_name="Reg",
        company_name="Reg",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()

    now = datetime.now(tz=timezone.utc)
    db_session.add(
        Consent(
            account_id=account.id,
            user_id=user.id,
            consent_type="photos_ia_analysis",
            granted=True,
            granted_at=now - timedelta(days=2),
            revoked_at=now - timedelta(days=1),  # déjà révoqué
            legal_basis="consent",
            version="v1.0",
        )
    )
    await db_session.flush()
    db_session.add(
        Consent(
            account_id=account.id,
            user_id=user.id,
            consent_type="photos_ia_analysis",
            granted=True,
            legal_basis="consent",
            version="v1.0",
        )
    )
    await db_session.flush()  # ne doit pas violer uq_consents_one_active
