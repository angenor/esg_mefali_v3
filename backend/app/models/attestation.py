"""Modèle SQLAlchemy Attestation (F08 — Attestation Vérifiable Ed25519).

Représente un acte de certification ponctuel d'un score (crédit, ESG, ou
combiné), signé numériquement Ed25519, lié à un ``account_id``
(multi-tenant F02), Auditable (F03).

Cycle de vie : ``authentic`` → ``revoked`` (par PME ou admin) ou
``authentic`` → ``expired`` (automatique après 1 an).

Note SQLite : les CHECK utilisant l'opérateur ``~`` (regex POSIX) ne sont
appliqués qu'en PostgreSQL via ``info={"postgres_only": True}``. Sur
SQLite (tests CI), ces CHECK sont retirés silencieusement par un listener
``before_cursor_execute`` (cf. ``app.core.dialect_filters``). Le fallback
applicatif Pydantic + service garantit la conformité format.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.auditable import Auditable
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.source import JSONType


# Whitelist applicative pour `attestation_type` (en plus du CHECK SQL).
ATTESTATION_TYPE_VALUES: frozenset[str] = frozenset({
    "credit_score",
    "esg_assessment",
    "combined",
})

# Préfixe display_id : ``ATT-YYYY-NNNNN``.
DISPLAY_ID_PREFIX = "ATT"


class Attestation(Auditable, UUIDMixin, TimestampMixin, Base):
    """Attestation vérifiable signée Ed25519.

    Multi-tenant via ``account_id`` (F02), Auditable (F03) — toutes les
    mutations sont tracées par le listener global ``before_flush``.
    """

    __tablename__ = "attestations"

    # Multi-tenant F02
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    attestation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONType, nullable=False)
    referential_snapshot: Mapped[list] = mapped_column(
        JSONType, nullable=False, default=list, server_default="[]",
    )

    pdf_path: Mapped[str] = mapped_column(String(500), nullable=False)
    pdf_hash_sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    signature_ed25519: Mapped[str] = mapped_column(String(255), nullable=False)
    public_key_id: Mapped[str] = mapped_column(
        String(50), nullable=False, default="v1", server_default="v1",
    )
    qr_code_path: Mapped[str] = mapped_column(String(500), nullable=False)

    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    revoked_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    verification_url: Mapped[str] = mapped_column(String(500), nullable=False)
    display_id: Mapped[str] = mapped_column(String(20), nullable=False)

    # Relationships (lazy noload — on n'a pas besoin de fetch automatique)
    user = relationship("User", foreign_keys=[user_id], lazy="noload")
    revoked_by_user = relationship(
        "User", foreign_keys=[revoked_by_user_id], lazy="noload",
    )
    account = relationship("Account", lazy="noload")

    __table_args__ = (
        # Contraintes CHECK portables (compatibles SQLite + PostgreSQL).
        CheckConstraint(
            "attestation_type IN ('credit_score', 'esg_assessment', 'combined')",
            name="attestation_type_chk",
        ),
        CheckConstraint(
            "valid_until > valid_from",
            name="valid_until_after_from_chk",
        ),
        CheckConstraint(
            "(revoked_at IS NULL AND revoked_reason IS NULL AND revoked_by_user_id IS NULL) "
            "OR (revoked_at IS NOT NULL AND revoked_reason IS NOT NULL AND revoked_by_user_id IS NOT NULL)",
            name="revoked_consistency_chk",
        ),
        # Note : les CHECK regex (``~``) sur ``pdf_hash_sha256``,
        # ``display_id``, ``public_key_id`` sont définis dans la migration
        # Alembic 026 (PostgreSQL uniquement). Sur SQLite (tests CI), le
        # fallback applicatif Pydantic + service garantit la conformité format.
        # Indexes (composites cf. data-model.md § Indexes)
        Index("idx_attestations_account_valid_until", "account_id", "valid_until"),
        Index("idx_attestations_user_id", "user_id"),
        # Unique sur display_id (visible sur le PDF)
        UniqueConstraint("display_id", name="uq_attestations_display_id"),
    )
