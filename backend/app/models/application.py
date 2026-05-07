"""Modeles SQLAlchemy pour le module Dossiers de Candidature."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.auditable import Auditable
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.source import JSONType


# --- Enumerations ---


class TargetType(str, enum.Enum):
    """Type de destinataire du dossier."""

    fund_direct = "fund_direct"
    intermediary_bank = "intermediary_bank"
    intermediary_agency = "intermediary_agency"
    intermediary_developer = "intermediary_developer"


class ApplicationStatus(str, enum.Enum):
    """Statut du dossier de candidature."""

    draft = "draft"
    preparing_documents = "preparing_documents"
    in_progress = "in_progress"
    review = "review"
    ready_for_intermediary = "ready_for_intermediary"
    ready_for_fund = "ready_for_fund"
    submitted_to_intermediary = "submitted_to_intermediary"
    submitted_to_fund = "submitted_to_fund"
    under_review = "under_review"
    accepted = "accepted"
    rejected = "rejected"


# Libelles francais pour chaque statut
STATUS_LABELS: dict[str, str] = {
    "draft": "Brouillon",
    "preparing_documents": "Préparation des documents",
    "in_progress": "Rédaction en cours",
    "review": "Relecture",
    "ready_for_intermediary": "Prêt pour l'intermédiaire",
    "ready_for_fund": "Prêt pour soumission au fonds",
    "submitted_to_intermediary": "Soumis à l'intermédiaire",
    "submitted_to_fund": "Soumis au fonds",
    "under_review": "En cours d'examen",
    "accepted": "Accepté",
    "rejected": "Rejeté",
}

# Matrice de transitions autorisees
# Cle = statut actuel, valeur = liste de statuts cibles autorises
VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["preparing_documents"],
    "preparing_documents": ["in_progress"],
    "in_progress": ["review"],
    "review": ["ready_for_intermediary", "ready_for_fund", "in_progress"],
    "ready_for_intermediary": ["submitted_to_intermediary", "review"],
    "ready_for_fund": ["submitted_to_fund", "review"],
    "submitted_to_intermediary": ["submitted_to_fund", "review"],
    "submitted_to_fund": ["under_review"],
    "under_review": ["accepted", "rejected"],
    "accepted": [],
    "rejected": [],
}


# --- Modele ---


class FundApplication(Auditable, UUIDMixin, TimestampMixin, Base):
    """Dossier de candidature a un fonds vert."""

    __tablename__ = "fund_applications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fund_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("funds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # F02 — multi-tenant
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fund_matches.id", ondelete="SET NULL"),
        nullable=True,
    )
    intermediary_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intermediaries.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_type: Mapped[TargetType] = mapped_column(
        Enum(TargetType, name="target_type_app_enum", create_constraint=True),
        nullable=False,
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(
            ApplicationStatus,
            name="application_status_enum",
            create_constraint=True,
        ),
        nullable=False,
        default=ApplicationStatus.draft,
    )
    sections: Mapped[dict] = mapped_column(
        JSON, nullable=False, server_default="{}"
    )
    checklist: Mapped[list] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )
    intermediary_prep: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
    simulation: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # F04 — Snapshot immuable à la transition submitted_*
    snapshot_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    snapshot_data: Mapped[dict | None] = mapped_column(
        JSONType, nullable=True,
    )

    # Relations
    fund: Mapped["Fund"] = relationship("Fund", lazy="selectin")
    intermediary: Mapped["Intermediary | None"] = relationship(
        "Intermediary", lazy="selectin"
    )
