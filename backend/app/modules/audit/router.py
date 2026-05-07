"""Router FastAPI pour l'audit log (F03).

Expose 4 endpoints :

- ``GET /api/audit/me`` (PME) : événements du compte courant.
- ``GET /api/audit/me/export`` (PME) : export CSV/JSON du compte courant.
- ``GET /api/admin/audit/{account_id}`` (Admin) : événements d'un compte
  PME donné. **Effet de bord** : insère un ``view_admin`` côté PME.
- ``GET /api/admin/audit`` (Admin) : log global filtrable.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_user
from app.core.constants import AuditAction, AuditSourceOfChange
from app.core.database import get_db
from app.models.account import Account
from app.models.user import User
from app.modules.audit.csv_writer import stream_csv, stream_json
from app.modules.audit.schemas import AuditEventList, AuditFilters
from app.modules.audit.service import AuditService

router = APIRouter()
admin_router = APIRouter()


def _filters_from_query(
    entity_type: str | None,
    entity_id: uuid.UUID | None,
    action: AuditAction | None,
    source_of_change: AuditSourceOfChange | None,
    since: datetime | None,
    until: datetime | None,
    page: int,
    limit: int,
    order: Literal["asc", "desc"],
    account_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> AuditFilters:
    return AuditFilters(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        source_of_change=source_of_change,
        since=since,
        until=until,
        page=page,
        limit=limit,
        order=order,
        account_id=account_id,
        user_id=user_id,
    )


@router.get("/me", response_model=AuditEventList)
async def list_me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    action: AuditAction | None = None,
    source_of_change: AuditSourceOfChange | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    order: Literal["asc", "desc"] = "desc",
) -> AuditEventList:
    """Retourne les événements d'audit du compte de l'utilisateur courant."""
    if current_user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cet endpoint requiert un compte PME (les Admin n'ont pas d'audit propre).",
        )
    filters = _filters_from_query(
        entity_type, entity_id, action, source_of_change,
        since, until, page, limit, order,
    )
    service = AuditService(db)
    events, total = await service.list_for_account(current_user.account_id, filters)
    return AuditEventList(events=events, total=total, page=page, limit=limit)


@router.get("/me/export")
async def export_me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    format: Literal["csv", "json"] = "csv",
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    action: AuditAction | None = None,
    source_of_change: AuditSourceOfChange | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    order: Literal["asc", "desc"] = "desc",
) -> StreamingResponse:
    """Exporte le log filtré au format CSV (UTF-8 BOM) ou JSON."""
    if current_user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Export PME : compte requis.",
        )
    filters = _filters_from_query(
        entity_type, entity_id, action, source_of_change,
        since, until, page=1, limit=200, order=order,
    )
    service = AuditService(db)
    today = date.today().strftime("%Y%m%d")
    suffix = "csv" if format == "csv" else "json"
    filename = f"audit-log-{current_user.account_id}-{today}.{suffix}"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
    }

    events_iter = service.stream_for_account(current_user.account_id, filters)
    if format == "csv":
        return StreamingResponse(
            stream_csv(events_iter),
            media_type="text/csv; charset=utf-8",
            headers=headers,
        )
    return StreamingResponse(
        stream_json(events_iter),
        media_type="application/json",
        headers=headers,
    )


@admin_router.get("/{account_id}", response_model=AuditEventList)
async def list_for_account_admin(
    account_id: uuid.UUID,
    request: Request,
    current_admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    action: AuditAction | None = None,
    source_of_change: AuditSourceOfChange | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    order: Literal["asc", "desc"] = "desc",
) -> AuditEventList:
    """Admin : log d'un compte PME spécifique. Trace `view_admin` côté PME."""
    # Vérifier que le compte existe
    from sqlalchemy import select

    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compte introuvable",
        )

    service = AuditService(db)
    # Trace AVANT la lecture (FR-024 : audit visible même si lecture échoue ensuite)
    await service.record_admin_view(current_admin, account_id, request)

    filters = _filters_from_query(
        entity_type, entity_id, action, source_of_change,
        since, until, page, limit, order,
    )
    events, total = await service.list_for_account(account_id, filters)
    return AuditEventList(events=events, total=total, page=page, limit=limit)


@admin_router.get("", response_model=AuditEventList)
async def list_global_admin(
    current_admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    account_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    action: AuditAction | None = None,
    source_of_change: AuditSourceOfChange | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    order: Literal["asc", "desc"] = "desc",
) -> AuditEventList:
    """Admin : log global (filtrable par compte/utilisateur)."""
    filters = _filters_from_query(
        entity_type, entity_id, action, source_of_change,
        since, until, page, limit, order,
        account_id=account_id, user_id=user_id,
    )
    service = AuditService(db)
    events, total = await service.list_global(filters)
    return AuditEventList(events=events, total=total, page=page, limit=limit)
