"""Modeles SQLAlchemy Referential et ReferentialIndicator (catalogue F01).

Referential = collection coherente d'indicateurs (taxonomie sectorielle).
ReferentialIndicator = jointure N-N portant `weight`, `threshold`, `source_id`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


# TODO(F02): account_id, TODO(F03): Auditable.
class Referential(UUIDMixin, TimestampMixin, Base):
    """Collection coherente d'indicateurs (referentiel sectoriel)."""

    __tablename__ = "referentials"

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
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
            "publication_status IN ('draft','published')",
            name="referentials_publication_status_chk",
        ),
    )


class ReferentialIndicator(UUIDMixin, TimestampMixin, Base):
    """Association N-N entre referentiel et indicateur, avec poids et seuil."""

    __tablename__ = "referential_indicators"

    referential_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("referentials.id", ondelete="CASCADE"),
        nullable=False,
    )
    indicator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("indicators.id", ondelete="RESTRICT"),
        nullable=False,
    )
    weight: Mapped[float] = mapped_column(
        Numeric(4, 2), nullable=False, default=1.0, server_default="1.00",
    )
    threshold: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "referential_id", "indicator_id", name="referential_indicators_uniq",
        ),
    )
