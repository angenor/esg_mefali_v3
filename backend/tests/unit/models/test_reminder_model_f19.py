"""F19 — Tests unitaires du modèle ``Reminder`` étendu.

Vérifie les nouvelles colonnes ``dedup_key``, ``sent_at``, ``archived``,
``read`` ainsi que la valeur enum ``attestation_renewal``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.action_plan import Reminder, ReminderType
from tests.conftest import make_account, make_unique_email


pytestmark = pytest.mark.unit


async def _make_user(db_session):
    """Helper : crée un User + Account pour les tests."""
    from app.core.security import hash_password
    from app.models.user import User

    account = await make_account(db_session)
    user = User(
        email=make_unique_email(),
        full_name="F19 Test User",
        company_name="F19 Test Corp",
        hashed_password=hash_password("password"),
        account_id=account.id,
        role="PME",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user, account


async def test_reminder_default_archived_false(db_session):
    """archived doit valoir False par défaut."""
    user, account = await _make_user(db_session)
    reminder = Reminder(
        user_id=user.id,
        account_id=account.id,
        type=ReminderType.action_due,
        message="Test reminder",
        scheduled_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(reminder)
    await db_session.flush()
    await db_session.refresh(reminder)
    assert reminder.archived is False


async def test_reminder_default_read_false(db_session):
    """read doit valoir False par défaut."""
    user, account = await _make_user(db_session)
    reminder = Reminder(
        user_id=user.id,
        account_id=account.id,
        type=ReminderType.action_due,
        message="Test reminder",
        scheduled_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(reminder)
    await db_session.flush()
    await db_session.refresh(reminder)
    assert reminder.read is False


async def test_reminder_default_sent_at_null(db_session):
    """sent_at doit être NULL tant que le reminder n'est pas dispatché."""
    user, account = await _make_user(db_session)
    reminder = Reminder(
        user_id=user.id,
        account_id=account.id,
        type=ReminderType.action_due,
        message="Test reminder",
        scheduled_at=datetime.now(timezone.utc),
    )
    db_session.add(reminder)
    await db_session.flush()
    await db_session.refresh(reminder)
    assert reminder.sent_at is None


async def test_reminder_dedup_key_can_be_null(db_session):
    """dedup_key est nullable."""
    user, account = await _make_user(db_session)
    reminder = Reminder(
        user_id=user.id,
        account_id=account.id,
        type=ReminderType.action_due,
        message="Test reminder",
        scheduled_at=datetime.now(timezone.utc),
    )
    db_session.add(reminder)
    await db_session.flush()
    await db_session.refresh(reminder)
    assert reminder.dedup_key is None


async def test_reminder_dedup_key_set(db_session):
    """dedup_key peut être défini."""
    user, account = await _make_user(db_session)
    key = f"{account.id}:fund_deadline:fund-1:2026-06-01:J-30"
    reminder = Reminder(
        user_id=user.id,
        account_id=account.id,
        type=ReminderType.fund_deadline,
        message="Test reminder",
        scheduled_at=datetime.now(timezone.utc),
        dedup_key=key,
    )
    db_session.add(reminder)
    await db_session.flush()
    await db_session.refresh(reminder)
    assert reminder.dedup_key == key


async def test_reminder_attestation_renewal_type_accepted(db_session):
    """ReminderType.attestation_renewal est accepté."""
    user, account = await _make_user(db_session)
    reminder = Reminder(
        user_id=user.id,
        account_id=account.id,
        type=ReminderType.attestation_renewal,
        message="Votre attestation expire dans 30 jours",
        scheduled_at=datetime.now(timezone.utc),
    )
    db_session.add(reminder)
    await db_session.flush()
    await db_session.refresh(reminder)
    assert reminder.type == ReminderType.attestation_renewal


async def test_reminder_dedup_key_unique_constraint(db_session):
    """Index unique partiel sur (account_id, dedup_key) si dedup_key NOT NULL.

    Note : sur SQLite (test backend), l'index unique standard est utilisé,
    qui contraint aussi quand dedup_key=NULL — mais NULL est traité comme
    distinct par SQLite, donc le test passe sur les 2 dialectes.
    """
    user, account = await _make_user(db_session)
    key = f"{account.id}:assessment_renewal:assess-1:J-30"
    r1 = Reminder(
        user_id=user.id,
        account_id=account.id,
        type=ReminderType.assessment_renewal,
        message="R1",
        scheduled_at=datetime.now(timezone.utc),
        dedup_key=key,
    )
    db_session.add(r1)
    await db_session.flush()

    r2 = Reminder(
        user_id=user.id,
        account_id=account.id,
        type=ReminderType.assessment_renewal,
        message="R2",
        scheduled_at=datetime.now(timezone.utc),
        dedup_key=key,
    )
    db_session.add(r2)
    with pytest.raises(Exception):  # IntegrityError
        await db_session.flush()
    await db_session.rollback()


async def test_reminder_dedup_key_null_not_subject_to_unique(db_session):
    """Plusieurs reminders avec dedup_key=NULL ne déclenchent pas la contrainte."""
    user, account = await _make_user(db_session)
    r1 = Reminder(
        user_id=user.id,
        account_id=account.id,
        type=ReminderType.custom,
        message="R1",
        scheduled_at=datetime.now(timezone.utc),
        dedup_key=None,
    )
    r2 = Reminder(
        user_id=user.id,
        account_id=account.id,
        type=ReminderType.custom,
        message="R2",
        scheduled_at=datetime.now(timezone.utc),
        dedup_key=None,
    )
    db_session.add_all([r1, r2])
    await db_session.flush()

    rows = (await db_session.execute(select(Reminder))).scalars().all()
    assert len(rows) >= 2
