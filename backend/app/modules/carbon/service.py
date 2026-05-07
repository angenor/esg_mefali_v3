"""Service metier pour le module Calculateur d'Empreinte Carbone."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.carbon import CarbonAssessment, CarbonEmissionEntry, CarbonStatusEnum
from app.modules.carbon.benchmarks import compute_benchmark_position, get_sector_benchmark
from app.modules.carbon.emission_factors import (
    EMISSION_CATEGORIES,
    compute_emissions_tco2e,
    compute_equivalences,
    get_applicable_categories,
    get_emission_factor,
)


# --- CRUD ---


async def create_assessment(
    db: AsyncSession,
    user_id: uuid.UUID,
    year: int,
    sector: str | None = None,
    conversation_id: uuid.UUID | None = None,
) -> CarbonAssessment:
    """Creer un nouveau bilan carbone. Leve une erreur si un bilan existe deja pour cette annee."""
    # Verifier l'unicite user_id + year
    existing = await db.execute(
        select(CarbonAssessment).where(
            CarbonAssessment.user_id == user_id,
            CarbonAssessment.year == year,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Un bilan carbone existe deja pour l'annee {year}")

    assessment = CarbonAssessment(
        user_id=user_id,
        conversation_id=conversation_id,
        year=year,
        sector=sector,
        status=CarbonStatusEnum.in_progress,
        completed_categories=[],
    )
    db.add(assessment)
    await db.flush()
    return assessment


async def get_assessment(
    db: AsyncSession,
    assessment_id: uuid.UUID,
    user_id: uuid.UUID,
) -> CarbonAssessment | None:
    """Recuperer un bilan carbone par ID, filtre par utilisateur."""
    result = await db.execute(
        select(CarbonAssessment).where(
            CarbonAssessment.id == assessment_id,
            CarbonAssessment.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def list_assessments(
    db: AsyncSession,
    user_id: uuid.UUID,
    status: str | None = None,
    page: int = 1,
    limit: int = 10,
) -> tuple[list[CarbonAssessment], int]:
    """Lister les bilans carbone d'un utilisateur avec pagination."""
    query = select(CarbonAssessment).where(CarbonAssessment.user_id == user_id)

    if status is not None:
        query = query.where(CarbonAssessment.status == status)

    # Compter le total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Pagination
    query = query.order_by(CarbonAssessment.created_at.desc())
    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    assessments = list(result.scalars().all())

    return assessments, total


