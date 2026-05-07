"""Modèle SQLAlchemy ``Offer`` (F07 — entité Offre = Couple Fonds × Intermédiaire).

Une Offre représente l'unité commercialement actionnable côté PME : c'est
le couple (Fonds, Intermédiaire) qui peut être candidaté. Le calcul
``compute_effective_offer`` produit les champs ``effective_*`` (intersection
des critères, union des documents requis, somme des frais et délais).

Catalogue global (pas d'``account_id``), édition admin only. Aucun mixin
``Auditable`` (cohérent avec la policy F03 catalogue exempt).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.source import JSONType, PublicationStatus
from app.models.versioning_mixin import VersioningMixin

if TYPE_CHECKING:
    from app.models.financing import Fund, Intermediary
    from app.models.source import Source


class Offer(UUIDMixin, TimestampMixin, VersioningMixin, Base):
    """Offre = couple Fonds × Intermédiaire.

    F07 : entité commercialement actionnable côté PME. Catalogue global
    (pas d'``account_id``), édition réservée aux admins.

    Le couple ``(fund_id, intermediary_id, version)`` est unique : pour créer
    une « v2 » de la même offre, l'admin doit incrémenter ``version``.
    """

    __tablename__ = "offers"

    fund_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("funds.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    intermediary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intermediaries.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    accepted_languages: Mapped[list[str]] = mapped_column(
        JSONType, nullable=False, server_default='["FR"]', default=lambda: ["FR"],
    )
    target_sector: Mapped[list[str] | None] = mapped_column(JSONType, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    effective_criteria: Mapped[dict[str, Any]] = mapped_column(
        JSONType, nullable=False, server_default="{}", default=dict,
    )
    effective_required_documents: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONType, nullable=False, server_default="[]", default=list,
    )
    effective_fees: Mapped[dict[str, Any]] = mapped_column(
        JSONType, nullable=False, server_default="{}", default=dict,
    )
    effective_processing_time_days_min: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    effective_processing_time_days_max: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    effective_disbursement_time_days_min: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    effective_disbursement_time_days_max: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true",
    )
    publication_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PublicationStatus.DRAFT.value,
        server_default=PublicationStatus.DRAFT.value,
        index=True,
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Relations
    fund: Mapped["Fund"] = relationship("Fund", lazy="selectin")
    intermediary: Mapped["Intermediary"] = relationship(
        "Intermediary", lazy="selectin",
    )
    source: Mapped["Source"] = relationship("Source", lazy="selectin")

    __table_args__ = (
        UniqueConstraint(
            "fund_id", "intermediary_id", "version",
            name="uq_offers_fund_intermediary_version",
        ),
        CheckConstraint(
            "publication_status IN ('draft', 'published')",
            name="offers_publication_status_chk",
        ),
        CheckConstraint(
            "effective_processing_time_days_min IS NULL "
            "OR effective_processing_time_days_max IS NULL "
            "OR effective_processing_time_days_min <= effective_processing_time_days_max",
            name="offers_processing_time_consistency_chk",
        ),
        CheckConstraint(
            "effective_disbursement_time_days_min IS NULL "
            "OR effective_disbursement_time_days_max IS NULL "
            "OR effective_disbursement_time_days_min <= effective_disbursement_time_days_max",
            name="offers_disbursement_time_consistency_chk",
        ),
        CheckConstraint(
            "publication_status = 'draft' OR is_active = TRUE",
            name="offers_published_active_chk",
        ),
        Index(
            "idx_offers_fund_intermediary_valid_to",
            "fund_id", "intermediary_id", "valid_to",
        ),
    )
