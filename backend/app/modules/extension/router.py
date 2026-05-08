"""Router FastAPI pour l'extension Chrome (F24).

Expose 4 endpoints sous ``/api/extension/v1/*`` :
- ``POST /auth/exchange`` (public)
- ``GET /me/profile-snapshot`` (auth)
- ``POST /detect`` (auth)
- ``GET /applications/active`` (auth)
"""

from __future__ import annotations

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
)
from app.models.account import Account
from app.models.user import User
from app.modules.extension.dependencies import get_current_extension_user
from app.modules.extension.schemas import (
    ActiveApplicationItem,
    AuthExchangeRequest,
    AuthExchangeResponse,
    DetectRequest,
    DetectResponse,
    ProfileSnapshot,
)
from app.modules.extension.service import (
    build_profile_snapshot,
    list_active_applications,
    match_url,
)
from app.services.refresh_token_service import persist_refresh_token

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/auth/exchange",
    response_model=AuthExchangeResponse,
    status_code=status.HTTP_200_OK,
)
async def exchange_credentials(
    data: AuthExchangeRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthExchangeResponse:
    """Échange identifiants → tokens scope=extension.

    Émet un access token (TTL standard) + un refresh token persistant
    (table ``refresh_tokens.scope='extension'``).
    """
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte utilisateur inactif",
        )
    if user.account_id is not None:
        account_res = await db.execute(
            select(Account).where(Account.id == user.account_id)
        )
        account = account_res.scalar_one_or_none()
        if account is None or not account.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ce compte est temporairement désactivé",
            )

    access_token = create_access_token(str(user.id))
    refresh_token_str, jti, expires_at = create_refresh_token(str(user.id))
    token_row = await persist_refresh_token(db, user.id, jti, expires_at)
    # F24 : marquer le refresh_token comme issu de l'extension.
    token_row.scope = "extension"
    await db.flush()
    await db.commit()

    expires_in = int(
        timedelta(days=settings.refresh_token_expire_days).total_seconds()
    )
    return AuthExchangeResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        scope="extension",
        expires_in=expires_in,
    )


@router.get(
    "/me/profile-snapshot",
    response_model=ProfileSnapshot,
)
async def get_profile_snapshot(
    user: User = Depends(get_current_extension_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileSnapshot:
    """Snapshot profil entreprise (sector, country) + 3 derniers projets actifs."""
    return await build_profile_snapshot(db, user.id, user.account_id)


@router.post(
    "/detect",
    response_model=DetectResponse,
    responses={204: {"description": "Aucune offre ne matche cette URL."}},
)
async def detect_offer(
    data: DetectRequest,
    user: User = Depends(get_current_extension_user),
    db: AsyncSession = Depends(get_db),
) -> Response | DetectResponse:
    """Détecte si l'URL fournie correspond à une offre publiée."""
    match = await match_url(db, data.url)
    if match is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return match


@router.get(
    "/applications/active",
    response_model=list[ActiveApplicationItem],
)
async def get_active_applications(
    user: User = Depends(get_current_extension_user),
    db: AsyncSession = Depends(get_db),
) -> list[ActiveApplicationItem]:
    """Liste des candidatures actives (statuts non finaux), tri date desc, max 50."""
    return await list_active_applications(db, user.id)
