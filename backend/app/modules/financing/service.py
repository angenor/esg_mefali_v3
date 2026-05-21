"""Service metier pour le module Financement Vert."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload

from app.models.financing import (
    AccessType,
    FinancingChunk,
    FinancingSourceType,
    Fund,
    FundIntermediary,
    FundMatch,
    FundStatus,
    Intermediary,
    MatchStatus,
)


# =====================================================================
# CRUD FONDS
# =====================================================================


async def get_funds(
    db: AsyncSession,
    fund_type: str | None = None,
    sector: str | None = None,
    min_amount: int | None = None,
    max_amount: int | None = None,
    access_type: str | None = None,
    status: str = "active",
    page: int = 1,
    limit: int = 20,
) -> tuple[list[Fund], int]:
    """Liste des fonds avec filtres et pagination."""
    query = select(Fund)

    if fund_type:
        query = query.where(Fund.fund_type == fund_type)
    if access_type:
        query = query.where(Fund.access_type == access_type)
    if status:
        query = query.where(Fund.status == status)
    if sector:
        query = query.where(Fund.sectors_eligible.contains([sector]))
    if min_amount is not None:
        query = query.where(
            (Fund.max_amount_xof.is_(None)) | (Fund.max_amount_xof >= min_amount)
        )
    if max_amount is not None:
        query = query.where(
            (Fund.min_amount_xof.is_(None)) | (Fund.min_amount_xof <= max_amount)
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Fund.name).offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def get_fund_by_id(db: AsyncSession, fund_id: uuid.UUID) -> Fund | None:
    """Recuperer un fonds par ID avec ses intermediaires."""
    result = await db.execute(select(Fund).where(Fund.id == fund_id))
    return result.scalar_one_or_none()


async def create_fund(db: AsyncSession, data: dict) -> Fund:
    """Creer un nouveau fonds."""
    fund = Fund(**data)
    db.add(fund)
    await db.flush()
    return fund


# =====================================================================
# CRUD INTERMEDIAIRES
# =====================================================================


async def get_intermediaries(
    db: AsyncSession,
    intermediary_type: str | None = None,
    organization_type: str | None = None,
    country: str | None = None,
    city: str | None = None,
    fund_id: uuid.UUID | None = None,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[Intermediary], int]:
    """Liste des intermediaires avec filtres et pagination."""
    query = select(Intermediary).where(Intermediary.is_active.is_(True))

    if intermediary_type:
        query = query.where(Intermediary.intermediary_type == intermediary_type)
    if organization_type:
        query = query.where(Intermediary.organization_type == organization_type)
    if country:
        query = query.where(Intermediary.country == country)
    if city:
        query = query.where(Intermediary.city == city)
    if fund_id:
        query = query.join(
            FundIntermediary,
            FundIntermediary.intermediary_id == Intermediary.id,
        ).where(FundIntermediary.fund_id == fund_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Intermediary.name).offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def get_intermediary_by_id(
    db: AsyncSession, intermediary_id: uuid.UUID
) -> Intermediary | None:
    """Recuperer un intermediaire par ID avec fonds couverts."""
    result = await db.execute(
        select(Intermediary)
        .options(
            selectinload(Intermediary.fund_intermediaries)
            .selectinload(FundIntermediary.fund)
        )
        .where(Intermediary.id == intermediary_id)
    )
    return result.scalar_one_or_none()


async def get_fund_intermediaries(
    db: AsyncSession, fund_id: uuid.UUID
) -> list[FundIntermediary]:
    """Recuperer les liaisons fonds-intermediaires pour un fonds."""
    result = await db.execute(
        select(FundIntermediary)
        .options(selectinload(FundIntermediary.intermediary))
        .where(FundIntermediary.fund_id == fund_id)
    )
    return list(result.scalars().all())


# =====================================================================
# RECHERCHE SEMANTIQUE (RAG)
# =====================================================================


async def search_financing_chunks(
    db: AsyncSession,
    query_text: str,
    source_type: str | None = None,
    limit: int = 5,
) -> list[FinancingChunk]:
    """Recherche semantique sur les chunks financing par cosine distance."""
    try:
        from langchain_openai import OpenAIEmbeddings

        from app.core.config import settings
    except ImportError:
        return []

    if not settings.openrouter_api_key:
        return []

    embeddings_model = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=settings.openrouter_api_key,
        openai_api_base="https://openrouter.ai/api/v1",
    )

    query_vector = await embeddings_model.aembed_query(query_text)

    query = select(FinancingChunk).where(
        FinancingChunk.embedding.is_not(None)
    )
    if source_type:
        query = query.where(FinancingChunk.source_type == source_type)

    query = query.order_by(
        FinancingChunk.embedding.cosine_distance(query_vector)
    ).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


# =====================================================================
# MATCHING (Phase 3 — US1)
# =====================================================================

# Ponderations du score de compatibilite
WEIGHT_SECTOR = 0.30
WEIGHT_ESG = 0.25
WEIGHT_SIZE = 0.15
WEIGHT_LOCATION = 0.10
WEIGHT_DOCUMENTS = 0.20


def _score_sector(
    company_sector: str | None, fund_sectors: list[str]
) -> int:
    """Score de compatibilite sectorielle (0-100)."""
    if not company_sector or not fund_sectors:
        return 30  # Score par defaut si pas de donnees
    sector_lower = company_sector.lower()
    fund_sectors_lower = [s.lower() for s in fund_sectors]
    if sector_lower in fund_sectors_lower:
        return 100
    # Correspondances partielles
    sector_mappings = {
        "agriculture": ["agriculture", "foret", "eau", "biodiversite"],
        "energie": ["energie", "electrification_rurale"],
        "industrie": ["industrie", "batiment"],
        "transport": ["transport"],
        "dechets": ["dechets", "environnement"],
        "recyclage": ["dechets", "environnement", "industrie"],
    }
    related = sector_mappings.get(sector_lower, [])
    if any(r in fund_sectors_lower for r in related):
        return 70
    return 20


def _score_esg(
    esg_score: int | None, fund_esg_req: dict
) -> int:
    """Score de compatibilite ESG (0-100)."""
    if esg_score is None:
        return 0  # Pas de score ESG = prerequis manquant
    min_required = fund_esg_req.get("min_score", 0)
    if min_required == 0:
        return 80  # Pas d'exigence ESG = bonne compatibilite
    if esg_score >= min_required:
        ratio = min(esg_score / max(min_required, 1), 2.0)
        return min(int(50 + ratio * 25), 100)
    # En dessous du minimum
    ratio = esg_score / max(min_required, 1)
    return max(int(ratio * 50), 10)


def _score_size(
    company_revenue: int | None,
    fund_min: int | None,
    fund_max: int | None,
) -> int:
    """Score de compatibilite taille (0-100)."""
    if company_revenue is None:
        return 40  # Pas de donnees
    if fund_min and company_revenue < fund_min:
        return max(int((company_revenue / fund_min) * 50), 10)
    if fund_max and company_revenue > fund_max * 10:
        return 30  # Trop grande entreprise pour ce fonds
    if fund_min and fund_max:
        if fund_min <= company_revenue <= fund_max:
            return 100
        return 70
    return 80


def _score_location(
    company_country: str | None,
    company_city: str | None,
    fund_eligibility: dict,
) -> int:
    """Score de compatibilite geographique (0-100)."""
    eligible_countries = fund_eligibility.get("country_eligibility", [])
    if not eligible_countries:
        return 80  # Pas de restriction geographique
    if not company_country:
        return 40  # Pas de donnees
    if company_country in eligible_countries:
        return 100
    # Verifier les variantes de nom
    country_lower = company_country.lower()
    eligible_lower = [c.lower() for c in eligible_countries]
    if country_lower in eligible_lower:
        return 100
    return 10


def _score_documents(
    available_docs: list[str], required_docs: list[str]
) -> int:
    """Score de completude documentaire (0-100)."""
    if not required_docs:
        return 90  # Pas de documents requis
    if not available_docs:
        return 20
    available_lower = {d.lower() for d in available_docs}
    required_lower = [d.lower() for d in required_docs]
    matched = sum(1 for d in required_lower if d in available_lower)
    return max(int((matched / len(required_lower)) * 100), 10)


def compute_compatibility_score(
    company_sector: str | None,
    esg_score: int | None,
    company_revenue: int | None,
    company_country: str | None,
    company_city: str | None,
    available_documents: list[str],
    fund: Fund,
) -> tuple[int, dict[str, int], dict[str, list[str]]]:
    """Calcule le score de compatibilite global entre une PME et un fonds.

    Retourne (score_global, sous_scores, criteres_manquants).
    """
    sector_score = _score_sector(company_sector, fund.sectors_eligible)
    esg_score_val = _score_esg(esg_score, fund.esg_requirements)
    size_score = _score_size(company_revenue, fund.min_amount_xof, fund.max_amount_xof)
    location_score = _score_location(
        company_country, company_city, fund.eligibility_criteria
    )
    docs_score = _score_documents(available_documents, fund.required_documents)

    matching_criteria = {
        "sector": sector_score,
        "esg": esg_score_val,
        "size": size_score,
        "location": location_score,
        "documents": docs_score,
    }

    global_score = int(
        sector_score * WEIGHT_SECTOR
        + esg_score_val * WEIGHT_ESG
        + size_score * WEIGHT_SIZE
        + location_score * WEIGHT_LOCATION
        + docs_score * WEIGHT_DOCUMENTS
    )

    # Identifier les criteres manquants
    missing_criteria: dict[str, list[str]] = {}
    if sector_score < 50:
        missing_criteria["sector"] = [
            f"Secteur requis : {', '.join(fund.sectors_eligible)}"
        ]
    if esg_score_val == 0:
        missing_criteria["esg"] = ["Score ESG requis — completez votre evaluation ESG"]
    elif esg_score_val < 50:
        min_req = fund.esg_requirements.get("min_score", 0)
        missing_criteria["esg"] = [f"Score ESG minimum requis : {min_req}/100"]
    if size_score < 50:
        missing_criteria["size"] = ["Chiffre d'affaires hors fourchette du fonds"]
    if location_score < 50:
        eligible = fund.eligibility_criteria.get("country_eligibility", [])
        missing_criteria["location"] = [
            f"Pays eligibles : {', '.join(eligible)}"
        ]
    if docs_score < 50:
        missing_criteria["documents"] = [
            f"Documents requis : {', '.join(fund.required_documents)}"
        ]

    return global_score, matching_criteria, missing_criteria


async def get_fund_matches(
    db: AsyncSession,
    user_id: uuid.UUID,
    company_sector: str | None = None,
    esg_score: int | None = None,
    company_revenue: int | None = None,
    company_country: str | None = None,
    company_city: str | None = None,
    available_documents: list[str] | None = None,
    account_id: uuid.UUID | None = None,
) -> list[FundMatch]:
    """Calcule ou met a jour les matches pour un utilisateur.

    Pour chaque fonds actif, calcule le score de compatibilite et upsert le match.
    Retourne les matches tries par score decroissant.
    """
    docs = available_documents or []

    # Recuperer tous les fonds actifs
    result = await db.execute(
        select(Fund).where(Fund.status == FundStatus.active)
    )
    active_funds = list(result.scalars().all())

    matches = []
    for fund in active_funds:
        score, criteria, missing = compute_compatibility_score(
            company_sector, esg_score, company_revenue,
            company_country, company_city, docs, fund,
        )

        # Trouver les intermediaires recommandes
        recommended = []
        if fund.access_type != AccessType.direct:
            inter_result = await db.execute(
                select(FundIntermediary)
                .options(selectinload(FundIntermediary.intermediary))
                .where(FundIntermediary.fund_id == fund.id)
                .order_by(FundIntermediary.is_primary.desc())
            )
            for fi in inter_result.scalars().all():
                intermediary = fi.intermediary
                if intermediary and intermediary.is_active:
                    recommended.append({
                        "id": str(intermediary.id),
                        "name": intermediary.name,
                        "city": intermediary.city,
                    })

        # Upsert le match
        existing_match = await db.execute(
            select(FundMatch)
            .options(selectinload(FundMatch.fund))
            .where(
                FundMatch.user_id == user_id,
                FundMatch.fund_id == fund.id,
            )
        )
        match = existing_match.scalar_one_or_none()

        if match is None:
            match = FundMatch(
                user_id=user_id,
                account_id=account_id,
                fund_id=fund.id,
                compatibility_score=score,
                matching_criteria=criteria,
                missing_criteria=missing,
                recommended_intermediaries=recommended,
                estimated_timeline_months=fund.typical_timeline_months,
                status=MatchStatus.suggested,
            )
            # Assigner la relation pour eviter un lazy load en async
            match.fund = fund
            db.add(match)
        else:
            match.compatibility_score = score
            match.matching_criteria = criteria
            match.missing_criteria = missing
            match.recommended_intermediaries = recommended
            match.estimated_timeline_months = fund.typical_timeline_months

        matches.append(match)

    await db.flush()

    # Trier par score decroissant
    matches.sort(key=lambda m: m.compatibility_score, reverse=True)
    return matches


async def get_match_by_fund(
    db: AsyncSession, user_id: uuid.UUID, fund_id: uuid.UUID
) -> FundMatch | None:
    """Recuperer un match specifique utilisateur-fonds."""
    result = await db.execute(
        select(FundMatch)
        .options(selectinload(FundMatch.fund))
        .where(
            FundMatch.user_id == user_id,
            FundMatch.fund_id == fund_id,
        )
    )
    return result.scalar_one_or_none()


async def get_match_by_id(
    db: AsyncSession, match_id: uuid.UUID, user_id: uuid.UUID
) -> FundMatch | None:
    """Recuperer un match par son ID."""
    result = await db.execute(
        select(FundMatch)
        .options(selectinload(FundMatch.fund))
        .where(
            FundMatch.id == match_id,
            FundMatch.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


# Transitions de statut valides
VALID_STATUS_TRANSITIONS: dict[MatchStatus, list[MatchStatus]] = {
    MatchStatus.suggested: [MatchStatus.interested],
    MatchStatus.interested: [MatchStatus.contacting_intermediary],
    MatchStatus.contacting_intermediary: [MatchStatus.applying],
    MatchStatus.applying: [MatchStatus.submitted],
    MatchStatus.submitted: [MatchStatus.accepted, MatchStatus.rejected],
    MatchStatus.accepted: [],
    MatchStatus.rejected: [MatchStatus.interested],
}


async def update_match_status(
    db: AsyncSession, match: FundMatch, new_status: MatchStatus
) -> FundMatch:
    """Met a jour le statut d'un match avec validation des transitions."""
    current = match.status
    allowed = VALID_STATUS_TRANSITIONS.get(current, [])
    if new_status not in allowed:
        allowed_str = ", ".join(s.value for s in allowed) or "aucune"
        raise ValueError(
            f"Transition invalide : {current.value} -> {new_status.value}. "
            f"Transitions autorisees depuis {current.value} : {allowed_str}"
        )
    match.status = new_status
    await db.flush()
    return match


