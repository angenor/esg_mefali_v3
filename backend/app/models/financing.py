"""Modeles SQLAlchemy pour le module Financement Vert."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.money import Money
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.versioning_mixin import VersioningMixin

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None


# --- Enumerations ---


class FundType(str, enum.Enum):
    """Type de fonds de financement vert."""

    international = "international"
    regional = "regional"
    national = "national"
    carbon_market = "carbon_market"
    local_bank_green_line = "local_bank_green_line"


class FundStatus(str, enum.Enum):
    """Statut d'un fonds."""

    active = "active"
    closed = "closed"
    upcoming = "upcoming"


class AccessType(str, enum.Enum):
    """Mode d'acces au fonds."""

    direct = "direct"
    intermediary_required = "intermediary_required"
    mixed = "mixed"


class IntermediaryType(str, enum.Enum):
    """Type d'intermediaire financier."""

    accredited_entity = "accredited_entity"
    partner_bank = "partner_bank"
    implementation_agency = "implementation_agency"
    project_developer = "project_developer"
    national_agency = "national_agency"


class OrganizationType(str, enum.Enum):
    """Type d'organisation de l'intermediaire."""

    bank = "bank"
    development_bank = "development_bank"
    un_agency = "un_agency"
    ngo = "ngo"
    government_agency = "government_agency"
    consulting_firm = "consulting_firm"
    carbon_developer = "carbon_developer"


class MatchStatus(str, enum.Enum):
    """Statut du matching utilisateur-fonds."""

    suggested = "suggested"
    interested = "interested"
    contacting_intermediary = "contacting_intermediary"
    applying = "applying"
    submitted = "submitted"
    accepted = "accepted"
    rejected = "rejected"


class FinancingSourceType(str, enum.Enum):
    """Type de source pour les chunks RAG financement."""

    fund = "fund"
    intermediary = "intermediary"


# --- Modeles ---


