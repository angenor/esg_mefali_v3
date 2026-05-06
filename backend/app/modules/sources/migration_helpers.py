"""Helpers pour migrer les valeurs codees en dur (F01 / US7).

Lit les modules existants :
- app.modules.carbon.emission_factors.EMISSION_FACTORS
- app.modules.esg.criteria.{ENVIRONMENT,SOCIAL,GOVERNANCE}_CRITERIA
- app.modules.esg.weights.SECTOR_WEIGHTS

et insere des EmissionFactor / Indicator / Referential / ReferentialIndicator
relies a leurs sources verifiees respectives.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.emission_factor import EmissionFactor
from app.models.indicator import Indicator
from app.models.referential import Referential, ReferentialIndicator
from app.models.simulation_factor import SimulationFactor
from app.models.source import PublicationStatus, Source, VerificationStatus
from app.models.user import User
from app.modules.sources.seed import SYSTEM_CURATOR_EMAIL, get_source_id_by_publisher

logger = logging.getLogger(__name__)


async def _get_curator_id(db: AsyncSession) -> UUID:
    """Recuperer l'ID du curator systeme."""
    result = await db.execute(
        select(User.id).where(User.email == SYSTEM_CURATOR_EMAIL)
    )
    cid = result.scalar_one_or_none()
    if cid is None:
        raise RuntimeError(
            "User systeme curator absent - lancer seed_sources d'abord",
        )
    return cid


async def seed_emission_factors(db: AsyncSession) -> int:
    """Migrer le dict EMISSION_FACTORS vers la table emission_factors.

    Mapping source :
    - category 'energy', 'transport', 'waste' -> ADEME (Base Carbone v23).
    - electricite par pays -> ADEME ou IEA selon dispo.

    Returns:
        Nombre de lignes crees.
    """
    from app.modules.carbon.emission_factors import EMISSION_FACTORS

    curator_id = await _get_curator_id(db)
    ademe_source_id = await get_source_id_by_publisher(db, "ADEME")
    iea_source_id = await get_source_id_by_publisher(db, "IEA")
    if ademe_source_id is None:
        raise RuntimeError("Source ADEME absente du catalogue")

    created = 0
    for code, entry in EMISSION_FACTORS.items():
        # Skip si deja present
        existing = await db.execute(
            select(EmissionFactor).where(EmissionFactor.code == code)
        )
        if existing.scalar_one_or_none() is not None:
            continue
        # Source : ADEME pour energy/transport/waste, IEA pour electricite
        # specifique a un pays.
        if "_ci" in code or "_sn" in code:
            sid = iea_source_id or ademe_source_id
        else:
            sid = ademe_source_id
        # Pays : Cote d'Ivoire pour _ci, sinon WORLD/UEMOA generique.
        country = "CI" if "_ci" in code else "UEMOA"
        ef = EmissionFactor(
            code=code,
            label=entry["label"],
            category=entry["category"],
            country=country,
            value=float(entry["factor"]),
            unit=entry["unit"],
            source_id=sid,
            publication_status=PublicationStatus.PUBLISHED.value,
            created_by_user_id=curator_id,
        )
        db.add(ef)
        created += 1
    await db.flush()
    logger.info("seed_emission_factors : %d lignes creees", created)
    return created


async def seed_esg_indicators(db: AsyncSession) -> int:
    """Migrer les 30 ESGCriterion vers la table indicators.

    Mapping source par pillar :
    - environment -> Taxonomie verte UEMOA.
    - social -> IFC Performance Standards.
    - governance -> ODD ONU 17.
    """
    from app.modules.esg.criteria import (
        ENVIRONMENT_CRITERIA,
        GOVERNANCE_CRITERIA,
        SOCIAL_CRITERIA,
    )

    curator_id = await _get_curator_id(db)

    # Resoudre les sources par pillar
    uemoa_id = await get_source_id_by_publisher(db, "UEMOA")
    ifc_id = await get_source_id_by_publisher(db, "IFC")
    odd_id = await get_source_id_by_publisher(db, "ODD ONU")

    if not (uemoa_id and ifc_id and odd_id):
        raise RuntimeError(
            "Sources requises absentes : UEMOA, IFC ou ODD ONU"
        )

    pillar_to_source = {
        "environment": uemoa_id,
        "social": ifc_id,
        "governance": odd_id,
    }
    all_criteria = list(ENVIRONMENT_CRITERIA) + list(SOCIAL_CRITERIA) + list(GOVERNANCE_CRITERIA)
    created = 0
    for crit in all_criteria:
        existing = await db.execute(
            select(Indicator).where(Indicator.code == crit.code)
        )
        if existing.scalar_one_or_none() is not None:
            continue
        ind = Indicator(
            code=crit.code,
            pillar=crit.pillar,
            label=crit.label,
            description=crit.description,
            question=crit.question,
            source_id=pillar_to_source[crit.pillar],
            publication_status=PublicationStatus.PUBLISHED.value,
            created_by_user_id=curator_id,
        )
        db.add(ind)
        created += 1
    await db.flush()
    logger.info("seed_esg_indicators : %d indicators crees", created)
    return created


