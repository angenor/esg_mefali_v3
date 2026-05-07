"""F23 — Schémas Pydantic v2 pour le module Skills.

Inclut :
- ``SkillCreate``, ``SkillUpdate``, ``SkillRead``, ``SkillReadDetailed``
- ``ActivationRules``
- ``GoldenExample``, ``GoldenContext``, ``GoldenExpected``
- ``SkillEvalReport``, ``FailedCase``
- ``SkillListResponse``, ``SkillListItem``
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.skill import SkillDomain, SkillStatus


class GoldenContext(BaseModel):
    """Contexte d'un golden example."""

    current_page: str | None = None
    active_module: str | None = None
    user_profile: dict[str, Any] | None = None
    offer_id: str | None = None
    fund_id: str | None = None
    intermediary_id: str | None = None

    model_config = ConfigDict(extra="allow")


class GoldenExpected(BaseModel):
    """Résultat attendu d'un golden example."""

    tool_called: str | list[str]
    payload_contains: dict[str, Any] | None = None
    fallback_acceptable: bool = False


class GoldenExample(BaseModel):
    """Cas de test d'une Skill (5 à 15 par skill)."""

    id: str = Field(..., min_length=1, max_length=100)
    category: SkillDomain
    context: GoldenContext
    user_message: str = Field(..., min_length=1)
    expected: GoldenExpected
    tags: list[str] = Field(default_factory=list)


class ActivationRules(BaseModel):
    """Règles de chargement contextuel d'une Skill."""

    page_slugs: list[str] = Field(default_factory=list)
    intent_keywords: list[str] = Field(default_factory=list)
    active_module: list[str] = Field(default_factory=list)
    offer_id: str | None = None
    fund_id: str | None = None
    intermediary_id: str | None = None


class SkillBase(BaseModel):
    """Champs communs SkillCreate / SkillUpdate / SkillRead."""

    name: str = Field(..., min_length=3, max_length=100, pattern=r"^skill_[a-z][a-z0-9_]*$")
    domain: SkillDomain
    prompt_expert: str = Field(..., min_length=50)
    procedure: str = Field(..., min_length=50)
    tool_whitelist: list[str] = Field(..., min_length=1)
    sources: list[UUID] = Field(default_factory=list)
    activation_rules: ActivationRules
    golden_examples: list[GoldenExample] = Field(default_factory=list)


class SkillCreate(SkillBase):
    """Payload de création d'une Skill (status forcé à draft)."""


class SkillUpdate(BaseModel):
    """Payload de mise à jour partielle d'une Skill."""

    domain: SkillDomain | None = None
    prompt_expert: str | None = Field(default=None, min_length=50)
    procedure: str | None = Field(default=None, min_length=50)
    tool_whitelist: list[str] | None = None
    sources: list[UUID] | None = None
    activation_rules: ActivationRules | None = None
    golden_examples: list[GoldenExample] | None = None

    @field_validator("golden_examples")
    @classmethod
    def _validate_golden_examples_count(
        cls, v: list[GoldenExample] | None
    ) -> list[GoldenExample] | None:
        if v is None:
            return v
        if len(v) > 15:
            raise ValueError("golden_examples must have at most 15 items")
        return v


class SkillRead(BaseModel):
    """Représentation API d'une Skill (lecture)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    domain: str
    version: str
    prompt_expert: str
    procedure: str
    tool_whitelist: list[str]
    sources: list[str]
    activation_rules: dict[str, Any]
    golden_examples: list[dict[str, Any]]
    status: str
    created_by: UUID
    verified_by: UUID | None = None
    valid_from: date
    valid_to: date | None = None
    superseded_by: UUID | None = None
    created_at: datetime
    updated_at: datetime


class SkillReadDetailed(SkillRead):
    """SkillRead enrichi avec les sources résolues (title/publisher/url)."""

    resolved_sources: list[dict[str, Any]] = Field(default_factory=list)


class SkillListItem(BaseModel):
    """Item allégé pour la liste paginée."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    domain: str
    version: str
    status: str
    valid_from: date
    valid_to: date | None = None
    created_at: datetime
    updated_at: datetime


class SkillListResponse(BaseModel):
    """Réponse paginée pour ``GET /api/admin/skills``."""

    items: list[SkillListItem]
    total: int
    page: int
    limit: int


class FailedCase(BaseModel):
    """Cas en échec dans un rapport d'eval."""

    case_id: str
    expected_tool: str | list[str]
    actual_tool: str | None = None
    payload_diff: dict[str, Any] | None = None
    latency_ms: int = 0
    error: str | None = None


class SkillEvalReport(BaseModel):
    """Rapport d'exécution des golden_examples (eval gating)."""

    skill_id: UUID
    run_id: UUID
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    total_cases: int
    passed: int
    failed: int
    success_rate: float
    threshold: float = 0.9
    gate_passed: bool
    failed_cases: list[FailedCase] = Field(default_factory=list)


class SkillPublishResponse(BaseModel):
    """Réponse 200 d'un publish réussi (skill + rapport)."""

    skill: SkillRead
    eval_report: SkillEvalReport
