"""Modèle SQLAlchemy ``OfferMatch`` (F14 — Matching Projet ↔ Offre).

Persistance d'un match calculé entre un Projet (F06) et une Offre (F07).
Score décomposé fund_score / intermediary_score / global_score, identification
du goulot (bottleneck), critères manquants sourcés (F01) et actions recommandées.

Multi-tenant via ``account_id`` (F02), Auditable (F03) — toutes les mutations
sont tracées par le listener global ``before_flush``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.auditable import Auditable
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.source import JSONType


# --- Whitelists applicatives ---

OFFER_MATCH_BOTTLENECK_VALUES: frozenset[str] = frozenset({
    "fund",
    "intermediary",
    "balanced",
})

OFFER_MATCH_STATUS_VALUES: frozenset[str] = frozenset({
    "suggested",
    "viewed",
    "dismissed",
    "converted",
})


class OfferMatch(Auditable, UUIDMixin, TimestampMixin, Base):
    """Match déterministe Project ↔ Offer avec score décomposé.

    UNIQUE ``(project_id, offer_id)`` : un seul match courant par paire,
    le recompute = UPDATE in-place.
    """

    __tablename__ = "offer_matches"

    # Multi-tenant F02
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("offers.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Scores (0..100)
    global_score: Mapped[int] = mapped_column(Integer, nullable=False)
    fund_score: Mapped[int] = mapped_column(Integer, nullable=False)
    intermediary_score: Mapped[int] = mapped_column(Integer, nullable=False)

    # Détail du calcul
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(
        JSONType, nullable=False, server_default="{}", default=dict,
    )
    bottleneck: Mapped[str] = mapped_column(String(20), nullable=False)
    recommended_actions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONType, nullable=False, server_default="[]", default=list,
    )

    # Cycle de vie
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="suggested", server_default="suggested",
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    last_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Relations (lazy=selectin pour éviter N+1 dans les listings)
    project = relationship("Project", lazy="selectin", foreign_keys=[project_id])
    offer = relationship("Offer", lazy="selectin", foreign_keys=[offer_id])

    __table_args__ = (
        UniqueConstraint(
            "project_id", "offer_id", name="uq_offer_matches_project_offer",
        ),
        CheckConstraint(
            "global_score BETWEEN 0 AND 100",
            name="offer_matches_global_score_chk",
        ),
        CheckConstraint(
            "fund_score BETWEEN 0 AND 100",
            name="offer_matches_fund_score_chk",
        ),
        CheckConstraint(
            "intermediary_score BETWEEN 0 AND 100",
            name="offer_matches_intermediary_score_chk",
        ),
        CheckConstraint(
            "bottleneck IN ('fund','intermediary','balanced')",
            name="offer_matches_bottleneck_chk",
        ),
        CheckConstraint(
            "status IN ('suggested','viewed','dismissed','converted')",
            name="offer_matches_status_chk",
        ),
        Index(
            "idx_offer_matches_project_computed",
            "project_id", "computed_at",
        ),
        Index(
            "idx_offer_matches_account_expires",
            "account_id", "expires_at",
        ),
        Index("idx_offer_matches_offer", "offer_id"),
        Index(
            "idx_offer_matches_account_score",
            "account_id", "global_score",
        ),
    )
