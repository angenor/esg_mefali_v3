"""Modeles SQLAlchemy pour le module Financement Vert."""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
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
from app.models.source import JSONType, PublicationStatus
from app.models.versioning_mixin import VersioningMixin

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None


# --- Enumerations ---


class FundType(str, enum.Enum):
    """Type de fonds de financement vert.

    F07 — valeurs renommées (migration 028) :
    - ``international`` → ``multilateral``
    - ``carbon_market`` → ``carbon_marketplace``
    - ``local_bank_green_line`` → ``private``
    + ajout ``bilateral``.
    """

    multilateral = "multilateral"
    bilateral = "bilateral"
    regional = "regional"
    national = "national"
    private = "private"
    carbon_marketplace = "carbon_marketplace"


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

    # F07 — Enrichissement (migration 028)
    instruments: Mapped[list[str]] = mapped_column(
        JSONType, nullable=False, server_default="[]", default=list,
    )
    theme: Mapped[list[str]] = mapped_column(
        JSONType, nullable=False, server_default="[]", default=list,
    )
    submission_mode: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="rolling", default="rolling",
    )
    submission_calendar: Mapped[list[dict] | None] = mapped_column(
        JSONType, nullable=True,
    )
    # F01 — Source obligatoire (NOT NULL post-migration 028).
    # Nullable=True dans le modèle pour permettre les tests legacy.
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=True,
    )
    publication_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PublicationStatus.DRAFT.value,
        server_default=PublicationStatus.DRAFT.value,
    )

    # Relations
    source: Mapped["Source | None"] = relationship(
        "Source", lazy="selectin", foreign_keys=[source_id],
    )
    # F24 — Extension Chrome : matchers d'URL pour la détection d'offre.
    url_patterns: Mapped[list[dict]] = mapped_column(
        JSONType, nullable=False, server_default="[]", default=list,
    )

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

    # F07 — Enrichissement (migration 028)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    """Code unique sparse (ex 'DIRECT' pour le singleton)."""
    required_documents: Mapped[list[dict]] = mapped_column(
        JSONType, nullable=False, server_default="[]", default=list,
    )
    fees_structured: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    processing_time_days_min: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    processing_time_days_max: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    disbursement_time_days_min: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    disbursement_time_days_max: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    submission_portal_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )
    success_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True,
    )
    total_funded_volume_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True,
    )
    total_funded_volume_currency: Mapped[str | None] = mapped_column(
        String(3), nullable=True,
    )
    # F01 — Source obligatoire (NOT NULL post-migration 028)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=True,
    )
    publication_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PublicationStatus.DRAFT.value,
        server_default=PublicationStatus.DRAFT.value,
    )

    # Relations
    source: Mapped["Source | None"] = relationship(
        "Source", lazy="selectin", foreign_keys=[source_id],
    )
    # F24 — Extension Chrome : matchers d'URL pour la détection d'offre.
    url_patterns: Mapped[list[dict]] = mapped_column(
        JSONType, nullable=False, server_default="[]", default=list,
    )

    fund_intermediaries: Mapped[list["FundIntermediary"]] = relationship(
        "FundIntermediary",
        back_populates="intermediary",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def total_funded_volume_money(self) -> Money | None:
        """F04 — Reconstruit Money depuis (amount, currency)."""
        return Money.from_columns(
            self.total_funded_volume_amount, self.total_funded_volume_currency,
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

    # F07 — Enrichissement (migration 028)
    accredited_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    """Date de début d'accréditation (NOT NULL post-migration 028)."""
    accredited_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    """Date de fin d'accréditation (NULL = encore accréditée)."""
    max_amount_per_fund_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True,
    )
    max_amount_per_fund_currency: Mapped[str | None] = mapped_column(
        String(3), nullable=True,
    )
    accreditation_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # Relations
    fund: Mapped["Fund"] = relationship("Fund", back_populates="fund_intermediaries")
    intermediary: Mapped["Intermediary"] = relationship(
        "Intermediary", back_populates="fund_intermediaries"
    )

    @property
    def max_amount_per_fund_money(self) -> Money | None:
        """F04 — Reconstruit Money depuis (amount, currency)."""
        return Money.from_columns(
            self.max_amount_per_fund_amount, self.max_amount_per_fund_currency,
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
