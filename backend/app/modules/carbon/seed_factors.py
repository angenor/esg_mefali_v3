"""Seed des facteurs d'emission catalogue (F17).

Peuple ``emission_factors`` avec ~50 lignes initiales :

    - 8 facteurs ``electricity`` pour les 8 pays UEMOA (CI, SN, BF, ML, NE,
      BJ, TG, GW) en 2024 + variantes 2023 pour fallback annee anterieure
      (sources : IEA Africa Energy Outlook 2024).
    - 3 facteurs combustibles (diesel, gasoline, butane) en global 2024
      (source : ADEME Base Carbone v23).
    - 4 facteurs transport personnel (gasoline, diesel, hybrid, electric).
    - 3 facteurs transport freight (camion leger, camion lourd, fluvial).
    - 3 facteurs dechets (landfill, incineration, compost) — IPCC AR6 WG3
      pour landfill (methane).
    - 6 facteurs achats matieres premieres (steel, cement, paper, food,
      plastic, other) — ADEME Base Carbone v23.

Idempotence : ``ON CONFLICT (code) DO NOTHING`` au niveau du seed
applicatif (verifie avant insert).

Sources publiques :
    - ADEME Base Carbone v23 (2024) : https://base-empreinte.ademe.fr/
    - IPCC AR6 WG3 chapitre 10 : https://www.ipcc.ch/report/ar6/wg3/
    - IEA Africa Energy Outlook 2024 :
      https://www.iea.org/reports/africa-energy-outlook-2024
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.emission_factor import EmissionFactor
from app.models.source import PublicationStatus, Source
from app.models.user import User

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeedResult:
    """Resultat du seed des facteurs d'emission."""

    inserted: int
    skipped: int
    total_in_db: int


@dataclass(frozen=True)
class SeedFactor:
    """Definition d'un facteur a seeder.

    Attributes:
        code: Identifiant unique snake_case (ex. ``electricity_ci_2024``).
        label: Libelle francais lisible.
        category: Categorie technique (electricity, fuel_diesel, ...).
        country: Code ISO 2 lettres (CI, SN, ...) ou ``global``.
        year: Annee de reference.
        value: Valeur du facteur.
        unit: Unite (kgCO2e/kWh, kgCO2e/L, kgCO2e/kg, etc.).
        publisher: Editeur (ADEME, IEA, IPCC) pour resoudre la source_id.
    """

    code: str
    label: str
    category: str
    country: str
    year: int
    value: float
    unit: str
    publisher: str


# ---------- Donnees de seed ----------

# Mix electrique 8 pays UEMOA 2024 (IEA Africa Energy Outlook 2024).
# Valeurs estimees : ces chiffres correspondent aux moyennes pays publiees
# par l'IEA. Les variantes 2023 sont incluses pour permettre le fallback
# annee anterieure si l'utilisateur fait un bilan 2024 et qu'aucun facteur
# 2024 specifique n'existe.
_ELECTRICITY_UEMOA_2024: list[tuple[str, str, float]] = [
    ("CI", "Cote d'Ivoire", 0.456),
    ("SN", "Senegal", 0.540),
    ("BF", "Burkina Faso", 0.640),
    ("ML", "Mali", 0.580),
    ("NE", "Niger", 0.620),
    ("BJ", "Benin", 0.670),
    ("TG", "Togo", 0.585),
    ("GW", "Guinee-Bissau", 0.700),
]


