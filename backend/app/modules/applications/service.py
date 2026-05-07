"""Service metier pour le module Dossiers de Candidature."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import (
    ApplicationStatus,
    FundApplication,
    TargetType,
    VALID_TRANSITIONS,
)
from app.models.financing import Fund, Intermediary, IntermediaryType
from app.modules.applications.snapshot import (
    SnapshotImmutableError,
    build_snapshot_data,
    estimate_snapshot_size_bytes,
    SNAPSHOT_WARN_SIZE_BYTES,
    validate_immutable,
)

logger = logging.getLogger(__name__)


# =====================================================================
# DETERMINATION DU TARGET_TYPE
# =====================================================================


INTERMEDIARY_TYPE_TO_TARGET: dict[str, TargetType] = {
    IntermediaryType.partner_bank: TargetType.intermediary_bank,
    IntermediaryType.implementation_agency: TargetType.intermediary_agency,
    IntermediaryType.project_developer: TargetType.intermediary_developer,
    IntermediaryType.accredited_entity: TargetType.intermediary_agency,
    IntermediaryType.national_agency: TargetType.intermediary_agency,
}


async def determine_target_type(
    db: AsyncSession,
    intermediary_id: uuid.UUID | None,
) -> TargetType:
    """Determiner le target_type a partir de l'intermediaire."""
    if intermediary_id is None:
        return TargetType.fund_direct

    result = await db.execute(
        select(Intermediary).where(Intermediary.id == intermediary_id)
    )
    intermediary = result.scalar_one_or_none()
    if intermediary is None:
        return TargetType.fund_direct

    return INTERMEDIARY_TYPE_TO_TARGET.get(
        intermediary.intermediary_type, TargetType.intermediary_agency
    )


# =====================================================================
# CRUD DOSSIERS
# =====================================================================


async def create_application(
    db: AsyncSession,
    user_id: uuid.UUID,
    fund_id: uuid.UUID,
    match_id: uuid.UUID | None = None,
    intermediary_id: uuid.UUID | None = None,
) -> FundApplication:
    """Creer un nouveau dossier de candidature."""
    from app.modules.applications.templates import (
        get_checklist_for_target,
        initialize_sections,
    )

    # Verifier que le fonds existe
    fund_result = await db.execute(select(Fund).where(Fund.id == fund_id))
    fund = fund_result.scalar_one_or_none()
    if fund is None:
        raise ValueError("Fonds non trouve")

    # Determiner le target_type
    target_type = await determine_target_type(db, intermediary_id)

    # Initialiser les sections et la checklist
    sections = initialize_sections(target_type.value)
    checklist = get_checklist_for_target(target_type.value)

    application = FundApplication(
        user_id=user_id,
        fund_id=fund_id,
        match_id=match_id,
        intermediary_id=intermediary_id,
        target_type=target_type,
        status=ApplicationStatus.draft,
        sections=sections,
        checklist=checklist,
    )
    db.add(application)
    await db.flush()
    await db.refresh(application, ["fund", "intermediary"])
    return application


async def get_application_by_id(
    db: AsyncSession,
    application_id: uuid.UUID,
) -> FundApplication | None:
    """Recuperer un dossier par ID."""
    result = await db.execute(
        select(FundApplication).where(FundApplication.id == application_id)
    )
    return result.scalar_one_or_none()


