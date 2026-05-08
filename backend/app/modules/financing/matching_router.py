"""Endpoints REST pour le matching Project ↔ Offer (F14).

5 endpoints sous ``/api/projects/{project_id}/`` :
- ``GET /matches`` : liste paginée triée par global_score DESC
- ``POST /recompute-matches`` : 202 Accepted + BackgroundTasks
- ``GET /compare`` : comparateur multi-intermédiaires (query fund_id)
- ``GET /match-details/{offer_id}`` : détail d'un match
- ``PATCH /match-alerts`` : toggle souscription alertes
"""

from __future__ import annotations

import logging
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import async_session_factory, get_db
from app.models.user import User
from app.modules.financing import matching_service
from app.modules.financing.matching_schemas import (
    ComparisonResult,
    MatchAlertSubscriptionRead,
    MatchAlertSubscriptionUpdate,
    OfferMatchDetail,
    OfferMatchListResponse,
    OfferMatchRead,
    RecomputeMatchesResponse,
)


logger = logging.getLogger(__name__)


router = APIRouter()


def _require_account_id(user: User) -> uuid.UUID:
    if user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte requis pour accéder au matching",
        )
    return user.account_id


@router.get(
    "/{project_id}/matches", response_model=OfferMatchListResponse,
)
async def list_matches_endpoint(
    project_id: uuid.UUID,
    min_score: int = Query(default=0, ge=0, le=100),
    bottleneck: str | None = Query(default=None),
    fund_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OfferMatchListResponse:
    """Liste paginée des matches actifs d'un projet."""
    account_id = _require_account_id(current_user)
    if bottleneck is not None and bottleneck not in {
        "fund", "intermediary", "balanced",
    }:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="bottleneck invalide",
        )
    items, total = await matching_service.list_matches_for_project(
        db,
        account_id=account_id,
        project_id=project_id,
        min_score=min_score,
        bottleneck=bottleneck,
        fund_id=fund_id,
        page=page,
        limit=limit,
    )
    return OfferMatchListResponse(
        items=[OfferMatchRead.model_validate(m) for m in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.post(
    "/{project_id}/recompute-matches",
    response_model=RecomputeMatchesResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def recompute_matches_endpoint(
    project_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecomputeMatchesResponse:
    """Déclenche un recompute async de tous les matches du projet."""
    _require_account_id(current_user)
    request_id, total = await matching_service.recompute_matches_for_project(
        db, project_id=project_id,
    )

    async def _runner() -> None:
        async with async_session_factory() as bg_db:
            try:
                await matching_service.execute_recompute_batch(
                    bg_db, project_id=project_id,
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "recompute_matches: échec batch (project=%s)", project_id,
                )

    background_tasks.add_task(_runner)
    return RecomputeMatchesResponse(
        recompute_request_id=request_id,
        total_offers_to_compute=total,
    )


@router.get(
    "/{project_id}/compare", response_model=ComparisonResult,
)
async def compare_offers_endpoint(
    project_id: uuid.UUID,
    fund_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComparisonResult:
    """Comparateur multi-intermédiaires pour un fonds donné."""
    _require_account_id(current_user)
    payload = await matching_service.compare_offers_for_fund(
        db, project_id=project_id, fund_id=fund_id,
    )
    return ComparisonResult.model_validate(payload)


@router.get(
    "/{project_id}/match-details/{offer_id}", response_model=OfferMatchDetail,
)
async def match_details_endpoint(
    project_id: uuid.UUID,
    offer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OfferMatchDetail:
    """Détail d'un match (avec critères manquants typés)."""
    account_id = _require_account_id(current_user)
    match = await matching_service.get_match_details(
        db,
        account_id=account_id,
        project_id=project_id,
        offer_id=offer_id,
    )
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match introuvable",
        )
    return OfferMatchDetail.model_validate(match)


@router.patch(
    "/{project_id}/match-alerts", response_model=MatchAlertSubscriptionRead,
)
async def update_match_alerts_endpoint(
    project_id: uuid.UUID,
    payload: MatchAlertSubscriptionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MatchAlertSubscriptionRead:
    """Toggle souscription alertes pour un projet."""
    account_id = _require_account_id(current_user)
    sub = await matching_service.update_subscription(
        db,
        account_id=account_id,
        project_id=project_id,
        min_global_score=payload.min_global_score,
        is_active=payload.is_active,
    )
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Souscription introuvable",
        )
    await db.commit()
    return MatchAlertSubscriptionRead.model_validate(sub)


@router.get(
    "/{project_id}/match-alerts", response_model=MatchAlertSubscriptionRead,
)
async def get_match_alerts_endpoint(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MatchAlertSubscriptionRead:
    """Lit la souscription d'alertes du projet."""
    account_id = _require_account_id(current_user)
    sub = await matching_service.get_subscription(
        db, account_id=account_id, project_id=project_id,
    )
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pas de souscription pour ce projet",
        )
    return MatchAlertSubscriptionRead.model_validate(sub)
