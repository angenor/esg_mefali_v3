"""Schemas Pydantic pour le module rapports ESG PDF."""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ReportTypeEnum(str, Enum):
    """Type de rapport genere.

    Doit rester aligne avec le modele SQLAlchemy `app.models.report.ReportTypeEnum`
    et l'enum PG `report_type_enum` (cf. migration 044).
    """

    esg_compliance = "esg_compliance"
    carbon = "carbon"


class ReportStatusEnum(str, Enum):
    """Statut de generation d'un rapport."""

    generating = "generating"
    completed = "completed"
    failed = "failed"


class ReportGenerateResponse(BaseModel):
    """Reponse apres lancement de la generation."""

    id: uuid.UUID
    assessment_id: uuid.UUID
    report_type: ReportTypeEnum
    status: ReportStatusEnum
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportStatusResponse(BaseModel):
    """Statut de generation pour le polling frontend."""

    id: uuid.UUID
    status: ReportStatusEnum
    generated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReportResponse(BaseModel):
    """Rapport complet retourne par l'API."""

    id: uuid.UUID
    assessment_id: uuid.UUID
    report_type: ReportTypeEnum
    status: ReportStatusEnum
    file_size: int | None = None
    generated_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    """Liste paginee de rapports."""

    items: list[ReportResponse]
    total: int
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=100)
