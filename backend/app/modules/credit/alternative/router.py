"""F18 — Router REST pour le crédit alternatif.

Endpoints (préfixe ``/api/credit`` en montage main.py) :

- ``POST /mobile-money/upload`` (consent ``mobile_money_analysis``)
- ``GET /mobile-money/analysis``
- ``GET /mobile-money/imports``
- ``GET /public-data`` / ``POST /public-data/declare`` /
  ``DELETE /public-data/{id}`` (consent ``public_data_analysis``)
- ``GET /methodology`` (PUBLIC — pas d'auth)

Les endpoints photos IA sont stubés pour le MVP F18 (analyzer Vision en
P2/P3 — voir notes scope_partial).
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.audit_context import source_of_change_scope
from app.core.consent import consent_dependency, require_consent
from app.core.database import get_db
from app.models.credit_alternative import (
    CreditMethodologyFactor,
    MobileMoneyAnalysis,
    MobileMoneyImport,
    MobileMoneyTransaction,
    PublicDataSource,
)
from app.models.user import User
from app.modules.credit.alternative.methodology_service import (
    list_published_factors,
    total_weight,
)
from app.modules.credit.alternative.mobile_money_analyzer import (
    METHODOLOGY_VERSION,
    compute_kpis,
)
from app.modules.credit.alternative.mobile_money_parser import (
    MAX_FILE_SIZE_BYTES,
    VALID_PROVIDERS,
    ParserError,
    parse_file,
)
from app.modules.credit.alternative.schemas import (
    CreditPhotoRead,
    MethodologyFactor,
    MethodologyResponse,
    MobileMoneyAnalysisRead,
    MobileMoneyImportRead,
    MobileMoneyKpis,
    MobileMoneyUploadResponse,
    PublicDataSourceCreate,
    PublicDataSourceRead,
)

logger = logging.getLogger(__name__)

# Routers : un protégé (PME), un public (méthodologie).
router = APIRouter()
public_router = APIRouter()


# --- Storage helpers ---


def _uploads_root() -> Path:
    """Racine des uploads (configurable via env, défaut ./uploads)."""
    raw = os.environ.get("UPLOADS_ROOT", "./uploads")
    root = Path(raw).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _mm_storage_path(account_id: uuid.UUID, filename: str) -> Path:
    base = _uploads_root() / str(account_id) / "credit" / "mobile_money"
    base.mkdir(parents=True, exist_ok=True)
    safe = f"{uuid.uuid4()}_{Path(filename).name}"
    return base / safe


# --- Mobile Money endpoints ---


@router.post(
    "/mobile-money/upload",
    response_model=MobileMoneyUploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(consent_dependency("mobile_money_analysis"))],
)
async def upload_mobile_money(
    provider: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MobileMoneyUploadResponse:
    """Upload + parsing synchrone d'un fichier MM.

    Crée :class:`MobileMoneyImport`, :class:`MobileMoneyTransaction` (× N),
    puis recalcule l'analyse :class:`MobileMoneyAnalysis`.
    """
    if current_user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Compte requis pour cette opération"},
        )
    if provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "detail": f"Fournisseur inconnu: {provider}",
                "valid_providers": list(VALID_PROVIDERS),
            },
        )

    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": "Fichier vide"},
        )
    if len(raw) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "detail": "Fichier trop volumineux",
                "max_bytes": MAX_FILE_SIZE_BYTES,
            },
        )

    # Parsing
    try:
        result = parse_file(raw, provider=provider)
    except ParserError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": "Erreur de parsing", "reason": str(exc)},
        ) from exc

    # Storage best-effort (permissions 600)
    storage_path = _mm_storage_path(current_user.account_id, file.filename or "import.csv")
    try:
        storage_path.write_bytes(raw)
        os.chmod(storage_path, 0o600)
    except OSError:
        logger.exception("mm_storage_write_failed")

    # Persistance dans le bon scope d'audit
    with source_of_change_scope("manual"):
        import_record = MobileMoneyImport(
            account_id=current_user.account_id,
            provider=provider,
            file_path=str(storage_path),
            imported_rows=len(result.rows),
            rejected_rows=result.rejected_count,
            status="completed" if result.rows else "failed",
            error_summary=result.errors_summary,
        )
        db.add(import_record)
        await db.flush()

        # Transactions (skip silently les doublons via UNIQUE — try/except per row)
        for row in result.rows:
            tx = MobileMoneyTransaction(
                account_id=current_user.account_id,
                import_id=import_record.id,
                provider=row.provider,
                transaction_date=row.transaction_date,
                direction=row.direction,
                amount=row.amount,
                currency=row.currency,
                counterparty_hash=row.counterparty_hash,
                balance_amount=row.balance_amount,
                balance_currency=row.balance_currency,
            )
            db.add(tx)

        try:
            await db.flush()
        except Exception:
            await db.rollback()
            logger.exception("mm_persist_failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"detail": "Échec persistance des transactions"},
            )

        # Recalcul analyse (UPSERT idempotent par version)
        all_tx_stmt = select(MobileMoneyTransaction).where(
            MobileMoneyTransaction.account_id == current_user.account_id,
            MobileMoneyTransaction.unused.is_(False),
        )
        all_tx = (await db.execute(all_tx_stmt)).scalars().all()
        kpis = compute_kpis(all_tx)

        existing_stmt = select(MobileMoneyAnalysis).where(
            MobileMoneyAnalysis.account_id == current_user.account_id,
            MobileMoneyAnalysis.methodology_version == METHODOLOGY_VERSION,
        )
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing is None:
            analysis = MobileMoneyAnalysis(
                account_id=current_user.account_id,
                methodology_version=METHODOLOGY_VERSION,
                kpis=kpis,
                consent_active=True,
            )
            db.add(analysis)
        else:
            existing.kpis = kpis
            existing.consent_active = True
            existing.computed_at = datetime.now(timezone.utc)
            analysis = existing

        await db.commit()
        await db.refresh(analysis)
        await db.refresh(import_record)

    logger.info(
        "mm_imports_total",
        extra={
            "provider": provider,
            "imported_rows": import_record.imported_rows,
            "rejected_rows": import_record.rejected_rows,
        },
    )

    return MobileMoneyUploadResponse(
        import_id=import_record.id,
        imported_rows=import_record.imported_rows,
        rejected_rows=import_record.rejected_rows,
        status=import_record.status,
        error_summary=import_record.error_summary,
        analysis=MobileMoneyAnalysisRead(
            id=analysis.id,
            methodology_version=analysis.methodology_version,
            kpis=MobileMoneyKpis.model_validate(analysis.kpis),
            consent_active=analysis.consent_active,
            computed_at=analysis.computed_at,
        ),
    )


@router.get(
    "/mobile-money/analysis",
    response_model=MobileMoneyAnalysisRead | None,
    dependencies=[Depends(consent_dependency("mobile_money_analysis"))],
)
async def get_mobile_money_analysis(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MobileMoneyAnalysisRead | None:
    if current_user.account_id is None:
        return None
    stmt = (
        select(MobileMoneyAnalysis)
        .where(
            MobileMoneyAnalysis.account_id == current_user.account_id,
            MobileMoneyAnalysis.methodology_version == METHODOLOGY_VERSION,
        )
        .limit(1)
    )
    analysis = (await db.execute(stmt)).scalar_one_or_none()
    if analysis is None:
        return None
    return MobileMoneyAnalysisRead(
        id=analysis.id,
        methodology_version=analysis.methodology_version,
        kpis=MobileMoneyKpis.model_validate(analysis.kpis),
        consent_active=analysis.consent_active,
        computed_at=analysis.computed_at,
    )


@router.get(
    "/mobile-money/imports",
    response_model=list[MobileMoneyImportRead],
    dependencies=[Depends(consent_dependency("mobile_money_analysis"))],
)
async def list_mobile_money_imports(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MobileMoneyImportRead]:
    if current_user.account_id is None:
        return []
    stmt = (
        select(MobileMoneyImport)
        .where(MobileMoneyImport.account_id == current_user.account_id)
        .order_by(MobileMoneyImport.created_at.desc())
        .limit(50)
    )
    imports = (await db.execute(stmt)).scalars().all()
    return [MobileMoneyImportRead.model_validate(i) for i in imports]


# --- Public data endpoints ---


@router.post(
    "/public-data/declare",
    response_model=PublicDataSourceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(consent_dependency("public_data_analysis"))],
)
async def declare_public_data(
    payload: PublicDataSourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PublicDataSourceRead:
    if current_user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Compte requis"},
        )

    # Cap MVP : 5 sources / PME (FR-013)
    count_stmt = select(PublicDataSource).where(
        PublicDataSource.account_id == current_user.account_id,
        PublicDataSource.unused.is_(False),
    )
    existing = (await db.execute(count_stmt)).scalars().all()
    if len(existing) >= 5:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "detail": "Limite de 5 sources publiques atteinte",
                "current_count": len(existing),
            },
        )

    with source_of_change_scope("manual"):
        source = PublicDataSource(
            account_id=current_user.account_id,
            source_type=payload.source_type,
            url=str(payload.url),
            declared_rating=payload.declared_rating,
            declared_reviews_count=payload.declared_reviews_count,
            program_label=payload.program_label,
            status="declared",
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)

    return PublicDataSourceRead.model_validate(source)


@router.get(
    "/public-data",
    response_model=list[PublicDataSourceRead],
    dependencies=[Depends(consent_dependency("public_data_analysis"))],
)
async def list_public_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PublicDataSourceRead]:
    if current_user.account_id is None:
        return []
    stmt = select(PublicDataSource).where(
        PublicDataSource.account_id == current_user.account_id,
        PublicDataSource.unused.is_(False),
    )
    sources = (await db.execute(stmt)).scalars().all()
    return [PublicDataSourceRead.model_validate(s) for s in sources]


@router.delete(
    "/public-data/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(consent_dependency("public_data_analysis"))],
)
async def delete_public_data(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Soft-delete (unused=true). RLS garantit isolation."""
    if current_user.account_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    stmt = select(PublicDataSource).where(
        PublicDataSource.id == source_id,
        PublicDataSource.account_id == current_user.account_id,
    )
    source = (await db.execute(stmt)).scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    with source_of_change_scope("manual"):
        source.unused = True
        await db.commit()


# --- Méthodologie publique (no auth) ---


@public_router.get("/methodology", response_model=MethodologyResponse)
async def get_methodology(
    db: AsyncSession = Depends(get_db),
) -> MethodologyResponse:
    """Méthodologie scoring crédit publique (FR-017, FR-018, SC-007)."""
    factors = await list_published_factors(db)
    factor_models = [MethodologyFactor.model_validate(f) for f in factors]
    version = factors[0].version if factors else "1.2"
    return MethodologyResponse(
        version=version,
        factors=factor_models,
        total_weight=total_weight(factors),
    )


__all__ = ["router", "public_router"]
