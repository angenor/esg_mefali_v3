"""Modèle SQLAlchemy Account (F02 — multi-tenant ; F05 — suppression compte)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Account(UUIDMixin, TimestampMixin, Base):
    """Compte PME : collectivité d'utilisateurs sous une même entreprise.

    Un Account est l'unité fondamentale du multi-tenant : chaque ligne d'une
    table métier appartient à exactement un Account, et la Row-Level Security
    PostgreSQL filtre l'accès via la variable de session ``app.current_account_id``.

    F05 ajoute :
    - ``deletion_scheduled_at`` : date programmée de purge effective (J+30).
    - ``deleted_at`` : date de purge effective.
    - ``purge_in_progress`` : flag idempotence du cron de purge.
    """

    __tablename__ = "accounts"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    # Plan tarifaire — préparé pour post-MVP, défaut "free".
    plan: Mapped[str] = mapped_column(
        String(32), nullable=False, default="free", server_default="free"
    )

    # F05 — suppression de compte avec délai de grâce + purge effective.
    deletion_scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    purge_in_progress: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    __table_args__ = (
        Index("idx_accounts_is_active", "is_active"),
        Index(
            "idx_accounts_deletion_scheduled",
            "deletion_scheduled_at",
            postgresql_where=text("deletion_scheduled_at IS NOT NULL"),
            sqlite_where=text("deletion_scheduled_at IS NOT NULL"),
        ),
        Index(
            "idx_accounts_deleted",
            "deleted_at",
            postgresql_where=text("deleted_at IS NOT NULL"),
            sqlite_where=text("deleted_at IS NOT NULL"),
        ),
    )
