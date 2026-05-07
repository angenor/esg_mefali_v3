"""Router admin pour les offres (F07).

Endpoints admin (rôle ``admin`` requis via ``get_current_admin``) :
- ``GET /api/admin/offers?include_drafts=true`` — liste complète
- ``POST /api/admin/offers/compute`` — preview du calcul auto
- ``POST /api/admin/offers`` — création depuis draft édité
- ``PATCH /api/admin/offers/{id}`` — édition (transitions status incluses)
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.models.user import User
from app.modules.offers import service
from app.modules.offers.schemas import (
    OfferCreate,
    OfferDraft,
    OfferListResponse,
    OfferRead,
    OfferSummary,
    OfferUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/offers", response_model=OfferListResponse)
async def admin_list_offers(
    include_drafts: bool = True,
    fund_id: UUID | None = None,
    intermediary_id: UUID | None = None,
    sort: str = Query("name", pattern="^(name|processing_time)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> OfferListResponse:
    """Liste complète des offres (drafts inclus par défaut côté admin)."""
    offers, total = await service.list_offers(
        db,
        fund_id=fund_id,
        intermediary_id=intermediary_id,
        include_drafts=include_drafts,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    items = [OfferSummary.model_validate(o) for o in offers]
    return OfferListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/offers/compute", response_model=OfferDraft)
async def admin_compute_offer(
    fund_id: UUID = Query(..., description="UUID du fonds source"),
    intermediary_id: UUID = Query(..., description="UUID de l'intermédiaire"),
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> OfferDraft:
    """Preview du calcul automatique d'une offre (sans persistance).

    Retourne un ``OfferDraft`` avec critères/documents/frais/délais effectifs.
    L'admin peut éditer puis appeler ``POST /api/admin/offers``.
    """
    try:
        return await service.compute_offer_preview(
            db, fund_id=fund_id, intermediary_id=intermediary_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.post(
    "/offers",
    response_model=OfferRead,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_offer(
    payload: OfferCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> OfferRead:
    """Crée une offre depuis un draft édité (admin only).

    L'offre est créée en ``publication_status='draft'`` et ``is_active=False``
    par défaut.
    """
    try:
        offer = await service.create_offer(db, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return OfferRead.model_validate(offer)


@router.patch("/offers/{offer_id}", response_model=OfferRead)
async def admin_update_offer(
    offer_id: UUID,
    payload: OfferUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> OfferRead:
    """Met à jour une offre (édition + transitions publication_status).

    Si la transition ``draft → published`` est demandée et qu'un prérequis
    manque, retourne 422 avec ``missing_prerequisites=[...]``.
    """
    offer, missing = await service.update_offer(db, offer_id, payload)
    if offer is None and not missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offre introuvable",
        )
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Prérequis de publication non remplis",
                "missing_prerequisites": missing,
            },
        )
    return OfferRead.model_validate(offer)
