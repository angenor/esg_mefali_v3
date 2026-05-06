"""Service métier pour les invitations et la gestion des membres d'un Account (F02)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import InvitationStatus, UserRole
from app.core.email_delivery import (
    EmailDeliveryService,
    format_invitation_body,
    format_invitation_subject,
)
from app.models.account import Account
from app.models.account_invitation import AccountInvitation
from app.models.user import User
from app.modules.account.tokens import (
    compute_token_lookup,
    generate_invite_token,
    hash_invite_token,
)
from app.services.refresh_token_service import revoke_all_refresh_tokens

logger = logging.getLogger(__name__)


class InvitationConflict(Exception):
    """Une invitation pending existe déjà pour cet email/account."""


class LastMemberError(Exception):
    """Tentative de retirer le dernier membre actif d'un Account."""


async def create_invitation(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    email: str,
    invited_by_user: User,
    email_service: EmailDeliveryService,
    invitation_url_template: str,
) -> tuple[AccountInvitation, str]:
    """Créer une invitation et déclencher l'envoi d'email (stub MVP).

    Retourne ``(invitation, raw_token)`` (le token clair n'est utilisé qu'ici
    pour construire le lien d'invitation et n'est jamais persisté).

    Lève ``InvitationConflict`` si une invitation pending existe déjà pour cet
    email sur cet Account.
    """
    # Vérifier qu'il n'y a pas déjà une invitation pending pour cet email.
    existing_stmt = select(AccountInvitation).where(
        AccountInvitation.account_id == account_id,
        AccountInvitation.email == email,
        AccountInvitation.status == InvitationStatus.PENDING.value,
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing is not None:
        raise InvitationConflict(
            f"Une invitation est déjà en attente pour {email}"
        )

    # Générer le token + hash + lookup.
    raw_token = generate_invite_token()
    token_hash = hash_invite_token(raw_token)
    token_lookup = compute_token_lookup(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.invite_token_ttl_days
    )

    invitation = AccountInvitation(
        account_id=account_id,
        email=email,
        token_hash=token_hash,
        token_lookup=token_lookup,
        invited_by_user_id=invited_by_user.id,
        status=InvitationStatus.PENDING.value,
        expires_at=expires_at,
    )
    db.add(invitation)
    await db.flush()

    # Construire et envoyer l'email d'invitation.
    invitation_url = invitation_url_template.format(token=raw_token)
    account_result = await db.execute(
        select(Account).where(Account.id == account_id)
    )
    account = account_result.scalar_one()
    subject = format_invitation_subject(account.name)
    body = format_invitation_body(invitation, invitation_url)
    await email_service.send(to=email, subject=subject, body=body)

    return invitation, raw_token


async def list_account_users(
    db: AsyncSession, account_id: uuid.UUID
) -> tuple[list[User], list[AccountInvitation]]:
    """Lister les membres actifs et les invitations en cours d'un Account."""
    members_stmt = (
        select(User)
        .where(User.account_id == account_id, User.is_active.is_(True))
        .order_by(User.created_at.asc())
    )
    members = list((await db.execute(members_stmt)).scalars().all())

    invitations_stmt = (
        select(AccountInvitation)
        .where(
            AccountInvitation.account_id == account_id,
            AccountInvitation.status == InvitationStatus.PENDING.value,
        )
        .order_by(AccountInvitation.created_at.desc())
    )
    invitations = list((await db.execute(invitations_stmt)).scalars().all())
    return members, invitations


async def remove_account_user(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    target_user_id: uuid.UUID,
) -> User:
    """Retirer un membre de l'Account (soft delete + révocation tokens).

    Lève ``LastMemberError`` si c'est le dernier membre actif.
    """
    # Vérifier qu'au moins un autre membre actif restera.
    count_stmt = select(func.count(User.id)).where(
        User.account_id == account_id, User.is_active.is_(True)
    )
    active_count = (await db.execute(count_stmt)).scalar_one()
    if active_count <= 1:
        raise LastMemberError(
            "Impossible de retirer le dernier membre actif du compte"
        )

    user_result = await db.execute(
        select(User).where(
            User.id == target_user_id,
            User.account_id == account_id,
        )
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise ValueError("Utilisateur introuvable dans ce compte")

    user.is_active = False
    await revoke_all_refresh_tokens(db, user.id)
    await db.flush()
    return user


async def revoke_invitation(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    invitation_id: uuid.UUID,
) -> AccountInvitation:
    """Révoquer une invitation pending."""
    result = await db.execute(
        select(AccountInvitation).where(
            AccountInvitation.id == invitation_id,
            AccountInvitation.account_id == account_id,
        )
    )
    invitation = result.scalar_one_or_none()
    if invitation is None:
        raise ValueError("Invitation introuvable")
    if invitation.status != InvitationStatus.PENDING.value:
        raise ValueError("Cette invitation n'est plus pending")
    invitation.status = InvitationStatus.REVOKED.value
    await db.flush()
    return invitation
