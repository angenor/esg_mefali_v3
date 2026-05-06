"""Modèle SQLAlchemy User (étendu F02 avec rôle et account_id)."""

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import UserRole
from app.models.base import Base, TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    """Représente un utilisateur inscrit sur la plateforme.

    F02 ajoute :
    - ``role`` : ``PME`` (par défaut) ou ``ADMIN``.
    - ``account_id`` : référence l'`Account` parent. NULL pour un Admin.

    Une contrainte CHECK garantit la cohérence rôle / account_id :
    - PME : account_id NOT NULL
    - ADMIN : account_id NULL
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # F02 — multi-tenant + rôles
    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=UserRole.PME.value,
        server_default=UserRole.PME.value,
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # Relations
    account = relationship("Account", foreign_keys=[account_id])

    __table_args__ = (
        CheckConstraint(
            "(role = 'PME' AND account_id IS NOT NULL) OR "
            "(role = 'ADMIN' AND account_id IS NULL)",
            name="users_role_account_consistency",
        ),
        Index("idx_users_account_id", "account_id"),
        Index("idx_users_role", "role"),
    )