async def get_applications(
    db: AsyncSession,
    user_id: uuid.UUID,
    status: str | None = None,
) -> tuple[list[FundApplication], int]:
    """Liste des dossiers d'un utilisateur."""
    query = select(FundApplication).where(FundApplication.user_id == user_id)

    if status:
        query = query.where(FundApplication.status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(FundApplication.updated_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def update_application_status(
    db: AsyncSession,
    application: FundApplication,
    new_status: str,
) -> FundApplication:
    """Mettre a jour le statut d'un dossier avec validation des transitions."""
    current_status = application.status.value if hasattr(application.status, 'value') else application.status
    allowed = VALID_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        raise ValueError(
            f"Transition invalide : {current_status} → {new_status}. "
            f"Transitions autorisees : {', '.join(allowed) if allowed else 'aucune'}"
        )

    application.status = new_status
    application.updated_at = datetime.now(timezone.utc)

    # Marquer la date de soumission si pertinent
    if new_status in ("submitted_to_intermediary", "submitted_to_fund"):
        application.submitted_at = datetime.now(timezone.utc)
        # F04 — Création automatique du snapshot immuable (FR-011, US1).
        # Le snapshot capture l'état du référentiel/fonds/scores au moment
        # de la soumission, garantissant que la candidature reste défendable
        # même si le catalogue évolue ensuite.
        if application.snapshot_at is None:
            await _create_snapshot(db, application)

    await db.flush()
    return application


async def _create_snapshot(
    db: AsyncSession,
    application: FundApplication,
) -> None:
    """Crée et persiste le snapshot immuable d'une candidature.

    Idempotent : si le snapshot existe déjà, lève :class:`SnapshotImmutableError`.
    Logue la taille du snapshot pour observabilité (T707).
    """
    snapshot_data = await build_snapshot_data(application.id, db)
    validate_immutable(application.snapshot_data, snapshot_data)
    application.snapshot_data = snapshot_data
    application.snapshot_at = datetime.now(timezone.utc)
    size_bytes = estimate_snapshot_size_bytes(snapshot_data)
    logger.info(
        "F04 snapshot created application_id=%s size_bytes=%d",
        application.id, size_bytes,
    )
    if size_bytes > SNAPSHOT_WARN_SIZE_BYTES:
        logger.warning(
            "F04 snapshot exceeds warn threshold (%d > %d bytes) "
            "application_id=%s — consider gzip post-MVP",
            size_bytes, SNAPSHOT_WARN_SIZE_BYTES, application.id,
        )


# =====================================================================
# SECTIONS
# =====================================================================


async def update_section(
    db: AsyncSession,
    application: FundApplication,
    section_key: str,
    content: str | None = None,
    status: str | None = None,
) -> dict:
    """Mettre a jour le contenu ou le statut d'une section."""
    sections = dict(application.sections)
    if section_key not in sections:
        raise ValueError(f"Section '{section_key}' non trouvee dans le dossier")

    section = dict(sections[section_key])
    if content is not None:
        section["content"] = content
    if status is not None:
        section["status"] = status
    section["updated_at"] = datetime.now(timezone.utc).isoformat()

    sections[section_key] = section
    application.sections = sections
    application.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "section_key": section_key,
        "title": section["title"],
        "content": section.get("content"),
        "status": section["status"],
        "updated_at": section["updated_at"],
    }


# =====================================================================
# GENERATION LLM
# =====================================================================


def build_section_prompt(
    target_type: str,
    section_key: str,
    section_config: dict,
    company_context: str,
    fund_context: str,
    rag_context: str = "",
) -> str:
    """Construire le prompt pour generer une section du dossier."""
    tone_instruction = section_config.get("tone", "Professionnel et factuel.")
    description = section_config.get("description", "")

    prompt = f"""Tu es un expert en redaction de dossiers de candidature aux fonds verts pour les PME africaines francophones.

CONTEXTE ENTREPRISE :
{company_context}

CONTEXTE FONDS :
{fund_context}

{"INFORMATIONS COMPLEMENTAIRES (RAG) :" + chr(10) + rag_context if rag_context else ""}

SECTION A REDIGER : {section_config.get('title', section_key)}
DESCRIPTION : {description}
TON ET STYLE : {tone_instruction}
TYPE DE DESTINATAIRE : {target_type}

INSTRUCTIONS :
- Redige le contenu de cette section en francais, de maniere professionnelle et complete.
- Utilise un format HTML structure (titres h3/h4, paragraphes, listes a puces).
- Adapte le ton au destinataire ({target_type}).
- Integre les donnees de l'entreprise et du fonds disponibles.
- Longueur visee : 300-800 mots selon la section.
- Ne mets pas de titre principal (il sera ajoute par l'interface).

Ecris directement le contenu HTML de la section :"""

    return prompt


async def generate_section(
    db: AsyncSession,
    application: FundApplication,
    section_key: str,
) -> dict:
    """Generer le contenu d'une section via LLM + RAG."""
    from app.modules.applications.templates import get_template_for_target

    sections = application.sections
    if section_key not in sections:
        raise ValueError(f"Section '{section_key}' non trouvee dans le dossier")

    # Recuperer la config de la section
    target_type = application.target_type.value if hasattr(application.target_type, 'value') else application.target_type
    template = get_template_for_target(target_type)
    section_config = next(
        (s for s in template if s["key"] == section_key), None
    )
    if section_config is None:
        raise ValueError(f"Configuration de section '{section_key}' non trouvee")

    # Construire le contexte entreprise
    company_context = "Aucun profil d'entreprise disponible."

    # Construire le contexte fonds
    fund = application.fund
    fund_context = f"Fonds : {fund.name} ({fund.organization})"
    if fund.description:
        fund_context += f"\nDescription : {fund.description}"
    if fund.sectors_eligible:
        fund_context += f"\nSecteurs eligibles : {', '.join(fund.sectors_eligible)}"

    # Recherche RAG (optionnel)
    rag_context = ""
    try:
        from app.graph.nodes import _fetch_rag_context_for_financing
        rag_context = await _fetch_rag_context_for_financing(
            f"{section_config['title']} {fund.name}"
        )
    except Exception:
        logger.debug("RAG non disponible, generation sans contexte supplementaire")

    # Construire le prompt
    prompt = build_section_prompt(
        target_type=target_type,
        section_key=section_key,
        section_config=section_config,
        company_context=company_context,
        fund_context=fund_context,
        rag_context=rag_context,
    )

    # Appeler le LLM
    from app.graph.nodes import get_llm
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_llm()
    response = await llm.ainvoke([
        SystemMessage(content=prompt),
        HumanMessage(content=f"Genere la section '{section_config['title']}' du dossier."),
    ])

    content = response.content

    # Mettre a jour la section
    return await update_section(
        db, application, section_key, content=content, status="generated"
    )


# =====================================================================
# CHECKLIST
# =====================================================================


async def get_checklist(
    db: AsyncSession,
    application: FundApplication,
) -> list[dict]:
    """Retourner la checklist du dossier."""
    return list(application.checklist)
