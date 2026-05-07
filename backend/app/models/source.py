"""Modele SQLAlchemy Source (F01 - Catalogue de sources verifiees).

Une Source represente un document de reference officiel mobilisable pour
etayer toute affirmation factuelle. Le workflow 4-yeux impose que le
captured_by (createur) soit different du verified_by (validateur).
"""

import uuid
from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.versioning_mixin import SourceVersioningMixin


class VerificationStatus(str, Enum):
    """Cycle de vie d'une Source."""

    DRAFT = "draft"
    PENDING = "pending"
    VERIFIED = "verified"
    OUTDATED = "outdated"


class PublicationStatus(str, Enum):
    """Cycle de vie d'une entite factuelle (publication)."""

    DRAFT = "draft"
    PUBLISHED = "published"


# Type JSONB compatible PostgreSQL et SQLite (tests).
JSONType = JSONB().with_variant(JSON(), "sqlite")


class Source(UUIDMixin, TimestampMixin, SourceVersioningMixin, Base):
    """Source : document officiel de reference.

    Workflow 4-yeux : captured_by (createur) != verified_by (validateur).

    F04 : utilise ``SourceVersioningMixin`` (champ ``catalog_version``) car
    le champ ``version`` existant représente la version du document métier
    (ex 'v2.3', 'AR6') et n'est pas concerné par le versioning catalogue.
    """

    __tablename__ = "sources"

    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    publisher: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    date_publi: Mapped[date] = mapped_column(Date, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(200), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    captured_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    verification_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=VerificationStatus.DRAFT.value,
        server_default=VerificationStatus.DRAFT.value,
        index=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    outdated_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # F02 : multi-tenant - account_id via owner Admin user.
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
    # Embedding pour recherche semantique (text-embedding-3-small, 1536 dim).
    # Stocke en JSON array pour compatibilite SQLite tests; pgvector via
    # migration ALTER COLUMN cote PostgreSQL.
    embedding: Mapped[list[float] | None] = mapped_column(JSONType, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "verified_by IS NULL OR verified_by != captured_by",
            name="sources_four_eyes_chk",
        ),
        CheckConstraint(
            "verification_status IN ('draft','pending','verified','outdated')",
            name="sources_verification_status_chk",
        ),
        CheckConstraint(
            "(verification_status IN ('verified','outdated') "
            "AND verified_by IS NOT NULL AND verified_at IS NOT NULL) "
            "OR verification_status IN ('draft','pending')",
            name="sources_verified_consistency_chk",
        ),
        CheckConstraint(
            "(verification_status = 'outdated' AND outdated_reason IS NOT NULL) "
            "OR verification_status != 'outdated'",
            name="sources_outdated_reason_chk",
        ),
        Index("sources_url_uniq_idx", "url", unique=True),
    )
