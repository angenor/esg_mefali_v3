"""Modèle SQLAlchemy CompanyProfile."""

import enum
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.auditable import Auditable
from app.models.base import Base, TimestampMixin, UUIDMixin


class SectorEnum(str, enum.Enum):
    """Secteurs d'activité adaptés au contexte africain."""

    agriculture = "agriculture"
    energie = "energie"
    recyclage = "recyclage"
    transport = "transport"
    construction = "construction"
    textile = "textile"
    agroalimentaire = "agroalimentaire"
    services = "services"
    commerce = "commerce"
    artisanat = "artisanat"
    autre = "autre"


class CompanyProfile(Auditable, UUIDMixin, TimestampMixin, Base):
    """Profil d'entreprise lié à un utilisateur (relation un-à-un)."""

    __tablename__ = "company_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    # F02 — multi-tenant : 1:1 avec Account (UNIQUE partiel WHERE archived = false
    # défini dans la migration Alembic 019).
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Identité
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sector: Mapped[SectorEnum | None] = mapped_column(
        Enum(SectorEnum, name="sector_type", create_constraint=True),
        nullable=True,
    )
    sub_sector: Mapped[str | None] = mapped_column(Text, nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annual_revenue_xof: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    year_founded: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Localisation
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ESG
    has_waste_management: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_energy_policy: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_gender_policy: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_training_program: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_financial_transparency: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )
    governance_structure: Mapped[str | None] = mapped_column(Text, nullable=True)
    environmental_practices: Mapped[str | None] = mapped_column(Text, nullable=True)
    social_practices: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Notes qualitatives
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_company_profiles_account_id", "account_id"),
    )
