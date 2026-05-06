"""Dépendances communes pour les routers FastAPI."""

import logging
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.core.database import get_db
from app.core.email_delivery import EmailDeliveryService, LoggingEmailDelivery
from app.core.rls_session import set_rls_context
from app.core.security import decode_token
from app.models.account import Account
from app.models.user import User

logger = logging.getLogger(__name__)

security_scheme = HTTPBearer(auto_error=False)


# Singleton module pour l'EmailDeliveryService (LoggingEmailDelivery en MVP F02).
_email_service: EmailDeliveryService = LoggingEmailDelivery()


def get_email_service() -> EmailDeliveryService:
    """Dépendance FastAPI : retourne le service de livraison d'emails."""
    return _email_service


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extraire et valider l'utilisateur courant depuis le token JWT.

    F02 : positionne aussi les variables de session PostgreSQL (RLS) avant
    toute requête métier ultérieure dans la transaction. Vérifie également
    que l'`Account` parent est actif (sinon 403).
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'authentification manquant",
        )

    user_id = decode_token(credentials.credentials, expected_type="access")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
        )

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
        )

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable ou inactif",
        )

    # F02 — Vérifier que l'Account du user est actif (sinon 403).
    if user.account_id is not None:
        account_result = await db.execute(
            select(Account).where(Account.id == user.account_id)
        )
        account = account_result.scalar_one_or_none()
        if account is None or not account.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ce compte est temporairement désactivé",
            )

    # F02 — Positionner le contexte RLS PostgreSQL pour la transaction courante.
    await set_rls_context(db, user.account_id, user.role, user.id)

    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dépendance pour les endpoints réservés aux Admin.

    Lève HTTP 403 si l'utilisateur n'a pas le rôle Admin.
    """
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs",
        )
    return current_user
