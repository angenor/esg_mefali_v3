"""Modèle SQLAlchemy ``AuditLog`` (F03 — audit log append-only).

Table strictement append-only : les triggers PostgreSQL
``audit_log_no_update`` / ``audit_log_no_delete`` interdisent toute mutation
(cf. migration ``021_create_audit_log``). Côté ORM, on n'expose donc ni
``UPDATE`` ni ``DELETE`` ; le mixin ``Auditable`` insère uniquement.

Le champ ``timestamp`` remplace ``created_at`` pour cohérence sémantique
(il n'existe ni ``created_at`` ni ``updated_at`` sur ce modèle).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import AuditAction, AuditSourceOfChange
from app.models.base import Base, UUIDMixin


# Sur PostgreSQL, on utilise des ENUMs natifs (créés en migration et liés via
# ``create_type=False``). Sur SQLite (tests unitaires), on dégrade en VARCHAR
# pour ne pas dépendre de l'extension PostgreSQL.
def _action_column_type():
    """Type SQL de la colonne ``action`` : portable PG (ENUM) / SQLite (VARCHAR)."""
    from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

    return PG_ENUM(
        AuditAction,
        name="audit_action",
        create_type=False,
        values_callable=lambda enum: [member.value for member in enum],
    ).with_variant(
        String(32),
        "sqlite",
    )


def _source_column_type():
    """Type SQL de la colonne ``source_of_change`` : ENUM PG / VARCHAR SQLite."""
    from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

    return PG_ENUM(
        AuditSourceOfChange,
        name="audit_source",
        create_type=False,
        values_callable=lambda enum: [member.value for member in enum],
    ).with_variant(
        String(32),
        "sqlite",
    )


def _jsonb_column_type():
    """Type colonne JSON : JSONB sur PG, JSON natif sur SQLite."""
    return JSONB().with_variant(JSON(), "sqlite")


class AuditLog(UUIDMixin, Base):
    """Événement d'audit immuable (append-only).

    Sémantique des champs (cf. data-model.md §2.5) :

    - ``user_id`` : acteur (l'admin pour ``view_admin``).
    - ``account_id`` : compte cible/propriétaire (le PME consulté pour ``view_admin``).
    - ``entity_type`` : ex. ``"company_profile"``, ``"account"`` (pour ``view_admin``).
    - ``entity_id`` : UUID de l'entité affectée.
    - ``action`` : ``create`` / ``update`` / ``delete`` / ``view_admin``.
    - ``field`` : nom du champ muté (NULL pour create/delete/view_admin).
    - ``old_value`` / ``new_value`` : valeurs avant/après, JSON (NULL admises).
    - ``source_of_change`` : ``manual`` / ``llm`` / ``import`` / ``admin``.
    - ``actor_metadata`` : ``tool_name``, ``conversation_id``, ``request_id``,
      ``ip_address``, ``user_agent``, ``endpoint`` (optionnels).
    """

    __tablename__ = "audit_log"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    action: Mapped[AuditAction] = mapped_column(
        _action_column_type(), nullable=False
    )
    field: Mapped[str | None] = mapped_column(String(128), nullable=True)
    old_value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        _jsonb_column_type(), nullable=True
    )
    new_value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        _jsonb_column_type(), nullable=True
    )
    source_of_change: Mapped[AuditSourceOfChange] = mapped_column(
        _source_column_type(), nullable=False
    )
    actor_metadata: Mapped[dict | None] = mapped_column(
        _jsonb_column_type(), nullable=True
    )

    __table_args__ = (
        Index(
            "idx_audit_log_account_timestamp",
            "account_id",
            "timestamp",
        ),
        Index(
            "idx_audit_log_account_entity",
            "account_id",
            "entity_type",
            "entity_id",
        ),
        Index("idx_audit_log_user_timestamp", "user_id", "timestamp"),
        Index(
            "idx_audit_log_source_timestamp",
            "source_of_change",
            "timestamp",
        ),
    )
