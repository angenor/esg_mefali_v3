"""Schemas Pydantic pour le module Financement Vert."""

import uuid
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


# --- Enumerations (paralleles aux modeles SQLAlchemy) ---


class FundTypeEnum(str, Enum):
    """F07 — valeurs renommées (migration 028)."""

    multilateral = "multilateral"
    bilateral = "bilateral"
    regional = "regional"
    national = "national"
    private = "private"
    carbon_marketplace = "carbon_marketplace"


class FundStatusEnum(str, Enum):
    active = "active"
    closed = "closed"
    upcoming = "upcoming"


class AccessTypeEnum(str, Enum):
    direct = "direct"
    intermediary_required = "intermediary_required"
    mixed = "mixed"


class IntermediaryTypeEnum(str, Enum):
    accredited_entity = "accredited_entity"
    partner_bank = "partner_bank"
    implementation_agency = "implementation_agency"
    project_developer = "project_developer"
    national_agency = "national_agency"


class OrganizationTypeEnum(str, Enum):
    bank = "bank"
    development_bank = "development_bank"
    un_agency = "un_agency"
    ngo = "ngo"
    government_agency = "government_agency"
    consulting_firm = "consulting_firm"
    carbon_developer = "carbon_developer"


class MatchStatusEnum(str, Enum):
    suggested = "suggested"
    interested = "interested"
    contacting_intermediary = "contacting_intermediary"
    applying = "applying"
    submitted = "submitted"
    accepted = "accepted"
    rejected = "rejected"


# --- Schemas de creation ---


class FundCreate(BaseModel):
    """Creation d'un fonds."""

    name: str = Field(min_length=1, max_length=255)
    organization: str = Field(min_length=1, max_length=255)
    fund_type: FundTypeEnum
    description: str = Field(min_length=1)
    website_url: str | None = None
    contact_info: dict | None = None
    eligibility_criteria: dict = Field(default_factory=dict)
    sectors_eligible: list[str] = Field(default_factory=list)
    min_amount_xof: int | None = None
    max_amount_xof: int | None = None
    application_deadline: date | None = None
    required_documents: list[str] = Field(default_factory=list)
    esg_requirements: dict = Field(default_factory=dict)
    status: FundStatusEnum = FundStatusEnum.active
    access_type: AccessTypeEnum
    intermediary_type: IntermediaryTypeEnum | None = None
    application_process: list[dict] = Field(default_factory=list)
    typical_timeline_months: int | None = None
    success_tips: str | None = None


# --- Schemas de reponse Fonds ---


class FundSummary(BaseModel):
    """Resume d'un fonds pour les listes."""

    id: uuid.UUID
    name: str
    organization: str
    fund_type: FundTypeEnum
    status: FundStatusEnum
    access_type: AccessTypeEnum
    intermediary_type: IntermediaryTypeEnum | None = None
    min_amount_xof: int | None = None
    max_amount_xof: int | None = None
    sectors_eligible: list[str] = Field(default_factory=list)
    typical_timeline_months: int | None = None

    model_config = {"from_attributes": True}


class FundIntermediaryResponse(BaseModel):
    """Intermediaire lie a un fonds."""

    id: uuid.UUID
    name: str
    intermediary_type: IntermediaryTypeEnum
    organization_type: OrganizationTypeEnum
    city: str
    role: str | None = None
    is_primary: bool = False
    services_offered: dict = Field(default_factory=dict)
    typical_fees: str | None = None

    model_config = {"from_attributes": True}


