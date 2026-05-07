"""Endpoints REST pour le module Dossiers de Candidature."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.modules.applications.schemas import (
    ApplicationCreate,
    ApplicationListResponse,
    ApplicationResponse,
    ApplicationStatusResponse,
    ApplicationStatusUpdate,
    ApplicationSummary,
    ChecklistItem,
    ExportRequest,
    FundInfo,
    IntermediaryInfo,
    MatchInfo,
    SectionGenerateRequest,
    SectionResponse,
    SectionUpdateRequest,
    compute_sections_progress,
    get_status_label,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =====================================================================
# CRUD DOSSIERS
# =====================================================================


@router.post("/", response_model=ApplicationResponse, status_code=201)
async def create_application(
    body: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationResponse:
    """Creer un nouveau dossier de candidature."""
    from app.modules.applications.service import create_application as create_app

    try:
        application = await create_app(
            db,
            user_id=current_user.id,
            fund_id=body.fund_id,
            match_id=body.match_id,
            intermediary_id=body.intermediary_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return _build_application_response(application)


@router.get("/", response_model=ApplicationListResponse)
async def list_applications(
    status: str | None = Query(None, description="Filtre par statut"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationListResponse:
    """Liste des dossiers de l'utilisateur."""
    from app.modules.applications.service import get_applications

    applications, total = await get_applications(
        db, user_id=current_user.id, status=status,
    )
    items = [_build_application_summary(app) for app in applications]
    return ApplicationListResponse(items=items, total=total)


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application_detail(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationResponse:
    """Detail d'un dossier."""
    application = await _get_user_application(db, application_id, current_user.id)
    return _build_application_response(application)


@router.patch("/{application_id}/status", response_model=ApplicationStatusResponse)
async def update_status(
    application_id: uuid.UUID,
    body: ApplicationStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationStatusResponse:
    """Mettre a jour le statut d'un dossier."""
    from app.modules.applications.service import update_application_status

    application = await _get_user_application(db, application_id, current_user.id)

    try:
        updated = await update_application_status(db, application, body.status.value)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    status_val = updated.status.value if hasattr(updated.status, 'value') else updated.status
    return ApplicationStatusResponse(
        id=updated.id,
        status=status_val,
        status_label=get_status_label(status_val),
        updated_at=updated.updated_at,
    )


# =====================================================================
# SECTIONS
# =====================================================================


@router.post("/{application_id}/generate-section", response_model=SectionResponse)
async def generate_section(
    application_id: uuid.UUID,
    body: SectionGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SectionResponse:
    """Generer ou regenerer une section via LLM + RAG."""
    from app.modules.applications.service import generate_section as gen_section

    application = await _get_user_application(db, application_id, current_user.id)

    try:
        result = await gen_section(db, application, body.section_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return SectionResponse(**result)


@router.patch("/{application_id}/sections/{section_key}", response_model=SectionResponse)
async def update_section(
    application_id: uuid.UUID,
    section_key: str,
    body: SectionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SectionResponse:
    """Modifier manuellement le contenu d'une section."""
    from app.modules.applications.service import update_section as upd_section

    application = await _get_user_application(db, application_id, current_user.id)

    try:
        result = await upd_section(
            db, application, section_key,
            content=body.content,
            status=body.status.value if body.status else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return SectionResponse(**result)


# =====================================================================
# CHECKLIST
# =====================================================================


@router.get("/{application_id}/checklist")
async def get_checklist(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Checklist documentaire adaptee au destinataire."""
    from app.modules.applications.service import get_checklist as get_cl

    application = await _get_user_application(db, application_id, current_user.id)
    checklist = await get_cl(db, application)
    return {"success": True, "data": checklist}


# =====================================================================
# EXPORT PDF / WORD
# =====================================================================


@router.post("/{application_id}/export")
async def export_application(
    application_id: uuid.UUID,
    body: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Exporter le dossier en PDF ou Word."""
    from app.modules.applications.export import export_application as do_export

    application = await _get_user_application(db, application_id, current_user.id)

    try:
        file_bytes, content_type, filename = await do_export(
            application, format=body.format,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =====================================================================
# FICHE DE PREPARATION INTERMEDIAIRE
# =====================================================================


@router.post("/{application_id}/prep-sheet")
async def generate_prep_sheet(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Generer la fiche de preparation intermediaire en PDF."""
    from app.modules.applications.prep_sheet import generate_prep_sheet as gen_prep

    application = await _get_user_application(db, application_id, current_user.id)

    target_val = application.target_type.value if hasattr(application.target_type, 'value') else application.target_type
    if target_val == "fund_direct":
        raise HTTPException(
            status_code=400,
            detail="La fiche de preparation n'est disponible que pour les dossiers avec intermediaire",
        )

    try:
        pdf_bytes = await gen_prep(db, application)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    fund_name = application.fund.name if application.fund else "dossier"
    filename = f"fiche_preparation_{fund_name.lower().replace(' ', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =====================================================================
# SIMULATION
# =====================================================================


@router.post("/{application_id}/simulate")
async def simulate_financing(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Lancer la simulation de financement."""
    from app.modules.applications.simulation import run_simulation

    application = await _get_user_application(db, application_id, current_user.id)

    try:
        result = await run_simulation(db, application)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"success": True, "data": result}


@router.post("/{application_id}/recompute-against-snapshot")
async def recompute_against_snapshot_endpoint(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """F04 — Recalcule le score d'une candidature contre son snapshot immuable.

    Garantit que le score est reproductible indépendamment des évolutions
    du référentiel. Réponse :
    - 200 : recompute OK avec ``comparison_with_origin``
    - 403 : la candidature appartient à un autre compte
    - 404 : candidature introuvable
    - 409 : candidature non encore soumise (``snapshot_at IS NULL``)
    """
    from app.modules.applications.recompute import recompute_against_snapshot
    from app.modules.applications.snapshot import SnapshotMissingError

    application = await _get_user_application(db, application_id, current_user.id)
    try:
        return await recompute_against_snapshot(application.id, db)
    except SnapshotMissingError as e:
        raise HTTPException(status_code=409, detail=str(e))


# =====================================================================
# HELPERS
# =====================================================================


async def _get_user_application(
    db: AsyncSession,
    application_id: uuid.UUID,
    user_id: uuid.UUID,
):
    """Recuperer un dossier en verifiant l'appartenance a l'utilisateur."""
    from app.modules.applications.service import get_application_by_id

    application = await get_application_by_id(db, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Dossier non trouve")
    if application.user_id != user_id:
        raise HTTPException(status_code=404, detail="Dossier non trouve")
    return application


def _build_application_summary(application) -> ApplicationSummary:
    """Construire un resume de dossier."""
    status_val = application.status.value if hasattr(application.status, 'value') else application.status
    target_val = application.target_type.value if hasattr(application.target_type, 'value') else application.target_type
    return ApplicationSummary(
        id=application.id,
        fund_name=application.fund.name if application.fund else "Inconnu",
        intermediary_name=application.intermediary.name if application.intermediary else None,
        target_type=target_val,
        status=status_val,
        status_label=get_status_label(status_val),
        sections_progress=compute_sections_progress(application.sections or {}),
        created_at=application.created_at,
        updated_at=application.updated_at,
    )


def _build_application_response(application) -> ApplicationResponse:
    """Construire la reponse complete d'un dossier."""
    status_val = application.status.value if hasattr(application.status, 'value') else application.status
    target_val = application.target_type.value if hasattr(application.target_type, 'value') else application.target_type

    fund_info = None
    if application.fund:
        fund_info = FundInfo(
            id=application.fund.id,
            name=application.fund.name,
            organization=application.fund.organization,
        )

    intermediary_info = None
    if application.intermediary:
        intermediary_info = IntermediaryInfo(
            id=application.intermediary.id,
            name=application.intermediary.name,
            contact_email=application.intermediary.contact_email,
            contact_phone=application.intermediary.contact_phone,
            physical_address=application.intermediary.physical_address,
        )

    match_info = None
    # match_id existe mais on n'a pas de relation chargee — a enrichir si besoin

    checklist_items = [
        ChecklistItem(**item) if isinstance(item, dict) else item
        for item in (application.checklist or [])
    ]

    return ApplicationResponse(
        id=application.id,
        fund=fund_info,
        intermediary=intermediary_info,
        match=match_info,
        target_type=target_val,
        status=status_val,
        status_label=get_status_label(status_val),
        sections=application.sections or {},
        checklist=checklist_items,
        intermediary_prep=application.intermediary_prep,
        simulation=application.simulation,
        created_at=application.created_at,
        updated_at=application.updated_at,
        submitted_at=application.submitted_at,
    )
