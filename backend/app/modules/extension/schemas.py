"""Schémas Pydantic v2 stricts pour l'extension Chrome (F24)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# --------------------------------------------------------------------------
# Auth — POST /auth/exchange
# --------------------------------------------------------------------------


class AuthExchangeRequest(BaseModel):
    """Body de la requête d'échange d'identifiants pour extension."""

    model_config = ConfigDict(strict=True, extra="forbid")

    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class AuthExchangeResponse(BaseModel):
    """Réponse contenant les tokens scoped extension."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    scope: Literal["extension"] = "extension"
    expires_in: int = Field(gt=0)


# --------------------------------------------------------------------------
# Profile snapshot — GET /me/profile-snapshot
# --------------------------------------------------------------------------


class ProjectSnapshotItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    name: str
    status: str


class ProfileSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sector: str | None = None
    country: str | None = None
    projects: list[ProjectSnapshotItem] = Field(default_factory=list, max_length=3)


# --------------------------------------------------------------------------
# Detect — POST /detect
# --------------------------------------------------------------------------


class DetectRequest(BaseModel):
    """Body de la requête de détection d'URL."""

    model_config = ConfigDict(strict=True, extra="forbid")

    url: str = Field(min_length=1, max_length=2000)

    @field_validator("url")
    @classmethod
    def validate_url_scheme(cls, v: str) -> str:
        """Vérifie que l'URL commence par http(s)://."""
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("L'URL doit commencer par http:// ou https://")
        return v


class DetectResponse(BaseModel):
    """Réponse de détection : une offre matche."""

    model_config = ConfigDict(extra="forbid")

    offer_id: uuid.UUID
    offer_name: str
    source_id: uuid.UUID | None = None
    confidence: float = Field(ge=0.0, le=1.0)


# --------------------------------------------------------------------------
# Applications active — GET /applications/active
# --------------------------------------------------------------------------


class ActiveApplicationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    offer_name: str
    status: str
    status_label_fr: str
    updated_at: datetime
    deep_link: str


# --------------------------------------------------------------------------
# Url patterns (config admin)
# --------------------------------------------------------------------------


class FundUrlPattern(BaseModel):
    """Pattern saisi sur Fund/Intermediary pour la détection extension."""

    model_config = ConfigDict(strict=True, extra="forbid")

    pattern: str = Field(min_length=1, max_length=500)
    scope: Literal["homepage", "submission_portal"]
