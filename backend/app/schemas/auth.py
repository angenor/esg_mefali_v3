"""Schemas Pydantic pour l'authentification."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.constants import UserRole
from app.schemas.account import AccountSummary


class RegisterRequest(BaseModel):
    """Données requises pour l'inscription.

    Si `invite_token` est fourni, l'utilisateur sera rattaché au compte de
    l'invitant au lieu de créer un nouvel `Account`. `company_name` peut être
    vide dans ce cas (l'`Account` cible donne déjà le nom).
    """

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    company_name: str = Field(default="", max_length=255)
    country: str | None = Field(default=None, max_length=100)
    invite_token: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    """Données requises pour la connexion."""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Données requises pour le rafraîchissement du token."""

    refresh_token: str


class TokenResponse(BaseModel):
    """Réponse contenant les jetons d'authentification."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """Profil utilisateur retourné par l'API."""

    id: uuid.UUID
    email: str
    full_name: str
    company_name: str
    role: UserRole = UserRole.PME
    account: AccountSummary | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class LogoutResponse(BaseModel):
    """Réponse vide d'un logout réussi (pour documentation OpenAPI)."""

    detail: str = "Déconnexion réussie"
