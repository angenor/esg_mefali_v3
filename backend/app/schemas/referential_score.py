"""Schémas Pydantic pour le scoring ESG multi-référentiels (F13)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ComputedBy(str, enum.Enum):
    """Source du calcul du score (cohérente avec ReferentialScore.computed_by)."""

    MANUAL = "manual"
    LLM = "llm"
    AUTO = "auto"


class MissingReason(str, enum.Enum):
    """Raison pour laquelle un critère est manquant."""

    NON_RENSEIGNE = "non_renseigne"
    INVALIDE = "invalide"
    HORS_SCOPE = "hors_scope"


class PillarScore(BaseModel):
    """Score d'un pilier (E/S/G ou autre selon référentiel)."""

    model_config = ConfigDict(extra="forbid")

    score: Decimal = Field(ge=0, le=100)
    weight: Decimal = Field(ge=0, le=1)
    criteria_count: int = Field(ge=0)
    criteria_renseignes: int = Field(ge=0, alias="criteria_renseignés")


class CoveredCriterion(BaseModel):
    """Critère couvert (indicateur renseigné)."""

    model_config = ConfigDict(extra="forbid")

    indicator_id: uuid.UUID
    indicator_code: str
    score: Decimal = Field(ge=0, le=100)
    weight: Decimal = Field(ge=0, le=1)
    source_id: uuid.UUID | None = None  # F01 traçabilité (None si indicator legacy F05)


class MissingCriterion(BaseModel):
    """Critère manquant (indicateur non renseigné, invalide ou hors scope)."""

    model_config = ConfigDict(extra="forbid")

    indicator_id: uuid.UUID
    indicator_code: str
    reason: MissingReason
    source_id: uuid.UUID | None = None  # F01 traçabilité
    suggestion: str | None = None


class ReferentialScoreRead(BaseModel):
    """ReferentialScore exposé en lecture API (avec jointures dénormalisées)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assessment_id: uuid.UUID
    referential_id: uuid.UUID
    referential_code: str
    referential_name: str
    referential_version: str

    overall_score: Decimal | None
    pillar_scores: dict[str, PillarScore] = Field(default_factory=dict)
    coverage_rate: Decimal
    covered_criteria: list[CoveredCriterion] = Field(default_factory=list)
    missing_criteria: list[MissingCriterion] = Field(default_factory=list)
    gap_to_threshold: Decimal | None
    eligibility: bool | None

    computed_at: datetime
    computed_by: ComputedBy
    computed_request_id: uuid.UUID | None = None

    is_fallback: bool = False  # True si fallback Mefali (cf. compute_referential_score_for_offer)


class ReferentialScoreCreate(BaseModel):
    """Création interne d'un score (utilisé par les services, pas exposé en API)."""

    model_config = ConfigDict(extra="forbid")

    account_id: uuid.UUID
    assessment_id: uuid.UUID
    referential_id: uuid.UUID
    referential_version: str
    overall_score: Decimal | None
    pillar_scores: dict[str, PillarScore] = Field(default_factory=dict)
    coverage_rate: Decimal = Field(ge=0, le=1)
    covered_criteria: list[CoveredCriterion] = Field(default_factory=list)
    missing_criteria: list[MissingCriterion] = Field(default_factory=list)
    gap_to_threshold: Decimal | None
    eligibility: bool | None
    computed_by: ComputedBy
    computed_request_id: uuid.UUID | None = None


class ComparisonResult(BaseModel):
    """Résultat du tool ``compare_referentials``."""

    model_config = ConfigDict(extra="forbid")

    scores: list[ReferentialScoreRead]
    gaps: dict[str, Decimal] = Field(default_factory=dict)
    divergent_criteria: dict[str, list[CoveredCriterion]] = Field(default_factory=dict)
    summary_text: str | None = None


class RecomputeRequestResponse(BaseModel):
    """Réponse 202 Accepted lors d'un recalcul async."""

    model_config = ConfigDict(extra="forbid")

    status: str = "accepted"
    recompute_request_id: uuid.UUID
    referentials_to_recompute: list[str] = Field(default_factory=list)
    estimated_duration_seconds: int = 5


class FinalizeAssessmentResult(BaseModel):
    """Résultat du tool ``finalize_esg_assessment``."""

    model_config = ConfigDict(extra="forbid")

    assessment_id: uuid.UUID
    finalized_at: datetime
    referential_scores: list[ReferentialScoreRead]
    failures: list[dict] = Field(default_factory=list)


class BottleneckInfo(BaseModel):
    """Information sur le goulot d'étranglement entre 2 référentiels (offer)."""

    model_config = ConfigDict(extra="forbid")

    bottleneck_referential_code: str
    bottleneck_referential_name: str
    bottleneck_score: Decimal
    other_referential_code: str
    other_referential_score: Decimal
    gap: Decimal
    eligibility_min: bool
    top_3_critical_indicators: list[str] = Field(default_factory=list)


class DualReferentialResponse(BaseModel):
    """Réponse de ``compute_referential_score_for_offer``."""

    model_config = ConfigDict(extra="forbid")

    fund_score: ReferentialScoreRead
    intermediary_score: ReferentialScoreRead | None = None
    bottleneck: BottleneckInfo | None = None
    is_dual_view: bool = True


class GenerateReportRequest(BaseModel):
    """Body pour POST /api/reports/esg/{id}/generate (F13 multi-réf)."""

    model_config = ConfigDict(extra="forbid")

    referentials: list[str] = Field(default_factory=lambda: ["mefali"])
    include_appendix_sources: bool = True
    format: str = "pdf"


class GenerateReportResponse(BaseModel):
    """Réponse 202 du POST /api/reports/esg/{id}/generate."""

    model_config = ConfigDict(extra="forbid")

    report_id: uuid.UUID
    status: str = "pending"