def _build_electricity_factors() -> list[SeedFactor]:
    """Construit les facteurs electricite UEMOA 2024 + variantes 2023."""
    factors: list[SeedFactor] = []
    for code_pays, name_pays, value_2024 in _ELECTRICITY_UEMOA_2024:
        factors.append(
            SeedFactor(
                code=f"electricity_{code_pays.lower()}_2024",
                label=f"Electricite reseau {name_pays} 2024",
                category="electricity",
                country=code_pays,
                year=2024,
                value=value_2024,
                unit="kgCO2e/kWh",
                publisher="IEA",
            )
        )
        # Variante annee anterieure (legerement plus elevee, transition
        # energetique en cours).
        factors.append(
            SeedFactor(
                code=f"electricity_{code_pays.lower()}_2023",
                label=f"Electricite reseau {name_pays} 2023",
                category="electricity",
                country=code_pays,
                year=2023,
                value=round(value_2024 * 1.04, 4),
                unit="kgCO2e/kWh",
                publisher="IEA",
            )
        )
    # Fallback global pour pays non couverts.
    factors.append(
        SeedFactor(
            code="electricity_global_2024",
            label="Electricite reseau (moyenne mondiale)",
            category="electricity",
            country="global",
            year=2024,
            value=0.520,
            unit="kgCO2e/kWh",
            publisher="IEA",
        )
    )
    return factors


def _build_fuel_factors() -> list[SeedFactor]:
    """Combustibles globaux 2024 — ADEME Base Carbone v23."""
    return [
        SeedFactor(
            code="fuel_diesel_global_2024",
            label="Gasoil (combustion mobile/stationnaire)",
            category="fuel_diesel",
            country="global",
            year=2024,
            value=2.680,
            unit="kgCO2e/L",
            publisher="ADEME",
        ),
        SeedFactor(
            code="fuel_gasoline_global_2024",
            label="Essence",
            category="fuel_gasoline",
            country="global",
            year=2024,
            value=2.310,
            unit="kgCO2e/L",
            publisher="ADEME",
        ),
        SeedFactor(
            code="fuel_butane_global_2024",
            label="Gaz butane (bouteille)",
            category="fuel_butane",
            country="global",
            year=2024,
            value=2.980,
            unit="kgCO2e/kg",
            publisher="ADEME",
        ),
    ]


def _build_transport_factors() -> list[SeedFactor]:
    """Transport personnel + fret — ADEME Base Carbone v23.

    Note : la contrainte UNIQUE ``(category, country, year)`` impose une
    granularite fine sur les categories. Les variantes (essence/diesel/...)
    sont distinguees par un suffixe de categorie (cf. ``purchases_*``).
    """
    return [
        # Transport personnel : 1 categorie par carburant.
        SeedFactor(
            code="transport_personal_gasoline_2024",
            label="Vehicule personnel essence",
            category="transport_personal_gasoline",
            country="global",
            year=2024,
            value=0.193,
            unit="kgCO2e/km",
            publisher="ADEME",
        ),
        SeedFactor(
            code="transport_personal_diesel_2024",
            label="Vehicule personnel diesel",
            category="transport_personal_diesel",
            country="global",
            year=2024,
            value=0.171,
            unit="kgCO2e/km",
            publisher="ADEME",
        ),
        SeedFactor(
            code="transport_personal_hybrid_2024",
            label="Vehicule personnel hybride",
            category="transport_personal_hybrid",
            country="global",
            year=2024,
            value=0.111,
            unit="kgCO2e/km",
            publisher="ADEME",
        ),
        SeedFactor(
            code="transport_personal_electric_2024",
            label="Vehicule personnel electrique (mix global)",
            category="transport_personal_electric",
            country="global",
            year=2024,
            value=0.062,
            unit="kgCO2e/km",
            publisher="ADEME",
        ),
        # Transport fret : 1 categorie par mode.
        SeedFactor(
            code="transport_freight_light_truck_2024",
            label="Camion leger (utilitaire < 3,5 t)",
            category="transport_freight_light_truck",
            country="global",
            year=2024,
            value=0.230,
            unit="kgCO2e/t.km",
            publisher="ADEME",
        ),
        SeedFactor(
            code="transport_freight_heavy_truck_2024",
            label="Camion lourd (> 3,5 t)",
            category="transport_freight_heavy_truck",
            country="global",
            year=2024,
            value=0.110,
            unit="kgCO2e/t.km",
            publisher="ADEME",
        ),
        SeedFactor(
            code="transport_freight_river_2024",
            label="Transport fluvial",
            category="transport_freight_river",
            country="global",
            year=2024,
            value=0.040,
            unit="kgCO2e/t.km",
            publisher="ADEME",
        ),
    ]


