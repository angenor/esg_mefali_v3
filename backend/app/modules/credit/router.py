"""Endpoints REST pour le module Scoring de Credit Vert."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.modules.credit.schemas import (
    CreditScoreBreakdownResponse,
    CreditScoreHistoryResponse,
    CreditScoreResponse,
    CreditScoreWithExpiry,
)

router = APIRouter()


def _score_to_response(score: object) -> dict:
    """Convertir un CreditScore ORM en dict pour le schema de reponse."""
    return {
        "id": str(score.id),
        "version": score.version,
        "combined_score": score.combined_score,
        "solvability_score": score.solvability_score,
        "green_impact_score": score.green_impact_score,
        "confidence_level": score.confidence_level,
        "confidence_label": score.confidence_label.value
        if hasattr(score.confidence_label, "value")
        else score.confidence_label,
        "generated_at": score.generated_at,
        "valid_until": score.valid_until,
    }


@router.post("/generate", response_model=CreditScoreResponse, status_code=201)
async def generate_score(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CreditScoreResponse:
    """Generer un nouveau score de credit vert."""
    from app.modules.credit.service import generate_credit_score

    # Verifier que le profil existe
    try:
        from app.models.company import CompanyProfile
        from sqlalchemy import select

        result = await db.execute(
            select(CompanyProfile).where(CompanyProfile.user_id == current_user.id)
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=422,
                detail="Profil entreprise requis pour generer un score. Completez votre profil d'abord.",
            )
    except HTTPException:
        raise
    except Exception:
        pass

    try:
        score = await generate_credit_score(
            db=db,
            user_id=current_user.id,
            account_id=current_user.account_id,
        )
        await db.commit()
        await db.refresh(score)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return CreditScoreResponse(**_score_to_response(score))


@router.get("/score", response_model=CreditScoreWithExpiry)
async def get_score(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CreditScoreWithExpiry:
    """Retourner le score le plus recent."""
    from app.modules.credit.service import get_latest_score

    score = await get_latest_score(db=db, user_id=current_user.id)
    if score is None:
        raise HTTPException(
            status_code=404,
            detail="Aucun score de credit vert genere. Utilisez POST /credit/generate pour en creer un.",
        )

    now = datetime.now(tz=timezone.utc)
    is_expired = score.valid_until < now if score.valid_until else False

    return CreditScoreWithExpiry(**_score_to_response(score), is_expired=is_expired)


@router.get("/score/breakdown", response_model=CreditScoreBreakdownResponse)
async def get_breakdown(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CreditScoreBreakdownResponse:
    """Retourner le detail complet du score le plus recent."""
    from app.modules.credit.service import get_latest_score

    score = await get_latest_score(db=db, user_id=current_user.id)
    if score is None:
        raise HTTPException(
            status_code=404,
            detail="Aucun score de credit vert genere. Utilisez POST /credit/generate pour en creer un.",
        )

    response_data = _score_to_response(score)
    response_data["score_breakdown"] = score.score_breakdown
    response_data["data_sources"] = score.data_sources
    response_data["recommendations"] = score.recommendations

    return CreditScoreBreakdownResponse(**response_data)


@router.get("/score/history", response_model=CreditScoreHistoryResponse)
async def get_history(
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CreditScoreHistoryResponse:
    """Retourner l'historique des scores."""
    from app.modules.credit.service import get_score_history

    scores, total = await get_score_history(
        db=db, user_id=current_user.id, limit=limit, offset=offset
    )

    return CreditScoreHistoryResponse(
        scores=[
            {
                "id": str(s.id),
                "version": s.version,
                "combined_score": s.combined_score,
                "solvability_score": s.solvability_score,
                "green_impact_score": s.green_impact_score,
                "confidence_level": s.confidence_level,
                "confidence_label": s.confidence_label.value
                if hasattr(s.confidence_label, "value")
                else s.confidence_label,
                "generated_at": s.generated_at,
            }
            for s in scores
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/score/certificate")
async def get_certificate(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Telecharger l'attestation PDF du score le plus recent."""
    from app.modules.credit.service import get_latest_score

    score = await get_latest_score(db=db, user_id=current_user.id)
    if score is None:
        raise HTTPException(
            status_code=404,
            detail="Aucun score disponible pour generer une attestation.",
        )

    now = datetime.now(tz=timezone.utc)
    if score.valid_until and score.valid_until < now:
        raise HTTPException(
            status_code=410,
            detail="Score expire. Regenerez votre score avant de telecharger l'attestation.",
        )

    # Recuperer le profil pour l'attestation
    company_name = current_user.company_name or "Entreprise"
    sector = ""
    location = ""
    try:
        from app.models.company import CompanyProfile
        from sqlalchemy import select

        result = await db.execute(
            select(CompanyProfile).where(CompanyProfile.user_id == current_user.id)
        )
        profile = result.scalar_one_or_none()
        if profile:
            company_name = getattr(profile, "company_name", company_name) or company_name
            sector = getattr(profile, "sector", "") or ""
            if hasattr(sector, "value"):
                sector = sector.value
            location = getattr(profile, "location", "") or ""
    except Exception:
        pass

    from app.modules.credit.certificate import generate_certificate_pdf

    pdf_bytes = generate_certificate_pdf(
        score=score,
        company_name=company_name,
        sector=sector,
        location=location,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="attestation_credit_vert_v{score.version}.pdf"'
        },
    )
