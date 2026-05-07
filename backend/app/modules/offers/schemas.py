"""Schémas Pydantic pour le module Offers (F07).

Inclut :
- ``OfferDraft`` : résultat de ``compute_effective_offer`` (non persisté).
- ``OfferRead`` / ``OfferDetail`` : lecture publique d'une offre.
- ``OfferCreate`` / ``OfferUpdate`` : payloads admin.
- ``OfferComparison`` : élément du comparateur multi-offres.
- ``OfferSummary`` : élément de la liste paginée.
- ``FundSummary`` / ``IntermediarySummary`` : sous-objets condensés.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.money import Money


# ---------------------------------------------------------------------------
# Sub-objects
# ---------------------------------------------------------------------------


class FundSummary(BaseModel):
    """Sous-objet Fund condensé pour les vues Offre."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    organization: str
    fund_type: str | None = None
    publication_status: str | None = None


class IntermediarySummary(BaseModel):
    """Sous-objet Intermediary condensé."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str | None = None
    country: str
    organization_type: str | None = None
    success_rate: float | None = None
    publication_status: str | None = None


class EffectiveDocument(BaseModel):
    """Document requis effectif (intersection fonds × intermédiaire)."""

    title: str
    source_id: UUID | None = None
    mandatory: bool = False
    format_spec: str | None = None


class EffectiveCriterion(BaseModel):
    """Critère effectif (le plus restrictif gagne)."""

    key: str
    value: Any
    source_id: UUID | None = None


class EffectiveFees(BaseModel):
    """Frais effectifs (somme cumulée Money typed)."""

    total_min: Money | None = None
    total_max: Money | None = None
    breakdown: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Offer schemas
# ---------------------------------------------------------------------------


class OfferDraft(BaseModel):
    """Résultat de compute_effective_offer (pas persisté en base).

    Utilisé pour preview admin avant création.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    fund_id: UUID
    intermediary_id: UUID
    name: str
    target_sector: list[str] | None = None
    effective_criteria: dict[str, Any] = Field(default_factory=dict)
    effective_required_documents: list[dict[str, Any]] = Field(default_factory=list)
    effective_fees: dict[str, Any] = Field(default_factory=dict)
    effective_processing_time_days_min: int | None = None
    effective_processing_time_days_max: int | None = None
    effective_disbursement_time_days_min: int | None = None
    effective_disbursement_time_days_max: int | None = None
    accepted_languages_hint: list[str] = Field(default_factory=lambda: ["FR"])
    notes: str | None = None
    suggested_source_id: UUID | None = None


class OfferSummary(BaseModel):
    """Élément résumé pour les listes /api/offers."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    fund_id: UUID
    intermediary_id: UUID
    accepted_languages: list[str] = Field(default_factory=lambda: ["FR"])
    publication_status: str
    is_active: bool
    effective_processing_time_days_min: int | None = None
    effective_processing_time_days_max: int | None = None
    effective_disbursement_time_days_min: int | None = None
    effective_disbursement_time_days_max: int | None = None


class OfferRead(BaseModel):
    """Lecture détaillée d'une offre (PME + admin)."""

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    id: UUID
    fund: FundSummary | None = None
    intermediary: IntermediarySummary | None = None
    fund_id: UUID
    intermediary_id: UUID
    name: str
    accepted_languages: list[str] = Field(default_factory=lambda: ["FR"])
    target_sector: list[str] | None = None
    effective_criteria: dict[str, Any] = Field(default_factory=dict)
    effective_required_documents: list[dict[str, Any]] = Field(default_factory=list)
    effective_fees: dict[str, Any] = Field(default_factory=dict)
    effective_processing_time_days_min: int | None = None
    effective_processing_time_days_max: int | None = None
    effective_disbursement_time_days_min: int | None = None
    effective_disbursement_time_days_max: int | None = None
    notes: str | None = None
    is_active: bool
    publication_status: str
    source_id: UUID
    version: str
    valid_from: date
    valid_to: date | None = None


class OfferCreate(BaseModel):
    """Payload de création depuis draft édité (admin only)."""

    fund_id: UUID
    intermediary_id: UUID
    name: str = Field(min_length=1, max_length=200)
    accepted_languages: list[str] = Field(default_factory=lambda: ["FR"])
    target_sector: list[str] | None = None
    effective_criteria: dict[str, Any] = Field(default_factory=dict)
    effective_required_documents: list[dict[str, Any]] = Field(default_factory=list)
    effective_fees: dict[str, Any] = Field(default_factory=dict)
    effective_processing_time_days_min: int | None = None
    effective_processing_time_days_max: int | None = None
    effective_disbursement_time_days_min: int | None = None
    effective_disbursement_time_days_max: int | None = None
    notes: str | None = None
    source_id: UUID
    publication_status: str = "draft"
    version: str = "1.0"


class OfferUpdate(BaseModel):
    """Payload d'édition d'une offre existante."""

    name: str | None = Field(None, min_length=1, max_length=200)
    accepted_languages: list[str] | None = None
    target_sector: list[str] | None = None
    effective_criteria: dict[str, Any] | None = None
    effective_required_documents: list[dict[str, Any]] | None = None
    effective_fees: dict[str, Any] | None = None
    effective_processing_time_days_min: int | None = None
    effective_processing_time_days_max: int | None = None
    effective_disbursement_time_days_min: int | None = None
    effective_disbursement_time_days_max: int | None = None
    notes: str | None = None
    is_active: bool | None = None
    publication_status: str | None = None
    source_id: UUID | None = None


class OfferComparison(BaseModel):
    """Élément du comparateur multi-offres pour un fonds."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    offer_id: UUID
    name: str
    intermediary_id: UUID
    intermediary_name: str
    intermediary_country: str
    intermediary_code: str | None = None
    accepted_languages: list[str] = Field(default_factory=lambda: ["FR"])
    effective_fees_total_min: Money | None = None
    effective_fees_total_max: Money | None = None
    effective_processing_time_days_min: int | None = None
    effective_processing_time_days_max: int | None = None
    effective_disbursement_time_days_min: int | None = None
    effective_disbursement_time_days_max: int | None = None
    success_rate: float | None = None
    documents_count: int = 0
    publication_status: str
    is_active: bool


class OfferListResponse(BaseModel):
    """Réponse de la liste paginée /api/offers."""

    items: list[OfferSummary]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Errors / messages
# ---------------------------------------------------------------------------


class PublicationPrerequisitesError(BaseModel):
    """Détail d'erreur 422 : prérequis publication non remplis."""

    detail: str = "Prérequis de publication non remplis"
    missing_prerequisites: list[str] = Field(default_factory=list)
