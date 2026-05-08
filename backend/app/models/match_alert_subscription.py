"""Modèle SQLAlchemy ``MatchAlertSubscription`` (F14).

Souscription par projet aux alertes nouvelles offres compatibles.
Multi-tenant via ``account_id`` (F02), Auditable (F03).
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.auditable import Auditable
from app.models.base import Base, TimestampMixin, UUIDMixin


class MatchAlertSubscription(Auditable, UUIDMixin, TimestampMixin, Base):
    """Souscription d'alertes nouvelles offres compatibles pour un projet."""

    __tablename__ = "match_alerts_subscriptions"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    min_global_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60, server_default="60",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true",
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id", name="uq_match_alerts_subscription_project",
        ),
        CheckConstraint(
            "min_global_score BETWEEN 0 AND 100",
            name="match_alerts_subscription_min_score_chk",
        ),
        Index(
            "idx_match_alerts_account_active",
            "account_id", "is_active",
        ),
    )
