"""Modèle SQLAlchemy ``Consent`` (F05 — consentements granulaires RGPD).

Stocke un consentement utilisateur granulaire pour un traitement donné. La
table satisfait l'invariant projet n°5 (« RGPD consentements ») : tout
traitement non-essentiel doit appeler ``app.core.consent.require_consent`` au
runtime, qui interroge cette table.

Invariants :

- Au plus **un consentement actif** par couple ``(account_id, consent_type)``
  garanti par l'index unique partial ``uq_consents_one_active``.
- ``revoked_at >= granted_at`` lorsque non NULL (CHECK
  ``chk_consents_revoked_after_granted``).
- ``account_id`` cascade DELETE pour purge complète du compte (F05 US3).
- ``user_id`` cascade SET NULL pour conserver l'historique post-purge user.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


# Liste figée des 7 types de consentements supportés en MVP.
CONSENT_TYPE_VALUES: tuple[str, ...] = (
    "profile_analysis",
    "document_analysis_ai",
    "mobile_money_analysis",
    "photos_ia_analysis",
    "public_data_analysis",
    "credit_certificate_generation",
    "product_communications",
)


# Bases légales RGPD (Art. 6.1 a/b/c/f).
LEGAL_BASIS_VALUES: tuple[str, ...] = (
    "consent",
    "contract",
    "legal_obligation",
    "legitimate_interest",
)


# Valeurs par défaut documentées (spec FR-005).
CONSENT_TYPE_DEFAULT_GRANTED: dict[str, bool] = {
    "profile_analysis": True,
    "document_analysis_ai": True,
    "mobile_money_analysis": False,
    "photos_ia_analysis": False,
    "public_data_analysis": False,
    "credit_certificate_generation": True,
    "product_communications": False,
}


CONSENT_TYPE_DEFAULT_LEGAL_BASIS: dict[str, str] = {
    "profile_analysis": "contract",
    "document_analysis_ai": "contract",
    "mobile_money_analysis": "consent",
    "photos_ia_analysis": "consent",
    "public_data_analysis": "consent",
    "credit_certificate_generation": "contract",
    "product_communications": "consent",
}


# Libellés et descriptions en français (utilisés dans l'API et l'UI).
CONSENT_TYPE_LABELS: dict[str, str] = {
    "profile_analysis": "Analyse de mon profil entreprise pour matching financements",
    "document_analysis_ai": "Analyse IA des documents que je téléverse",
    "mobile_money_analysis": "Analyse de mes flux Mobile Money pour scoring crédit",
    "photos_ia_analysis": "Analyse IA de mes photos d'exploitation",
    "public_data_analysis": "Analyse de données publiques me concernant",
    "credit_certificate_generation": "Génération automatique d'attestation crédit transmissible",
    "product_communications": "Communications produit et newsletter",
}


CONSENT_TYPE_DESCRIPTIONS: dict[str, str] = {
    "profile_analysis": (
        "Permet à la plateforme d'analyser votre profil pour vous proposer des fonds adaptés."
    ),
    "document_analysis_ai": (
        "Permet à l'IA d'extraire automatiquement les informations ESG de vos documents."
    ),
    "mobile_money_analysis": (
        "Permet d'inclure vos données Mobile Money dans le calcul de votre score crédit alternatif."
    ),
    "photos_ia_analysis": (
        "Permet à l'IA d'analyser des photos de votre activité pour enrichir le scoring."
    ),
    "public_data_analysis": (
        "Permet d'inclure des données publiques (réseaux sociaux, avis) dans l'analyse."
    ),
    "credit_certificate_generation": (
        "Autorise la génération de votre attestation crédit signée Ed25519 pour transmission aux financeurs."
    ),
    "product_communications": (
        "Recevoir des informations sur les nouveautés ESG Mefali (au plus 1 email/mois)."
    ),
}


# Libellés courts pour messages 403 du helper require_consent.
CONSENT_SHORT_LABELS: dict[str, str] = {
    "profile_analysis": "Analyse profil",
    "document_analysis_ai": "Analyse documents IA",
    "mobile_money_analysis": "Mobile Money",
    "photos_ia_analysis": "Photos IA",
    "public_data_analysis": "Données publiques",
    "credit_certificate_generation": "Génération attestation crédit",
    "product_communications": "Communications produit",
}


def _consent_type_column_type():
    """Type SQL portable PostgreSQL ENUM / SQLite VARCHAR."""
    return PG_ENUM(
        *CONSENT_TYPE_VALUES,
        name="consent_type_enum",
        create_type=False,
    ).with_variant(String(64), "sqlite")


def _legal_basis_column_type():
    """Type SQL portable PostgreSQL ENUM / SQLite VARCHAR."""
    return PG_ENUM(
        *LEGAL_BASIS_VALUES,
        name="legal_basis_enum",
        create_type=False,
    ).with_variant(String(32), "sqlite")


def _jsonb_column_type():
    """JSONB sur PostgreSQL, JSON natif sur SQLite (tests)."""
    return JSONB().with_variant(JSON(), "sqlite")


class Consent(UUIDMixin, TimestampMixin, Base):
    """Consentement RGPD granulaire pour un traitement non-essentiel.

    Hors `Auditable` : la mutation est tracée explicitement par le service via
    ``audit_log.action='consent_granted'`` / ``'consent_revoked'`` avec metadata
    riche (ip, user_agent, version), pas par le mixin générique.
    """

    __tablename__ = "consents"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    consent_type: Mapped[str] = mapped_column(
        _consent_type_column_type(),
        nullable=False,
    )
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    legal_basis: Mapped[str] = mapped_column(
        _legal_basis_column_type(),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(16), nullable=False)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",
        _jsonb_column_type(),
        nullable=False,
        server_default="{}",
        default=dict,
    )

    __table_args__ = (
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= granted_at",
            name="chk_consents_revoked_after_granted",
        ),
        Index(
            "idx_consents_active",
            "account_id",
            "consent_type",
            postgresql_where=text("revoked_at IS NULL AND granted = true"),
            sqlite_where=text("revoked_at IS NULL AND granted = 1"),
        ),
        Index(
            "uq_consents_one_active",
            "account_id",
            "consent_type",
            unique=True,
            postgresql_where=text("revoked_at IS NULL AND granted = true"),
            sqlite_where=text("revoked_at IS NULL AND granted = 1"),
        ),
    )