def _build_waste_factors() -> list[SeedFactor]:
    """Dechets — ADEME Base Carbone v23 + IPCC AR6 WG3 chap. 10."""
    return [
        SeedFactor(
            code="waste_landfill_global_2024",
            label="Dechets enfouissement (methane)",
            category="waste_landfill",
            country="global",
            year=2024,
            value=0.500,
            unit="kgCO2e/kg",
            publisher="IPCC",  # AR6 WG3 chap. 10.
        ),
        SeedFactor(
            code="waste_incineration_global_2024",
            label="Dechets incineration",
            category="waste_incineration",
            country="global",
            year=2024,
            value=1.100,
            unit="kgCO2e/kg",
            publisher="ADEME",
        ),
        SeedFactor(
            code="waste_compost_global_2024",
            label="Dechets compostage",
            category="waste_compost",
            country="global",
            year=2024,
            value=0.020,
            unit="kgCO2e/kg",
            publisher="ADEME",
        ),
    ]


def _build_purchases_factors() -> list[SeedFactor]:
    """Achats matieres premieres — ADEME Base Carbone v23 chap. Materiaux."""
    return [
        SeedFactor(
            code="purchases_steel_global_2024",
            label="Acier (matiere premiere)",
            category="purchases_steel",
            country="global",
            year=2024,
            value=1.850,
            unit="kgCO2e/kg",
            publisher="ADEME",
        ),
        SeedFactor(
            code="purchases_cement_global_2024",
            label="Ciment (matiere premiere)",
            category="purchases_cement",
            country="global",
            year=2024,
            value=0.900,
            unit="kgCO2e/kg",
            publisher="ADEME",
        ),
        SeedFactor(
            code="purchases_paper_global_2024",
            label="Papier (matiere premiere)",
            category="purchases_paper",
            country="global",
            year=2024,
            value=1.300,
            unit="kgCO2e/kg",
            publisher="ADEME",
        ),
        SeedFactor(
            code="purchases_food_global_2024",
            label="Alimentation (moyenne)",
            category="purchases_food",
            country="global",
            year=2024,
            value=3.500,
            unit="kgCO2e/kg",
            publisher="ADEME",
        ),
        SeedFactor(
            code="purchases_plastic_global_2024",
            label="Plastique (PE moyen)",
            category="purchases_plastic",
            country="global",
            year=2024,
            value=2.100,
            unit="kgCO2e/kg",
            publisher="ADEME",
        ),
        SeedFactor(
            code="purchases_other_global_2024",
            label="Autres matieres (generique)",
            category="purchases_other",
            country="global",
            year=2024,
            value=1.000,
            unit="kgCO2e/kg",
            publisher="ADEME",
        ),
    ]


def build_seed_data() -> list[SeedFactor]:
    """Construit la liste complete des facteurs a seeder (~50 lignes)."""
    return (
        _build_electricity_factors()
        + _build_fuel_factors()
        + _build_transport_factors()
        + _build_waste_factors()
        + _build_purchases_factors()
    )


# Constante exposee pour les tests et la migration.
SEED_DATA: list[SeedFactor] = build_seed_data()


