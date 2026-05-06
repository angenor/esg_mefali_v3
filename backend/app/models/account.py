"""Modèle SQLAlchemy Account (F02 — multi-tenant)."""

from sqlalchemy import Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Account(UUIDMixin, TimestampMixin, Base):
    """Compte PME : collectivité d'utilisateurs sous une même entreprise.

    Un Account est l'unité fondamentale du multi-tenant : chaque ligne d'une
    table métier appartient à exactement un Account, et la Row-Level Security
    PostgreSQL filtre l'accès via la variable de session ``app.current_account_id``.
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

    __table_args__ = (
        Index("idx_accounts_is_active", "is_active"),
    )
