"""Sous-router admin /offers (F09).

Pré-requis spécifique : pour publier une offre, le ``Fund`` ET
l'``Intermediary`` doivent être tous deux ``published`` (FR-006).
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.models.financing import Fund, Intermediary
from app.models.offer import Offer
from app.models.user import User
from app.modules.admin.catalog_publish_helper import (
    EntityNotFoundError,
    PublishGatingError,
    publish_entity,
)
from app.modules.admin.schemas import PublishResponse

logger = logging.getLogger(__name__)


router = APIRouter()


def _serialize(offer: Offer) -> dict:
    return {
        "id": offer.id,
        "publication_status": offer.publication_status,
        "fund_id": offer.fund_id,
        "intermediary_id": offer.intermediary_id,
        "created_at": offer.created_at,
        "updated_at": offer.updated_at,
    }


@router.get("", status_code=status.HTTP_200_OK)
async def list_offers(
    publication_status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(Offer)
    count_stmt = select(func.count(Offer.id))
    if publication_status:
        stmt = stmt.where(Offer.publication_status == publication_status)
        count_stmt = count_stmt.where(Offer.publication_status == publication_status)
    offset = (page - 1) * page_size
    stmt = stmt.order_by(Offer.created_at.desc()).offset(offset).limit(page_size)
    items = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one() or 0
    return {
        "items": [_serialize(o) for o in items],
        "total": total,
        "page": page,
        "limit": page_size,
    }


@router.get("/{offer_id}", status_code=status.HTTP_200_OK)
async def get_offer(
    offer_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    res = await db.execute(select(Offer).where(Offer.id == offer_id))
    offer = res.scalar_one_or_none()
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer introuvable")
    return _serialize(offer)


@router.post(
    "/{offer_id}/publish",
    response_model=PublishResponse,
    status_code=status.HTTP_200_OK,
)
async def publish_offer(
    offer_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> PublishResponse:
    """Publier une offre — exige Fund ET Intermediary published."""
    res = await db.execute(select(Offer).where(Offer.id == offer_id))
    offer = res.scalar_one_or_none()
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer introuvable")

    fund = (
        await db.execute(select(Fund).where(Fund.id == offer.fund_id))
    ).scalar_one_or_none()
    if fund is None or fund.publication_status != "published":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "fund_not_published",
                "message": "Le fonds parent doit être publié avant l'offre.",
            },
        )

    inter = (
        await db.execute(
            select(Intermediary).where(Intermediary.id == offer.intermediary_id)
        )
    ).scalar_one_or_none()
    if inter is None or inter.publication_status != "published":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "intermediary_not_published",
                "message": "L'intermédiaire parent doit être publié avant l'offre.",
            },
        )

    try:
        result = await publish_entity(
            db,
            entity_type="offer",
            entity_id=offer_id,
            admin_id=current_admin.id,
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PublishGatingError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "publish_gating",
                "message": str(exc),
                "blocking_sources": [str(s) for s in exc.blocking_sources],
            },
        ) from exc
    return PublishResponse(**result)
