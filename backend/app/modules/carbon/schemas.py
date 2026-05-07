"""Schemas Pydantic pour le module Calculateur d'Empreinte Carbone."""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class CarbonStatusEnum(str, Enum):
    """Statut d'un bilan carbone."""

    in_progress = "in_progress"
    completed = "completed"


# --- Schemas de creation ---


class CarbonAssessmentCreate(BaseModel):
    """Creation d'un bilan carbone."""

    year: int = Field(ge=2020, le=2100)
    conversation_id: uuid.UUID | None = None


class EmissionEntryCreate(BaseModel):
    """Creation d'une entree d'emission.

    F17 : ``source_id`` et ``factor_id`` (UUID) sont desormais obligatoires
    pour le sourcage F01 et la tracabilite snapshot du facteur applique.
    Le champ legacy ``source_description`` reste accepte (texte libre)
    pour la compatibilite, mais sera deprecie 2 sprints apres F17.
    """

    category: str = Field(min_length=1, max_length=30)
    subcategory: str = Field(min_length=1, max_length=50)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=20)
    emission_factor: float = Field(gt=0)
    emissions_tco2e: float = Field(gt=0)
    source_description: str | None = None
    # F17 — FK obligatoires pour sourcage et snapshot.
    source_id: uuid.UUID
    factor_id: uuid.UUID


class EmissionFactorResolutionResponse(BaseModel):
    """Reponse exposant un facteur d'emission resolu (F17).

    Utilise par les tools LangChain et l'API pour signaler au LLM/UI :
        - ``factor_used`` : le code/label/value/unit du facteur applique.
        - ``source_id`` : la source a citer via ``cite_source``.
        - ``is_approximate`` : True si fallback (annee tres anterieure ou pays global).
        - ``fallback_reason`` : ``year_older``, ``country_global`` ou None.
    """

    factor_used: dict
    source_id: uuid.UUID
    is_approximate: bool
    fallback_reason: str | None = None


class AddEntriesRequest(BaseModel):
    """Requete d'ajout d'entrees d'emissions."""

    entries: list[EmissionEntryCreate] = Field(min_length=1)
    mark_category_complete: str | None = None


# --- Schemas de reponse ---


class EmissionEntryResponse(BaseModel):
    """Entree d'emission retournee par l'API."""

    id: uuid.UUID
    category: str
    subcategory: str
    quantity: float
    unit: str
    emission_factor: float
    emissions_tco2e: float
    source_description: str | None = None
    # F17 — sourcage + snapshot facteur (optionnels pour les anciennes
    # entries non backfillees ou backfill en cours).
    source_id: uuid.UUID | None = None
    factor_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CarbonAssessmentResponse(BaseModel):
    """Bilan carbone retourne par l'API."""

    id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    year: int
    status: CarbonStatusEnum = CarbonStatusEnum.in_progress
    sector: str | None = None
    total_emissions_tco2e: float | None = None
    completed_categories: list[str] = Field(default_factory=list)
    reduction_plan: dict | None = None
    entries: list[EmissionEntryResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CarbonAssessmentSummary(BaseModel):
    """Resume d'un bilan pour les listes."""

    id: uuid.UUID
    year: int
    status: CarbonStatusEnum
    total_emissions_tco2e: float | None = None
    completed_categories: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CarbonAssessmentList(BaseModel):
    """Liste paginee de bilans."""

    items: list[CarbonAssessmentSummary]
    total: int
    page: int
    limit: int


class AddEntriesResponse(BaseModel):
    """Reponse apres ajout d'entrees."""

    entries_added: int
    total_emissions_tco2e: float
    completed_categories: list[str]


class CategoryBreakdown(BaseModel):
    """Ventilation des emissions par categorie."""

    emissions_tco2e: float
    percentage: float
    entries_count: int


class EquivalenceResponse(BaseModel):
    """Equivalence parlante."""

    label: str
    value: float


class SectorBenchmarkResponse(BaseModel):
    """Comparaison sectorielle."""

    sector: str
    sector_average_tco2e: float | None = None
    position: str
    percentile: int | None = None


class CarbonSummaryResponse(BaseModel):
    """Resume complet d'un bilan pour la page resultats."""

    assessment_id: uuid.UUID
    year: int
    status: CarbonStatusEnum
    total_emissions_tco2e: float
    by_category: dict[str, CategoryBreakdown]
    equivalences: list[EquivalenceResponse]
    reduction_plan: dict | None = None
    sector_benchmark: SectorBenchmarkResponse | None = None


class BenchmarkDetailResponse(BaseModel):
    """Benchmark sectoriel detaille."""

    sector: str
    average_emissions_tco2e: float
    median_emissions_tco2e: float
    by_category: dict[str, float]
    sample_size: str
    source: str
    fallback_sector: str | None = None
