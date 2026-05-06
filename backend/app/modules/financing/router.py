"""Endpoints REST pour le module Financement Vert."""

import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_user
from app.core.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)
from app.modules.financing.schemas import (
    AccessTypeEnum,
    FundCreate,
    FundIntermediaryResponse,
    FundListResponse,
    FundMatchResponse,
    FundMatchSummary,
    FundResponse,
    FundSummary,
    IntermediaryListResponse,
    IntermediaryResponse,
    IntermediarySummary,
    MatchFundSummary,
    MatchIntermediaryUpdate,
    MatchListResponse,
    MatchStatusUpdate,
    FundCoveredResponse,
    RecommendedIntermediary,
)

router = APIRouter()


# =====================================================================
# FONDS
# =====================================================================


@router.get("/funds", response_model=FundListResponse)
async def list_funds(
    fund_type: str | None = Query(None, description="Type de fonds"),
    sector: str | None = Query(None, description="Secteur eligible"),
    min_amount: int | None = Query(None, ge=0, description="Montant minimum FCFA"),
    max_amount: int | None = Query(None, ge=0, description="Montant maximum FCFA"),
    access_type: str | None = Query(None, description="Mode d'acces"),
    status: str = Query("active", description="Statut du fonds"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FundListResponse:
    """Liste des fonds avec filtres."""
    from app.modules.financing.service import get_funds

    funds, total = await get_funds(
        db, fund_type=fund_type, sector=sector,
        min_amount=min_amount, max_amount=max_amount,
        access_type=access_type, status=status,
        page=page, limit=limit,
    )
    return FundListResponse(
        items=[FundSummary.model_validate(f) for f in funds],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/funds/{fund_id}", response_model=FundResponse)
async def get_fund_detail(
    fund_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FundResponse:
    """Detail d'un fonds avec ses intermediaires."""
    from app.modules.financing.service import get_fund_by_id, get_fund_intermediaries

    fund = await get_fund_by_id(db, fund_id)
    if fund is None:
        raise HTTPException(status_code=404, detail="Fonds non trouve")

    fund_inters = await get_fund_intermediaries(db, fund_id)
    intermediaries_data = []
    for fi in fund_inters:
        inter = fi.intermediary
        if inter:
            intermediaries_data.append(FundIntermediaryResponse(
                id=inter.id,
                name=inter.name,
                intermediary_type=inter.intermediary_type.value,
                organization_type=inter.organization_type.value,
                city=inter.city,
                role=fi.role,
                is_primary=fi.is_primary,
                services_offered=inter.services_offered,
                typical_fees=inter.typical_fees,
            ))

    fund_data = FundResponse.model_validate(fund)
    fund_data.intermediaries = intermediaries_data
    return fund_data


@router.post("/funds", response_model=FundResponse, status_code=201)
async def create_fund_endpoint(
    body: FundCreate,
    db: AsyncSession = Depends(get_db),
    # F02 : protection via dépendance get_current_admin (suppression de la
    # whitelist email statique anti-pattern).
    current_admin: User = Depends(get_current_admin),
) -> FundResponse:
    """Créer un nouveau fonds (admin uniquement).

    Les fonds sont normalement créés via le seed, pas via l'API. Cet endpoint
    est réservé à l'équipe Mefali (rôle ADMIN).
    """
    from app.modules.financing.service import create_fund

    fund = await create_fund(db, body.model_dump())
    await db.commit()
    await db.refresh(fund)
    return FundResponse.model_validate(fund)


# =====================================================================
# INTERMEDIAIRES
# =====================================================================


@router.get("/intermediaries", response_model=IntermediaryListResponse)
async def list_intermediaries(
    intermediary_type: str | None = Query(None),
    organization_type: str | None = Query(None),
    country: str | None = Query(None),
    city: str | None = Query(None),
    fund_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IntermediaryListResponse:
    """Liste des intermediaires avec filtres."""
    from app.modules.financing.service import get_intermediaries

    items, total = await get_intermediaries(
        db, intermediary_type=intermediary_type,
        organization_type=organization_type,
        country=country, city=city, fund_id=fund_id,
        page=page, limit=limit,
    )
    return IntermediaryListResponse(
        items=[IntermediarySummary.model_validate(i) for i in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/intermediaries/nearby", response_model=list[IntermediarySummary])
async def get_nearby_intermediaries(
    city: str = Query(..., description="Ville de l'utilisateur"),
    fund_id: uuid.UUID | None = Query(None, description="Fonds specifique"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[IntermediarySummary]:
    """Intermediaires proches filtres par ville."""
    from app.modules.financing.service import get_intermediaries

    items, _ = await get_intermediaries(
        db, city=city, fund_id=fund_id, limit=50,
    )
    return [IntermediarySummary.model_validate(i) for i in items]


@router.get("/intermediaries/{intermediary_id}", response_model=IntermediaryResponse)
async def get_intermediary_detail(
    intermediary_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IntermediaryResponse:
    """Detail d'un intermediaire avec fonds couverts."""
    from app.modules.financing.service import get_intermediary_by_id

    inter = await get_intermediary_by_id(db, intermediary_id)
    if inter is None:
        raise HTTPException(status_code=404, detail="Intermediaire non trouve")

    funds_covered = []
    for fi in inter.fund_intermediaries:
        fund = fi.fund
        if fund:
            funds_covered.append(FundCoveredResponse(
                id=fund.id,
                name=fund.name,
                role=fi.role,
                is_primary=fi.is_primary,
            ))

    data = IntermediaryResponse.model_validate(inter)
    data.funds_covered = funds_covered
    return data


# =====================================================================
# MATCHING
# =====================================================================


@router.get("/matches", response_model=MatchListResponse)
async def list_matches(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MatchListResponse:
    """Fonds recommandes tries par compatibilite."""
    from app.modules.financing.service import check_esg_prerequisite, get_fund_matches

    # Verifier prerequis ESG
    redirect = await check_esg_prerequisite(db, current_user.id)
    if redirect:
        raise HTTPException(status_code=428, detail=redirect)

    # Recuperer le profil utilisateur
    company_sector = None
    company_revenue = None
    company_country = "Cote d'Ivoire"
    company_city = "Abidjan"
    esg_score = None
    available_documents: list[str] = []

    try:
        from app.modules.company.service import get_or_create_profile

        profile = await get_or_create_profile(db, current_user.id)
        if profile.sector:
            company_sector = profile.sector.value if hasattr(profile.sector, "value") else profile.sector
        if profile.annual_revenue:
            company_revenue = int(profile.annual_revenue)
        if profile.city:
            company_city = profile.city
        if profile.country:
            company_country = profile.country
    except Exception:
        logger.warning("Erreur lors de la recuperation du profil pour le matching", exc_info=True)

    try:
        from app.models.esg import ESGAssessment
        from sqlalchemy import select as sa_select

        esg_result = await db.execute(
            sa_select(ESGAssessment)
            .where(ESGAssessment.user_id == current_user.id)
            .order_by(ESGAssessment.created_at.desc())
            .limit(1)
        )
        esg_assessment = esg_result.scalar_one_or_none()
        if esg_assessment and hasattr(esg_assessment, "total_score"):
            esg_score = int(esg_assessment.total_score) if esg_assessment.total_score else None
    except Exception:
        logger.warning("Erreur lors de la recuperation du score ESG pour le matching", exc_info=True)

    try:
        from app.models.document import Document
        from sqlalchemy import select as sa_select

        doc_result = await db.execute(
            sa_select(Document.document_type)
            .where(Document.user_id == current_user.id)
            .distinct()
        )
        available_documents = [
            row[0].value if hasattr(row[0], "value") else str(row[0])
            for row in doc_result.all()
            if row[0] is not None
        ]
    except Exception:
        logger.warning("Erreur lors de la recuperation des documents pour le matching", exc_info=True)

    matches = await get_fund_matches(
        db, current_user.id,
        company_sector=company_sector,
        esg_score=esg_score,
        company_revenue=company_revenue,
        company_country=company_country,
        company_city=company_city,
        available_documents=available_documents,
    )
    await db.commit()

    items = []
    for match in matches:
        fund = match.fund
        items.append(FundMatchSummary(
            id=match.id,
            fund=MatchFundSummary.model_validate(fund),
            compatibility_score=match.compatibility_score,
            matching_criteria=match.matching_criteria,
            missing_criteria=match.missing_criteria,
            recommended_intermediaries=[
                RecommendedIntermediary(**r) for r in match.recommended_intermediaries
            ],
            estimated_timeline_months=match.estimated_timeline_months,
            status=match.status.value,
        ))

    return MatchListResponse(items=items, total=len(items))


@router.get("/matches/{fund_id}", response_model=FundMatchResponse)
async def get_match_detail(
    fund_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FundMatchResponse:
    """Detail du matching pour un fonds avec parcours d'acces."""
    from app.modules.financing.service import (
        generate_access_pathway,
        get_fund_by_id,
        get_match_by_fund,
        recommend_intermediaries,
    )

    match = await get_match_by_fund(db, current_user.id, fund_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match non trouve")

    fund = await get_fund_by_id(db, fund_id)
    if fund is None:
        raise HTTPException(status_code=404, detail="Fonds non trouve")

    # Recuperer la ville de l'utilisateur
    company_city = "Abidjan"
    try:
        from app.modules.company.service import get_or_create_profile

        profile = await get_or_create_profile(db, current_user.id)
        if profile.city:
            company_city = profile.city
    except Exception:
        logger.warning("Erreur lors de la recuperation du profil pour le parcours d'acces", exc_info=True)

    # Generer le parcours d'acces
    pathway = await generate_access_pathway(db, fund, company_city=company_city)

    return FundMatchResponse(
        id=match.id,
        fund=MatchFundSummary.model_validate(fund),
        compatibility_score=match.compatibility_score,
        matching_criteria=match.matching_criteria,
        missing_criteria=match.missing_criteria,
        recommended_intermediaries=[
            RecommendedIntermediary(**r) for r in match.recommended_intermediaries
        ],
        access_pathway=pathway,
        estimated_timeline_months=match.estimated_timeline_months,
        status=match.status.value,
        contacted_intermediary_id=match.contacted_intermediary_id,
        created_at=match.created_at,
    )


# =====================================================================
# STATUT ET INTERMEDIAIRE CHOISI
# =====================================================================


@router.patch("/matches/{match_id}/status", response_model=FundMatchSummary)
async def update_status(
    match_id: uuid.UUID,
    body: MatchStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FundMatchSummary:
    """Mettre a jour le statut d'un match."""
    from app.modules.financing.service import get_match_by_id, update_match_status

    match = await get_match_by_id(db, match_id, current_user.id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match non trouve")

    try:
        match = await update_match_status(db, match, body.status)
        await db.commit()
        await db.refresh(match)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    fund = match.fund
    return FundMatchSummary(
        id=match.id,
        fund=MatchFundSummary.model_validate(fund),
        compatibility_score=match.compatibility_score,
        matching_criteria=match.matching_criteria,
        missing_criteria=match.missing_criteria,
        recommended_intermediaries=[
            RecommendedIntermediary(**r) for r in match.recommended_intermediaries
        ],
        estimated_timeline_months=match.estimated_timeline_months,
        status=match.status.value,
    )


@router.get("/matches/{match_id}/preparation-sheet")
async def get_preparation_sheet(
    match_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Generer et telecharger la fiche de preparation PDF."""
    from app.modules.financing.preparation_sheet import generate_preparation_sheet
    from app.modules.financing.service import get_fund_by_id, get_match_by_id

    match = await get_match_by_id(db, match_id, current_user.id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match non trouve")

    fund = await get_fund_by_id(db, match.fund_id)
    if fund is None:
        raise HTTPException(status_code=404, detail="Fonds non trouve")

    # Recuperer les infos du profil
    company_name = "Mon entreprise"
    company_sector = "Non defini"
    company_city = "Abidjan"
    try:
        from app.modules.company.service import get_or_create_profile

        profile = await get_or_create_profile(db, current_user.id)
        if profile.company_name:
            company_name = profile.company_name
        if profile.sector:
            company_sector = profile.sector.value if hasattr(profile.sector, "value") else str(profile.sector)
        if profile.city:
            company_city = profile.city
    except Exception:
        logger.warning("Erreur lors de la recuperation du profil pour la fiche PDF", exc_info=True)

    # Recuperer le score ESG
    esg_score = None
    try:
        from sqlalchemy import select as sa_select

        from app.models.esg import ESGAssessment

        esg_result = await db.execute(
            sa_select(ESGAssessment)
            .where(ESGAssessment.user_id == current_user.id)
            .order_by(ESGAssessment.created_at.desc())
            .limit(1)
        )
        esg_assessment = esg_result.scalar_one_or_none()
        if esg_assessment and hasattr(esg_assessment, "total_score"):
            esg_score = int(esg_assessment.total_score) if esg_assessment.total_score else None
    except Exception:
        logger.warning("Erreur lors de la recuperation du score ESG pour la fiche PDF", exc_info=True)

    # Recuperer le bilan carbone
    carbon_total = None
    try:
        from sqlalchemy import select as sa_select

        from app.models.carbon import CarbonAssessment

        carbon_result = await db.execute(
            sa_select(CarbonAssessment)
            .where(CarbonAssessment.user_id == current_user.id)
            .order_by(CarbonAssessment.created_at.desc())
            .limit(1)
        )
        carbon_assessment = carbon_result.scalar_one_or_none()
        if carbon_assessment and hasattr(carbon_assessment, "total_emissions_tco2e"):
            carbon_total = float(carbon_assessment.total_emissions_tco2e) if carbon_assessment.total_emissions_tco2e else None
    except Exception:
        logger.warning("Erreur lors de la recuperation du bilan carbone pour la fiche PDF", exc_info=True)

    # Recuperer l'intermediaire choisi
    intermediary_name = None
    intermediary_contact = None
    intermediary_address = None
    if match.contacted_intermediary_id:
        try:
            from app.modules.financing.service import get_intermediary_by_id

            inter = await get_intermediary_by_id(db, match.contacted_intermediary_id)
            if inter:
                intermediary_name = inter.name
                intermediary_contact = inter.contact_email
                intermediary_address = inter.physical_address
        except Exception:
            logger.warning("Erreur lors de la recuperation de l'intermediaire pour la fiche PDF", exc_info=True)

    pdf_bytes = await generate_preparation_sheet(
        company_name=company_name,
        company_sector=company_sector,
        company_city=company_city,
        fund_name=fund.name,
        fund_organization=fund.organization,
        compatibility_score=match.compatibility_score,
        matching_criteria=match.matching_criteria,
        missing_criteria=match.missing_criteria,
        esg_score=esg_score,
        carbon_total=carbon_total,
        intermediary_name=intermediary_name,
        intermediary_contact=intermediary_contact,
        intermediary_address=intermediary_address,
        required_documents=fund.required_documents,
        timeline_months=fund.typical_timeline_months or 6,
    )

    # Nettoyer le nom pour eviter l'injection dans le header Content-Disposition
    safe_name = re.sub(r'[^a-z0-9\-]', '', fund.name.replace(" ", "-").lower())[:40]
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="fiche-preparation-{safe_name}.pdf"',
        },
    )


@router.patch("/matches/{match_id}/intermediary", response_model=FundMatchSummary)
async def update_intermediary(
    match_id: uuid.UUID,
    body: MatchIntermediaryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FundMatchSummary:
    """Enregistrer l'intermediaire choisi."""
    from app.modules.financing.service import (
        get_match_by_id,
        update_match_intermediary,
    )

    match = await get_match_by_id(db, match_id, current_user.id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match non trouve")

    try:
        match = await update_match_intermediary(db, match, body.intermediary_id)
        await db.commit()
        await db.refresh(match)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    fund = match.fund
    return FundMatchSummary(
        id=match.id,
        fund=MatchFundSummary.model_validate(fund),
        compatibility_score=match.compatibility_score,
        matching_criteria=match.matching_criteria,
        missing_criteria=match.missing_criteria,
        recommended_intermediaries=[
            RecommendedIntermediary(**r) for r in match.recommended_intermediaries
        ],
        estimated_timeline_months=match.estimated_timeline_months,
        status=match.status.value,
    )
