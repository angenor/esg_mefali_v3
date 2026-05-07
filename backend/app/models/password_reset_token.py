"""Modèle SQLAlchemy ``PasswordResetToken`` (F09 — Reset password admin).

Token de réinitialisation de mot de passe émis par un admin pour le compte
d'un utilisateur. Le token plain est envoyé par email à l'utilisateur ; en
BDD on ne conserve que son hash sha256 (sécurité).

Workflow :
1. Admin déclenche reset → backend crée ``PasswordResetToken(token_hash,
   expires_at = now + 1h)`` puis envoie email à l'utilisateur (lien
   ``/auth/reset?token=<plain>``).
2. Utilisateur soumet le formulaire → backend hash le plain, cherche en
   BDD, vérifie ``expires_at`` et ``used_at IS NULL``, met à jour le
   password puis marque ``used_at = now()``.

Référence : ``specs/035-f09-back-office-admin/data-model.md`` (FR-016).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class PasswordResetToken(UUIDMixin, Base):
    """Token de réinitialisation de mot de passe (F09)."""

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User")

    def __repr__(self) -> str:  # pragma: no cover - debugging
        return (
            f"<PasswordResetToken id={self.id} user_id={self.user_id} "
            f"used={self.used_at is not None}>"
        )
