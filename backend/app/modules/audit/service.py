"""Service audit (F03) : query helpers + record_admin_view + export.

L'idempotence par requête de :meth:`AuditService.record_admin_view` est
assurée par un cache ``request.state.audit_view_recorded: dict[UUID, bool]``
initialisé à la demande.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from fastapi import Request
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_context import source_of_change_scope
from app.core.constants import AuditAction, AuditSourceOfChange
from app.models.audit_log import AuditLog
from app.models.user import User
from app.modules.audit.schemas import AuditEvent, AuditFilters

logger = logging.getLogger(__name__)


def _audit_log_to_event(row: AuditLog, user_email: str | None) -> AuditEvent:
    """Convertit une ligne ORM en :class:`AuditEvent` (Pydantic)."""
    # Normalise l'enum stocké (PG ENUM) ou string brute (SQLite).
    action_value = row.action.value if isinstance(row.action, AuditAction) else str(row.action)
    source_value = (
        row.source_of_change.value
        if isinstance(row.source_of_change, AuditSourceOfChange)
        else str(row.source_of_change)
    )
    return AuditEvent(
        id=row.id,
        timestamp=row.timestamp,
        user_id=row.user_id,
        user_email=user_email,
        account_id=row.account_id,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        action=action_value,  # type: ignore[arg-type]
        field=row.field,
        old_value=row.old_value,
        new_value=row.new_value,
        source_of_change=source_value,  # type: ignore[arg-type]
        actor_metadata=row.actor_metadata,
    )


class AuditService:
    """Service métier audit log (F03)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_admin_view(
        self,
        admin_user: User,
        target_account_id: uuid.UUID,
        request: Request,
    ) -> AuditLog | None:
        """Trace un événement ``view_admin`` (idempotent par requête).

        Retourne ``None`` si la trace a déjà été insérée pour cette requête
        (cache request.state.audit_view_recorded), sinon retourne la nouvelle
        ligne.

        Source forcée à ``admin`` via :func:`source_of_change_scope` même si
        le middleware n'est pas actif (sécurité défensive).
        """
        # Init cache de requête
        if not hasattr(request.state, "audit_view_recorded"):
            request.state.audit_view_recorded = {}

        if request.state.audit_view_recorded.get(target_account_id):
            return None

        request.state.audit_view_recorded[target_account_id] = True

        # Récupérer ip + user_agent
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        request_id = (
            getattr(request.state, "request_id", None)
            or request.headers.get("x-request-id")
        )

        actor_metadata: dict[str, Any] = {
            "endpoint": str(request.url.path),
            "request_id": request_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        log = AuditLog(
            user_id=admin_user.id,
            account_id=target_account_id,
            entity_type="account",
            entity_id=target_account_id,
            action=AuditAction.view_admin,
            source_of_change=AuditSourceOfChange.admin,
            actor_metadata=actor_metadata,
        )
        # Force la source à admin même si la ContextVar n'est pas SET admin.
        with source_of_change_scope("admin"):
            self.db.add(log)
            await self.db.flush()
        return log

    async def list_for_account(
        self,
        account_id: uuid.UUID,
        filters: AuditFilters,
    ) -> tuple[list[AuditEvent], int]:
        """Retourne (events, total) pour un compte donné, avec filtres + pagination."""
        base_query = select(AuditLog).where(AuditLog.account_id == account_id)
        base_query = self._apply_filters(base_query, filters)

        # Total
        count_query = select(func.count()).select_from(
            self._apply_filters(
                select(AuditLog).where(AuditLog.account_id == account_id),
                filters,
            ).subquery()
        )
        total = (await self.db.execute(count_query)).scalar_one() or 0

        # Tri + pagination
        order_col = AuditLog.timestamp
        if filters.order == "asc":
            base_query = base_query.order_by(order_col.asc(), AuditLog.id.asc())
        else:
            base_query = base_query.order_by(desc(order_col), desc(AuditLog.id))

        offset = (filters.page - 1) * filters.limit
        base_query = base_query.offset(offset).limit(filters.limit)

        result = await self.db.execute(base_query)
        rows = list(result.scalars().all())
        events = await self._enrich_with_emails(rows)
        return events, int(total)

    async def list_global(
        self, filters: AuditFilters
    ) -> tuple[list[AuditEvent], int]:
        """Retourne (events, total) global (admin only, RLS bypass via admin_full_access)."""
        base_query = select(AuditLog)
        base_query = self._apply_filters(base_query, filters)
        if filters.account_id is not None:
            base_query = base_query.where(AuditLog.account_id == filters.account_id)
        if filters.user_id is not None:
            base_query = base_query.where(AuditLog.user_id == filters.user_id)

        # Total
        count_q = select(func.count()).select_from(base_query.subquery())
        total = (await self.db.execute(count_q)).scalar_one() or 0

        order_col = AuditLog.timestamp
        if filters.order == "asc":
            base_query = base_query.order_by(order_col.asc(), AuditLog.id.asc())
        else:
            base_query = base_query.order_by(desc(order_col), desc(AuditLog.id))

        offset = (filters.page - 1) * filters.limit
        base_query = base_query.offset(offset).limit(filters.limit)

        result = await self.db.execute(base_query)
        rows = list(result.scalars().all())
        events = await self._enrich_with_emails(rows)
        return events, int(total)

    async def stream_for_account(
        self,
        account_id: uuid.UUID,
        filters: AuditFilters,
    ) -> AsyncIterator[AuditEvent]:
        """Streaming des événements (export sans pagination)."""
        # Pour streaming, on utilise une requête sans LIMIT/OFFSET
        base_query = select(AuditLog).where(AuditLog.account_id == account_id)
        base_query = self._apply_filters(base_query, filters)
        order_col = AuditLog.timestamp
        if filters.order == "asc":
            base_query = base_query.order_by(order_col.asc(), AuditLog.id.asc())
        else:
            base_query = base_query.order_by(desc(order_col), desc(AuditLog.id))

        # On collecte les user_emails en une seule requête en bulk pour
        # éviter le N+1.
        result = await self.db.execute(base_query)
        rows = list(result.scalars().all())
        emails_by_uid = await self._fetch_emails([r.user_id for r in rows])
        for row in rows:
            yield _audit_log_to_event(row, emails_by_uid.get(row.user_id))

    # --- Helpers internes -------------------------------------------------

    def _apply_filters(self, query, filters: AuditFilters):
        if filters.entity_type is not None:
            query = query.where(AuditLog.entity_type == filters.entity_type)
        if filters.entity_id is not None:
            query = query.where(AuditLog.entity_id == filters.entity_id)
        if filters.action is not None:
            query = query.where(AuditLog.action == filters.action)
        if filters.source_of_change is not None:
            query = query.where(AuditLog.source_of_change == filters.source_of_change)
        if filters.since is not None:
            query = query.where(AuditLog.timestamp >= filters.since)
        if filters.until is not None:
            query = query.where(AuditLog.timestamp <= filters.until)
        return query

    async def _enrich_with_emails(self, rows: list[AuditLog]) -> list[AuditEvent]:
        if not rows:
            return []
        emails = await self._fetch_emails([r.user_id for r in rows])
        return [_audit_log_to_event(r, emails.get(r.user_id)) for r in rows]

    async def _fetch_emails(
        self, user_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, str | None]:
        if not user_ids:
            return {}
        # uniques
        unique = list({uid for uid in user_ids if uid is not None})
        if not unique:
            return {}
        result = await self.db.execute(
            select(User.id, User.email).where(User.id.in_(unique))
        )
        return {row[0]: row[1] for row in result.fetchall()}
