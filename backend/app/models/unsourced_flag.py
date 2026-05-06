"""Modele SQLAlchemy UnsourcedFlag (journal F01).

Enregistrement append-only de chaque invocation `flag_unsourced` par l'agent IA.
Permet la revue administrateur et le calcul des metriques (SC-012).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


# TODO(F02): account_id (nullable, conserve histoire pour metrique organisationnelle).
class UnsourcedFlag(UUIDMixin, Base):
    """Affirmation explicitement marquee comme non sourcable par l'agent IA."""

    __tablename__ = "unsourced_flags"

    claim: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    __table_args__ = (
        Index("unsourced_flags_created_at_idx", "created_at"),
    )
