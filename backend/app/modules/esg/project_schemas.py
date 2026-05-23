"""DTO Pydantic v2 strict pour l'évaluation ESG-projet (F047)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


_STRICT = ConfigDict(extra="forbid", from_attributes=True)


ResponseType = Literal[
    "qcu",
    "qcm",
    "qcu_justification",
    "qcm_justification",
    "numeric",
    "money",
    "free_text",
]


class ProjectEsgAssessmentCreate(BaseModel):
    """Payload de création d'une évaluation ESG-projet (state=draft)."""

    model_config = ConfigDict(extra="forbid")

    referential_id: UUID


class ProjectEsgAssessmentRead(BaseModel):
    """Lecture publique d'une évaluation (liste ou détail léger)."""

    model_config = _STRICT

    id: UUID
    account_id: UUID
    project_id: UUID
    referential_id: UUID
    referential_version: str
    state: Literal["draft", "finalized"]
    score: int | None = Field(default=None, ge=0, le=100)
    pillar_scores: dict[str, Any] = Field(default_factory=dict)
    covered_criteria: list[UUID] = Field(default_factory=list)
    missing_criteria: list[UUID] = Field(default_factory=list)
    coverage_rate: Decimal | None = Field(default=None, ge=0, le=1)
    snapshot_data: dict[str, Any] | None = None
    finalized_at: datetime | None = None
    superseded_at: datetime | None = None
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class ProjectEsgCriterionResponseRead(BaseModel):
    """Lecture d'une réponse critère persistée."""

    model_config = _STRICT

    id: UUID
    assessment_id: UUID
    criterion_id: UUID
    response_type: ResponseType
    response_value: dict[str, Any]
    normalized_score: Decimal
    source_id: UUID | None
    unsourced: bool
    created_at: datetime
    updated_at: datetime


class ProjectEsgAssessmentDetail(ProjectEsgAssessmentRead):
    """Détail d'une évaluation incluant l'ensemble des réponses critères."""

    responses: list[ProjectEsgCriterionResponseRead] = Field(default_factory=list)


class ProjectEsgCriterionResponseSave(BaseModel):
    """Payload de sauvegarde (CREATE/UPDATE révision draft) d'une réponse."""

    model_config = ConfigDict(extra="forbid")

    criterion_id: UUID
    response_type: ResponseType
    response_value: dict[str, Any]
    source_id: UUID | None = None
    unsourced: bool = False

    @model_validator(mode="after")
    def check_source_xor_unsourced(self) -> "ProjectEsgCriterionResponseSave":
        if (self.source_id is None) == (not self.unsourced):
            # XOR strict : exactement l'un des deux doit être renseigné
            raise ValueError(
                "source_id et unsourced doivent être mutuellement exclusifs "
                "(XOR strict — F01)"
            )
        return self


class ProjectEsgAssessmentFinalize(BaseModel):
    """Payload de finalisation (déterministe — aucun champ)."""

    model_config = ConfigDict(extra="forbid")


class CriterionRef(BaseModel):
    """Référence légère vers un critère (utilisée dans missing_criteria détaillé)."""

    model_config = _STRICT

    id: UUID
    code: str
    label: str


class ProjectEsgAssessmentFinalizeResult(BaseModel):
    """Réponse retournée par la finalisation."""

    model_config = _STRICT

    assessment: ProjectEsgAssessmentRead
    score: int = Field(ge=0, le=100)
    pillar_scores: dict[str, Any]
    missing_criteria: list[CriterionRef] = Field(default_factory=list)
    coverage_rate: Decimal = Field(ge=0, le=1)
