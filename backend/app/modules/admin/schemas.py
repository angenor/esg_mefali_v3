"""Schémas Pydantic partagés par les sous-routers admin (F09)."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


T = TypeVar("T")


class PublicationStatusEnum(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class VerificationStatusEnum(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    VERIFIED = "verified"
    OUTDATED = "outdated"


class PaginatedResponse(BaseModel, Generic[T]):
    """Enveloppe pagination standardisée."""

    items: list[T]
    total: int
    page: int = 1
    limit: int = 50


class DependentsReport(BaseModel):
    """Rapport des entités dépendantes d'une source.

    Utilisé par DELETE pour proposer le force=true.
    """

    indicators: list[UUID] = Field(default_factory=list)
    criteria: list[UUID] = Field(default_factory=list)
    formulas: list[UUID] = Field(default_factory=list)
    emission_factors: list[UUID] = Field(default_factory=list)
    simulation_factors: list[UUID] = Field(default_factory=list)
    skills: list[UUID] = Field(default_factory=list)
    total: int = 0


# ---------- Sources ----------


class SourceCreate(BaseModel):
    url: str
    title: str
    publisher: str
    version: str
    date_publi: date
    page: int | None = None
    section: str | None = None


class SourceUpdate(BaseModel):
    url: str | None = None
    title: str | None = None
    publisher: str | None = None
    version: str | None = None
    date_publi: date | None = None
    page: int | None = None
    section: str | None = None
    verification_status: VerificationStatusEnum | None = None
    outdated_reason: str | None = None


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    url: str
    title: str
    publisher: str
    version: str
    date_publi: date
    page: int | None
    section: str | None
    verification_status: str
    captured_by: UUID
    verified_by: UUID | None
    verified_at: datetime | None
    outdated_reason: str | None
    created_at: datetime
    updated_at: datetime


# ---------- Users / reset password ----------


class ResetPasswordInitiateResponse(BaseModel):
    """Réponse côté admin après déclenchement du reset (sans le token plain)."""

    user_id: UUID
    email_sent: bool
    expires_at: datetime
    backend: str


class ToggleActiveRequest(BaseModel):
    reason: str = Field(..., min_length=10, max_length=500)


class ToggleActiveResponse(BaseModel):
    user_id: UUID
    is_active: bool


class ResetPasswordCompleteRequest(BaseModel):
    """Requête publique côté utilisateur pour finaliser le reset."""

    token: str = Field(..., min_length=20)
    new_password: str = Field(..., min_length=8, max_length=200)


class ResetPasswordCompleteResponse(BaseModel):
    success: bool
    message: str = "Mot de passe réinitialisé."


# ---------- Funds / Intermediaries / Offers (publish) ----------


class PublishResponse(BaseModel):
    entity_type: str
    entity_id: UUID
    publication_status: str
    published_at: datetime | None = None


class PublishGatingError(BaseModel):
    """Réponse 400 quand le publish est bloqué par sources non-verified."""

    error: str = "publish_gating"
    blocking_sources: list[UUID] = Field(default_factory=list)
    message: str


# ---------- Metrics ----------


class MetricsCount(BaseModel):
    total: int
    breakdown: dict[str, int] = Field(default_factory=dict)


class MetricsOverview(BaseModel):
    sources: MetricsCount
    accounts: MetricsCount
    applications: MetricsCount
    attestations: MetricsCount
    llm_costs: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime
