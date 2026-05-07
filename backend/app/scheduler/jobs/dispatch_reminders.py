"""F19 — Job ``dispatch_reminders`` : push des rappels dus via SSE.

Lit les ``Reminder`` éligibles (``scheduled_at <= now() AND sent=FALSE AND
archived=FALSE``), les marque ``sent=True, sent_at=now()``, push un évènement
``reminder_due`` sur le bus SSE pour le ``account_id`` ciblé, et trace dans
``audit_log`` (F03).

Concurrence : ``FOR UPDATE SKIP LOCKED`` sur PostgreSQL pour éviter le double
dispatch en cas de multi-process. Sur SQLite (tests), l'option est ignorée
gracieusement.

Schedule : toutes les 5 minutes (cf. ``register_jobs``).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction, AuditSourceOfChange
from app.core.database import async_session_factory
from app.models.action_plan import Reminder
from app.models.audit_log import AuditLog
from app.services.notifications.reminder_notifier import build_reminder_payload
from app.services.notifications.sse_bus import bus

logger = logging.getLogger(__name__)


async def _dispatch_one(
    db: AsyncSession,
    reminder: Reminder,
    *,
    now: datetime,
) -> bool:
    """Dispatch un reminder : marque sent + push SSE + audit log.

    Retourne ``True`` si le push SSE a effectivement réussi (subscriber actif),
    ``False`` sinon (mais le reminder est quand même marqué sent — l'UI le
    récupère via polling).
    """
    # Marque sent=True via UPDATE direct (déjà locké par FOR UPDATE SKIP LOCKED).
    await db.execute(
        update(Reminder)
        .where(Reminder.id == reminder.id)
        .values(sent=True, sent_at=now)
    )

    # Refresh pour avoir l'état post-update sur l'objet.
    reminder.sent = True
    reminder.sent_at = now

    # Push SSE.
    payload = build_reminder_payload(reminder)
    delivered = 0
    if reminder.account_id is not None:
        delivered = await bus.notify_user(
            reminder.account_id, "reminder_due", payload
        )

    # Audit log F03.
    audit = AuditLog(
        user_id=reminder.user_id,
        account_id=reminder.account_id,
        entity_type="reminder",
        entity_id=reminder.id,
        action=AuditAction.update,
        field="dispatched",
        new_value={
            "reminder_id": str(reminder.id),
            "type": reminder.type.value,
            "delivered_subscribers": delivered,
            "event": "reminder_dispatched",
        },
        source_of_change=AuditSourceOfChange.import_,
    )
    db.add(audit)

    return delivered > 0


async def run(*, batch_limit: int | None = None) -> dict[str, int | list]:
    """Job principal : dispatch tous les reminders dus dans la limite ``batch_limit``.

    Retourne ``{"dispatched_count": N, "errors": [...], "duration_ms": ...}``.
    """
    from app.core.config import settings

    if batch_limit is None:
        batch_limit = settings.dispatch_batch_limit

    started = time.monotonic()
    now = datetime.now(timezone.utc)
    dispatched_count = 0
    errors: list[dict] = []

    async with async_session_factory() as db:
        try:
            # Sélection des reminders éligibles avec verrouillage.
            stmt = (
                select(Reminder)
                .where(
                    Reminder.sent == False,  # noqa: E712
                    Reminder.archived == False,  # noqa: E712
                    Reminder.scheduled_at <= now,
                )
                .order_by(Reminder.scheduled_at.asc())
                .limit(batch_limit)
            )

            # FOR UPDATE SKIP LOCKED : PG only — gracieux sur SQLite (ignore).
            try:
                stmt = stmt.with_for_update(skip_locked=True)
            except Exception:
                pass

            result = await db.execute(stmt)
            reminders = list(result.scalars().all())

            for reminder in reminders:
                try:
                    await _dispatch_one(db, reminder, now=now)
                    dispatched_count += 1
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "scheduler.dispatch_reminders | reminder_id=%s error=%s",
                        reminder.id,
                        exc,
                    )
                    errors.append({"reminder_id": str(reminder.id), "error": str(exc)})

            await db.commit()
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            logger.exception("scheduler.dispatch_reminders | global error=%s", exc)
            errors.append({"reminder_id": None, "error": f"global: {exc}"})

    duration_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        "scheduler.dispatch_reminders | dispatched=%d errors=%d duration_ms=%d",
        dispatched_count,
        len(errors),
        duration_ms,
    )
    return {
        "dispatched_count": dispatched_count,
        "errors": errors,
        "duration_ms": duration_ms,
    }
