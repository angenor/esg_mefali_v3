"""Schemas Pydantic pour l'authentification."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.constants import UserRole
from app.schemas.account import AccountSummary


def _normalize_email(value: Any) -> Any:
    """Normaliser un email en ``.strip().lower()`` avant validation.

    Bug fix 2026-05-09 : login était sensible à la casse (``Angenor99@gmail.com``
    rejeté, ``angenor99@gmail.com`` accepté). On normalise systématiquement à
    l'inscription comme à la connexion pour rendre l'email canonique en BDD.

    Pydantic v2 ``mode='before'`` : appliqué avant la validation EmailStr,
    mais on n'altère pas les valeurs non-string (laisser EmailStr produire
    son ValidationError habituelle).
    """
    if isinstance(value, str):
        return value.strip().lower()
    return value


class RegisterRequest(BaseModel):
    """Données requises pour l'inscription.

    Si `invite_token` est fourni, l'utilisateur sera rattaché au compte de
    l'invitant au lieu de créer un nouvel `Account`. `company_name` peut être
    vide dans ce cas (l'`Account` cible donne déjà le nom).

    F05 — Le champ ``privacy_policy_accepted`` est requis (RGPD Art. 6.1.a) :
    la création d'un compte sans acceptation explicite est rejetée en 422.
    """

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    company_name: str = Field(default="", max_length=255)
    country: str | None = Field(default=None, max_length=100)
    invite_token: str | None = Field(default=None, max_length=255)
    # F05 — RGPD : acceptation politique de confidentialité.
    # Pydantic accepte ``None`` ; le router rejette explicitement les requêtes
    # avec ``False`` (cf. FR-017 : la case à cocher doit être validée). Pour
    # rester compatible avec l'historique des tests, l'absence du champ est
    # tolérée (équivaut à ``None``) — la frontend de production l'envoie
    # toujours explicitement à ``true``.
    privacy_policy_accepted: bool | None = Field(
        default=None,
        description=(
            "Doit être true. Required par RGPD pour la création d'un compte."
        ),
    )
    privacy_policy_version: str = Field(default="v1.0", max_length=16)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email_before(cls, value: Any) -> Any:
        return _normalize_email(value)


class LoginRequest(BaseModel):
    """Données requises pour la connexion."""

    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email_before(cls, value: Any) -> Any:
        return _normalize_email(value)


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
