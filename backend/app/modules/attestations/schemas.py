"""Schémas Pydantic v2 pour les attestations (F08 — T017).

DTO publics et privés :

- ``AttestationCreate`` — input pour POST /api/attestations
- ``AttestationRevoke`` — input pour POST /api/attestations/{id}/revoke
- ``AttestationRead`` — détail authentifié (PME)
- ``AttestationSummary`` — résumé liste (PME et admin)
- ``VerificationResult`` — discriminated union (4 variantes) pour endpoint public

Toutes les classes utilisent ``model_config = ConfigDict(strict=True, ...)``
pour rejeter les champs inconnus et empêcher les fuites de sérialisation auto.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ----------------------------------------------------------------------
# Inputs (PME)
# ----------------------------------------------------------------------


class AttestationCreate(BaseModel):
    """Payload de création d'une attestation."""

    model_config = ConfigDict(extra="forbid")

    attestation_type: Literal["credit_score", "esg_assessment", "combined"] = Field(
        ..., description="Type d'attestation à générer."
    )


class AttestationRevoke(BaseModel):
    """Payload de révocation (PME ou admin)."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Raison de la révocation (min 10 caractères).",
    )


# ----------------------------------------------------------------------
# Reads (PME / admin)
# ----------------------------------------------------------------------


class AttestationSummary(BaseModel):
    """Résumé pour la liste (PME et admin)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_id: str
    attestation_type: Literal["credit_score", "esg_assessment", "combined"]
    valid_from: datetime
    valid_until: datetime
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None
    verification_url: str
    pdf_hash_sha256: str
    public_key_id: str
    created_at: datetime
    # Pour la vue admin uniquement (cross-tenant).
    account_id: Optional[UUID] = None
    user_id: Optional[UUID] = None


class AttestationRead(AttestationSummary):
    """Détail complet (PME ou admin)."""

    payload: dict[str, Any]
    referential_snapshot: list[dict[str, Any]]


# ----------------------------------------------------------------------
# DTOs publics — discriminated union par ``status``
# ----------------------------------------------------------------------


class _VerificationBase(BaseModel):
    """Champs communs aux 4 statuts (whitelist explicite)."""

    model_config = ConfigDict(extra="forbid")

    status: str
    verified_at: datetime
    message: str


class AuthenticVerification(_VerificationBase):
    """Statut ``authentic`` — attestation valide et non révoquée."""

    status: Literal["authentic"] = "authentic"
    attestation_id: UUID
    display_id: str
    attestation_type: Literal["credit_score", "esg_assessment", "combined"]
    valid_from: datetime
    valid_until: datetime
    issued_at: datetime
    scores: dict[str, int]
    referentials: list[dict[str, Any]]
    pdf_hash_sha256: str
    public_key_id: str


class RevokedVerification(_VerificationBase):
    """Statut ``revoked`` — attestation révoquée par PME ou admin."""

    status: Literal["revoked"] = "revoked"
    attestation_id: UUID
    display_id: str
    attestation_type: Literal["credit_score", "esg_assessment", "combined"]
    valid_from: datetime
    valid_until: datetime
    issued_at: datetime
    scores: dict[str, int]
    referentials: list[dict[str, Any]]
    pdf_hash_sha256: str
    public_key_id: str
    revoked_at: datetime
    revoked_reason: str
    revoked_by_role: Literal["pme", "admin"]


class ExpiredVerification(_VerificationBase):
    """Statut ``expired`` — attestation au-delà de ``valid_until``."""

    status: Literal["expired"] = "expired"
    attestation_id: UUID
    display_id: str
    attestation_type: Literal["credit_score", "esg_assessment", "combined"]
    valid_from: datetime
    valid_until: datetime
    issued_at: datetime
    scores: dict[str, int]
    referentials: list[dict[str, Any]]
    pdf_hash_sha256: str
    public_key_id: str
    expired_since: datetime


class InvalidVerification(_VerificationBase):
    """Statut ``invalid`` — UUID inexistant ou signature corrompue.

    Aucun champ technique exposé pour empêcher l'énumération.
    """

    status: Literal["invalid"] = "invalid"


VerificationResult = Annotated[
    Union[
        AuthenticVerification,
        RevokedVerification,
        ExpiredVerification,
        InvalidVerification,
    ],
    Field(discriminator="status"),
]


# ----------------------------------------------------------------------
# Public key endpoint
# ----------------------------------------------------------------------


class PublicKeyResponse(BaseModel):
    """Réponse de ``GET /api/public/attestation-public-key``."""

    model_config = ConfigDict(extra="forbid")

    public_key_id: str
    algorithm: Literal["ed25519"] = "ed25519"
    public_key_pem: str
    canonical_format_doc_url: str = Field(
        default="https://docs.esg-mefali.com/attestations-and-verification",
    )
    issued_at: datetime
