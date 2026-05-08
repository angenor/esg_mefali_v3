"""F18 — Seed du catalogue ``CreditMethodologyFactor`` v1.2 publié.

Idempotent : check ``(version, name)`` avant INSERT (UNIQUE).

Chaque facteur référence ``source_id`` NOT NULL (invariant F01). Les
publishers sont retrouvés via :func:`app.modules.sources.seed.get_source_id_by_publisher`
qui renvoie la 1re Source ``verified`` correspondante. Les sources doivent
donc être seedées AVANT (`seed_sources`).

Pondérations FR-016 : la catégorie ``public_data`` est plafonnée à 10 %
(FR-015 / SC-005) — c'est le compute_combined_score qui applique le cap
strict (le seed est juste informatif côté UI méthodologie publique).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit_alternative import CreditMethodologyFactor
from app.modules.sources.seed import get_source_id_by_publisher

logger = logging.getLogger(__name__)


METHODOLOGY_VERSION = "1.2"


@dataclass(frozen=True)
class _SeedFactor:
    """Définition immuable d'un facteur méthodologique (cf. PEP 8)."""

    name: str
    category: str
    weight: Decimal
    description: str
    publisher: str  # Publisher F01 (BCEAO, ADEME, IPCC, ...)


# Catalogue MVP F18 v1.2 — 7 facteurs publiés (Mobile Money + Public + ESG).
# Toute pondération est indicative ; le compute_combined_score applique le
# cap strict ``public_data ≤ 10 %`` (FR-015).
SEED_FACTORS: tuple[_SeedFactor, ...] = (
    # === Mobile Money flux (~30 % cumulés) ===
    _SeedFactor(
        name="MM Régularité 30j",
        category="mobile_money_flux",
        weight=Decimal("0.150"),
        description=(
            "Taux d'activité Mobile Money sur 30 jours glissants "
            "(jours actifs / 30). Signal de régularité opérationnelle."
        ),
        publisher="BCEAO",
    ),
    _SeedFactor(
        name="MM Volume mensuel moyen",
        category="mobile_money_flux",
        weight=Decimal("0.100"),
        description=(
            "Volume entrant moyen mensuel (XOF). Échelle d'activité "
            "économique mesurée."
        ),
        publisher="BCEAO",
    ),
    _SeedFactor(
        name="MM Croissance 12 mois",
        category="mobile_money_flux",
        weight=Decimal("0.050"),
        description=(
            "Tendance relative entre 1er et dernier mois actif. Signal "
            "de progression d'activité."
        ),
        publisher="BCEAO",
    ),
    # === Photos IA (P2 — déclaré 0 %, P2 ticket follow-up) ===
    _SeedFactor(
        name="Photos IA Qualité d'exploitation",
        category="photos_ia",
        weight=Decimal("0.050"),
        description=(
            "Indicateurs visuels d'exploitation (équipements, espace, "
            "stocks). Différé en P2 (analyse Vision)."
        ),
        publisher="ADEME",
    ),
    # === Données publiques (≤ 10 % — FR-015) ===
    _SeedFactor(
        name="Avis publics et notoriété",
        category="public_data",
        weight=Decimal("0.060"),
        description=(
            "Note moyenne et nombre d'avis (Google Reviews, Trustpilot). "
            "Données déclaratives non vérifiées — plafonné à 10 % du score."
        ),
        publisher="UEMOA",
    ),
    _SeedFactor(
        name="Programmes verts labellisés",
        category="public_data",
        weight=Decimal("0.040"),
        description=(
            "Adhésion à un label PNUE/ADEME/GRI Sustainability. "
            "Plafonné à 10 % du score (FR-015)."
        ),
        publisher="ADEME",
    ),
    # === ESG / carbone (poids hérités du compute_combined_score actuel) ===
    _SeedFactor(
        name="Score ESG global",
        category="esg",
        weight=Decimal("0.200"),
        description=(
            "Score ESG agrégé (E + S + G) pondéré sectoriellement. "
            "Méthodologie référentielle Mefali / GCF / IFC."
        ),
        publisher="IPCC",
    ),
)


async def seed_credit_methodology_factors(
    db: AsyncSession,
) -> tuple[int, int]:
    """Seed les facteurs méthodologiques v1.2 publiés.

    Returns:
        (created_count, skipped_count) pour observabilité.

    Raises:
        RuntimeError: si une source publisher cible n'existe pas en BDD
            (seed_sources doit avoir tourné avant).
    """
    created = 0
    skipped = 0

    # Cache local des source_id par publisher (évite N requêtes).
    source_cache: dict[str, object] = {}

    for entry in SEED_FACTORS:
        # Idempotence : check (version, name) UNIQUE.
        existing = await db.execute(
            select(CreditMethodologyFactor).where(
                CreditMethodologyFactor.version == METHODOLOGY_VERSION,
                CreditMethodologyFactor.name == entry.name,
            )
        )
        if existing.scalar_one_or_none() is not None:
            skipped += 1
            continue

        if entry.publisher not in source_cache:
            source_id = await get_source_id_by_publisher(db, entry.publisher)
            if source_id is None:
                raise RuntimeError(
                    f"Source publisher '{entry.publisher}' introuvable en BDD. "
                    "Lancez `seed_sources` avant `seed_credit_methodology_factors`."
                )
            source_cache[entry.publisher] = source_id

        factor = CreditMethodologyFactor(
            version=METHODOLOGY_VERSION,
            name=entry.name,
            category=entry.category,
            weight=entry.weight,
            description=entry.description,
            source_id=source_cache[entry.publisher],
            publication_status="published",
        )
        db.add(factor)
        created += 1

    await db.flush()
    logger.info(
        "seed_credit_methodology_factors : %d crees, %d ignores (version %s)",
        created,
        skipped,
        METHODOLOGY_VERSION,
    )
    return created, skipped


__all__ = [
    "seed_credit_methodology_factors",
    "SEED_FACTORS",
    "METHODOLOGY_VERSION",
]
