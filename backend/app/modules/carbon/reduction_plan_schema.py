"""Schemas Pydantic pour le plan de reduction carbone (F17 user story 4).

Chaque action du `reduction_plan` doit etre soit sourcee (source_id renseigne,
unsourced=False) soit explicitement marquee comme non sourcee (source_id=None,
unsourced=True). Les combinaisons incoherentes sont rejetees par un
``model_validator`` Pydantic.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReductionPlanAction(BaseModel):
    """Action recommandee dans le plan de reduction carbone.

    Schema canonique adopte par F17 (clarification Q4 du 2026-05-07) :
        ``{title, description, estimated_reduction_tco2e, cost_estimate_fcfa,
        timeline, source_id, unsourced}``.

    Coherence ``source_id`` <-> ``unsourced`` :
        - ``source_id is None`` <=> ``unsourced is True``
        - sinon : ValidationError
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)
    estimated_reduction_tco2e: float = Field(ge=0)
    cost_estimate_fcfa: int | None = Field(default=None, ge=0)
    timeline: str = Field(min_length=1, max_length=100)
    source_id: str | None = Field(default=None)
    unsourced: bool = Field(default=False)

    @model_validator(mode="after")
    def check_source_unsourced_consistency(self) -> "ReductionPlanAction":
        """Garantit la coherence ``source_id`` <-> ``unsourced``.

        Une action est soit sourcee (source_id non vide, unsourced=False)
        soit explicitement non sourcee (source_id=None, unsourced=True).
        """
        if self.source_id is None and not self.unsourced:
            raise ValueError(
                "source_id is None but unsourced is False (incoherent)"
            )
        if self.source_id is not None and self.unsourced:
            raise ValueError(
                "source_id is provided but unsourced is True (incoherent)"
            )
        return self


class ReductionPlan(BaseModel):
    """Plan de reduction stocke dans ``CarbonAssessment.reduction_plan`` (JSON)."""

    model_config = ConfigDict(extra="forbid")

    actions: list[ReductionPlanAction] = Field(default_factory=list)
