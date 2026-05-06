"""Modèle SQLAlchemy AccountInvitation (F02 — invitations d'équipe PME)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import InvitationStatus
from app.models.base import Base, TimestampMixin, UUIDMixin


class AccountInvitation(UUIDMixin, TimestampMixin, Base):
    """Invitation envoyée par un PME à un futur collaborateur.

    Le token clair est transmis dans le lien d'invitation (jamais stocké).
    En BDD on conserve :
    - ``token_hash`` : bcrypt du token (vérification)
    - ``token_lookup`` : SHA256 hex du token (lookup déterministe rapide)
    """

    __tablename__ = "account_invitations"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    token_lookup: Mapped[str] = mapped_column(String(64), nullable=False)
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=InvitationStatus.PENDING.value,
        server_default=InvitationStatus.PENDING.value,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accepted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relations
    account = relationship("Account", foreign_keys=[account_id])
    invited_by = relationship("User", foreign_keys=[invited_by_user_id])
    accepted_by = relationship("User", foreign_keys=[accepted_by_user_id])

    __table_args__ = (
        Index("idx_invitations_account_id", "account_id"),
        Index("idx_invitations_email_status", "email", "status"),
        Index("idx_invitations_status_expires_at", "status", "expires_at"),
        Index("idx_invitations_token_lookup", "token_lookup", unique=True),
    )