async def update_match_intermediary(
    db: AsyncSession,
    match: FundMatch,
    intermediary_id: uuid.UUID,
) -> FundMatch:
    """Enregistre l'intermediaire choisi pour un match."""
    # Verifier que l'intermediaire est lie au fonds
    link = await db.execute(
        select(FundIntermediary).where(
            FundIntermediary.fund_id == match.fund_id,
            FundIntermediary.intermediary_id == intermediary_id,
        )
    )
    if link.scalar_one_or_none() is None:
        raise ValueError("Cet intermediaire n'est pas lie a ce fonds.")

    match.contacted_intermediary_id = intermediary_id
    if match.status == MatchStatus.interested:
        match.status = MatchStatus.contacting_intermediary
    await db.flush()
    return match


async def check_esg_prerequisite(
    db: AsyncSession, user_id: uuid.UUID
) -> dict | None:
    """Verifie que l'utilisateur a un score ESG. Retourne un message de redirection si non."""
    try:
        from app.models.esg import ESGAssessment

        result = await db.execute(
            select(ESGAssessment)
            .where(ESGAssessment.user_id == user_id)
            .order_by(ESGAssessment.created_at.desc())
            .limit(1)
        )
        assessment = result.scalar_one_or_none()
        if assessment is None:
            return {
                "redirect": "/esg",
                "message": "Vous devez d'abord realiser votre evaluation ESG avant de consulter les recommandations de financement.",
            }
        return None
    except Exception:
        return None


