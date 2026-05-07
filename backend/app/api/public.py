"""Endpoints publics no-auth pour la vérification d'attestations (F08 — T048).

2 endpoints (rate-limité) :

- ``GET /api/public/verify/{attestation_id}`` : vérification publique.
- ``GET /api/public/attestation-public-key`` : exposition de la clé publique.

Ces endpoints ne nécessitent JAMAIS d'authentification. Ils sont rate-limités
par IP (10 req/min) via ``app.middleware.rate_limit``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.attestations.schemas import (
    PublicKeyResponse,
)
from app.modules.attestations.service import verify_attestation
from app.modules.attestations.signing import (
    get_public_key_id,
    get_public_key_pem,
)

logger = logging.getLogger(__name__)


router = APIRouter()


@router.get("/verify/{attestation_id}")
async def verify_attestation_public_endpoint(
    request: Request,
    attestation_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """Vérifie le statut public d'une attestation (no-auth).

    Réponses possibles :

    - HTTP 200 + ``{status, ...}`` selon le DTO ``VerificationResult``.
    - HTTP 429 si rate-limit dépassé (géré par le middleware).

    JAMAIS de 404 / 410 : statut uniforme pour empêcher l'énumération.
    """
    # Détection IP pour logs (rate-limiting déjà appliqué par le middleware).
    client_ip = request.client.host if request.client else "unknown"
    result = await verify_attestation(db, attestation_id)
    if result.status == "invalid":
        logger.info(
            "verify_attestation: status=invalid id=%s ip=%s",
            attestation_id, client_ip,
        )
    return result.model_dump(mode="json")


@router.get(
    "/attestation-public-key",
    response_model=PublicKeyResponse,
)
async def get_public_key_endpoint() -> PublicKeyResponse:
    """Expose la clé publique Ed25519 et son identifiant.

    Permet à un fund officer technique de vérifier hors-ligne la signature
    d'une attestation reçue.
    """
    return PublicKeyResponse(
        public_key_id=get_public_key_id(),
        public_key_pem=get_public_key_pem(),
        issued_at=datetime.now(tz=timezone.utc),
    )
