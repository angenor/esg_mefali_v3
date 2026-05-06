"""Modele SQLAlchemy Source (catalogue de sources verifiables) — feature F01.

Source = document de reference officiel (taxonomie, standard, circulaire,
base de donnees publique) mobilisable pour etayer toute affirmation factuelle
produite par l'agent IA. Workflow 4-yeux : `captured_by != verified_by`.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin

try:
    from pgvector.sqlalchemy import Vector

    EMBEDDING_DIM = 1536
    _embedding_type = Vector(EMBEDDING_DIM)
except ImportError:  # pragma: no cover - fallback pour tests SQLite
    _embedding_type = None  # type: ignore[assignment]


class VerificationStatus(str, enum.Enum):
    """Statut de verification d'une source dans le workflow 4-yeux."""

    DRAFT = "draft"
    PENDING = "pending"
    VERIFIED = "verified"
    OUTDATED = "outdated"


# TODO(F02): account_id NOT NULL FK accounts.id — migration ulterieure.
# TODO(F03): Auditable mixin pour journaliser les transitions.
class Source(UUIDMixin, TimestampMixin, Base):
    """Document de reference officiel mobilisable par l'agent IA.

    Workflow 4-yeux :
    - captured_by : admin createur (NOT NULL).
    - verified_by : admin valideur, distinct du createur (NULL tant que pending).
    - CHECK (verified_by IS NULL OR verified_by != captured_by).

    Transitions d'etat :
        draft -> pending -> verified -> outdated (terminal).
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

    # TODO(F02): remplacer par account_id FK accounts.id NOT NULL.
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Embedding sera nullable en F01 (calcule a la creation si OpenAI dispo).
    if _embedding_type is not None:
        embedding: Mapped[list[float] | None] = mapped_column(
            _embedding_type, nullable=True,
        )

    __table_args__ = (
        CheckConstraint(
            "verified_by IS NULL OR verified_by != captured_by",
            name="sources_four_eyes_chk",
        ),
        CheckConstraint(
            "verification_status IN ('draft','pending','verified','outdated')",
            name="sources_status_chk",
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