# =====================================================================
# PARCOURS D'ACCES (Phase 4 — US2)
# =====================================================================


async def recommend_intermediaries(
    db: AsyncSession,
    fund_id: uuid.UUID,
    city: str | None = None,
) -> list[dict]:
    """Recommande les intermediaires pour un fonds, tries par pertinence."""
    result = await db.execute(
        select(FundIntermediary)
        .options(selectinload(FundIntermediary.intermediary))
        .where(FundIntermediary.fund_id == fund_id)
        .order_by(FundIntermediary.is_primary.desc())
    )
    fund_inters = list(result.scalars().all())

    recommendations = []
    for fi in fund_inters:
        inter = fi.intermediary
        if not inter or not inter.is_active:
            continue
        rec = {
            "id": str(inter.id),
            "name": inter.name,
            "intermediary_type": inter.intermediary_type.value,
            "organization_type": inter.organization_type.value,
            "city": inter.city,
            "country": inter.country,
            "contact_email": inter.contact_email,
            "contact_phone": inter.contact_phone,
            "physical_address": inter.physical_address,
            "role": fi.role,
            "is_primary": fi.is_primary,
            "services_offered": inter.services_offered,
            "typical_fees": inter.typical_fees,
            "geographic_coverage": fi.geographic_coverage,
        }
        recommendations.append(rec)

    # Trier : is_primary d'abord, puis meme ville en priorite
    if city:
        recommendations.sort(
            key=lambda r: (not r["is_primary"], r["city"].lower() != city.lower())
        )

    return recommendations


