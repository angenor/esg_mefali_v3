"""Endpoints REST pour la gestion des invitations d'équipe (F02)."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_email_service
from app.core.constants import UserRole
from app.core.database import get_db
from app.core.email_delivery import EmailDeliveryService
from app.models.user import User
from app.modules.account.service import (
    InvitationConflict,
    LastMemberError,
    create_invitation,
    list_account_users,
    remove_account_user,
    revoke_invitation,
)
from app.schemas.account import (
    AccountMemberSummary,
    AccountUsersResponse,
    InvitationCreate,
    InvitationInviter,
    InvitationResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _frontend_invitation_url(request: Request) -> str:
    """Construire le template d'URL d'invitation côté frontend."""
    # En MVP F02, on suppose que le frontend tourne sur http://localhost:3000.
    # On utilise l'origine si disponible (Origin header), sinon fallback.
    origin = request.headers.get("origin", "http://localhost:3000")
    return f"{origin}/register?invite={{token}}"


@router.post(
    "/invite",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    body: InvitationCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    email_service: EmailDeliveryService = Depends(get_email_service),
) -> InvitationResponse:
    """Créer une invitation pour un nouveau collaborateur.

    Réservé aux utilisateurs PME (un Admin n'a pas d'Account).
    """
    if current_user.role != UserRole.PME.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls les utilisateurs PME peuvent inviter des collaborateurs",
        )
    if current_user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun compte associé à cet utilisateur",
        )

    try:
        invitation, _raw_token = await create_invitation(
            db,
            account_id=current_user.account_id,
            email=body.email,
            invited_by_user=current_user,
            email_service=email_service,
            invitation_url_template=_frontend_invitation_url(request),
        )
    except InvitationConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    return InvitationResponse(
        id=invitation.id,
        email=invitation.email,
        status=invitation.status,
        expires_at=invitation.expires_at,
        invited_by=InvitationInviter(
            id=current_user.id, full_name=current_user.full_name
        ),
        created_at=invitation.created_at,
    )


@router.get("/users", response_model=AccountUsersResponse)
async def list_team(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AccountUsersResponse:
    """Lister les membres actifs et les invitations en cours du compte courant."""
    if current_user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun compte associé à cet utilisateur",
        )

    members, invitations = await list_account_users(db, current_user.account_id)
    member_payload = [
        AccountMemberSummary(
            id=m.id,
            email=m.email,
            full_name=m.full_name,
            role=m.role,
            is_active=m.is_active,
            joined_at=m.created_at,
        )
        for m in members
    ]
    invitation_payload = [
        InvitationResponse(
            id=inv.id,
            email=inv.email,
            status=inv.status,
            expires_at=inv.expires_at,
            invited_by=InvitationInviter(
                id=inv.invited_by_user_id or uuid.UUID(int=0),
                full_name=(
                    inv.invited_by.full_name
                    if inv.invited_by is not None
                    else "Utilisateur supprimé"
                ),
            ),
            created_at=inv.created_at,
        )
        for inv in invitations
    ]
    return AccountUsersResponse(
        members=member_payload, pending_invitations=invitation_payload
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Retirer un membre du compte (soft delete + révocation tokens)."""
    if current_user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun compte associé à cet utilisateur",
        )
    try:
        await remove_account_user(
            db, account_id=current_user.account_id, target_user_id=user_id
        )
    except LastMemberError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete(
    "/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def revoke_invitation_endpoint(
    invitation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Révoquer une invitation pending."""
    if current_user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun compte associé à cet utilisateur",
        )
    try:
        await revoke_invitation(
            db,
            account_id=current_user.account_id,
            invitation_id=invitation_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
