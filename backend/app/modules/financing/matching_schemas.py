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
    # F045 — Double score projet/entreprise + divergence
    project_score: int = Field(ge=0, le=100, default=0)
    company_score: int = Field(ge=0, le=100, default=0)
    project_score_breakdown: dict[str, Any] = Field(default_factory=dict)
    divergence_explanation: str | None = None
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


# =====================================================================
# F045 - Matching projet-centric : schemas dedicies
# Reference : data-model.md §3 + §9 de specs/045-matching-projet-centric/
# =====================================================================


SubScoreKey = Literal[
    "sector",
    "taxonomy",
    "gcf_themes",
    "co2_impact",
    "beneficiaries",
    "gender",
    "vulnerable",
    "project_esg",
]


FactorStatus = Literal["ok", "sources_pending", "unsourced_fallback"]


class ProjectSubScoresSchema(BaseModel):
    """8 sub-scores projet (cf research.md R5)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sector: int = Field(ge=0, le=100)
    taxonomy: int = Field(ge=0, le=100)
    gcf_themes: int = Field(ge=0, le=100)
    co2_impact: int = Field(ge=0, le=100)
    beneficiaries: int = Field(ge=0, le=100)
    gender: int = Field(ge=0, le=100)
    vulnerable: int = Field(ge=0, le=100)
    project_esg: int = Field(ge=0, le=100)


class SourceUsedSchema(BaseModel):
    """Source F01 mobilisee pour un sub_score."""

    model_config = ConfigDict(extra="forbid")

    sub_score: SubScoreKey
    source_id: uuid.UUID
    source_name: str
    url: str | None = None


class MissingCriterionSchema(BaseModel):
    """Critere projet manquant (top 5 par impact negatif)."""

    model_config = ConfigDict(extra="forbid")

    key: str
    label_fr: str
    source_id: uuid.UUID | None = None
    kind: Literal["below_threshold", "missing", "wrong_value"]
    current_value: float | int | str | None = None
    target_value: float | int | str | None = None


class BoostAppliedSchema(BaseModel):
    """Trace du boost post-tri (R13 : rouge_entreprise_vert_projet)."""

    model_config = ConfigDict(extra="forbid")

    rule_triggered: bool
    rule_name: str | None = None


class ProjectScoreBreakdown(BaseModel):
    """Breakdown complet du calcul project_score (persiste dans JSONB)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    weights_version: str = "1.0"
    sub_scores: ProjectSubScoresSchema
    sources_used: list[SourceUsedSchema] = Field(default_factory=list)
    missing_criteria: list[MissingCriterionSchema] = Field(
        default_factory=list, max_length=5,
    )
    boost_applied: BoostAppliedSchema
    computed_at: datetime
    factor_status: FactorStatus = "ok"


class MatchFundsRequest(BaseModel):
    """Query params du POST /api/projects/{project_id}/match-funds."""

    model_config = ConfigDict(extra="forbid")

    min_score: int = Field(default=60, ge=0, le=100)
    limit: int = Field(default=10, ge=1, le=50)
    force_recompute: bool = False


class MatchFundsItem(BaseModel):
    """Un match projet-centric expose au LLM / frontend."""

    model_config = ConfigDict(extra="forbid")

    offer_id: uuid.UUID
    fund_id: uuid.UUID
    fund_name: str
    intermediary_id: uuid.UUID | None = None
    intermediary_name: str | None = None
    project_score: int = Field(ge=0, le=100)
    company_score: int = Field(ge=0, le=100)
    project_score_breakdown: dict[str, Any] = Field(default_factory=dict)
    divergence_explanation: str | None = None
    computed_at: datetime
    expires_at: datetime


class MatchFundsResponse(BaseModel):
    """Reponse du POST /api/projects/{project_id}/match-funds."""

    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID
    project_name: str
    matches_count: int = Field(ge=0)
    top_matches: list[MatchFundsItem] = Field(default_factory=list)
    no_match_reason: str | None = None
    recompute_request_id: uuid.UUID | None = None
