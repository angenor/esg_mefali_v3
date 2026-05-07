"""Router public pour les offres (F07).

Endpoints :
- ``GET /api/offers`` — liste paginée filtrée + triée
- ``GET /api/offers/{id}`` — détail
- ``GET /api/offers/comparator`` — comparateur multi-offres pour un fonds

Filtre strict ``publication_status='published' AND is_active=true``.
Aucune authentification requise (catalogue public).
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.offers import service
from app.modules.offers.schemas import (
    OfferComparison,
    OfferListResponse,
    OfferRead,
    OfferSummary,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/offers", response_model=OfferListResponse)
async def list_offers_endpoint(
    fund_id: UUID | None = None,
    intermediary_id: UUID | None = None,
    theme: str | None = None,
    instrument: str | None = None,
    country: str | None = None,
    language: str | None = None,
    sort: str = Query("name", pattern="^(name|processing_time)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> OfferListResponse:
    """Liste paginée des offres publiées et actives.

    Filtre strict ``publication_status='published' AND is_active=true``.
    """
    offers, total = await service.list_offers(
        db,
        fund_id=fund_id,
        intermediary_id=intermediary_id,
        theme=theme,
        instrument=instrument,
        country=country,
        language=language,
        include_drafts=False,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    items = [OfferSummary.model_validate(o) for o in offers]
    return OfferListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/offers/comparator", response_model=list[OfferComparison])
async def comparator_endpoint(
    fund_id: UUID = Query(..., description="UUID du fonds à comparer"),
    db: AsyncSession = Depends(get_db),
) -> list[OfferComparison]:
    """Retourne toutes les offres publiées+actives pour un fonds donné.

    Format optimisé pour comparateur côte-à-côte.
    """
    return await service.compare_offers_for_fund(db, fund_id=fund_id)


@router.get("/offers/{offer_id}", response_model=OfferRead)
async def get_offer_endpoint(
    offer_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> OfferRead:
    """Récupère une offre par ID.

    Retourne 404 si l'offre est en draft (anti-fuite côté API publique).
    """
    offer = await service.get_offer(db, offer_id, include_drafts=False)
    if offer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offre introuvable",
        )
    return OfferRead.model_validate(offer)
