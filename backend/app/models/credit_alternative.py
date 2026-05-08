"""F18 — Modèles SQLAlchemy pour le module crédit alternatif.

Tables :
- ``MobileMoneyImport`` : trace de chaque upload de fichier MM.
- ``MobileMoneyTransaction`` : transaction MM normalisée et hachée.
- ``MobileMoneyAnalysis`` : KPIs courants par PME.
- ``CreditPhoto`` : photo téléversée + analyse IA structurée.
- ``PublicDataSource`` : déclaration source publique par la PME.
- ``CreditMethodologyFactor`` : catalogue méthodologie scoring crédit (admin).

Toutes les tables tenant ont ``account_id`` FK ``accounts.id`` + RLS F02.
``CreditMethodologyFactor`` est un catalogue exempt (admin only).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.auditable import Auditable
from app.models.base import Base, UUIDMixin


_JSONB = JSONB().with_variant(JSON(), "sqlite")


class MobileMoneyImport(Auditable, UUIDMixin, Base):
    """Trace d'un upload de fichier Mobile Money (CSV/Excel)."""

    __tablename__ = "mobile_money_imports"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('wave','orange_money','mtn_momo','moov_money')",
            name="mm_imports_provider_chk",
        ),
        CheckConstraint(
            "status IN ('pending','completed','failed')",
            name="mm_imports_status_chk",
        ),
        Index(
            "idx_mm_imports_account_created", "account_id", "created_at"
        ),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    imported_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    rejected_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    error_summary: Mapped[dict | None] = mapped_column(_JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    transactions = relationship(
        "MobileMoneyTransaction",
        back_populates="import_record",
        cascade="all, delete-orphan",
    )


class MobileMoneyTransaction(Auditable, UUIDMixin, Base):
    """Transaction Mobile Money normalisée et hachée."""

    __tablename__ = "mobile_money_transactions"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "transaction_date",
            "amount",
            "counterparty_hash",
            "direction",
            name="uq_mm_transaction_dedup",
        ),
        CheckConstraint(
            "direction IN ('incoming','outgoing')",
            name="mm_tx_direction_chk",
        ),
        CheckConstraint("amount >= 0", name="mm_tx_amount_chk"),
        CheckConstraint(
            "currency IN ('XOF','EUR','USD','GBP','JPY')",
            name="mm_tx_currency_chk",
        ),
        CheckConstraint(
            "balance_currency IS NULL OR balance_currency IN "
            "('XOF','EUR','USD','GBP','JPY')",
            name="mm_tx_balance_currency_chk",
        ),
        Index(
            "idx_mm_tx_account_date", "account_id", "transaction_date"
        ),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    import_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mobile_money_imports.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    counterparty_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    balance_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    balance_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    unused: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    purge_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    import_record = relationship(
        "MobileMoneyImport", back_populates="transactions"
    )


class MobileMoneyAnalysis(UUIDMixin, Base):
    """Agrégat analytique courant d'une PME (artefact recalculé, exempté Auditable)."""

    __tablename__ = "mobile_money_analyses"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "methodology_version",
            name="uq_mm_analysis_account_version",
        ),
        Index(
            "idx_mm_analyses_account_computed",
            "account_id",
            "computed_at",
        ),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    methodology_version: Mapped[str] = mapped_column(String(20), nullable=False)
    kpis: Mapped[dict] = mapped_column(_JSONB, nullable=False)
    consent_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CreditPhoto(Auditable, UUIDMixin, Base):
    """Photo crédit + analyse IA structurée."""

    __tablename__ = "credit_photos"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "content_hash", name="uq_credit_photo_dedup"
        ),
        CheckConstraint(
            "quality_status IN ('pending','ok','low_quality','failed')",
            name="credit_photos_quality_chk",
        ),
        Index(
            "idx_credit_photos_account_created", "account_id", "created_at"
        ),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    analyzed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    analysis_result: Mapped[dict | None] = mapped_column(_JSONB, nullable=True)
    quality_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    methodology_version: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    unused: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    purge_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PublicDataSource(Auditable, UUIDMixin, Base):
    """Source publique déclarative par la PME."""

    __tablename__ = "public_data_sources"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('google_my_business','facebook_page','google_reviews',"
            "'trustpilot','green_program','other')",
            name="public_data_source_type_chk",
        ),
        CheckConstraint(
            "status IN ('declared','evidence_attached','pending_review')",
            name="public_data_status_chk",
        ),
        CheckConstraint(
            "declared_rating IS NULL OR "
            "(declared_rating >= 0 AND declared_rating <= 5)",
            name="public_data_rating_chk",
        ),
        CheckConstraint(
            "declared_reviews_count IS NULL OR declared_reviews_count >= 0",
            name="public_data_reviews_chk",
        ),
        Index(
            "idx_public_data_account_type", "account_id", "source_type"
        ),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    declared_rating: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 1), nullable=True
    )
    declared_reviews_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    program_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    evidence_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="declared"
    )
    sentiment_score: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2), nullable=True
    )
    green_signals: Mapped[dict | None] = mapped_column(_JSONB, nullable=True)
    unused: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    purge_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CreditMethodologyFactor(UUIDMixin, Base):
    """Catalogue de la méthodologie de scoring crédit (admin only).

    Exempt RLS et exempt Auditable (catalogue admin only).
    """

    __tablename__ = "credit_methodology_factors"
    __table_args__ = (
        UniqueConstraint(
            "version", "name", name="uq_credit_methodology_factor"
        ),
        CheckConstraint(
            "weight >= 0 AND weight <= 1",
            name="credit_methodology_weight_chk",
        ),
        CheckConstraint(
            "publication_status IN ('draft','published')",
            name="credit_methodology_publication_chk",
        ),
        Index(
            "idx_credit_methodology_version", "version", "publication_status"
        ),
    )

    version: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    publication_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="draft"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


__all__ = [
    "MobileMoneyImport",
    "MobileMoneyTransaction",
    "MobileMoneyAnalysis",
    "CreditPhoto",
    "PublicDataSource",
    "CreditMethodologyFactor",
]