async def generate_access_pathway(
    db: AsyncSession,
    fund: Fund,
    company_city: str | None = None,
) -> dict:
    """Genere le parcours d'acces pour un fonds."""
    if fund.access_type == AccessType.direct:
        return {
            "type": "direct",
            "steps": [
                {
                    "step": i + 1,
                    "phase": step.get("title", ""),
                    "title": step.get("title", ""),
                    "description": step.get("description", ""),
                    "duration_weeks": None,
                }
                for i, step in enumerate(fund.application_process)
            ],
            "total_duration_months": fund.typical_timeline_months,
            "message": "Vous pouvez candidater directement aupres de ce fonds.",
        }

    # Pour les fonds via intermediaire ou mixtes
    intermediaries = await recommend_intermediaries(db, fund.id, city=company_city)
    primary = next((i for i in intermediaries if i["is_primary"]), None)
    primary_name = primary["name"] if primary else "un intermediaire accredite"

    steps = []
    for i, step_data in enumerate(fund.application_process):
        steps.append({
            "step": i + 1,
            "phase": _step_phase(i, len(fund.application_process)),
            "title": step_data.get("title", ""),
            "description": step_data.get("description", ""),
            "duration_weeks": None,
        })

    pathway_type = "intermediary" if fund.access_type == AccessType.intermediary_required else "mixed"
    message = (
        f"Ce fonds necessite de passer par un intermediaire. "
        f"Nous recommandons {primary_name} comme point de contact principal."
    )
    if fund.access_type == AccessType.mixed:
        message = (
            f"Ce fonds offre un acces mixte : direct pour les grands projets, "
            f"via intermediaire pour les PME. Nous recommandons {primary_name}."
        )

    return {
        "type": pathway_type,
        "steps": steps,
        "total_duration_months": fund.typical_timeline_months,
        "intermediaries": intermediaries,
        "recommended_primary": primary,
        "message": message,
    }


def build_initial_financing_state() -> dict:
    """Initialiser le financing_data dans le state LangGraph.

    Appele quand l'utilisateur pose une question financement.
    """
    return {
        "active": True,
        "query_count": 0,
    }


def _step_phase(index: int, total: int) -> str:
    """Determine la phase d'une etape du parcours."""
    if total <= 1:
        return "action"
    ratio = index / max(total - 1, 1)
    if ratio <= 0.2:
        return "preparation"
    if ratio <= 0.5:
        return "contact"
    if ratio <= 0.8:
        return "instruction"
    return "finalisation"
