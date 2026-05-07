"""Endpoints REST admin pour les attestations (F08 — T064).

2 endpoints admin (cross-tenant) :

- ``GET /api/admin/attestations`` : liste cross-tenant avec filtres.
- ``POST /api/admin/attestations/{id}/revoke`` : révocation admin.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.models.user import User
from app.modules.attestations.schemas import (
    AttestationRevoke,
    AttestationSummary,
)
from app.modules.attestations.service import (
    AttestationAlreadyRevokedError,
    AttestationNotFoundError,
    list_all_attestations_admin,
    revoke_attestation,
)

logger = logging.getLogger(__name__)


router = APIRouter()


def _to_summary(attestation) -> dict[str, Any]:
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


@router.get("", response_model=list[AttestationSummary])
async def list_attestations_admin_endpoint(
    status_filter: str | None = Query(default=None, alias="status"),
    account_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
) -> list[dict[str, Any]]:
    """Liste cross-tenant pour les admins."""
    attestations = await list_all_attestations_admin(
        db,
        status=status_filter,
        account_id=account_id,
        limit=limit,
        offset=offset,
    )
    return [_to_summary(a) for a in attestations]


@router.post("/{attestation_id}/revoke", response_model=AttestationSummary)
async def revoke_attestation_admin_endpoint(
    attestation_id: uuid.UUID,
    payload: AttestationRevoke,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Révoque une attestation cross-tenant (admin)."""
    try:
        attestation = await revoke_attestation(
            db,
            account_id=admin_user.account_id or uuid.uuid4(),  # ignoré pour admin
            user_id=admin_user.id,
            attestation_id=attestation_id,
            reason=payload.reason,
            actor_role="admin",
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
