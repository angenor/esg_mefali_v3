"""F05 — Schémas Pydantic du module ``/api/me/*``.

Tous les schémas appliquent ``model_config = ConfigDict(extra="forbid")``
pour rejeter les champs inattendus (défense en profondeur côté boundary).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ConsentTypeLiteral = Literal[
    "profile_analysis",
    "document_analysis_ai",
    "mobile_money_analysis",
    "photos_ia_analysis",
    "public_data_analysis",
    "credit_certificate_generation",
    "product_communications",
]


LegalBasisLiteral = Literal[
    "consent",
    "contract",
    "legal_obligation",
    "legitimate_interest",
]


# ----------------------------------------------------------------------
# Inventory
# ----------------------------------------------------------------------


class InventoryCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: int = 0
    projects: int = 0
    applications: int = 0
    esg_assessments: int = 0
    carbon_assessments: int = 0
    credit_scores: int = 0
    documents: int = 0
    conversations: int = 0
    messages: int = 0
    attestations: int = 0
    consents: int = 0


class InventoryLastModified(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: Optional[datetime] = None
    projects: Optional[datetime] = None
    applications: Optional[datetime] = None
    esg_assessments: Optional[datetime] = None
    carbon_assessments: Optional[datetime] = None
    credit_scores: Optional[datetime] = None
    documents: Optional[datetime] = None
    conversations: Optional[datetime] = None
    messages: Optional[datetime] = None
    attestations: Optional[datetime] = None
    consents: Optional[datetime] = None


class InventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counts: InventoryCounts
    last_modified: InventoryLastModified


# ----------------------------------------------------------------------
# Export
# ----------------------------------------------------------------------


class ExportAsyncResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    status: Literal["pending", "ready"] = "pending"
    estimated_completion_at: Optional[datetime] = None
    message: str


# ----------------------------------------------------------------------
# Consents
# ----------------------------------------------------------------------


class ConsentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ConsentTypeLiteral
    granted: bool
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    legal_basis: LegalBasisLiteral
    version: str
    label: str
    description: str


class ConsentGrantResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ConsentTypeLiteral
    granted: bool
    granted_at: datetime
    version: str


class ConsentRevokeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ConsentTypeLiteral
    granted: bool
    revoked_at: Optional[datetime] = None


# ----------------------------------------------------------------------
# Account deletion
# ----------------------------------------------------------------------


class VerifyPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(..., min_length=1, max_length=200)


class VerifyPasswordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verified: bool


class ScheduleDeletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(..., min_length=1, max_length=200)
    confirmation_text: Literal["SUPPRIMER"] = Field(
        ..., description="Doit être exactement 'SUPPRIMER'"
    )


class ScheduleDeletionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deletion_scheduled_at: datetime
    cancel_url: Optional[str] = None
    message: str


class CancelDeletionRequest(BaseModel):
    """Body de POST /api/me/account/cancel-deletion (vide pour mode JWT)."""

    model_config = ConfigDict(extra="forbid")


class CancelDeletionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cancelled_at: datetime
    message: str


__all__ = [
    "ConsentTypeLiteral",
    "LegalBasisLiteral",
    "InventoryCounts",
    "InventoryLastModified",
    "InventoryResponse",
    "ExportAsyncResponse",
    "ConsentItem",
    "ConsentGrantResponse",
    "ConsentRevokeResponse",
    "VerifyPasswordRequest",
    "VerifyPasswordResponse",
    "ScheduleDeletionRequest",
    "ScheduleDeletionResponse",
    "CancelDeletionRequest",
    "CancelDeletionResponse",
]
