"""Modeles SQLAlchemy pour le module Scoring de Credit Vert."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


# --- Enumerations ---


class CreditCategory(str, enum.Enum):
    """Categorie de facteur de scoring."""

    solvability = "solvability"
    green_impact = "green_impact"


class ConfidenceLabel(str, enum.Enum):
    """Label de confiance affichable."""

    very_low = "very_low"
    low = "low"
    medium = "medium"
    good = "good"
    excellent = "excellent"


# --- Modeles ---


class CreditScore(UUIDMixin, Base):
    """Score de credit vert genere pour un utilisateur, versionne."""

    __tablename__ = "credit_scores"
    __table_args__ = (
        UniqueConstraint("user_id", "version", name="uq_credit_score_user_version"),
        Index("ix_credit_scores_user_id", "user_id"),
        Index("ix_credit_scores_user_generated", "user_id", "generated_at"),
        Index("idx_credit_scores_account_id", "account_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # F02 — multi-tenant
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    solvability_score: Mapped[float] = mapped_column(Float, nullable=False)
    green_impact_score: Mapped[float] = mapped_column(Float, nullable=False)
    combined_score: Mapped[float] = mapped_column(Float, nullable=False)
    score_breakdown: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    data_sources: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    confidence_level: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_label: Mapped[str] = mapped_column(
        Enum(ConfidenceLabel, name="confidence_label_enum", create_constraint=True),
        nullable=False,
    )
    recommendations: Mapped[list] = mapped_column(JSON, nullable=False, server_default="[]")
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relations
    data_points = relationship(
        "CreditDataPoint", back_populates="credit_score", cascade="all, delete-orphan"
    )


class CreditDataPoint(UUIDMixin, Base):
    """Donnee unitaire collectee pour le calcul du score."""

    __tablename__ = "credit_data_points"
    __table_args__ = (
        Index("ix_credit_data_points_user_id", "user_id"),
        Index("ix_credit_data_points_user_category", "user_id", "category"),
        Index("ix_credit_data_points_user_source", "user_id", "source"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    credit_score_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("credit_scores.id"), nullable=True
    )
    category: Mapped[str] = mapped_column(
        Enum(CreditCategory, name="credit_category_enum", create_constraint=True),
        nullable=False,
    )
    subcategory: Mapped[str] = mapped_column(String(100), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relations
    credit_score = relationship("CreditScore", back_populates="data_points")
