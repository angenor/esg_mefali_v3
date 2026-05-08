"""F15 — Schémas Pydantic v2 pour ``TemplateDossier``."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SectionDef(BaseModel):
    """Définition d'une section du template."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., min_length=2, max_length=50, pattern=r"^[a-z][a-z0-9_]+$")
    title: str = Field(..., min_length=3, max_length=200)
    instructions: str = Field(..., min_length=10, max_length=2000)
    target_length: int = Field(default=500, ge=100, le=5000)
    tone: str | None = Field(default=None, max_length=100)
    required: bool = True


class RequiredDocument(BaseModel):
    """Document requis (membre de la checklist)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=2, max_length=200)
    mandatory: bool = True
    source_id: uuid.UUID | None = None
    origin: Literal["fund", "intermediary", "both", "template"] = "template"


class TemplateRead(BaseModel):
    """Lecture publique d'un template."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    offer_id: uuid.UUID | None
    instrument_type: str
    language: Literal["fr", "en"]
    sections: list[dict[str, Any]]
    required_documents: list[dict[str, Any]]
    tone: str
    vocabulary_hints: dict[str, Any] | None = None
    anti_patterns: list[Any] | None = None
    skill_id: uuid.UUID
    source_id: uuid.UUID
    version: str
    valid_from: date
    valid_to: date | None
    superseded_by: uuid.UUID | None
    status: Literal["draft", "published"]
    captured_by: uuid.UUID
    verified_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class TemplateCreate(BaseModel):
    """Schéma création (admin only)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=5, max_length=200)
    offer_id: uuid.UUID | None = None
    instrument_type: Literal[
        "subvention", "prêt_concessionnel", "equity", "blending", "mixte",
    ]
    language: Literal["fr", "en"] = "fr"
    sections: list[SectionDef] = Field(..., min_length=1, max_length=30)
    required_documents: list[RequiredDocument]
    tone: str = Field(..., min_length=2, max_length=100)
    vocabulary_hints: dict[str, Any] | None = None
    anti_patterns: list[Any] | None = None
    skill_id: uuid.UUID
    source_id: uuid.UUID
    version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")


class TemplateListResponse(BaseModel):
    items: list[TemplateRead]
    total: int


class TemplatePublishRequest(BaseModel):
    """Schéma de publication 4-yeux."""

    model_config = ConfigDict(extra="forbid")

    verified_by: uuid.UUID
