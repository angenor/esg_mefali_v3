"""Modeles SQLAlchemy pour le module Calculateur d'Empreinte Carbone."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class CarbonStatusEnum(str, enum.Enum):
    """Statut d'un bilan carbone."""

    in_progress = "in_progress"
    completed = "completed"


VALID_CATEGORIES = ("energy", "transport", "waste", "industrial", "agriculture")


class CarbonAssessment(UUIDMixin, TimestampMixin, Base):
    """Bilan carbone annuel pour une entreprise."""

    __tablename__ = "carbon_assessments"

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
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    sector: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_emissions_tco2e: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[CarbonStatusEnum] = mapped_column(
        Enum(CarbonStatusEnum, name="carbon_status_enum", create_constraint=True),
        nullable=False,
        default=CarbonStatusEnum.in_progress,
    )
    completed_categories: Mapped[list | None] = mapped_column(
        JSON, nullable=True, default=list
    )
    reduction_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relation one-to-many vers les entrees d'emissions
    entries: Mapped[list["CarbonEmissionEntry"]] = relationship(
        "CarbonEmissionEntry",
        back_populates="assessment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CarbonEmissionEntry(UUIDMixin, Base):
    """Ligne d'emission individuelle dans un bilan carbone."""

    __tablename__ = "carbon_emission_entries"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("carbon_assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    subcategory: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    emission_factor: Mapped[float] = mapped_column(Float, nullable=False)
    emissions_tco2e: Mapped[float] = mapped_column(Float, nullable=False)
    source_description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Timestamp creation seulement (pas de updated_at pour les entrees)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relation inverse
    assessment: Mapped["CarbonAssessment"] = relationship(
        "CarbonAssessment",
        back_populates="entries",
    )
