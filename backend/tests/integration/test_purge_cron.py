"""F05 — Tests d'intégration du cron de purge (T068, T069).

Vérifie le flow end-to-end : programmer suppression → avancer date →
purge effective → audit_log anonymisé + ``accounts.deleted_at`` positionné.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.models.account import Account
from app.models.audit_log import AuditLog
from app.models.user import User
from app.modules.me.purge import purge_account_data


async def _bootstrap(db_session) -> tuple[User, Account]:
    account = Account(name="CronCo")
    db_session.add(account)
    await db_session.flush()
    user = User(
        email=f"cron-{uuid.uuid4().hex[:8]}@x.com",
        hashed_password=hash_password("p"),
        full_name="C",
        company_name="CronCo",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user, account


def _bearer(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


@pytest.mark.asyncio
async def test_full_cron_flow(client, db_session) -> None:
    """Programmer suppression → avancer date → purge → vérifier purge effective."""
    user, account = await _bootstrap(db_session)
    # 1. Programmer la suppression via l'API
    res = await client.post(
        "/api/me/account/schedule-deletion",
        headers=_bearer(user),
        json={"password": "p", "confirmation_text": "SUPPRIMER"},
    )
    assert res.status_code == 200
    # 2. Avancer la date
    refreshed = (
        await db_session.execute(select(Account).where(Account.id == account.id))
    ).scalar_one()
    refreshed.deletion_scheduled_at = datetime.now(tz=timezone.utc) - timedelta(
        hours=1
    )
    await db_session.commit()
    # 3. Exécuter la purge
    result = await purge_account_data(db_session, account.id)
    await db_session.commit()
    assert result.deleted_at is not None

    # 4. Vérifier audit_log anonymisé : aucune row avec account_id == account.id
    logs_with_account = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.account_id == account.id)
        )
    ).scalars().all()
    assert len(logs_with_account) == 0

    # 5. accounts.deleted_at est positionné
    refreshed = (
        await db_session.execute(select(Account).where(Account.id == account.id))
    ).scalar_one()
    assert refreshed.deleted_at is not None


@pytest.mark.asyncio
async def test_purge_idempotent_double_run(client, db_session) -> None:
    """Lancer la purge deux fois ne lève pas d'erreur (idempotent)."""
    user, account = await _bootstrap(db_session)
    res1 = await purge_account_data(db_session, account.id)
    await db_session.commit()
    res2 = await purge_account_data(db_session, account.id)
    await db_session.commit()
    assert res1.deleted_at == res2.deleted_at