async def get_resumable_assessment(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> CarbonAssessment | None:
    """Trouver un bilan in_progress existant pour reprise."""
    result = await db.execute(
        select(CarbonAssessment)
        .where(
            CarbonAssessment.user_id == user_id,
            CarbonAssessment.status == CarbonStatusEnum.in_progress,
        )
        .order_by(CarbonAssessment.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_assessment(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> CarbonAssessment | None:
    """Trouver le bilan le plus recent pour un utilisateur, quel que soit le statut.

    Utile pour la consultation : un utilisateur peut avoir uniquement des bilans
    `completed` et vouloir les relire. `get_resumable_assessment` ne retourne
    que `in_progress` et renvoie None dans ce cas.
    """
    result = await db.execute(
        select(CarbonAssessment)
        .where(CarbonAssessment.user_id == user_id)
        .order_by(CarbonAssessment.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# --- Ajout d'entrees ---


async def add_entries(
    db: AsyncSession,
    assessment: CarbonAssessment,
    entries_data: list[dict],
    mark_category_complete: str | None = None,
) -> tuple[int, float, list[str]]:
    """Ajouter des entrees d'emissions a un bilan.

    Retourne (nombre d'entrees ajoutees, total emissions, categories completees).
    """
    if assessment.status == CarbonStatusEnum.completed:
        raise ValueError("Ce bilan est deja finalise")

    added = 0
    for entry_data in entries_data:
        entry = CarbonEmissionEntry(
            assessment_id=assessment.id,
            category=entry_data["category"],
            subcategory=entry_data["subcategory"],
            quantity=entry_data["quantity"],
            unit=entry_data["unit"],
            emission_factor=entry_data["emission_factor"],
            emissions_tco2e=entry_data["emissions_tco2e"],
            source_description=entry_data.get("source_description"),
            # F17 — FK source_id + factor_id pour le sourcage (None tolere
            # pour entries legacy non backfillees ; le tool refactore valide
            # la presence avant d'invoquer ``add_entries``).
            source_id=entry_data.get("source_id"),
            factor_id=entry_data.get("factor_id"),
        )
        db.add(entry)
        added += 1

    # Marquer une categorie comme completee
    completed = list(assessment.completed_categories or [])
    if mark_category_complete and mark_category_complete not in completed:
        completed.append(mark_category_complete)
        assessment.completed_categories = completed

    # Recalculer le total des emissions
    await db.flush()
    total = await _compute_total_emissions(db, assessment.id)
    assessment.total_emissions_tco2e = total

    return added, total, completed


async def _compute_total_emissions(
    db: AsyncSession,
    assessment_id: uuid.UUID,
) -> float:
    """Calculer le total des emissions pour un bilan."""
    result = await db.execute(
        select(func.sum(CarbonEmissionEntry.emissions_tco2e)).where(
            CarbonEmissionEntry.assessment_id == assessment_id,
        )
    )
    return result.scalar() or 0.0


# --- Finalisation ---


async def complete_assessment(
    db: AsyncSession,
    assessment: CarbonAssessment,
    reduction_plan: dict | None = None,
) -> CarbonAssessment:
    """Finaliser un bilan carbone.

    F17 (T046) : si ``reduction_plan`` est fourni avec la cle ``actions``
    (schema F17 canonique), il est valide via ``ReductionPlan.model_validate``
    avant attribution. Les anciens formats (``quick_wins`` / ``long_term``)
    restent acceptes en passe-passe pour retro-compatibilite.
    """
    total = await _compute_total_emissions(db, assessment.id)
    assessment.total_emissions_tco2e = total
    assessment.status = CarbonStatusEnum.completed
    if reduction_plan is not None:
        # F17 — validation Pydantic du nouveau schema actions[].
        if isinstance(reduction_plan, dict) and "actions" in reduction_plan:
            from app.modules.carbon.reduction_plan_schema import ReductionPlan

            # Leve une ValueError si invalide (cohesion source_id <-> unsourced).
            ReductionPlan.model_validate(reduction_plan)
        assessment.reduction_plan = reduction_plan
    await db.flush()
    return assessment


# --- Resume / Summary ---


async def get_assessment_summary(
    db: AsyncSession,
    assessment: CarbonAssessment,
) -> dict:
    """Generer le resume complet d'un bilan pour la page resultats."""
    # Ventilation par categorie
    entries_query = select(CarbonEmissionEntry).where(
        CarbonEmissionEntry.assessment_id == assessment.id
    )
    result = await db.execute(entries_query)
    entries = list(result.scalars().all())

    total = assessment.total_emissions_tco2e or 0.0
    by_category: dict[str, dict] = {}

    for entry in entries:
        cat = entry.category
        if cat not in by_category:
            by_category[cat] = {"emissions_tco2e": 0.0, "entries_count": 0}
        by_category[cat]["emissions_tco2e"] += entry.emissions_tco2e
        by_category[cat]["entries_count"] += 1

    # Calculer les pourcentages
    for cat_data in by_category.values():
        cat_data["percentage"] = (
            round((cat_data["emissions_tco2e"] / total) * 100, 1) if total > 0 else 0.0
        )

    # Equivalences parlantes
    equivalences = compute_equivalences(total)

    # Benchmark sectoriel
    sector_benchmark = None
    if assessment.sector:
        sector_benchmark = compute_benchmark_position(total, assessment.sector)

    return {
        "assessment_id": str(assessment.id),
        "year": assessment.year,
        "status": assessment.status.value if hasattr(assessment.status, "value") else assessment.status,
        "total_emissions_tco2e": total,
        "by_category": by_category,
        "equivalences": equivalences,
        "reduction_plan": assessment.reduction_plan,
        "sector_benchmark": sector_benchmark,
    }


# --- Helpers pour le carbon_node ---


def build_initial_carbon_state(
    assessment_id: str,
    sector: str | None = None,
) -> dict:
    """Construire l'etat initial du carbon_data pour le ConversationState."""
    applicable = get_applicable_categories(sector)
    return {
        "assessment_id": assessment_id,
        "status": "in_progress",
        "current_category": applicable[0] if applicable else "energy",
        "completed_categories": [],
        "applicable_categories": applicable,
        "entries": [],
        "total_emissions_tco2e": 0.0,
        "sector": sector,
    }


def get_next_category(current: str, applicable: list[str]) -> str | None:
    """Retourne la prochaine categorie apres la categorie actuelle."""
    try:
        idx = applicable.index(current)
        if idx + 1 < len(applicable):
            return applicable[idx + 1]
    except ValueError:
        pass
    return None


def compute_category_label(category_key: str) -> str:
    """Retourne le label francais d'une categorie."""
    for cat in EMISSION_CATEGORIES:
        if cat["key"] == category_key:
            return cat["label"]
    return category_key.capitalize()
