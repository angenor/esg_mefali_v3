"""Modeles SQLAlchemy Indicator/Criterion/Formula/Threshold (catalogue F01).

Indicateur = unite atomique de mesure ESG. Critere = condition logique sur
indicateurs. Formule = calcul mobilisant indicateurs. Seuil = valeur de coupure.
Tous lies obligatoirement a une Source (FR-006).
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin

# Type JSONB compatible PostgreSQL et SQLite (tests).
_JSONType = JSONB().with_variant(JSON(), "sqlite")


# TODO(F02): account_id NOT NULL.
# TODO(F03): Auditable mixin sur transitions publication_status.
class Indicator(UUIDMixin, TimestampMixin, Base):
    """Indicateur ESG atomique, lie a une Source verifiee pour publication."""

    __tablename__ = "indicators"

    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    pillar: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
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
            "pillar IN ('environment','social','governance')",
            name="indicators_pillar_chk",
        ),
        CheckConstraint(
            "publication_status IN ('draft','published')",
            name="indicators_publication_status_chk",
        ),
    )


# TODO(F02): account_id, TODO(F03): Auditable.
class Criterion(UUIDMixin, TimestampMixin, Base):
    """Condition logique sur un ou plusieurs indicateurs."""

    __tablename__ = "criteria"

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    expression: Mapped[dict] = mapped_column(_JSONType, nullable=False)
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
            name="criteria_publication_status_chk",
        ),
    )


# TODO(F02): account_id, TODO(F03): Auditable.
class Formula(UUIDMixin, TimestampMixin, Base):
    """Formule de calcul mobilisant indicateurs et constantes."""

    __tablename__ = "formulas"

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[dict] = mapped_column(_JSONType, nullable=False)
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
            name="formulas_publication_status_chk",
        ),
    )


# TODO(F02): account_id, TODO(F03): Auditable.
class Threshold(UUIDMixin, TimestampMixin, Base):
    """Seuil d'eligibilite ou classification (PME, investissement, etc.)."""

    __tablename__ = "thresholds"

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(20, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    scope: Mapped[str] = mapped_column(String(100), nullable=False)
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
            name="thresholds_publication_status_chk",
        ),
    )
