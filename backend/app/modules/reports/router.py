"""Endpoints REST pour le module rapports ESG PDF."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.modules.reports.schemas import (
    ReportGenerateResponse,
    ReportListResponse,
    ReportResponse,
    ReportStatusResponse,
)
from app.schemas.referential_score import GenerateReportRequest

router = APIRouter()

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "uploads" / "reports"


@router.post(
    "/esg/{assessment_id}/generate",
    response_model=ReportGenerateResponse,
    status_code=201,
)
async def generate_esg_report(
    assessment_id: uuid.UUID,
    body: GenerateReportRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportGenerateResponse:
    """Lancer la generation d'un rapport PDF pour une evaluation ESG.

    F13 — Accepte un body optionnel ``{referentials, include_appendix_sources}``
    pour générer un rapport multi-référentiels (default ``["mefali"]`` pour
    rétrocompatibilité F06). Si un code de référentiel est invalide, retourne
    422 avec la liste des codes valides.
    """
    from app.core.constants import REFERENTIAL_CODES_MVP
    from app.modules.reports.service import generate_report

    # Validation des codes de référentiels (FR-033)
    if body is not None and body.referentials:
        invalid = [c for c in body.referentials if c not in REFERENTIAL_CODES_MVP]
        if invalid:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": f"Codes de référentiels invalides : {invalid}",
                    "valid_codes": list(REFERENTIAL_CODES_MVP),
                },
            )

    try:
        report = await generate_report(db, assessment_id, current_user.id)
    except ValueError as e:
        msg = str(e)
        if "introuvable" in msg:
            raise HTTPException(status_code=404, detail=msg)
        if "deja en cours" in msg:
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=400, detail=msg)

    return ReportGenerateResponse.model_validate(report)


@router.get(
    "/{report_id}/status",
    response_model=ReportStatusResponse,
)
async def get_report_status(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportStatusResponse:
    """Verifier le statut de generation d'un rapport."""
    from app.modules.reports.service import get_report

    report = await get_report(db, report_id, current_user.id)
    if report is None:
        raise HTTPException(status_code=404, detail="Rapport non trouve.")

    return ReportStatusResponse.model_validate(report)


@router.get("/{report_id}/download")
async def download_report(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Telecharger le fichier PDF d'un rapport."""
    from app.modules.reports.service import get_report, get_report_any_user

    # Verifier que le rapport existe
    report = await get_report_any_user(db, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Rapport non trouve.")

    # Verifier l'ownership
    if report.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acces refuse.")

    # Verifier que le fichier existe
    pdf_path = UPLOADS_DIR / report.file_path
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Fichier PDF non trouve.")

    filename = report.file_path
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/", response_model=ReportListResponse)
async def list_reports_endpoint(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    assessment_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportListResponse:
    """Lister les rapports de l'utilisateur connecte."""
    from app.modules.reports.service import list_reports

    reports, total = await list_reports(
        db=db,
        user_id=current_user.id,
        assessment_id=assessment_id,
        page=page,
        limit=limit,
    )

    return ReportListResponse(
        items=[ReportResponse.model_validate(r) for r in reports],
        total=total,
        page=page,
        limit=limit,
    )
