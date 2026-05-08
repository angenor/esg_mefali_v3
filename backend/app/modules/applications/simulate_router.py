"""F16 — Router REST pour la simulation multi-offres sourcée.

Endpoint :
- ``POST /api/projects/{project_id}/simulate-multi`` : compare 1..5 offres.

Auth : ``Depends(get_current_user)``. Multi-tenant : le projet et toutes
les offres doivent être accessibles à ``current_user.account_id`` (FR-013).
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.modules.applications.multi_simulate_service import (
    OfferAccessDeniedError,
    ProjectNotFoundError,
    simulate_multi,
)
from app.modules.applications.simulation_schemas import (
    MultiSimulateRequest,
    MultiSimulateResponse,
)


logger = logging.getLogger(__name__)


router = APIRouter()


@router.post(
    "/{project_id}/simulate-multi",
    response_model=MultiSimulateResponse,
)
async def simulate_multi_endpoint(
    project_id: uuid.UUID,
    body: MultiSimulateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MultiSimulateResponse:
    """F16 — Simule jusqu'à 5 offres pour un projet, calcul à la demande.

    Réponses :
    - 200 : :class:`MultiSimulateResponse` (chaque offre = nominale ou dégradée).
    - 401 : auth manquante (filtré par ``Depends``).
    - 403 : au moins une offre est inaccessible au compte.
    - 404 : projet inexistant ou hors tenant (FR-013, on ne révèle pas
      l'existence d'un projet d'un autre compte).
    - 422 : payload invalide (offer_ids hors borne, dedup → 0).
    """
    account_id = getattr(current_user, "account_id", None)
    try:
        return await simulate_multi(
            db,
            project_id=project_id,
            offer_ids=body.offer_ids,
            account_id=account_id,
        )
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="project_not_found")
    except OfferAccessDeniedError:
        raise HTTPException(status_code=403, detail="offer_access_denied")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
