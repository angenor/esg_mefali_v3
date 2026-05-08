"""Schemas Pydantic v2 pour le module Matching (F14)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


MatchBottleneck = Literal["fund", "intermediary", "balanced"]
MatchStatus = Literal["suggested", "viewed", "dismissed", "converted"]


class MissingCriterion(BaseModel):
    """Critère manquant identifié dans un score décomposé F14."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    indicator_id: uuid.UUID | None = None
    indicator_code: str | None = None
    label: str
    referential_id: uuid.UUID | None = None
    source_id: uuid.UUID | None = None


class MatchSubBreakdown(BaseModel):
    """Détail d'un sous-score (côté fund OU côté intermediary)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sector_match: int = Field(ge=0, le=100)
    esg_match: int = Field(ge=0, le=100)
    size_match: int = Field(ge=0, le=100)
    location_match: int = Field(ge=0, le=100)
    documents_match: int = Field(ge=0, le=100)
    instrument_match: int = Field(ge=0, le=100)
    missing_criteria: list[MissingCriterion] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    """Détail complet du score décomposé F14."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fund: MatchSubBreakdown
    intermediary: MatchSubBreakdown
    assessment_missing: bool = False
    size_match_currency_mismatch: bool = False


class RecommendedAction(BaseModel):
    """Action recommandée FR pour combler un écart (top 3)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    indicator_id: uuid.UUID | None = None
    referential_id: uuid.UUID | None = None
    source_id: uuid.UUID | None = None


class OfferMatchRead(BaseModel):
    """Sérialisation API d'un OfferMatch."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    project_id: uuid.UUID
    offer_id: uuid.UUID
    global_score: int = Field(ge=0, le=100)
    fund_score: int = Field(ge=0, le=100)
    intermediary_score: int = Field(ge=0, le=100)
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    bottleneck: MatchBottleneck
    recommended_actions: list[dict[str, Any]] = Field(default_factory=list)
    status: MatchStatus
    computed_at: datetime
    expires_at: datetime
    last_notified_at: datetime | None = None


class OfferMatchListResponse(BaseModel):
    """Réponse paginée pour /matches."""

    model_config = ConfigDict(extra="forbid")

    items: list[OfferMatchRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=100)


class OfferMatchDetail(OfferMatchRead):
    """Détail enrichi d'un match (avec critères manquants typés)."""

    pass


class RecomputeMatchesResponse(BaseModel):
    """Réponse 202 du POST /recompute-matches."""

    model_config = ConfigDict(extra="forbid")

    recompute_request_id: uuid.UUID
    total_offers_to_compute: int = Field(ge=0)


class ComparisonValue(BaseModel):
    """Valeur d'une cellule du comparateur F11."""

    model_config = ConfigDict(extra="forbid")

    subject_id: str
    raw: Any | None = None
    display: str
    source_id: uuid.UUID | None = None
    is_winner: bool = False


class ComparisonRow(BaseModel):
    """Ligne du comparateur F11."""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    type: str = "string"
    values: list[ComparisonValue]


class ComparisonSubject(BaseModel):
    """Sujet (colonne) du comparateur F11."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComparisonResult(BaseModel):
    """Résultat d'un comparateur multi-intermédiaires (réutilisable F11)."""

    model_config = ConfigDict(extra="forbid")

    fund_id: uuid.UUID
    project_id: uuid.UUID
    subjects: list[ComparisonSubject]
    rows: list[ComparisonRow]


class MatchAlertSubscriptionRead(BaseModel):
    """Sérialisation API d'une souscription d'alerte."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    min_global_score: int = Field(ge=0, le=100)
    is_active: bool


class MatchAlertSubscriptionUpdate(BaseModel):
    """Payload PATCH pour mise à jour d'une souscription."""

    model_config = ConfigDict(extra="forbid")

    min_global_score: int | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None