class Fund(UUIDMixin, TimestampMixin, VersioningMixin, Base):
    """Fonds de financement vert.

    F04 : versioning catalogue + paires Money (min_amount/max_amount).
    Les anciennes colonnes ``min_amount_xof`` / ``max_amount_xof`` sont
    conservées (cohabitation phase 1) et migrées via le backfill.
    """

    __tablename__ = "funds"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    organization: Mapped[str] = mapped_column(String(255), nullable=False)
    fund_type: Mapped[FundType] = mapped_column(
        Enum(FundType, name="fund_type_enum", create_constraint=True),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    eligibility_criteria: Mapped[dict] = mapped_column(
        JSON, nullable=False, server_default="{}"
    )
    sectors_eligible: Mapped[list] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )
    min_amount_xof: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    max_amount_xof: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # F04 — Money typed (cohabitation avec _xof legacy).
    min_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    min_amount_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    max_amount_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    application_deadline: Mapped[datetime | None] = mapped_column(
        Date, nullable=True
    )
    required_documents: Mapped[list] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )
    esg_requirements: Mapped[dict] = mapped_column(
        JSON, nullable=False, server_default="{}"
    )
    status: Mapped[FundStatus] = mapped_column(
        Enum(FundStatus, name="fund_status_enum", create_constraint=True),
        nullable=False,
        default=FundStatus.active,
    )
    access_type: Mapped[AccessType] = mapped_column(
        Enum(AccessType, name="access_type_enum", create_constraint=True),
        nullable=False,
    )
    intermediary_type: Mapped[IntermediaryType | None] = mapped_column(
        Enum(IntermediaryType, name="intermediary_type_enum", create_constraint=True),
        nullable=True,
    )
    application_process: Mapped[list] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )
    typical_timeline_months: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    success_tips: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relations
    fund_intermediaries: Mapped[list["FundIntermediary"]] = relationship(
        "FundIntermediary",
        back_populates="fund",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    matches: Mapped[list["FundMatch"]] = relationship(
        "FundMatch",
        back_populates="fund",
        cascade="all, delete-orphan",
    )

    @property
    def min_amount_money(self) -> Money | None:
        """F04 — Reconstruit Money depuis (min_amount, min_amount_currency)
        ou fallback sur le champ legacy ``min_amount_xof`` (XOF par défaut)."""
        if self.min_amount is not None and self.min_amount_currency:
            return Money(amount=self.min_amount, currency=self.min_amount_currency)
        if self.min_amount_xof is not None:
            return Money(amount=Decimal(self.min_amount_xof), currency="XOF")
        return None

    @property
    def max_amount_money(self) -> Money | None:
        """F04 — Reconstruit Money depuis (max_amount, max_amount_currency)
        ou fallback sur le champ legacy ``max_amount_xof`` (XOF par défaut)."""
        if self.max_amount is not None and self.max_amount_currency:
            return Money(amount=self.max_amount, currency=self.max_amount_currency)
        if self.max_amount_xof is not None:
            return Money(amount=Decimal(self.max_amount_xof), currency="XOF")
        return None


class Intermediary(UUIDMixin, TimestampMixin, VersioningMixin, Base):
    """Intermediaire financier (banque, agence ONU, developpeur carbone, etc.).

    F04 : versioning catalogue (4 colonnes via ``VersioningMixin``).
    """

    __tablename__ = "intermediaries"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    intermediary_type: Mapped[IntermediaryType] = mapped_column(
        Enum(IntermediaryType, name="intermediary_type_enum", create_constraint=True),
        nullable=False,
    )
    organization_type: Mapped[OrganizationType] = mapped_column(
        Enum(OrganizationType, name="organization_type_enum", create_constraint=True),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    physical_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    accreditations: Mapped[list] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )
    services_offered: Mapped[dict] = mapped_column(
        JSON, nullable=False, server_default="{}"
    )
    typical_fees: Mapped[str | None] = mapped_column(Text, nullable=True)
    eligibility_for_sme: Mapped[dict] = mapped_column(
        JSON, nullable=False, server_default="{}"
    )
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    # Relations
    fund_intermediaries: Mapped[list["FundIntermediary"]] = relationship(
        "FundIntermediary",
        back_populates="intermediary",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class FundIntermediary(UUIDMixin, VersioningMixin, Base):
    """Liaison N-N entre un fonds et un intermediaire.

    F04 : versioning catalogue (4 colonnes via ``VersioningMixin``).
    """

    __tablename__ = "fund_intermediaries"
    __table_args__ = (
        UniqueConstraint("fund_id", "intermediary_id", name="uq_fund_intermediary"),
    )

    fund_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("funds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    intermediary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intermediaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    geographic_coverage: Mapped[list] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relations
    fund: Mapped["Fund"] = relationship("Fund", back_populates="fund_intermediaries")
    intermediary: Mapped["Intermediary"] = relationship(
        "Intermediary", back_populates="fund_intermediaries"
    )


class FundMatch(UUIDMixin, Base):
    """Match entre un utilisateur et un fonds de financement."""

    __tablename__ = "fund_matches"
    __table_args__ = (
        UniqueConstraint("user_id", "fund_id", name="uq_user_fund_match"),
        Index("idx_fund_matches_account_id", "account_id"),
    )

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
    )
    fund_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("funds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    compatibility_score: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    matching_criteria: Mapped[dict] = mapped_column(
        JSON, nullable=False, server_default="{}"
    )
    missing_criteria: Mapped[dict] = mapped_column(
        JSON, nullable=False, server_default="{}"
    )
    recommended_intermediaries: Mapped[list] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )
    access_pathway: Mapped[dict] = mapped_column(
        JSON, nullable=False, server_default="{}"
    )
    estimated_timeline_months: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, name="match_status_enum", create_constraint=True),
        nullable=False,
        default=MatchStatus.suggested,
    )
    contacted_intermediary_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intermediaries.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relations
    fund: Mapped["Fund"] = relationship("Fund", back_populates="matches")
    contacted_intermediary: Mapped["Intermediary | None"] = relationship(
        "Intermediary", foreign_keys=[contacted_intermediary_id]
    )


class FinancingChunk(UUIDMixin, Base):
    """Chunk RAG pour la recherche semantique sur les financements."""

    __tablename__ = "financing_chunks"

    source_type: Mapped[FinancingSourceType] = mapped_column(
        Enum(
            FinancingSourceType,
            name="financing_source_type_enum",
            create_constraint=True,
        ),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(
        Vector(1536) if Vector is not None else Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# Index HNSW pour la recherche vectorielle sur les embeddings financement
if Vector is not None:
    financing_hnsw_index = Index(
        "ix_financing_chunks_embedding_hnsw",
        FinancingChunk.embedding,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
