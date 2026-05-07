"""F11 — Schémas Pydantic stricts pour les tools de visualisation typés.

Ce module définit les DTOs Pydantic v2 utilisés en transit LLM → backend → frontend.
Aucune persistance : ces modèles sont éphémères (rendu inline dans le chat).

Tous les modèles utilisent ``model_config = ConfigDict(extra="forbid")``
pour rejeter strictement les champs inconnus (anti-hallucination LLM).

Voir :
- spec.md §FR-001..FR-031
- data-model.md §2-6
- contracts/visualization-tools.md
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.money import Money


# =====================================================================
# Énumérations partagées
# =====================================================================

DeltaDirection = Literal["up", "down", "neutral"]
KPIColor = Literal["emerald", "blue", "rose", "amber", "violet"]
MarkerType = Literal["project", "intermediary", "fund_office", "company_hq"]
ComparisonValueType = Literal[
    "text", "money", "duration", "percentage", "rating", "boolean",
]


# =====================================================================
# 3. KPICardArgs
# =====================================================================


class KPICardArgs(BaseModel):
    """Args strict pour show_kpi_card.

    Champs obligatoires : ``title``, ``value``.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=120)
    value: str = Field(..., min_length=1, max_length=60)
    value_money: Money | None = Field(None)  # F04
    delta: float | None = Field(None, ge=-1e9, le=1e9)
    delta_label: str | None = Field(None, max_length=60)
    delta_direction: DeltaDirection | None = None
    delta_is_good: bool | None = None
    icon: str | None = Field(None, max_length=40)  # nom heroicon
    color: KPIColor = "emerald"
    source_id: UUID | None = None  # F01
    drilldown_url: str | None = Field(None, max_length=500)


# =====================================================================
# 4. MatchCardArgs
# =====================================================================


class MatchCardArgs(BaseModel):
    """Args strict pour show_match_card."""

    model_config = ConfigDict(extra="forbid")

    project_id: UUID  # F06
    offer_id: UUID  # F07
    fund_name: str = Field(..., min_length=1, max_length=120)
    fund_logo_url: str | None = Field(None, max_length=500)
    intermediary_name: str = Field(..., min_length=1, max_length=120)
    intermediary_logo_url: str | None = Field(None, max_length=500)
    compatibility_score: int = Field(..., ge=0, le=100)
    compatibility_breakdown: dict[str, int] | None = Field(
        None,
        description='ex: {"fund_score": 80, "intermediary_score": 65}',
    )
    amount_range: str = Field(..., min_length=1, max_length=80)
    timeline: str = Field(..., min_length=1, max_length=80)
    instruments: list[str] = Field(..., min_length=1, max_length=8)
    missing_criteria_count: int = Field(..., ge=0, le=99)
    cta_label: str = Field("Explorer", min_length=1, max_length=40)
    drilldown_url: str = Field(..., min_length=1, max_length=500)


# =====================================================================
# 5. MapMarker + MapArgs
# =====================================================================


class MapMarker(BaseModel):
    """Marker individuel pour show_map."""

    model_config = ConfigDict(extra="forbid")

    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    label: str = Field(..., min_length=1, max_length=120)
    type: MarkerType
    icon: str | None = Field(None, max_length=40)  # nom heroicon optionnel
    popup_content: str | None = Field(None, max_length=500)  # HTML court (sanitisé front)
    drilldown_url: str | None = Field(None, max_length=500)


class MapArgs(BaseModel):
    """Args strict pour show_map."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, max_length=120)
    center: tuple[float, float] | None = None  # (lat, lon) ; défaut centre UEMOA
    zoom: int = Field(6, ge=1, le=18)
    markers: list[MapMarker] = Field(..., min_length=1, max_length=50)
    show_uemoa_overlay: bool = False


# =====================================================================
# 6. ComparisonTable (4 entités imbriquées)
# =====================================================================


class ComparisonValue(BaseModel):
    """Cellule individuelle d'une row de ComparisonTable."""

    model_config = ConfigDict(extra="forbid")

    subject_id: str = Field(..., min_length=1, max_length=80)
    value: str | int | float = Field(...)
    money: Money | None = None  # utilisé si row.type == "money"
    annotation: str | None = Field(None, max_length=120)
    source_id: UUID | None = None  # F01


class ComparisonRow(BaseModel):
    """Ligne (un critère) de ComparisonTable."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(..., min_length=1, max_length=120)
    values: list[ComparisonValue] = Field(..., min_length=2, max_length=5)
    type: ComparisonValueType
    higher_is_better: bool = True


class ComparisonSubject(BaseModel):
    """Colonne (une entité comparée) de ComparisonTable."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, max_length=80)
    label: str = Field(..., min_length=1, max_length=120)
    sublabel: str | None = Field(None, max_length=120)
    drilldown_url: str | None = Field(None, max_length=500)


class ComparisonTableArgs(BaseModel):
    """Args strict pour show_comparison_table.

    Validateur cross-field : chaque ``ComparisonRow.values`` doit
    contenir exactement une ``ComparisonValue`` par sujet (subject_id
    ⊆ subjects.id).
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=200)
    subjects: list[ComparisonSubject] = Field(..., min_length=2, max_length=5)
    rows: list[ComparisonRow] = Field(..., min_length=1, max_length=20)
    highlight_winner: bool = True

    @field_validator("rows", mode="after")
    @classmethod
    def _check_values_match_subjects(
        cls, rows: list[ComparisonRow], info,
    ) -> list[ComparisonRow]:
        """Vérifier que les subject_id des values correspondent exactement aux subjects.id."""
        subjects = info.data.get("subjects")
        if not subjects:
            return rows
        subject_ids = {s.id for s in subjects}
        for r_index, r in enumerate(rows):
            value_ids = {v.subject_id for v in r.values}
            if value_ids != subject_ids:
                raise ValueError(
                    f"Row {r_index} ('{r.label}') : les subject_id des values "
                    f"({sorted(value_ids)}) ne correspondent pas aux subjects "
                    f"({sorted(subject_ids)}).",
                )
        return rows


__all__ = [
    "ComparisonRow",
    "ComparisonSubject",
    "ComparisonTableArgs",
    "ComparisonValue",
    "ComparisonValueType",
    "DeltaDirection",
    "KPICardArgs",
    "KPIColor",
    "MapArgs",
    "MapMarker",
    "MarkerType",
    "MatchCardArgs",
]
