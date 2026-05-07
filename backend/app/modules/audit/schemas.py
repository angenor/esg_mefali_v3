"""Schémas Pydantic v2 pour le module audit (F03)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import AuditAction, AuditSourceOfChange


class AuditEvent(BaseModel):
    """Représentation API d'une ligne ``audit_log``.

    Note : ``user_email`` est récupéré via JOIN sur ``users`` au moment de la
    sérialisation (champ optionnel : NULL si l'utilisateur a été supprimé).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    timestamp: datetime
    user_id: UUID
    user_email: str | None = None
    account_id: UUID
    entity_type: str
    entity_id: UUID
    action: AuditAction
    field: str | None = None
    old_value: Any | None = None
    new_value: Any | None = None
    source_of_change: AuditSourceOfChange
    actor_metadata: dict[str, Any] | None = None


class AuditEventList(BaseModel):
    """Réponse paginée pour les listings ``GET /api/audit/me`` et admin."""

    events: list[AuditEvent]
    total: int
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=200)


class AuditFilters(BaseModel):
    """Filtres communs aux endpoints PME et admin.

    Les champs ``account_id`` et ``user_id`` ne sont utilisés que par
    l'endpoint global admin (``GET /api/admin/audit``).
    """

    entity_type: str | None = None
    entity_id: UUID | None = None
    action: AuditAction | None = None
    source_of_change: AuditSourceOfChange | None = None
    since: datetime | None = None
    until: datetime | None = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=50, ge=1, le=200)
    order: Literal["asc", "desc"] = "desc"

    # Admin uniquement (ignoré côté PME) :
    account_id: UUID | None = None
    user_id: UUID | None = None


# Format d'export disponible (cf. FR-027).
AuditExportFormat = Literal["csv", "json"]
