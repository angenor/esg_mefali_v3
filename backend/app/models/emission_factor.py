"""Modele SQLAlchemy EmissionFactor (F01, etendu F17).

Migre les EMISSION_FACTORS du module carbone vers une table sourcee.

F17 ajoute la colonne ``year`` (Integer NOT NULL) et la contrainte UNIQUE
``(category, country, year)``, plus un index composite ``idx_emission_factors_lookup``
pour les requetes du service ``get_emission_factor``.
"""

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.source import PublicationStatus
from app.models.versioning_mixin import VersioningMixin


class EmissionFactor(UUIDMixin, TimestampMixin, VersioningMixin, Base):
    """Facteur d'emission par categorie, pays et annee (ADEME, IPCC, IEA).

    F17 ajoute la colonne ``year`` pour stocker l'annee de reference du
    facteur (ex. 2024). Cette dimension permet le matching pays/annee dans
    le service ``get_emission_factor``.
    """

    __tablename__ = "emission_factors"

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(50), nullable=False)
    # F17 — annee de reference du facteur d'emission (ex. 2024).
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
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
            name="emission_factors_publication_status_chk",
        ),
        Index("emission_factors_code_uniq_idx", "code", unique=True),
        Index(
            "emission_factors_category_country_idx",
            "category",
            "country",
        ),
        # F17 — index composite pour le service get_emission_factor.
        Index(
            "idx_emission_factors_lookup",
            "category",
            "country",
            "year",
        ),
        # F17 — UNIQUE (category, country, year) pour idempotence et
        # cohesion metier (un seul facteur par triplet).
        UniqueConstraint(
            "category",
            "country",
            "year",
            name="emission_factors_cat_country_year_uniq",
        ),
    )
