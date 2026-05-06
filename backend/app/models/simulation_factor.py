"""Modele SQLAlchemy SimulationFactor (catalogue F01).

Constante numerique utilisee par les simulateurs (taux d'epargne, impact
carbone par MXOF, etc.). Le `status` peut etre `pending` (sans source) ou
`verified` (avec source). Contrainte CHECK garantit la coherence.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


# TODO(F02): account_id, TODO(F03): Auditable.
class SimulationFactor(UUIDMixin, TimestampMixin, Base):
    """Constante de simulation. Status `pending` si aucune source officielle."""

    __tablename__ = "simulation_factors"

    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
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
        String(20), nullable=False, default="pending", server_default="pending",
    )
    # TODO(F02): account_id.
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('verified','pending')",
            name="simulation_factors_status_chk",
        ),
        CheckConstraint(
            "(status = 'verified' AND source_id IS NOT NULL) "
            "OR (status = 'pending' AND source_id IS NULL)",
            name="simulation_factors_source_required_chk",
        ),
    )
