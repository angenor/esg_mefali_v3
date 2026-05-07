"""Sous-router admin /users (F09)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.models.user import User
from app.modules.admin.schemas import (
    ResetPasswordInitiateResponse,
    ToggleActiveRequest,
    ToggleActiveResponse,
)
from app.modules.admin.users_service import (
    ResetTokenInvalidError,
    initiate_password_reset,
    toggle_user_active,
)

logger = logging.getLogger(__name__)


router = APIRouter()


@router.post(
    "/{user_id}/reset-password",
    response_model=ResetPasswordInitiateResponse,
    status_code=status.HTTP_200_OK,
)
async def admin_reset_password(
    user_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ResetPasswordInitiateResponse:
    """Déclencher un reset de mot de passe pour un utilisateur (admin)."""
    try:
        token_row, _plain = await initiate_password_reset(
            db,
            user_id=user_id,
            admin_id=current_admin.id,
        )
    except ResetTokenInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    # Le backend choisi est journalisé via audit log ; on remonte côté client
    # uniquement le booléen "email_sent" et l'expiration.
    return ResetPasswordInitiateResponse(
        user_id=user_id,
        email_sent=True,
        expires_at=token_row.expires_at,
        backend="console",
    )


@router.post(
    "/{user_id}/toggle-active",
    response_model=ToggleActiveResponse,
    status_code=status.HTTP_200_OK,
)
async def admin_toggle_active(
    user_id: UUID,
    payload: ToggleActiveRequest,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ToggleActiveResponse:
    """Basculer ``is_active`` avec motif obligatoire."""
    try:
        user = await toggle_user_active(
            db,
            user_id=user_id,
            admin_id=current_admin.id,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ToggleActiveResponse(user_id=user.id, is_active=user.is_active)