class FundResponse(BaseModel):
    """Detail complet d'un fonds."""

    id: uuid.UUID
    name: str
    organization: str
    fund_type: FundTypeEnum
    description: str
    website_url: str | None = None
    contact_info: dict | None = None
    eligibility_criteria: dict = Field(default_factory=dict)
    sectors_eligible: list[str] = Field(default_factory=list)
    min_amount_xof: int | None = None
    max_amount_xof: int | None = None
    application_deadline: date | None = None
    required_documents: list[str] = Field(default_factory=list)
    esg_requirements: dict = Field(default_factory=dict)
    status: FundStatusEnum
    access_type: AccessTypeEnum
    intermediary_type: IntermediaryTypeEnum | None = None
    application_process: list[dict] = Field(default_factory=list)
    typical_timeline_months: int | None = None
    success_tips: str | None = None
    intermediaries: list[FundIntermediaryResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FundListResponse(BaseModel):
    """Liste paginee de fonds."""

    items: list[FundSummary]
    total: int
    page: int
    limit: int


# --- Schemas de reponse Intermediaire ---


class IntermediarySummary(BaseModel):
    """Resume d'un intermediaire pour les listes."""

    id: uuid.UUID
    name: str
    intermediary_type: IntermediaryTypeEnum
    organization_type: OrganizationTypeEnum
    country: str
    city: str
    is_active: bool = True
    services_offered: dict = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class FundCoveredResponse(BaseModel):
    """Fonds couvert par un intermediaire."""

    id: uuid.UUID
    name: str
    role: str | None = None
    is_primary: bool = False

    model_config = {"from_attributes": True}


class IntermediaryResponse(BaseModel):
    """Detail complet d'un intermediaire."""

    id: uuid.UUID
    name: str
    intermediary_type: IntermediaryTypeEnum
    organization_type: OrganizationTypeEnum
    description: str | None = None
    country: str
    city: str
    website_url: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    physical_address: str | None = None
    accreditations: list = Field(default_factory=list)
    services_offered: dict = Field(default_factory=dict)
    typical_fees: str | None = None
    eligibility_for_sme: dict = Field(default_factory=dict)
    is_active: bool = True
    funds_covered: list[FundCoveredResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IntermediaryListResponse(BaseModel):
    """Liste paginee d'intermediaires."""

    items: list[IntermediarySummary]
    total: int
    page: int
    limit: int


# --- Schemas de reponse Match ---


class MatchFundSummary(BaseModel):
    """Resume du fonds dans un match."""

    id: uuid.UUID
    name: str
    organization: str
    fund_type: FundTypeEnum
    access_type: AccessTypeEnum
    intermediary_type: IntermediaryTypeEnum | None = None
    min_amount_xof: int | None = None
    max_amount_xof: int | None = None

    model_config = {"from_attributes": True}


class RecommendedIntermediary(BaseModel):
    """Intermediaire recommande dans un match."""

    id: uuid.UUID
    name: str
    city: str


class AccessPathwayStep(BaseModel):
    """Etape du parcours d'acces."""

    step: int
    phase: str
    title: str
    description: str
    duration_weeks: int | None = None


class AccessPathway(BaseModel):
    """Parcours d'acces complet."""

    steps: list[AccessPathwayStep] = Field(default_factory=list)
    total_duration_months: int | None = None


class FundMatchSummary(BaseModel):
    """Resume d'un match pour les listes."""

    id: uuid.UUID
    fund: MatchFundSummary
    compatibility_score: int
    matching_criteria: dict = Field(default_factory=dict)
    missing_criteria: dict = Field(default_factory=dict)
    recommended_intermediaries: list[RecommendedIntermediary] = Field(
        default_factory=list
    )
    estimated_timeline_months: int | None = None
    status: MatchStatusEnum

    model_config = {"from_attributes": True}


class FundMatchResponse(BaseModel):
    """Detail complet d'un match avec parcours d'acces."""

    id: uuid.UUID
    fund: MatchFundSummary
    compatibility_score: int
    matching_criteria: dict = Field(default_factory=dict)
    missing_criteria: dict = Field(default_factory=dict)
    recommended_intermediaries: list[RecommendedIntermediary] = Field(
        default_factory=list
    )
    access_pathway: AccessPathway | None = None
    estimated_timeline_months: int | None = None
    status: MatchStatusEnum
    contacted_intermediary_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MatchListResponse(BaseModel):
    """Liste de matches."""

    items: list[FundMatchSummary]
    total: int


# --- Schemas de mise a jour ---


class MatchStatusUpdate(BaseModel):
    """Mise a jour du statut d'un match."""

    status: MatchStatusEnum


class MatchIntermediaryUpdate(BaseModel):
    """Enregistrement de l'intermediaire choisi."""

    intermediary_id: uuid.UUID
