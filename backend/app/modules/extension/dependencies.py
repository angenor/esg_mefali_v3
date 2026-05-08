"""Dépendances FastAPI pour l'extension Chrome (F24).

Vérifie que le bearer token a bien été émis avec ``scope='extension'`` afin
qu'un access token web standard ne donne pas accès au endpoints extension
(par défense en profondeur — l'API tolère néanmoins les tokens web pour
ergonomie en MVP, voir ``ALLOW_WEB_TOKENS``).
"""

from __future__ import annotations

import logging
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rls_session import set_rls_context
from app.core.security import decode_token
from app.models.account import Account
from app.models.user import User

logger = logging.getLogger(__name__)

security_scheme = HTTPBearer(auto_error=False)


async def get_current_extension_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Vérifie le bearer + RLS + actif. Retourne l'utilisateur authentifié.

    NB MVP : on n'exige pas formellement le claim ``scope='extension'`` dans
    l'access token — le JWT actuel n'embarque pas cette info, et l'extension
    réutilise l'infra access token F02 (TTL 24 h). Le scope est porté par le
    refresh token (table ``refresh_tokens.scope='extension'``), permettant
    une révocation ciblée admin si besoin.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'authentification manquant",
        )

    user_id_str = decode_token(credentials.credentials, expected_type="access")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
        )

    try:
        user_uuid = uuid.UUID(user_id_str)
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

    await set_rls_context(db, user.account_id, user.role, user.id)
    return user
