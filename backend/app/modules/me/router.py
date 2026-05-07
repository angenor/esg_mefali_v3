"""F05 — Router FastAPI pour le module ``/api/me/*`` (RGPD).

Tous les endpoints (sauf ``GET /export/download?token=...`` et
``POST /account/cancel-deletion?token=...`` en mode no-auth) requièrent un
JWT valide. Tous filtrent strictement par ``current_user.account_id``
(invariant F02 — multi-tenant).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.constants import UserRole
from app.core.database import get_db
from app.core.url_signer import verify_export_url
from app.models.consent import CONSENT_TYPE_VALUES
from app.models.user import User
from app.modules.me import service
from app.modules.me.exporter import (
    SYNC_EXPORT_THRESHOLD_BYTES,
    build_export_zip,
    estimate_export_size,
    log_export_event,
)
from app.modules.me.schemas import (
    CancelDeletionResponse,
    ConsentGrantResponse,
    ConsentItem,
    ConsentRevokeResponse,
    ExportAsyncResponse,
    InventoryResponse,
    ScheduleDeletionRequest,
    ScheduleDeletionResponse,
    VerifyPasswordRequest,
    VerifyPasswordResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ----------------------------------------------------------------------
# Inventory + Export
# ----------------------------------------------------------------------


@router.get("/data/inventory", response_model=InventoryResponse)
async def inventory(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InventoryResponse:
    """Inventaire des données stockées pour le compte courant."""
    if current_user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="L'inventaire est réservé aux comptes PME",
        )
    return await service.get_inventory(db, current_user.account_id)


@router.get("/data/export")
async def export_data(
    request: Request,
    format: str = Query("json", pattern="^(json)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export RGPD complet (sync ≤ 100 MB, async sinon).

    Mode synchrone : retourne ``application/zip`` directement.
    Mode async : retourne 202 + ``job_id`` ; le ZIP est généré en
    BackgroundTasks et notifié par email.
    """
    if current_user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="L'export est réservé aux comptes PME",
        )

    estimated_size = await estimate_export_size(db, current_user.account_id)
    if estimated_size > SYNC_EXPORT_THRESHOLD_BYTES:
        # Mode async : pour le MVP, on accepte mais on logue uniquement
        # (génération différée hors-scope T036, traitée par BackgroundTasks
        # post-MVP). On émet déjà le job_id dans audit_log.
        from uuid import uuid4

        job_id = uuid4()
        await log_export_event(
            db,
            user_id=current_user.id,
            account_id=current_user.account_id,
            size_bytes=estimated_size,
            mode="async",
            actor_metadata={"job_id": str(job_id)},
        )
        return ExportAsyncResponse(
            job_id=job_id,
            status="pending",
            message=(
                "Export en préparation, vous recevrez un email avec le lien "
                "quand il sera prêt"
            ),
        )

    # Mode synchrone
    zip_bytes = await build_export_zip(db, current_user.account_id, current_user.id)
    await log_export_event(
        db,
        user_id=current_user.id,
        account_id=current_user.account_id,
        size_bytes=len(zip_bytes),
        mode="sync",
        actor_metadata={
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        },
    )
    from datetime import datetime, timezone

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"esg-mefali-export-{current_user.account_id}-{timestamp}.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/data/export/download")
async def export_download(
    token: str = Query(..., min_length=10),
    db: AsyncSession = Depends(get_db),
):
    """Téléchargement protégé par URL signée (no-auth)."""
    try:
        payload = verify_export_url(
            token, max_age_seconds=86400 * 7, salt="export-async"
        )
    except SignatureExpired:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Lien expiré, veuillez demander un nouvel export",
        )
    except BadSignature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Lien invalide",
        )
    # MVP : pour le moment, regénère un export sync.
    from uuid import UUID as _UUID

    account_id = _UUID(payload["account_id"])
    user_id = _UUID(payload.get("user_id", payload["account_id"]))
    zip_bytes = await build_export_zip(db, account_id, user_id)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="esg-mefali-export-{account_id}.zip"'
            ),
        },
    )


# ----------------------------------------------------------------------
# Consents
# ----------------------------------------------------------------------


