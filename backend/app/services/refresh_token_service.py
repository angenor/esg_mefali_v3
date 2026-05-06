"""Service de gestion des refresh tokens (F02).

Implémente :
- ``persist_refresh_token`` : enregistrer un nouveau refresh token actif.
- ``rotate_refresh_token`` : révoquer un ancien token et émettre un successeur,
  avec gestion de la fenêtre de grâce (5 s par défaut) pour le multi-onglets.
- ``revoke_all_refresh_tokens`` : révoquer tous les tokens actifs d'un user
  (utilisé par /auth/logout et lors de la désactivation d'un Account).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.refresh_token import RefreshToken

logger = logging.getLogger(__name__)


async def persist_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    jti: str,
    expires_at: datetime,
) -> RefreshToken:
    """Insérer un nouveau refresh token en base."""
    token = RefreshToken(
        jti=jti,
        user_id=user_id,
        expires_at=expires_at,
    )
    db.add(token)
    await db.flush()
    return token


async def get_refresh_token_by_jti(
    db: AsyncSession, jti: str
) -> RefreshToken | None:
    """Récupérer un refresh token par son JTI."""
    result = await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
    return result.scalar_one_or_none()


async def rotate_refresh_token(
    db: AsyncSession,
    old_jti: str,
    new_jti: str,
    user_id: uuid.UUID,
    new_expires_at: datetime,
) -> tuple[RefreshToken, str]:
    """Rotation : révoque l'ancien token, émet un nouveau, retourne (nouveau, action).

    ``action`` est ``"new"`` (rotation normale) ou ``"grace_window_reuse"``
    (replay dans la fenêtre de grâce, on retourne le successeur déjà émis sans
    en créer un nouveau).

    Lève ValueError si l'ancien token est inconnu, ou si replay hors fenêtre.
    """
    old_token = await get_refresh_token_by_jti(db, old_jti)
    if old_token is None:
        raise ValueError("refresh_token_unknown")

    if old_token.user_id != user_id:
        raise ValueError("refresh_token_user_mismatch")

    now = datetime.now(timezone.utc)

    # Cas 1 : token déjà révoqué — vérifier la fenêtre de grâce.
    if old_token.revoked_at is not None:
        revoked_dt = old_token.revoked_at
        if revoked_dt.tzinfo is None:
            revoked_dt = revoked_dt.replace(tzinfo=timezone.utc)
        elapsed = (now - revoked_dt).total_seconds()
        grace = settings.refresh_token_grace_window_seconds
        if elapsed <= grace and old_token.replaced_by_jti:
            logger.warning(
                "grace_window_reuse jti=%s replaced_by=%s elapsed=%.2fs",
                old_jti,
                old_token.replaced_by_jti,
                elapsed,
            )
            successor = await get_refresh_token_by_jti(
                db, old_token.replaced_by_jti
            )
            if successor is None:
                raise ValueError("refresh_token_replay")
            return successor, "grace_window_reuse"
        # Hors fenêtre : replay attaque/erreur.
        logger.warning(
            "refresh_token_replay jti=%s elapsed=%.2fs grace=%ss",
            old_jti,
            elapsed,
            grace,
        )
        raise ValueError("refresh_token_replay")

    # Cas 2 : token actif — rotation normale.
    new_token = RefreshToken(
        jti=new_jti,
        user_id=user_id,
        expires_at=new_expires_at,
    )
    db.add(new_token)
    await db.flush()

    old_token.revoked_at = now
    old_token.replaced_by_jti = new_jti
    await db.flush()

    return new_token, "new"


async def revoke_all_refresh_tokens(
    db: AsyncSession, user_id: uuid.UUID
) -> int:
    """Révoque tous les refresh tokens actifs d'un utilisateur.

    Retourne le nombre de tokens révoqués.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    result = await db.execute(stmt)
    return result.rowcount or 0


def compute_refresh_token_expiry() -> datetime:
    """Calcule la date d'expiration d'un nouveau refresh token."""
    return datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
