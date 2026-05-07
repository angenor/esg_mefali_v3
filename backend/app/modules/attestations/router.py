"""Endpoints REST authentifiés pour les attestations PME (F08 — T032).

4 endpoints :

- ``POST /api/attestations`` : générer une nouvelle attestation.
- ``GET /api/attestations`` : lister les attestations du tenant courant.
- ``POST /api/attestations/{id}/revoke`` : révoquer une attestation.
- ``GET /api/attestations/{id}/download`` : télécharger le PDF.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.modules.attestations.schemas import (
    AttestationCreate,
    AttestationRead,
    AttestationRevoke,
    AttestationSummary,
)
from app.modules.attestations.service import (
    AttestationAlreadyRevokedError,
    AttestationNotFoundError,
    CreditScoreMissingError,
    EsgAssessmentMissingError,
    PdfGenerationError,
    generate_attestation,
    get_attestation_for_user,
    list_attestations_for_user,
    revoke_attestation,
)

logger = logging.getLogger(__name__)


router = APIRouter()


def _require_account_id(user: User) -> uuid.UUID:
    """Lève 403 si le user n'a pas d'account."""
    if user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte requis pour gérer les attestations",
        )
    return user.account_id


def _to_summary(attestation) -> dict[str, Any]:
    """Sérialise une Attestation en dict pour AttestationSummary."""
    return {
        "id": attestation.id,
        "display_id": attestation.display_id,
        "attestation_type": attestation.attestation_type,
        "valid_from": attestation.valid_from,
        "valid_until": attestation.valid_until,
        "revoked_at": attestation.revoked_at,
        "revoked_reason": attestation.revoked_reason,
        "verification_url": attestation.verification_url,
        "pdf_hash_sha256": attestation.pdf_hash_sha256,
        "public_key_id": attestation.public_key_id,
        "created_at": attestation.created_at,
        "account_id": attestation.account_id,
        "user_id": attestation.user_id,
    }


@router.post(
    "",
    response_model=AttestationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_attestation_endpoint(
    payload: AttestationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Générer une nouvelle attestation (PME)."""
    account_id = _require_account_id(current_user)
    try:
        attestation = await generate_attestation(
            db,
            account_id=account_id,
            user_id=current_user.id,
            attestation_type=payload.attestation_type,
            source_of_change="manual",
        )
    except CreditScoreMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except EsgAssessmentMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except PdfGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    summary = _to_summary(attestation)
    summary["payload"] = attestation.payload
    summary["referential_snapshot"] = attestation.referential_snapshot or []
    return summary


@router.get("", response_model=list[AttestationSummary])
async def list_attestations_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Liste les attestations du tenant courant (PME)."""
    account_id = _require_account_id(current_user)
    attestations = await list_attestations_for_user(db, account_id=account_id)
    return [_to_summary(a) for a in attestations]


@router.get("/{attestation_id}", response_model=AttestationRead)
async def get_attestation_endpoint(
    attestation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Détail d'une attestation appartenant au tenant courant."""
    account_id = _require_account_id(current_user)
    attestation = await get_attestation_for_user(
        db, account_id=account_id, attestation_id=attestation_id,
    )
    if attestation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attestation introuvable",
        )
    summary = _to_summary(attestation)
    summary["payload"] = attestation.payload
    summary["referential_snapshot"] = attestation.referential_snapshot or []
    return summary


@router.post("/{attestation_id}/revoke", response_model=AttestationSummary)
async def revoke_attestation_endpoint(
    attestation_id: uuid.UUID,
    payload: AttestationRevoke,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Révoque une attestation appartenant au tenant courant (PME)."""
    account_id = _require_account_id(current_user)
    try:
        attestation = await revoke_attestation(
            db,
            account_id=account_id,
            user_id=current_user.id,
            attestation_id=attestation_id,
            reason=payload.reason,
            actor_role="pme",
        )
    except AttestationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attestation introuvable",
        )
    except AttestationAlreadyRevokedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette attestation est déjà révoquée",
        )
    return _to_summary(attestation)


@router.get("/{attestation_id}/download")
async def download_attestation_pdf(
    attestation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Télécharge le PDF d'une attestation (PME, du tenant courant uniquement)."""
    account_id = _require_account_id(current_user)
    attestation = await get_attestation_for_user(
        db, account_id=account_id, attestation_id=attestation_id,
    )
    if attestation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attestation introuvable",
        )
    pdf_path = Path(attestation.pdf_path)
    if not pdf_path.exists():
        logger.error(
            "Fichier PDF manquant pour attestation %s : %s",
            attestation_id, pdf_path,
        )
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Fichier PDF non disponible",
        )
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"{attestation.display_id}.pdf",
    )
