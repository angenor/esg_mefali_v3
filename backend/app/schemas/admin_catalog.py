"""Schemas Pydantic v2 pour `/api/admin/catalog/*` (F25, feature 044).

Lecture seule. Réutilise les fondations F01 (Source), F04 (Money), F06/F07
(Fund, Intermediary, Offer, FundIntermediary).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.money import Money


# Onglets valides du catalogue admin.
CatalogTab = Literal["funds", "intermediaries", "offers", "fund_intermediaries"]

# Statut de publication des entités catalogue (cohérent avec PublicationStatus F01).
PublicationStatusLiteral = Literal["draft", "published", "deprecated"]

# Statut spécifique aux liaisons fund_intermediaries.
FundIntermediaryStatusLiteral = Literal["active", "expired", "all"]


# ---------- Compteurs (`GET /summary`) ----------


class CatalogTabCounts(BaseModel):
    """Compteurs par statut pour un onglet (funds, intermediaries, offers)."""

    model_config = ConfigDict(strict=True)

    total: int = Field(..., ge=0)
    by_status: dict[str, int] = Field(default_factory=dict)


class CatalogFundIntermediariesCounts(BaseModel):
    """Compteurs spécifiques aux liaisons fonds × intermédiaires."""

    model_config = ConfigDict(strict=True)

    total: int = Field(..., ge=0)
    active: int = Field(..., ge=0)
    expired: int = Field(..., ge=0)


class CatalogSummary(BaseModel):
    """Résumé global du catalogue (4 onglets)."""

    model_config = ConfigDict(strict=True)

    funds: CatalogTabCounts
    intermediaries: CatalogTabCounts
    offers: CatalogTabCounts
    fund_intermediaries: CatalogFundIntermediariesCounts


# ---------- Référence Source allégée ----------


class SourceRef(BaseModel):
    """Référence légère vers une source F01 (id + métadonnées d'affichage)."""

    model_config = ConfigDict(strict=True)

    id: UUID
    title: str | None = None
    url: str | None = None
    status: Literal["draft", "pending", "verified", "outdated"]


# ---------- Lignes génériques de liste ----------


class CatalogRowBase(BaseModel):
    """Champs communs à toutes les lignes de liste catalogue."""

    model_config = ConfigDict(strict=True)

    id: str = Field(..., description="UUID stringifié ou clé composite (liaisons)")
    name: str
    publication_status: str | None = None
    version: str | None = None
    updated_at: datetime
    has_incoherence: bool = False


# ---------- Liaisons fund_intermediaries ----------


class FundIntermediaryRow(BaseModel):
    """Ligne de liste pour l'onglet liaisons fonds × intermédiaires."""

    model_config = ConfigDict(strict=True)

    id: str = Field(..., description='Format "{fund_id}:{intermediary_id}"')
    fund_id: UUID
    fund_name: str
    intermediary_id: UUID
    intermediary_name: str
    accredited_from: date | None = None
    accredited_to: date | None = None
    is_active: bool
    max_amount_per_fund_money: Money | None = None
    has_source: bool
    has_incoherence: bool
    updated_at: datetime


class FundIntermediaryDetail(FundIntermediaryRow):
    """Fiche détaillée d'une liaison."""

    accreditation_source: SourceRef | None = None
    fund_link: str
    intermediary_link: str
    created_at: datetime
    # F25 US2 — versioning F04 exposé sur la fiche détail.
    version: str | None = None
    superseded_by: UUID | None = None


# ---------- Pagination conditionnelle (FR-013a) ----------

T = TypeVar("T")


class PaginatedListResponse(BaseModel, Generic[T]):
    """Enveloppe paginée. `paginated=False` => liste complète (total<2000)."""

    model_config = ConfigDict(strict=True)

    items: list[T]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    paginated: bool


# ---------- Export CSV ----------


CatalogExportTab = Literal["funds", "intermediaries", "offers", "fund_intermediaries"]
