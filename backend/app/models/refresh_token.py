"""Modèle SQLAlchemy RefreshToken (F02 — rotation et révocation)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class RefreshToken(UUIDMixin, Base):
    """Audit-friendly enregistrement d'un refresh token JWT émis.

    À chaque rotation, l'ancien refresh token est révoqué (``revoked_at``)
    et un lien ``replaced_by_jti`` pointe vers le successeur. Une fenêtre de
    grâce (cf. ``REFRESH_TOKEN_GRACE_WINDOW_SECONDS``) tolère un replay
    immédiat (cas multi-onglets) en retournant le successeur déjà émis.
    """

    __tablename__ = "refresh_tokens"

    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    replaced_by_jti: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_refresh_tokens_user_id", "user_id"),
        # Index partiel sur les tokens actifs (PostgreSQL only ; pas de
        # postgresql_where en SQLite mais reste valide en métadata Alembic).
        Index(
            "idx_refresh_tokens_active",
            "user_id",
            "revoked_at",
        ),
    )
