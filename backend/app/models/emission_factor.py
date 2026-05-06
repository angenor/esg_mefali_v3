"""Modele SQLAlchemy EmissionFactor (catalogue F01).

Facteur d'emission par categorie et par pays (ADEME, IPCC, IEA).
Lie obligatoirement a une Source verifiee pour pouvoir etre publie.
"""

from __future__ import annotations

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


# TODO(F02): account_id, TODO(F03): Auditable.
class EmissionFactor(UUIDMixin, TimestampMixin, Base):
    """Facteur d'emission carbone (kgCO2e/unite) par pays et categorie."""

    __tablename__ = "emission_factors"

    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
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
            name="emission_factors_publication_status_chk",
        ),
        Index("emission_factors_category_country_idx", "category", "country"),
    )
