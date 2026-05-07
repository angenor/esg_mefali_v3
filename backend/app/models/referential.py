"""Modeles SQLAlchemy Referential + ReferentialIndicator (F01).

Un Referential agrege des Indicators avec poids et seuils, chacun lie a une Source.
"""

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.source import PublicationStatus
from app.models.versioning_mixin import VersioningMixin


class Referential(UUIDMixin, TimestampMixin, VersioningMixin, Base):
    """Collection coherente d'indicateurs (par exemple 'Referentiel ESG UEMOA Standard')."""

    __tablename__ = "referentials"

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    publication_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PublicationStatus.DRAFT.value,
        server_default=PublicationStatus.DRAFT.value,
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
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
        Index("referentials_code_uniq_idx", "code", unique=True),
    )


class ReferentialIndicator(UUIDMixin, TimestampMixin, VersioningMixin, Base):
    """Jointure N-N : associe un Indicator a un Referential avec poids et seuil."""

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
        Numeric(4, 2), nullable=False, default=1.00, server_default="1.00",
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