async def seed_sector_weights(db: AsyncSession) -> int:
    """Migrer SECTOR_WEIGHTS vers referentials + referential_indicators.

    Pour chaque secteur :
    - 1 referential `<sector>-WEIGHTS` cree (source : BOAD).
    - N referential_indicators avec poids non-unitaires.
    """
    from app.modules.esg.weights import SECTOR_WEIGHTS

    curator_id = await _get_curator_id(db)
    boad_id = await get_source_id_by_publisher(db, "BOAD")
    if boad_id is None:
        raise RuntimeError("Source BOAD absente du catalogue")

    created = 0
    for sector, weights in SECTOR_WEIGHTS.items():
        ref_code = f"{sector.upper()}-WEIGHTS"
        existing = await db.execute(
            select(Referential).where(Referential.code == ref_code)
        )
        ref = existing.scalar_one_or_none()
        if ref is None:
            ref = Referential(
                code=ref_code,
                label=f"Ponderations sectorielles {sector}",
                description=f"Poids ESG specifiques au secteur {sector} (UEMOA).",
                source_id=boad_id,
                publication_status=PublicationStatus.PUBLISHED.value,
                created_by_user_id=curator_id,
            )
            db.add(ref)
            await db.flush()
        # Pour chaque (critere, poids) : creer un referential_indicators si
        # l'indicateur correspondant existe.
        for code, weight in weights.items():
            ind_result = await db.execute(
                select(Indicator).where(Indicator.code == code)
            )
            ind = ind_result.scalar_one_or_none()
            if ind is None:
                continue
            # eviter doublons
            existing_link = await db.execute(
                select(ReferentialIndicator).where(
                    ReferentialIndicator.referential_id == ref.id,
                    ReferentialIndicator.indicator_id == ind.id,
                )
            )
            if existing_link.scalar_one_or_none() is not None:
                continue
            link = ReferentialIndicator(
                referential_id=ref.id,
                indicator_id=ind.id,
                weight=weight,
                source_id=boad_id,
            )
            db.add(link)
            created += 1
    await db.flush()
    logger.info("seed_sector_weights : %d liaisons creees", created)
    return created


async def seed_simulation_factors(db: AsyncSession) -> int:
    """Migrer les constantes du simulateur en `pending` (sans source officielle).

    Constants migrees (placeholder ; les valeurs reelles peuvent etre ajustees
    en consultant les modules financier/simulateur lorsqu'ils existent).
    """
    curator_id = await _get_curator_id(db)
    factors = [
        {
            "code": "savings_rate",
            "label": "Taux d'epargne PME UEMOA (estimation)",
            "value": 0.15,
            "unit": "ratio",
            "scope": "UEMOA",
        },
        {
            "code": "carbon_impact_per_mxof",
            "label": "Impact carbone par million de FCFA investi (estimation)",
            "value": 1.7,
            "unit": "tCO2e/MXOF",
            "scope": "UEMOA",
        },
    ]
    created = 0
    for factor in factors:
        existing = await db.execute(
            select(SimulationFactor).where(SimulationFactor.code == factor["code"])
        )
        if existing.scalar_one_or_none() is not None:
            continue
        sf = SimulationFactor(
            code=factor["code"],
            label=factor["label"],
            value=factor["value"],
            unit=factor["unit"],
            scope=factor["scope"],
            source_id=None,
            status="pending",
            created_by_user_id=curator_id,
        )
        db.add(sf)
        created += 1
    await db.flush()
    logger.info("seed_simulation_factors : %d lignes creees", created)
    return created


async def run_full_migration(db: AsyncSession) -> dict[str, int]:
    """Orchestre toutes les migrations F01."""
    from app.modules.sources.seed import seed_sources

    sources_created, _ = await seed_sources(db)
    indicators_created = await seed_esg_indicators(db)
    factors_created = await seed_emission_factors(db)
    sectors_created = await seed_sector_weights(db)
    sim_created = await seed_simulation_factors(db)
    return {
        "sources": sources_created,
        "indicators": indicators_created,
        "emission_factors": factors_created,
        "sector_weights": sectors_created,
        "simulation_factors": sim_created,
    }
