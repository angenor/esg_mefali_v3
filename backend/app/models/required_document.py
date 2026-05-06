"""Modele SQLAlchemy RequiredDocument (catalogue F01).

Document obligatoire exige par un Fund OU un Intermediary (XOR).
Lie obligatoirement a une Source verifiee pour pouvoir etre publie.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


# TODO(F02): account_id, TODO(F03): Auditable.
class RequiredDocument(UUIDMixin, TimestampMixin, Base):
    """Document obligatoire pour un dossier, lie a un fond OU un intermediaire."""

    __tablename__ = "required_documents"

    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    fund_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("funds.id", ondelete="CASCADE"),
        nullable=True,
    )
    intermediary_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intermediaries.id", ondelete="CASCADE"),
        nullable=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    publication_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default="draft",
    )
    # TODO(F02): account_id.
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "(fund_id IS NOT NULL AND intermediary_id IS NULL) "
            "OR (fund_id IS NULL AND intermediary_id IS NOT NULL)",
            name="required_documents_owner_chk",
        ),
        CheckConstraint(
            "publication_status IN ('draft','published')",
            name="required_documents_publication_status_chk",
        ),
    )
