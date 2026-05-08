"""F21 — Schémas Pydantic du rapport carbone."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class CarbonReportStatus(str, Enum):
    """Statuts d'un job de génération de rapport carbone."""

    pending = "pending"
    generating = "generating"
    ready = "ready"
    failed = "failed"
    # Compatibilité legacy avec le statut F06 ``completed`` mappé en ``ready``.
    completed = "completed"


class CarbonReportRequest(BaseModel):
    """Body optionnel pour POST /api/reports/carbon/{assessment_id}/generate."""

    include_appendix_sources: bool = Field(
        default=True,
        description="Inclure l'annexe « Sources et références » F01 (recommandé).",
    )


class CarbonReportResponse(BaseModel):
    """Réponse 202 — job de génération créé."""

    id: uuid.UUID
    assessment_id: uuid.UUID
    report_type: str = "carbon"
    status: CarbonReportStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class CarbonReportListItem(BaseModel):
    """Item de la liste /api/reports?type=carbon."""

    id: uuid.UUID
    assessment_id: uuid.UUID
    status: CarbonReportStatus
    file_size: int | None = None
    generated_at: datetime | None = None
    created_at: datetime
    download_url: str | None = None

    model_config = {"from_attributes": True}
