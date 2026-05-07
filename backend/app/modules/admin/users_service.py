"""Service admin — gestion des utilisateurs (F09).

Fonctionnalités :
- ``initiate_password_reset`` : un admin déclenche le reset → token plain
  généré (URL-safe), hash sha256 stocké en BDD, email envoyé via le service
  email configuré (``console`` en MVP).
- ``complete_password_reset`` : un utilisateur consomme le token → vérifie
  expiration / réutilisation, hash le nouveau mot de passe (bcrypt) et
  marque ``used_at = now()``.
- ``toggle_user_active`` : bascule ``is_active`` avec motif obligatoire et
  audit log.

Toutes les opérations passent par audit log F03 via :func:`log_admin_action`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email_service import (
    EmailServiceProtocol,
    build_reset_link,
    get_email_service,
)
from app.core.security import (
    generate_reset_token,
    hash_password,
    hash_token,
)
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.modules.admin.audit_helpers import log_admin_action

logger = logging.getLogger(__name__)


RESET_TOKEN_TTL = timedelta(hours=1)


class ResetTokenError(Exception):
    """Base : erreur métier sur reset token."""


class ResetTokenInvalidError(ResetTokenError):
    """Token absent ou inconnu."""


class ResetTokenExpiredError(ResetTokenError):
    """Token expiré (au-delà de 1h)."""


class ResetTokenAlreadyUsedError(ResetTokenError):
    """Token déjà consommé."""


async def initiate_password_reset(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    admin_id: uuid.UUID,
    email_service: EmailServiceProtocol | None = None,
) -> tuple[PasswordResetToken, str]:
    """Déclencher un reset de mot de passe pour ``user_id``.

    Retourne ``(token_row, plain_token)``. Le ``plain_token`` n'est JAMAIS
    persisté en BDD ; il est utilisé pour construire le lien email puis
    perdu côté serveur.
    """
    # Vérifier que l'utilisateur existe
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if user is None:
        raise ResetTokenInvalidError(f"User {user_id} introuvable")

    plain = generate_reset_token()
    token_row = PasswordResetToken(
        user_id=user_id,
        token_hash=hash_token(plain),
        expires_at=datetime.now(timezone.utc) + RESET_TOKEN_TTL,
    )
    db.add(token_row)
    await db.flush()

    # Email
    service = email_service or get_email_service()
    reset_link = build_reset_link(plain)
    email_result = await service.send_password_reset_email(
        user_email=user.email,
        reset_link=reset_link,
    )

    # Audit log
    await log_admin_action(
        db,
        admin_id=admin_id,
        action="reset_password_initiated",
        entity_type="user",
        entity_id=user_id,
        metadata={
            "expires_at": token_row.expires_at.isoformat(),
            "email_backend": email_result.backend,
            "email_sent": email_result.success,
        },
        account_id=user.account_id,
    )

    return token_row, plain


async def complete_password_reset(
    db: AsyncSession,
    *,
    plain_token: str,
    new_password: str,
) -> User:
    """Consommer un token de reset et changer le mot de passe.

    Lève les exceptions métier dédiées en cas d'erreur (à mapper en 400 par
    le router). Retourne le :class:`User` mis à jour.
    """
    if not plain_token or len(plain_token) < 20:
        raise ResetTokenInvalidError("Token absent ou trop court")

    token_hash = hash_token(plain_token)
    res = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash
        )
    )
    token_row = res.scalar_one_or_none()
    if token_row is None:
        raise ResetTokenInvalidError("Token inconnu")

    if token_row.used_at is not None:
        raise ResetTokenAlreadyUsedError("Token déjà utilisé")

    now = datetime.now(timezone.utc)
    expires_at = token_row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise ResetTokenExpiredError("Token expiré")

    user_res = await db.execute(select(User).where(User.id == token_row.user_id))
    user = user_res.scalar_one_or_none()
    if user is None:
        raise ResetTokenInvalidError("User introuvable")

    user.hashed_password = hash_password(new_password)
    token_row.used_at = now
    await db.flush()

    return user


async def toggle_user_active(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    admin_id: uuid.UUID,
    reason: str,
) -> User:
    """Basculer l'attribut ``is_active`` d'un utilisateur avec motif obligatoire."""
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if user is None:
        raise ValueError(f"User {user_id} introuvable")

    new_state = not user.is_active
    user.is_active = new_state
    await db.flush()

    await log_admin_action(
        db,
        admin_id=admin_id,
        action="user_toggled_active",
        entity_type="user",
        entity_id=user_id,
        metadata={"new_state": new_state, "reason": reason},
        account_id=user.account_id,
    )
    return user