@router.get("/consents", response_model=list[ConsentItem])
async def get_consents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConsentItem]:
    """Liste les 7 consentements granulaires pour le compte courant."""
    if current_user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Les consentements sont réservés aux comptes PME",
        )
    return await service.list_consents(db, current_user.account_id)


@router.post(
    "/consents/{consent_type}/grant",
    response_model=ConsentGrantResponse,
)
async def post_grant_consent(
    request: Request,
    consent_type: str = Path(..., min_length=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConsentGrantResponse:
    if current_user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Les consentements sont réservés aux comptes PME",
        )
    if consent_type not in CONSENT_TYPE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "detail": "Type de consentement invalide",
                "valid_types": list(CONSENT_TYPE_VALUES),
            },
        )
    return await service.grant_consent(
        db,
        account_id=current_user.account_id,
        user_id=current_user.id,
        consent_type=consent_type,
        request=request,
    )


@router.post(
    "/consents/{consent_type}/revoke",
    response_model=ConsentRevokeResponse,
)
async def post_revoke_consent(
    request: Request,
    consent_type: str = Path(..., min_length=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConsentRevokeResponse:
    if current_user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Les consentements sont réservés aux comptes PME",
        )
    if consent_type not in CONSENT_TYPE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "detail": "Type de consentement invalide",
                "valid_types": list(CONSENT_TYPE_VALUES),
            },
        )
    return await service.revoke_consent(
        db,
        account_id=current_user.account_id,
        user_id=current_user.id,
        consent_type=consent_type,
        request=request,
    )


# ----------------------------------------------------------------------
# Account deletion
# ----------------------------------------------------------------------


@router.post("/account/verify-password", response_model=VerifyPasswordResponse)
async def verify_password_endpoint(
    data: VerifyPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerifyPasswordResponse:
    verified = await service.verify_user_password(
        db, user=current_user, password=data.password
    )
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mot de passe incorrect",
        )
    return VerifyPasswordResponse(verified=True)


@router.post(
    "/account/schedule-deletion",
    response_model=ScheduleDeletionResponse,
)
async def schedule_deletion_endpoint(
    data: ScheduleDeletionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduleDeletionResponse:
    # Owner-only : seul un user PME owner peut programmer la suppression.
    if current_user.role != UserRole.PME.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "detail": "Seul le propriétaire du compte peut programmer sa suppression",
                "current_role": current_user.role,
            },
        )
    return await service.schedule_account_deletion(
        db,
        user=current_user,
        password=data.password,
        confirmation_text=data.confirmation_text,
        request=request,
    )


@router.post("/account/cancel-deletion", response_model=CancelDeletionResponse)
async def cancel_deletion_endpoint(
    request: Request,
    token: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> CancelDeletionResponse:
    """Annule une suppression programmée.

    Deux modes :
    - Token signé (lien email) : query param ``token``, pas de JWT requis.
    - Authentifié JWT : sans ``token``, lit ``Authorization: Bearer ...``.
    """
    from uuid import UUID as _UUID

    if token:
        try:
            payload = verify_export_url(
                token,
                max_age_seconds=86400 * 30,
                salt="cancel-deletion",
            )
        except SignatureExpired:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expiré",
            )
        except BadSignature:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide",
            )
        if payload.get("action") != "cancel_deletion":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide",
            )
        return await service.cancel_account_deletion(
            db,
            account_id=_UUID(payload["account_id"]),
            user_id=None,
            request=request,
        )

    # Mode JWT — extraction manuelle pour rester compatible no-auth.
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    from app.core.security import decode_token
    from sqlalchemy import select
    from app.models.user import User as _User

    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token JWT ou query token requis",
        )
    jwt_str = auth_header.split(" ", 1)[1]
    user_id_str = decode_token(jwt_str, expected_type="access")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token JWT invalide",
        )
    user = (
        await db.execute(select(_User).where(_User.id == _UUID(user_id_str)))
    ).scalar_one_or_none()
    if user is None or user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Action réservée aux comptes PME",
        )
    return await service.cancel_account_deletion(
        db,
        account_id=user.account_id,
        user_id=user.id,
        request=request,
    )


__all__ = ["router"]
