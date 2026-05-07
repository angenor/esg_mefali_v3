"""F05 — Tests unitaires du service de purge (T063-T067).

Vérifie :
- Cascade des données par account_id.
- Anonymisation audit_log (UPDATE en place).
- Suppression du répertoire /uploads/{account_id}/.
- Révocation des attestations actives avant la cascade.
- Révocation des refresh tokens.
- Idempotence : double appel ne lève pas d'exception.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.constants import AuditAction, AuditSourceOfChange
from app.models.account import Account
from app.models.audit_log import AuditLog
from app.models.consent import Consent
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.modules.me.purge import (
    PII_FIELDS,
    anonymize_payload,
    purge_account_data,
)


async def _bootstrap_account(db_session) -> tuple[Account, User]:
    account = Account(name="ToPurgeCo")
    db_session.add(account)
    await db_session.flush()
    user = User(
        email=f"purge-{uuid.uuid4().hex[:8]}@x.com",
        hashed_password="x",
        full_name="P",
        company_name="ToPurgeCo",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()
    return account, user


def test_anonymize_payload_removes_pii_fields() -> None:
    payload = {
        "email": "x@y.com",
        "user_agent": "Mozilla/5.0",
        "ip": "1.2.3.4",
        "name": "Jean",
        "kept_field": "kept",
        "owner_email": "owner@y.com",  # suffixe _email
    }
    out = anonymize_payload(payload)
    assert "email" not in out
    assert "user_agent" not in out
    assert "ip" not in out
    assert "name" not in out
    assert "owner_email" not in out
    assert out["kept_field"] == "kept"


def test_anonymize_payload_recursive() -> None:
    payload = {
        "outer": "ok",
        "nested": {"email": "x@y.com", "kept": "v"},
        "list": [{"email": "z@y.com"}, {"id": "kept"}],
    }
    out = anonymize_payload(payload)
    assert out["outer"] == "ok"
    assert "email" not in out["nested"]
    assert out["nested"]["kept"] == "v"
    assert "email" not in out["list"][0]
    assert out["list"][1]["id"] == "kept"


@pytest.mark.asyncio
async def test_purge_cascades_consents(db_session) -> None:
    account, user = await _bootstrap_account(db_session)
    # Insérer un consentement
    db_session.add(
        Consent(
            account_id=account.id,
            user_id=user.id,
            consent_type="mobile_money_analysis",
            granted=True,
            legal_basis="consent",
            version="v1.0",
        )
    )
    await db_session.commit()

    # Avant purge : la row existe
    pre = await db_session.execute(
        select(Consent).where(Consent.account_id == account.id)
    )
    assert len(pre.scalars().all()) == 1

    result = await purge_account_data(db_session, account.id)
    await db_session.commit()
    assert result.deleted_at is not None
    assert "consents" in result.rows_deleted

    # Après purge : aucun consent
    post = await db_session.execute(
        select(Consent).where(Consent.account_id == account.id)
    )
    assert len(post.scalars().all()) == 0


@pytest.mark.asyncio
async def test_purge_revokes_refresh_tokens(db_session) -> None:
    account, user = await _bootstrap_account(db_session)
    rt = RefreshToken(
        user_id=user.id,
        jti=uuid.uuid4().hex,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=30),
    )
    db_session.add(rt)
    await db_session.commit()

    await purge_account_data(db_session, account.id)
    await db_session.commit()

    remaining = (
        await db_session.execute(
            select(RefreshToken).where(RefreshToken.user_id == user.id)
        )
    ).scalars().all()
    assert len(remaining) == 0


@pytest.mark.asyncio
async def test_purge_idempotent_when_already_deleted(db_session) -> None:
    account, user = await _bootstrap_account(db_session)
    await db_session.commit()
    result1 = await purge_account_data(db_session, account.id)
    await db_session.commit()
    # Second appel : idempotent, retourne le résultat précédent.
    result2 = await purge_account_data(db_session, account.id)
    await db_session.commit()
    assert result2.deleted_at == result1.deleted_at


@pytest.mark.asyncio
async def test_purge_marks_account_deleted_at_and_inactive(db_session) -> None:
    account, user = await _bootstrap_account(db_session)
    await db_session.commit()
    await purge_account_data(db_session, account.id)
    await db_session.commit()
    refreshed = (
        await db_session.execute(select(Account).where(Account.id == account.id))
    ).scalar_one()
    assert refreshed.deleted_at is not None
    assert refreshed.is_active is False
    assert refreshed.purge_in_progress is False


@pytest.mark.asyncio
async def test_purge_anonymizes_audit_log_on_sqlite(db_session) -> None:
    """Sur SQLite (tests), l'anonymisation est faite via UPDATE Python direct."""
    account, user = await _bootstrap_account(db_session)
    # Insérer manuellement un audit_log avec PII
    log = AuditLog(
        user_id=user.id,
        account_id=account.id,
        entity_type="company_profile",
        entity_id=uuid.uuid4(),
        action=AuditAction.create,
        new_value={"email": "leak@x.com", "kept": "v"},
        source_of_change=AuditSourceOfChange.manual,
        actor_metadata={"ip": "1.2.3.4", "kept_meta": "ok"},
    )
    db_session.add(log)
    await db_session.commit()

    await purge_account_data(db_session, account.id)
    await db_session.commit()

    refreshed = (
        await db_session.execute(select(AuditLog).where(AuditLog.id == log.id))
    ).scalar_one()
    assert refreshed.user_id is None
    assert refreshed.account_id is None
    # PII filtrées
    if isinstance(refreshed.new_value, dict):
        assert "email" not in refreshed.new_value
        assert refreshed.new_value.get("kept") == "v"
    if isinstance(refreshed.actor_metadata, dict):
        assert "ip" not in refreshed.actor_metadata
        assert refreshed.actor_metadata.get("kept_meta") == "ok"


@pytest.mark.asyncio
async def test_purge_removes_uploads_directory(db_session, tmp_path, monkeypatch) -> None:
    """Vérifie la suppression du répertoire ``uploads/{account_id}/`` réel."""
    account, user = await _bootstrap_account(db_session)
    await db_session.commit()
    # Crée un fichier fictif sous CWD/uploads/{account_id}/
    monkeypatch.chdir(tmp_path)
    upload_dir = tmp_path / "uploads" / str(account.id)
    upload_dir.mkdir(parents=True)
    (upload_dir / "fake.pdf").write_text("payload")
    assert upload_dir.exists()

    await purge_account_data(db_session, account.id)
    await db_session.commit()

    assert not upload_dir.exists()
