"""Schemas Pydantic pour le module Dashboard."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.modules.action_plan.schemas import BadgeResponse


# --- F21 — DTO sourçage des scores ---


class ScoreSourceRef(BaseModel):
    """Référence légère vers une Source F01 utilisée par un score."""

    source_id: uuid.UUID
    title: str
    publisher: str | None = None
    version: str | None = None
    url: str | None = None


# --- Sous-sections du dashboard ---


class EsgSummary(BaseModel):
    """Resume ESG pour le dashboard."""

    score: float
    grade: str
    trend: str | None = None
    last_assessment_date: str | None = None
    pillar_scores: dict[str, float] = Field(default_factory=dict)
    # F21 — sources rattachées au score (cliquables vers SourceModal F01).
    sources: list[ScoreSourceRef] = Field(default_factory=list)


class CarbonSummary(BaseModel):
    """Resume carbone pour le dashboard."""

    total_tco2e: float
    year: int
    variation_percent: float | None = None
    top_category: str | None = None
    categories: dict[str, float] = Field(default_factory=dict)
    # F21 — sources rattachées au score.
    sources: list[ScoreSourceRef] = Field(default_factory=list)


class CreditSummary(BaseModel):
    """Resume credit vert pour le dashboard."""

    score: float
    grade: str
    last_calculated: str | None = None
    sources: list[ScoreSourceRef] = Field(default_factory=list)


# --- F21 — Cards de candidatures par Offre (US1) ---


class ApplicationCard(BaseModel):
    """Card synthétique de candidature affichée sur le dashboard.

    Granularité par Offre = couple (Fonds × Intermédiaire) — F07.
    """

    application_id: uuid.UUID
    offer_id: uuid.UUID | None = None
    fund_name: str
    intermediary_name: str  # « Accès direct » si null en BDD
    fund_logo_url: str | None = None
    intermediary_logo_url: str | None = None
    status: str  # statut technique brut
    current_step: str  # libellé FR pour humains
    next_deadline: date | None = None
    next_reminder: str | None = None
    last_activity_at: datetime


# --- F21 — Carte intermédiaires actifs (US3) ---


class ActiveIntermediary(BaseModel):
    """Intermédiaire actif lié à au moins une candidature/projet de la PME."""

    intermediary_id: uuid.UUID
    name: str
    type: str  # gov_agency / dfi / commercial_bank / mfi / ngo / consulting
    country: str
    lat: float
    lon: float
    is_fallback_capital: bool = False
    accreditations: list[str] = Field(default_factory=list)
    applications_count: int = 0


class FinancingSummary(BaseModel):
    """Resume financements pour le dashboard."""

    recommended_funds_count: int = 0
    active_applications_count: int = 0
    application_statuses: dict[str, int] = Field(default_factory=dict)
    next_intermediary_action: dict | None = None
    has_intermediary_paths: bool = False
    # F21 — Cards par offre (US1) + intermédiaires actifs (US3).
    applications_by_offer: list[ApplicationCard] = Field(default_factory=list)
    active_intermediaries: list[ActiveIntermediary] = Field(default_factory=list)


class NextAction(BaseModel):
    """Prochaine action pour le dashboard."""

    id: uuid.UUID
    title: str
    category: str
    due_date: str | None = None
    status: str
    intermediary_name: str | None = None
    intermediary_address: str | None = None


class ActivityEvent(BaseModel):
    """Evenement d'activite recente."""

    type: str
    title: str
    description: str | None = None
    timestamp: datetime
    related_entity_type: str | None = None
    related_entity_id: uuid.UUID | None = None


# --- Dashboard complet ---


class DashboardSummary(BaseModel):
    """Vue synthetique du dashboard."""

    esg: EsgSummary | None = None
    carbon: CarbonSummary | None = None
    credit: CreditSummary | None = None
    financing: FinancingSummary = Field(default_factory=FinancingSummary)
    next_actions: list[NextAction] = Field(default_factory=list)
    recent_activity: list[ActivityEvent] = Field(default_factory=list)
    badges: list[BadgeResponse] = Field(default_factory=list)


# --- F21 — Endpoint dédié intermédiaires actifs (US3) ---


class ActiveIntermediariesResponse(BaseModel):
    """Réponse de GET /api/dashboard/active-intermediaries."""

    items: list[ActiveIntermediary] = Field(default_factory=list)
    total: int = 0
