"""Schémas Pydantic v2 pour le module Account (F02)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.constants import InvitationStatus, UserRole


class AccountSummary(BaseModel):
    """Résumé public d'un compte (PME)."""

    id: uuid.UUID
    name: str
    is_active: bool
    plan: str = "free"

    model_config = ConfigDict(from_attributes=True)


class AccountMemberSummary(BaseModel):
    """Résumé d'un membre actif d'un Account."""

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvitationCreate(BaseModel):
    """Body de création d'une invitation."""

    email: EmailStr


class InvitationInviter(BaseModel):
    """Sous-objet : invitant d'une invitation."""

    id: uuid.UUID
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class InvitationResponse(BaseModel):
    """Représentation d'une invitation côté API."""

    id: uuid.UUID
    email: EmailStr
    status: InvitationStatus
    expires_at: datetime
    invited_by: InvitationInviter
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccountUsersResponse(BaseModel):
    """Liste des membres d'un compte + invitations en cours."""

    members: list[AccountMemberSummary] = Field(default_factory=list)
    pending_invitations: list[InvitationResponse] = Field(default_factory=list)
