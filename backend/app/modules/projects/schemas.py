"""Schémas Pydantic v2 strict pour le module Projects (F06)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.money import Money


# Whitelists (parallèles aux enums du modèle SQLAlchemy)
OBJECTIVE_ENV_VALUES: frozenset[str] = frozenset({
    "mitigation",
    "adaptation",
    "biodiversity",
    "circular_economy",
    "water",
    "renewable_energy",
    "sustainable_agriculture",
    "mixed",
})
MATURITY_VALUES: frozenset[str] = frozenset({
    "ideation",
    "pre_feasibility",
    "pilot",
    "scale",
    "replication",
})
STATUS_VALUES: frozenset[str] = frozenset({
    "draft",
    "seeking_funding",
    "funded",
    "in_execution",
    "closed",
    "cancelled",
})
FINANCING_STRUCTURE_VALUES: frozenset[str] = frozenset({
    "subvention",
    "pret_concessionnel",
    "equity",
    "blending",
    "mixte",
})
DOC_TYPE_VALUES: frozenset[str] = frozenset({
    "feasibility_study",
    "business_plan",
    "impact_assessment",
    "support_letter",
    "other",
})

# Statuts d'application considérés inactifs (n'empêchent PAS la suppression).
INACTIVE_APPLICATION_STATUSES: frozenset[str] = frozenset({
    "rejected",
    "accepted",
    "cancelled",
})


class ProjectBase(BaseModel):
    """Base partagée par Create / Read."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=200)]
    description: str | None = None
    objective_env: list[str] = Field(default_factory=list)
    maturity: str | None = None
    status: str = "draft"
    target_amount: Money | None = None
    duration_months: Annotated[int | None, Field(default=None, gt=0)] = None
    financing_structure: str | None = None
    expected_impact_tco2e: Annotated[Decimal | None, Field(default=None, ge=0)] = None
    expected_jobs_created: Annotated[int | None, Field(default=None, ge=0)] = None
    expected_beneficiaries: Annotated[int | None, Field(default=None, ge=0)] = None
    expected_hectares_restored: Annotated[
        Decimal | None, Field(default=None, ge=0)
    ] = None
    expected_other_impacts: dict[str, Any] | None = None
    location_country: Annotated[
        str | None, Field(default=None, min_length=2, max_length=2)
    ] = None
    location_region: Annotated[
        str | None, Field(default=None, max_length=100)
    ] = None

    @field_validator("objective_env")
    @classmethod
    def _validate_objective_env(cls, v: list[str]) -> list[str]:
        for o in v:
            if o not in OBJECTIVE_ENV_VALUES:
                raise ValueError(
                    f"objective_env value '{o}' not in {sorted(OBJECTIVE_ENV_VALUES)}"
                )
        return v

    @field_validator("maturity")
    @classmethod
    def _validate_maturity(cls, v: str | None) -> str | None:
        if v is not None and v not in MATURITY_VALUES:
            raise ValueError(f"maturity must be in {sorted(MATURITY_VALUES)}")
        return v

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str) -> str:
        if v not in STATUS_VALUES:
            raise ValueError(f"status must be in {sorted(STATUS_VALUES)}")
        return v

    @field_validator("financing_structure")
    @classmethod
    def _validate_financing_structure(cls, v: str | None) -> str | None:
        if v is not None and v not in FINANCING_STRUCTURE_VALUES:
            raise ValueError(
                f"financing_structure must be in {sorted(FINANCING_STRUCTURE_VALUES)}"
            )
        return v

    @field_validator("location_country")
    @classmethod
    def _validate_country(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.isalpha():
            raise ValueError("location_country must be 2 ISO alpha letters")
        return v.upper()


class ProjectCreate(ProjectBase):
    """Payload de création."""

    pass


class ProjectUpdate(BaseModel):
    """Payload de mise à jour partielle. Aucun champ obligatoire."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: Annotated[
        str | None, Field(default=None, min_length=1, max_length=200)
    ] = None
    description: str | None = None
    objective_env: list[str] | None = None
    maturity: str | None = None
    status: str | None = None
    target_amount: Money | None = None
    duration_months: Annotated[int | None, Field(default=None, gt=0)] = None
    financing_structure: str | None = None
    expected_impact_tco2e: Annotated[Decimal | None, Field(default=None, ge=0)] = None
    expected_jobs_created: Annotated[int | None, Field(default=None, ge=0)] = None
    expected_beneficiaries: Annotated[int | None, Field(default=None, ge=0)] = None
    expected_hectares_restored: Annotated[
        Decimal | None, Field(default=None, ge=0)
    ] = None
    expected_other_impacts: dict[str, Any] | None = None
    location_country: Annotated[
        str | None, Field(default=None, min_length=2, max_length=2)
    ] = None
    location_region: Annotated[
        str | None, Field(default=None, max_length=100)
    ] = None

    @field_validator("objective_env")
    @classmethod
    def _validate_objective_env(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        for o in v:
            if o not in OBJECTIVE_ENV_VALUES:
                raise ValueError(
                    f"objective_env value '{o}' not in {sorted(OBJECTIVE_ENV_VALUES)}"
                )
        return v

    @field_validator("maturity")
    @classmethod
    def _validate_maturity(cls, v: str | None) -> str | None:
        if v is not None and v not in MATURITY_VALUES:
            raise ValueError(f"maturity must be in {sorted(MATURITY_VALUES)}")
        return v

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in STATUS_VALUES:
            raise ValueError(f"status must be in {sorted(STATUS_VALUES)}")
        return v

    @field_validator("financing_structure")
    @classmethod
    def _validate_financing_structure(cls, v: str | None) -> str | None:
        if v is not None and v not in FINANCING_STRUCTURE_VALUES:
            raise ValueError(
                f"financing_structure must be in {sorted(FINANCING_STRUCTURE_VALUES)}"
            )
        return v

    @field_validator("location_country")
    @classmethod
    def _validate_country(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.isalpha():
            raise ValueError("location_country must be 2 ISO alpha letters")
        return v.upper()


class ProjectDocumentRead(BaseModel):
    """Lien projet ↔ document."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    document_id: uuid.UUID
    doc_type: str
    created_at: datetime


class ProjectSummary(BaseModel):
    """Réponse résumée pour les listes (cards)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: str
    maturity: str | None
    objective_env: list[str]
    target_amount: Money | None
    expected_impact_tco2e: Decimal | None
    auto_generated: bool
    applications_count: int = 0
    created_at: datetime


class ProjectDetail(ProjectBase):
    """Réponse détaillée."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    auto_generated: bool
    created_at: datetime
    updated_at: datetime
    project_documents: list[ProjectDocumentRead] = Field(default_factory=list)
    applications_count: int = 0


class BlockedApplication(BaseModel):
    """Application bloquante pour la suppression."""

    application_id: uuid.UUID
    fund_name: str
    status: str


class DeleteResult(BaseModel):
    """Résultat de DELETE /api/projects/{id}."""

    ok: bool
    blocked_by: list[BlockedApplication] = Field(default_factory=list)
    hint: str | None = None


class DuplicateProjectRequest(BaseModel):
    """Payload de POST /api/projects/{id}/duplicate."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    new_name: Annotated[
        str | None, Field(default=None, min_length=1, max_length=200)
    ] = None


class ProjectFilters(BaseModel):
    """Query params de GET /api/projects."""

    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    maturity: str | None = None
    objective_env: str | None = None
    auto_generated: bool | None = None
    page: Annotated[int, Field(default=1, ge=1)] = 1
    limit: Annotated[int, Field(default=25, ge=1, le=100)] = 25


class ProjectListResponse(BaseModel):
    """Liste paginée de projets."""

    items: list[ProjectSummary]
    total: int
    page: int
    limit: int


class ProjectApplicationSummary(BaseModel):
    """Résumé d'une application liée à un projet."""

    model_config = ConfigDict(from_attributes=True)

    application_id: uuid.UUID
    fund_id: uuid.UUID
    fund_name: str
    status: str
    intermediary_id: uuid.UUID | None
    intermediary_name: str | None
    target_type: str
    created_at: datetime


class LinkDocumentRequest(BaseModel):
    """Payload de POST /api/projects/{id}/documents."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    document_id: uuid.UUID
    doc_type: Annotated[str, Field(min_length=1, max_length=32)]

    @field_validator("doc_type")
    @classmethod
    def _validate_doc_type(cls, v: str) -> str:
        if v not in DOC_TYPE_VALUES:
            raise ValueError(f"doc_type must be in {sorted(DOC_TYPE_VALUES)}")
        return v
