"""F16 — Service ``simulate_multi`` : compose simulate_offer pour 1..5 offres.

- Charge un snapshot unique de facteurs (FR-017).
- Vérifie l'isolation multi-tenant (FR-013).
- Calcule chaque offre indépendamment ; en cas d'échec d'une offre,
  retourne une :class:`DegradedColumn` sans interrompre le rendu des autres
  (FR-016).
- Calcule ``cheapest_offer_id`` (min total_cost en devise PME) et
  ``fastest_offer_id`` (min sum(weeks_max)) parmi les colonnes nominales.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.money import Currency, Money
from app.models.emission_factor import EmissionFactor
from app.models.offer import Offer
from app.models.project import Project
from app.modules.applications.factor_service import (
    FactorSnapshot,
    load_factors_snapshot,
)
from app.modules.applications.simulation_engine import (
    FactorMissingError,
    OfferDataMissingError,
    simulate_offer,
)
from app.modules.applications.simulation_schemas import (
    ComparisonMetadata,
    DegradedColumn,
    MultiSimulateResponse,
    SimulationResult,
)


logger = logging.getLogger(__name__)


PME_CURRENCY: Currency = "XOF"


class ProjectNotFoundError(Exception):
    """Levé quand le projet n'existe pas ou n'appartient pas au compte."""


class OfferAccessDeniedError(Exception):
    """Levé quand au moins une offre n'est pas accessible (publication,
    multi-tenant)."""


async def _load_project(
    db: AsyncSession, project_id: uuid.UUID, account_id: uuid.UUID | None
) -> Project:
    """Charge le projet en respectant l'isolation tenant.

    NB : RLS PG est censé filtrer ; on double-check applicativement pour
    SQLite et pour ne pas révéler l'existence (FR-013, VR-003).
    """
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError("project_not_found")
    if account_id is not None and project.account_id != account_id:
        raise ProjectNotFoundError("project_not_found")
    return project


async def _load_offers(
    db: AsyncSession, offer_ids: list[uuid.UUID]
) -> list[Offer]:
    """Charge les offres avec fund + intermediary chargés (selectinload)."""
    stmt = (
        select(Offer)
        .options(
            joinedload(Offer.fund),
            joinedload(Offer.intermediary),
        )
        .where(Offer.id.in_(offer_ids))
    )
    result = await db.execute(stmt)
    offers = list(result.unique().scalars().all())
    return offers


async def _resolve_sector_factor(
    db: AsyncSession, project: Project, year: int
) -> tuple[Decimal | None, uuid.UUID | None, bool]:
    """Cherche un facteur sectoriel d'émission via F17 (lecture seule).

    Stratégie :
    1. country exact + year exact ;
    2. country exact + year < year (la plus récente) ;
    3. country = 'GLOBAL' + year exact ;
    4. country = 'GLOBAL' + year le plus récent.

    Retourne ``(value, source_id, is_approximate)`` ou ``(None, None, False)``
    si rien.
    """
    country = (project.location_country or "GLOBAL").upper()
    # 1. exact
    stmt = (
        select(EmissionFactor)
        .where(
            EmissionFactor.category == "sector_carbon_intensity",
            EmissionFactor.country == country,
            EmissionFactor.year == year,
        )
        .limit(1)
    )
    res = await db.execute(stmt)
    ef = res.scalar_one_or_none()
    if ef is not None:
        return Decimal(str(ef.value)), ef.source_id, False
    # 2. country + older
    stmt = (
        select(EmissionFactor)
        .where(
            EmissionFactor.category == "sector_carbon_intensity",
            EmissionFactor.country == country,
            EmissionFactor.year < year,
        )
        .order_by(EmissionFactor.year.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    ef = res.scalar_one_or_none()
    if ef is not None:
        return Decimal(str(ef.value)), ef.source_id, True
    # 3. global exact
    stmt = (
        select(EmissionFactor)
        .where(
            EmissionFactor.category == "sector_carbon_intensity",
            EmissionFactor.country == "GLOBAL",
            EmissionFactor.year == year,
        )
        .limit(1)
    )
    res = await db.execute(stmt)
    ef = res.scalar_one_or_none()
    if ef is not None:
        return Decimal(str(ef.value)), ef.source_id, country != "GLOBAL"
    # 4. global older
    stmt = (
        select(EmissionFactor)
        .where(
            EmissionFactor.category == "sector_carbon_intensity",
            EmissionFactor.country == "GLOBAL",
        )
        .order_by(EmissionFactor.year.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    ef = res.scalar_one_or_none()
    if ef is not None:
        return Decimal(str(ef.value)), ef.source_id, True
    return None, None, False


def _total_weeks(result: SimulationResult) -> int | None:
    """Somme des ``weeks_max`` non-nuls. Retourne None si toute timeline
    incomplète."""
    weeks: list[int] = []
    for step in result.timeline:
        if step.step_id == "preparation":
            continue  # effort PME, hors comparaison
        if step.weeks_max is None:
            return None
        weeks.append(step.weeks_max)
    return sum(weeks) if weeks else None


def _rank_offers(
    per_offer: dict[uuid.UUID, SimulationResult | DegradedColumn],
) -> tuple[uuid.UUID | None, uuid.UUID | None, list[uuid.UUID]]:
    """Calcule cheapest/fastest et la liste des dégradés.

    Comparaison naïve : on compare ``total_cost.amount`` quand les devises
    sont identiques ; sinon on prend tel quel (le frontend convertit). Le
    tie-break est lexicographique sur l'UUID pour déterminisme.
    """
    nominal: list[SimulationResult] = [
        v for v in per_offer.values() if isinstance(v, SimulationResult)
    ]
    degraded: list[uuid.UUID] = [
        v.offer_id
        for v in per_offer.values()
        if isinstance(v, DegradedColumn)
    ]
    if len(nominal) < 2:
        return None, None, degraded

    # Cheapest : min total_cost.amount (avec tie-break UUID)
    cheapest = min(
        nominal,
        key=lambda r: (r.cost_breakdown.total_cost.amount, str(r.offer_id)),
    )
    # Fastest : min total weeks (None excluded)
    candidates_with_tw = [
        (r, _total_weeks(r)) for r in nominal
    ]
    candidates_with_tw = [(r, tw) for (r, tw) in candidates_with_tw if tw is not None]
    fastest_id: uuid.UUID | None = None
    if candidates_with_tw:
        fastest = min(candidates_with_tw, key=lambda x: (x[1], str(x[0].offer_id)))
        fastest_id = fastest[0].offer_id

    return cheapest.offer_id, fastest_id, degraded


async def simulate_multi(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    offer_ids: list[uuid.UUID],
    account_id: uuid.UUID | None,
) -> MultiSimulateResponse:
    """Service principal F16 : simulation multi-offres pour un projet."""
    if len(offer_ids) > 5:
        raise ValueError("max_5_offres")
    if len(offer_ids) < 1:
        raise ValueError("min_1_offre")
    # Dédoublonnage applicatif (le validator Pydantic le fait aussi en amont)
    deduped: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for oid in offer_ids:
        if oid not in seen:
            seen.add(oid)
            deduped.append(oid)

    project = await _load_project(db, project_id, account_id)
    offers = await _load_offers(db, deduped)
    found_ids = {o.id for o in offers}
    if not found_ids.issuperset(set(deduped)):
        # Au moins une offre est introuvable ou non accessible.
        # On ne révèle pas laquelle (FR-013).
        raise OfferAccessDeniedError("offer_access_denied")

    snapshot: FactorSnapshot = await load_factors_snapshot(db)

    # Facteur sectoriel carbone (1 lookup par appel — partagé entre offres)
    year = datetime.now(timezone.utc).year
    sector_factor, sector_source_id, sf_approx = await _resolve_sector_factor(
        db, project, year
    )

    per_offer: dict[uuid.UUID, SimulationResult | DegradedColumn] = {}
    offers_by_id = {o.id: o for o in offers}
    for oid in deduped:
        offer = offers_by_id[oid]
        try:
            result = simulate_offer(
                project=project,
                offer=offer,
                snapshot=snapshot,
                sector_factor=sector_factor,
                sector_factor_source_id=sector_source_id,
                is_approximate=sf_approx,
            )
            per_offer[oid] = result
        except (FactorMissingError, OfferDataMissingError) as exc:
            logger.warning(
                "Offer %s degraded: %s", oid, exc
            )
            per_offer[oid] = DegradedColumn(
                offer_id=oid,
                reason=str(exc),
                computed_at=datetime.now(timezone.utc),
            )
        except Exception as exc:  # filet de sécurité
            logger.error("Offer %s unexpected failure: %s", oid, exc)
            per_offer[oid] = DegradedColumn(
                offer_id=oid,
                reason="erreur_calcul_inattendue",
                computed_at=datetime.now(timezone.utc),
            )

    cheapest, fastest, degraded = _rank_offers(per_offer)
    metadata = ComparisonMetadata(
        cheapest_offer_id=cheapest,
        fastest_offer_id=fastest,
        degraded_offers=degraded,
        total_offers=len(deduped),
    )

    return MultiSimulateResponse(
        project_id=project_id,
        per_offer=per_offer,
        comparison_metadata=metadata,
        factor_snapshot_loaded_at=snapshot.loaded_at,
    )
