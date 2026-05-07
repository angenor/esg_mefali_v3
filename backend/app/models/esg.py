"""Modele SQLAlchemy ESGAssessment."""

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.auditable import Auditable
from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.referential_score import ReferentialScore


class ESGStatusEnum(str, enum.Enum):
    """Statut d'une evaluation ESG."""

    draft = "draft"
    in_progress = "in_progress"
    completed = "completed"


class ESGAssessment(Auditable, UUIDMixin, TimestampMixin, Base):
    """Evaluation ESG complete pour une entreprise."""

    __tablename__ = "esg_assessments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # F02 — multi-tenant
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[ESGStatusEnum] = mapped_column(
        Enum(ESGStatusEnum, name="esg_status_type", create_constraint=True),
        nullable=False,
        default=ESGStatusEnum.draft,
        index=True,
    )
    sector: Mapped[str] = mapped_column(String(50), nullable=False)

    # Scores
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    environment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    social_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    governance_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Donnees detaillees JSON
    assessment_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recommendations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    strengths: Mapped[list | None] = mapped_column(JSON, nullable=True)
    gaps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sector_benchmark: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Etat de progression
    current_pillar: Mapped[str | None] = mapped_column(String(20), nullable=True)
    evaluated_criteria: Mapped[list | None] = mapped_column(
        JSON, nullable=True, default=list
    )

    # F13 — Scoring multi-référentiels (1 EsgAssessment → N ReferentialScore)
    referential_scores: Mapped[list["ReferentialScore"]] = relationship(
        "ReferentialScore",
        foreign_keys="ReferentialScore.assessment_id",
        back_populates="assessment",
        cascade="all, delete-orphan",
    )
