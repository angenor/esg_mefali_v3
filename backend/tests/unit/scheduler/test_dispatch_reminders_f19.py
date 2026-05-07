"""F19 — Tests unitaires du job ``dispatch_reminders``.

Patch ``async_session_factory`` pour utiliser la session de test SQLite.
Patch le bus SSE pour vérifier les pushs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.action_plan import Reminder, ReminderType
from tests.conftest import (
    make_account,
    make_unique_email,
    test_session_factory,
)


pytestmark = pytest.mark.unit


async def _make_user(db_session):
    """Crée un User + Account de test."""
    from app.core.security import hash_password
    from app.models.user import User

    account = await make_account(db_session)
    user = User(
        email=make_unique_email(),
        full_name="F19 Disp",
        company_name="F19 Disp Corp",
        hashed_password=hash_password("password"),
        account_id=account.id,
        role="PME",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user, account


async def _seed_reminder(
    db_session,
    user,
    account,
    *,
    scheduled_at,
    sent: bool = False,
    archived: bool = False,
    type_: ReminderType = ReminderType.action_due,
    message: str = "Test",
) -> Reminder:
    """Crée un Reminder de test."""
    reminder = Reminder(
        user_id=user.id,
        account_id=account.id,
        type=type_,
        message=message,
        scheduled_at=scheduled_at,
        sent=sent,
        archived=archived,
    )
    db_session.add(reminder)
    await db_session.flush()
    return reminder


async def test_dispatch_pending_reminder_marks_sent(db_session):
    """1 reminder pending → sent=True, sent_at non-null."""
    user, account = await _make_user(db_session)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    reminder = await _seed_reminder(db_session, user, account, scheduled_at=past)
    await db_session.commit()
    reminder_id = reminder.id

    # Patch async_session_factory pour pointer sur le test sessionmaker.
    with patch(
        "app.scheduler.jobs.dispatch_reminders.async_session_factory",
        test_session_factory,
    ):
        with patch(
            "app.scheduler.jobs.dispatch_reminders.bus.notify_user",
            new=AsyncMock(return_value=1),
        ) as mock_notify:
            from app.scheduler.jobs.dispatch_reminders import run

            result = await run()

    assert result["dispatched_count"] == 1
    assert mock_notify.call_count == 1

    # Vérifier l'état BDD.
    async with test_session_factory() as session:
        row = (await session.execute(select(Reminder).where(Reminder.id == reminder_id))).scalar_one()
        assert row.sent is True
        assert row.sent_at is not None


async def test_dispatch_ignores_already_sent(db_session):
    """Reminder déjà sent=True doit être ignoré."""
    user, account = await _make_user(db_session)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    await _seed_reminder(
        db_session, user, account, scheduled_at=past, sent=True
    )
    await db_session.commit()

    with patch(
        "app.scheduler.jobs.dispatch_reminders.async_session_factory",
        test_session_factory,
    ):
        with patch(
            "app.scheduler.jobs.dispatch_reminders.bus.notify_user",
            new=AsyncMock(return_value=0),
        ) as mock_notify:
            from app.scheduler.jobs.dispatch_reminders import run

            result = await run()

    assert result["dispatched_count"] == 0
    assert mock_notify.call_count == 0


async def test_dispatch_ignores_archived(db_session):
    """Reminder archived=True doit être ignoré."""
    user, account = await _make_user(db_session)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    await _seed_reminder(
        db_session, user, account, scheduled_at=past, archived=True
    )
    await db_session.commit()

    with patch(
        "app.scheduler.jobs.dispatch_reminders.async_session_factory",
        test_session_factory,
    ):
        with patch(
            "app.scheduler.jobs.dispatch_reminders.bus.notify_user",
            new=AsyncMock(return_value=0),
        ):
            from app.scheduler.jobs.dispatch_reminders import run

            result = await run()

    assert result["dispatched_count"] == 0


async def test_dispatch_ignores_future_reminder(db_session):
    """Reminder dans le futur (scheduled_at > now) doit être ignoré."""
    user, account = await _make_user(db_session)
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    await _seed_reminder(db_session, user, account, scheduled_at=future)
    await db_session.commit()

    with patch(
        "app.scheduler.jobs.dispatch_reminders.async_session_factory",
        test_session_factory,
    ):
        with patch(
            "app.scheduler.jobs.dispatch_reminders.bus.notify_user",
            new=AsyncMock(return_value=0),
        ):
            from app.scheduler.jobs.dispatch_reminders import run

            result = await run()

    assert result["dispatched_count"] == 0


async def test_dispatch_pushes_sse_with_payload(db_session):
    """Le bus SSE est appelé avec un payload conforme au schema."""
    user, account = await _make_user(db_session)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    await _seed_reminder(
        db_session,
        user,
        account,
        scheduled_at=past,
        type_=ReminderType.fund_deadline,
        message="Deadline J-30",
    )
    await db_session.commit()

    with patch(
        "app.scheduler.jobs.dispatch_reminders.async_session_factory",
        test_session_factory,
    ):
        with patch(
            "app.scheduler.jobs.dispatch_reminders.bus.notify_user",
            new=AsyncMock(return_value=1),
        ) as mock_notify:
            from app.scheduler.jobs.dispatch_reminders import run

            await run()

    assert mock_notify.call_count == 1
    args, _kwargs = mock_notify.call_args
    # Args : (account_id, event_type, payload)
    assert args[1] == "reminder_due"
    payload = args[2]
    assert "id" in payload
    assert payload["type"] == "fund_deadline"
    assert payload["message"] == "Deadline J-30"
    assert "metadata" in payload
    assert "action_url" in payload["metadata"]


async def test_dispatch_batch_limit_respected(db_session):
    """batch_limit=2 → seulement 2 dispatchés malgré 5 pending."""
    user, account = await _make_user(db_session)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    for i in range(5):
        await _seed_reminder(
            db_session,
            user,
            account,
            scheduled_at=past - timedelta(seconds=i),
            message=f"R{i}",
        )
    await db_session.commit()

    with patch(
        "app.scheduler.jobs.dispatch_reminders.async_session_factory",
        test_session_factory,
    ):
        with patch(
            "app.scheduler.jobs.dispatch_reminders.bus.notify_user",
            new=AsyncMock(return_value=1),
        ):
            from app.scheduler.jobs.dispatch_reminders import run

            result = await run(batch_limit=2)

    assert result["dispatched_count"] == 2


async def test_dispatch_audit_log_created(db_session):
    """Une entrée audit_log est insérée pour chaque dispatch."""
    from app.models.audit_log import AuditLog

    user, account = await _make_user(db_session)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    await _seed_reminder(db_session, user, account, scheduled_at=past)
    await db_session.commit()

    with patch(
        "app.scheduler.jobs.dispatch_reminders.async_session_factory",
        test_session_factory,
    ):
        with patch(
            "app.scheduler.jobs.dispatch_reminders.bus.notify_user",
            new=AsyncMock(return_value=1),
        ):
            from app.scheduler.jobs.dispatch_reminders import run

            await run()

    async with test_session_factory() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(AuditLog.entity_type == "reminder")
            )
        ).scalars().all()
        assert len(rows) >= 1
        # Au moins une trace doit avoir new_value.event = reminder_dispatched.
        events = [r.new_value.get("event") for r in rows if r.new_value]
        assert "reminder_dispatched" in events
