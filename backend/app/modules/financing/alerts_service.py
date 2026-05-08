"""Service alertes nouvelles offres compatibles (F14).

Cron `notify_new_offer_matches` :
- Pour chaque souscription active, recalcule les matches.
- Si nouveau match (last_notified_at IS NULL) ET global_score >=
  subscription.min_global_score → crée un Reminder F19 ``new_offer_alert``.
- Met à jour ``OfferMatch.last_notified_at`` (idempotence).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action_plan import Reminder, ReminderType
from app.models.match_alert_subscription import MatchAlertSubscription
from app.models.offer_match import OfferMatch

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NotificationResult:
    """Résultat d'une exécution du cron alertes."""

    subscriptions_processed: int
    reminders_created: int
    matches_marked: int


async def notify_new_offer_matches(db: AsyncSession) -> NotificationResult:
    """Cron idempotent : crée des Reminder pour les nouveaux matches.

    Pour chaque ``MatchAlertSubscription`` active, parcourt les
    ``OfferMatch`` du projet où ``last_notified_at IS NULL`` ET
    ``global_score >= min_global_score`` ET ``expires_at > now()``,
    crée un Reminder ``new_offer_alert`` et met à jour ``last_notified_at``.
    """
    now = datetime.now(timezone.utc)
    subs = (
        await db.execute(
            select(MatchAlertSubscription).where(
                MatchAlertSubscription.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()

    reminders_created = 0
    matches_marked = 0

    from app.models.user import User

    for sub in subs:
        eligible_q = await db.execute(
            select(OfferMatch).where(
                OfferMatch.project_id == sub.project_id,
                OfferMatch.account_id == sub.account_id,
                OfferMatch.last_notified_at.is_(None),
                OfferMatch.global_score >= sub.min_global_score,
                OfferMatch.expires_at > now,
            )
        )
        eligible = eligible_q.scalars().all()

        # Résoudre un user_id du compte (premier user)
        user_q = await db.execute(
            select(User.id).where(User.account_id == sub.account_id).limit(1)
        )
        user_id = user_q.scalar_one_or_none()
        if user_id is None:
            logger.warning(
                "notify_new_offer_matches: aucun user pour account=%s, skip.",
                sub.account_id,
            )
            continue

        for match in eligible:
            try:
                payload: dict[str, Any] = {
                    "project_id": str(match.project_id),
                    "offer_id": str(match.offer_id),
                    "global_score": match.global_score,
                    "fund_score": match.fund_score,
                    "intermediary_score": match.intermediary_score,
                    "bottleneck": match.bottleneck,
                }
                _create_new_offer_alert_reminder(
                    db, sub=sub, payload=payload, user_id=user_id,
                )
                reminders_created += 1
                match.last_notified_at = now
                matches_marked += 1
            except Exception:  # noqa: BLE001
                logger.exception(
                    "notify_new_offer_matches: échec création Reminder "
                    "(project=%s, offer=%s)",
                    match.project_id, match.offer_id,
                )

    await db.flush()
    return NotificationResult(
        subscriptions_processed=len(subs),
        reminders_created=reminders_created,
        matches_marked=matches_marked,
    )


def _create_new_offer_alert_reminder(
    db: AsyncSession,
    *,
    sub: MatchAlertSubscription,
    payload: dict[str, Any],
    user_id: uuid.UUID | None = None,
) -> Reminder:
    """Crée un Reminder ``new_offer_alert`` pour la souscription donnée.

    Si ``user_id`` n'est pas fourni, on tente de le résoudre via le compte.
    Le type ``new_offer_alert`` est ajouté à l'enum reminder_type_enum par
    la migration 036.
    """
    try:
        kind = ReminderType.new_offer_alert
    except AttributeError:
        kind = ReminderType.custom

    if user_id is None:
        raise ValueError(
            "Impossible de résoudre user_id pour Reminder F14"
        )

    reminder = Reminder(
        user_id=user_id,
        account_id=sub.account_id,
        type=kind,
        message=(
            f"Nouvelle offre compatible (score {payload['global_score']}) "
            "disponible pour votre projet."
        ),
        scheduled_at=datetime.now(timezone.utc),
    )
    db.add(reminder)
    return reminder