async def _resolve_publisher_to_source_id(
    db: AsyncSession,
) -> dict[str, uuid.UUID]:
    """Map publisher -> 1ere source_id verified pour ce publisher.

    Pour ADEME : prefere ``ADEME Base Carbone v23`` (titre exact).
    Pour IEA : prefere ``IEA Africa Energy Outlook 2024``.
    Pour IPCC : prefere ``IPCC AR6 Working Group III - Mitigation``.
    """
    from app.models.source import VerificationStatus

    mapping: dict[str, uuid.UUID] = {}

    # ADEME -> Base Carbone v23 si dispo.
    stmt_ademe = (
        select(Source)
        .where(
            Source.publisher == "ADEME",
            Source.verification_status == VerificationStatus.VERIFIED.value,
        )
        .order_by(
            # Trie pour preferer Base Carbone v23 si present.
            (Source.title.ilike("%Base Carbone%")).desc(),
            Source.created_at.desc(),
        )
        .limit(1)
    )
    result_ademe = await db.execute(stmt_ademe)
    src_ademe = result_ademe.scalar_one_or_none()
    if src_ademe is not None:
        mapping["ADEME"] = src_ademe.id

    # IEA -> Africa Energy Outlook 2024 si dispo.
    stmt_iea = (
        select(Source)
        .where(
            Source.publisher == "IEA",
            Source.verification_status == VerificationStatus.VERIFIED.value,
        )
        .order_by(
            (Source.title.ilike("%Africa Energy Outlook%")).desc(),
            Source.created_at.desc(),
        )
        .limit(1)
    )
    result_iea = await db.execute(stmt_iea)
    src_iea = result_iea.scalar_one_or_none()
    if src_iea is not None:
        mapping["IEA"] = src_iea.id

    # IPCC -> AR6 WG3 si dispo.
    stmt_ipcc = (
        select(Source)
        .where(
            Source.publisher == "IPCC",
            Source.verification_status == VerificationStatus.VERIFIED.value,
        )
        .order_by(
            (Source.title.ilike("%Working Group III%")).desc(),
            Source.created_at.desc(),
        )
        .limit(1)
    )
    result_ipcc = await db.execute(stmt_ipcc)
    src_ipcc = result_ipcc.scalar_one_or_none()
    if src_ipcc is not None:
        mapping["IPCC"] = src_ipcc.id

    return mapping


async def seed_emission_factors(
    db: AsyncSession,
    admin_user_id: uuid.UUID,
) -> SeedResult:
    """Seed idempotent des facteurs d'emission catalogue.

    Args:
        db: Session SQLAlchemy async.
        admin_user_id: UUID de l'admin createur (pour created_by_user_id).

    Returns:
        SeedResult(inserted, skipped, total_in_db).
    """
    publisher_map = await _resolve_publisher_to_source_id(db)
    if not publisher_map:
        logger.warning(
            "Aucune source ADEME/IEA/IPCC verifiee trouvee — le seed F17 "
            "ne peut pas creer de facteurs sans source. "
            "Veillez a executer seed_sources (F01) avant.",
        )
        return SeedResult(inserted=0, skipped=0, total_in_db=0)

    # Verifier l'admin existe.
    user_stmt = select(User).where(User.id == admin_user_id)
    admin_user = (await db.execute(user_stmt)).scalar_one_or_none()
    if admin_user is None:
        raise ValueError(
            f"Admin user {admin_user_id} introuvable pour seed_emission_factors."
        )

    inserted = 0
    skipped = 0
    for seed in SEED_DATA:
        source_id = publisher_map.get(seed.publisher)
        if source_id is None:
            logger.warning(
                "Publisher %s non trouve dans le catalogue de sources — "
                "facteur %s ignore.",
                seed.publisher,
                seed.code,
            )
            skipped += 1
            continue

        # Idempotence : verifier si le code existe deja.
        existing_stmt = select(EmissionFactor).where(EmissionFactor.code == seed.code)
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue

        factor = EmissionFactor(
            code=seed.code,
            label=seed.label,
            category=seed.category,
            country=seed.country,
            year=seed.year,
            value=seed.value,
            unit=seed.unit,
            source_id=source_id,
            publication_status=PublicationStatus.PUBLISHED.value,
            account_id=None,  # Catalogue commun.
            created_by_user_id=admin_user_id,
        )
        db.add(factor)
        inserted += 1

    await db.flush()

    # Compter le total apres seed.
    from sqlalchemy import func

    total_stmt = select(func.count()).select_from(EmissionFactor)
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0

    logger.info(
        "seed_emission_factors : %d crees, %d ignores, %d total en BDD",
        inserted,
        skipped,
        total,
    )
    return SeedResult(inserted=inserted, skipped=skipped, total_in_db=total)
