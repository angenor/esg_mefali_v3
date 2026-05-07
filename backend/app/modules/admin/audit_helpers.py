"""Helpers d'audit log spécifiques au back-office admin (F09).

Wrappers minces autour de :class:`AuditLog` pour standardiser :
- la dédup quotidienne du ``view_admin`` (1 entrée par admin / par account
  par jour),
- l'écriture d'événements admin métier (publish, verify, reset_password,
  toggle_active, source_revoked, attestation_revoked) via
  ``AuditAction.update`` + ``actor_metadata.admin_action``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, time, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_context import source_of_change_scope
from app.core.constants import AuditAction, AuditSourceOfChange
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def log_admin_action(
    db: AsyncSession,
    *,
    admin_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    metadata: dict[str, Any] | None = None,
    account_id: uuid.UUID | None = None,
) -> AuditLog:
    """Logger une action admin métier dans :class:`AuditLog`.

    Args:
        admin_id : UUID de l'administrateur qui agit.
        action : libellé fonctionnel (ex ``"source_verified"``,
            ``"fund_published"``, ``"reset_password_initiated"``).
            Stocké dans ``actor_metadata.admin_action``.
        entity_type : type d'entité ciblée (ex ``"source"``, ``"fund"``,
            ``"user"``).
        entity_id : UUID de l'entité ciblée.
        metadata : payload optionnel additionnel.
        account_id : compte cible si applicable (sinon None).

    L'``AuditAction`` PG est ``update`` (action métier) et la
    ``source_of_change`` est forcée à ``admin``.
    """
    payload: dict[str, Any] = {"admin_action": action}
    if metadata:
        payload.update(metadata)

    log = AuditLog(
        user_id=admin_id,
        account_id=account_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=AuditAction.update,
        source_of_change=AuditSourceOfChange.admin,
        actor_metadata=payload,
    )
    with source_of_change_scope("admin"):
        db.add(log)
        await db.flush()
    return log


async def log_view_admin_dedup(
    db: AsyncSession,
    *,
    admin_id: uuid.UUID,
    account_id: uuid.UUID,
) -> AuditLog | None:
    """Logger un ``view_admin`` avec dédup quotidienne.

    Cherche un :class:`AuditLog` existant avec ``user_id=admin_id``,
    ``entity_id=account_id``, ``action=view_admin``, ``timestamp >=
    today_start_utc``. Si trouvé → skip et retourne ``None``. Sinon →
    insère une nouvelle ligne et la retourne.
    """
    today_start = datetime.combine(
        datetime.now(timezone.utc).date(),
        time.min,
        tzinfo=timezone.utc,
    )

    existing = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.user_id == admin_id,
            AuditLog.entity_id == account_id,
            AuditLog.action == AuditAction.view_admin,
            AuditLog.timestamp >= today_start,
        )
        .limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return None

    log = AuditLog(
        user_id=admin_id,
        account_id=account_id,
        entity_type="account",
        entity_id=account_id,
        action=AuditAction.view_admin,
        source_of_change=AuditSourceOfChange.admin,
        actor_metadata={"dedup_strategy": "daily"},
    )
    with source_of_change_scope("admin"):
        db.add(log)
        await db.flush()
    return log
