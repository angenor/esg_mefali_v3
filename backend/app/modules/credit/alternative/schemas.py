"""F18 — Schémas Pydantic v2 pour le module crédit alternatif."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


# --- Mobile Money ---


Provider = Literal["wave", "orange_money", "mtn_momo", "moov_money"]
ImportStatus = Literal["pending", "completed", "failed"]
Direction = Literal["incoming", "outgoing"]


class MobileMoneyImportRead(BaseModel):
    """Lecture d'un import MM (état + compteurs)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    provider: Provider
    file_path: str
    imported_rows: int = Field(ge=0)
    rejected_rows: int = Field(ge=0)
    status: ImportStatus
    error_summary: dict | None = None
    created_at: datetime


class TopCounterparty(BaseModel):
    """Contre-partie anonymisée + total."""

    model_config = ConfigDict(extra="forbid")

    counterparty_hash: str = Field(min_length=64, max_length=64)
    total_amount: Decimal = Field(ge=0)
    transaction_count: int = Field(ge=0)


class MobileMoneyKpis(BaseModel):
    """KPIs analytiques calculés à partir des transactions MM.

    Au minimum 5 KPIs distincts (FR-004 / SC-003).
    """

    model_config = ConfigDict(extra="forbid")

    monthly_volume_avg: Decimal = Field(ge=0)
    monthly_volume_stddev: Decimal = Field(ge=0)
    regularity_30d: float = Field(ge=0.0, le=1.0, description="Taux de régularité 0..1")
    avg_balance_estimate: Decimal = Field(ge=0)
    growth_12m: float = Field(description="Tendance 12 mois (-1.0..+inf)")
    top_counterparties: list[TopCounterparty] = Field(default_factory=list, max_length=5)
    transaction_count: int = Field(ge=0)
    period_start: datetime | None = None
    period_end: datetime | None = None


class MobileMoneyAnalysisRead(BaseModel):
    """Analyse MM courante (KPIs + version méthodologie)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    methodology_version: str
    kpis: MobileMoneyKpis
    consent_active: bool
    computed_at: datetime


class MobileMoneyUploadResponse(BaseModel):
    """Réponse à un upload MM (synchrone, parsing immédiat)."""

    model_config = ConfigDict(extra="forbid")

    import_id: uuid.UUID
    imported_rows: int = Field(ge=0)
    rejected_rows: int = Field(ge=0)
    status: ImportStatus
    error_summary: dict | None = None
    analysis: MobileMoneyAnalysisRead | None = None


# --- Photos IA ---


PhotoQualityStatus = Literal["pending", "ok", "low_quality", "failed"]


class PhotoAnalysisScores(BaseModel):
    """5 scores numériques (0..100) par dimension visuelle."""

    model_config = ConfigDict(extra="forbid")

    material: int = Field(ge=0, le=100, description="État du matériel")
    organization: int = Field(ge=0, le=100, description="Organisation des espaces")
    hygiene: int = Field(ge=0, le=100, description="Hygiène / sécurité")
    env_practices: int = Field(
        ge=0, le=100, description="Pratiques environnementales visibles"
    )
    activity: int = Field(ge=0, le=100, description="Activité observée")


class PhotoAnalysisResult(BaseModel):
    """Résultat structuré d'une analyse IA."""

    model_config = ConfigDict(extra="forbid")

    scores: PhotoAnalysisScores
    observations: list[str] = Field(default_factory=list, max_length=20)
    red_flags: list[str] = Field(default_factory=list, max_length=10)
    green_signals: list[str] = Field(default_factory=list, max_length=10)


class CreditPhotoRead(BaseModel):
    """Lecture d'une photo crédit + son analyse éventuelle."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    file_path: str
    captured_at: datetime | None = None
    analyzed_at: datetime | None = None
    analysis_result: PhotoAnalysisResult | None = None
    quality_status: PhotoQualityStatus
    methodology_version: str | None = None
    created_at: datetime


# --- Données publiques ---


SourceType = Literal[
    "google_my_business",
    "facebook_page",
    "google_reviews",
    "trustpilot",
    "green_program",
    "other",
]
PublicDataStatus = Literal["declared", "evidence_attached", "pending_review"]


class PublicDataSourceCreate(BaseModel):
    """Création d'une source publique déclarative."""

    model_config = ConfigDict(extra="forbid")

    source_type: SourceType
    url: HttpUrl
    declared_rating: Decimal | None = Field(default=None, ge=0, le=5)
    declared_reviews_count: int | None = Field(default=None, ge=0)
    program_label: str | None = Field(default=None, max_length=100)


class PublicDataSourceRead(BaseModel):
    """Lecture d'une source publique."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    source_type: SourceType
    url: str
    declared_rating: Decimal | None = None
    declared_reviews_count: int | None = None
    program_label: str | None = None
    evidence_path: str | None = None
    status: PublicDataStatus
    created_at: datetime


# --- Méthodologie publique ---


class MethodologyFactor(BaseModel):
    """Facteur publié de la méthodologie scoring crédit."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    version: str
    name: str
    category: str
    weight: Decimal = Field(ge=0, le=1)
    description: str
    source_id: uuid.UUID
    publication_status: Literal["draft", "published"]


class MethodologyResponse(BaseModel):
    """Réponse de l'endpoint public de méthodologie."""

    model_config = ConfigDict(extra="forbid")

    version: str
    factors: list[MethodologyFactor]
    total_weight: Decimal

    @field_validator("total_weight")
    @classmethod
    def _check_total_weight(cls, v: Decimal) -> Decimal:
        # Pas de contrainte stricte (les factors peuvent évoluer) — info indicative.
        return v


__all__ = [
    "Provider",
    "ImportStatus",
    "Direction",
    "MobileMoneyImportRead",
    "MobileMoneyKpis",
    "MobileMoneyAnalysisRead",
    "MobileMoneyUploadResponse",
    "TopCounterparty",
    "PhotoQualityStatus",
    "PhotoAnalysisScores",
    "PhotoAnalysisResult",
    "CreditPhotoRead",
    "SourceType",
    "PublicDataStatus",
    "PublicDataSourceCreate",
    "PublicDataSourceRead",
    "MethodologyFactor",
    "MethodologyResponse",
]
