"""Modele SQLAlchemy SimulationFactor (F01)."""

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class SimulationFactor(UUIDMixin, TimestampMixin, Base):
    """Constante numerique d'un simulateur (taux d'epargne, impact carbone par MFCFA, etc.).

    status='pending' avec source_id NULL est autorise quand aucune source officielle
    ne couvre encore la valeur (Liste de suivi naturelle pour traitement editorial).
    """

    __tablename__ = "simulation_factors"

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    scope: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
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
            "(status = 'verified' AND source_id IS NOT NULL) "
            "OR (status = 'pending' AND source_id IS NULL)",
            name="simulation_factors_source_required_chk",
        ),
        CheckConstraint(
            "status IN ('verified','pending')",
            name="simulation_factors_status_chk",
        ),
        Index("simulation_factors_code_uniq_idx", "code", unique=True),
    )
