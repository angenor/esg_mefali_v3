"""Service metier pour le module Dossiers de Candidature."""

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

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
    fund_id: uuid.UUID | None = None,
    match_id: uuid.UUID | None = None,
    intermediary_id: uuid.UUID | None = None,
    offer_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
) -> FundApplication:
    """Creer un nouveau dossier de candidature (chemin partagé chat/UI — F048 D5).

    Si ``offer_id`` est fourni (prioritaire, F07), ``fund_id`` et
    ``intermediary_id`` sont dérivés de l'offre. ``project_id`` rattache le
    dossier au projet cible (F06).

    Dédup (FR-006) : si un dossier ``draft`` existe déjà pour le triplet
    ``(user_id, project_id, offer_id)``, il est retourné tel quel plutôt que
    de créer un doublon. La parité chat/UI (FR-016) est garantie : le tool chat
    et l'endpoint REST appellent ce même service.

    Raises:
        ValueError: offre/fonds introuvable, ou aucune cible fournie.
    """
    from app.modules.applications.templates import (
        get_checklist_for_target,
        initialize_sections,
    )
    from app.models.offer import Offer

    # F07 — Résoudre fund_id/intermediary_id depuis l'offre (prioritaire).
    if offer_id is not None:
        offer = await db.get(Offer, offer_id)
        if offer is None:
            raise ValueError("Offre non trouvee")
        fund_id = offer.fund_id
        intermediary_id = offer.intermediary_id

    if fund_id is None:
        raise ValueError(
            "Un identifiant d'offre (offer_id) ou de fonds (fund_id) est requis."
        )

    # FR-006 — Dédup : réutiliser le dossier draft existant pour ce triplet.
    # Scopé au demandeur (user_id) ET au tenant (account_id si connu) afin
    # d'éviter tout chevauchement cross-compte (F02).
    if offer_id is not None and project_id is not None:
        dedup_filters = [
            FundApplication.user_id == user_id,
            FundApplication.project_id == project_id,
            FundApplication.offer_id == offer_id,
            FundApplication.status == ApplicationStatus.draft,
        ]
        if account_id is not None:
            dedup_filters.append(FundApplication.account_id == account_id)
        existing = await db.execute(
            select(FundApplication).where(*dedup_filters)
        )
        existing_draft = existing.scalar_one_or_none()
        if existing_draft is not None:
            # 050 — charger ``project`` (lazy selectin non déclenché hors requête)
            # pour que la réponse expose le projet sans MissingGreenlet (async).
            await db.refresh(existing_draft, ["fund", "intermediary", "project"])
            return existing_draft

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
        offer_id=offer_id,
        project_id=project_id,
        account_id=account_id,
        target_type=target_type,
        status=ApplicationStatus.draft,
        sections=sections,
        checklist=checklist,
    )
    db.add(application)
    await db.flush()
    # 050 — ``project`` chargé explicitement (selectin non déclenché à la
    # création) pour exposer le projet lié dans la réponse sans MissingGreenlet.
    await db.refresh(application, ["fund", "intermediary", "project"])
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
    project_context: str = "",
) -> str:
    """Construire le prompt pour generer une section du dossier.

    050 — ``project_context`` (issu de :func:`build_project_context`) injecte
    les données réelles du PROJET vert lié au dossier (lien 1:1, F06). Sans lui,
    les sections « projet » (description, impacts, budget) seraient inventées par
    le LLM à partir des seules données génériques d'entreprise. Vide → bloc omis
    (cas legacy ``project_id`` NULL).
    """
    tone_instruction = section_config.get("tone", "Professionnel et factuel.")
    description = section_config.get("description", "")

    project_block = ""
    project_instruction = ""
    if project_context:
        project_block = (
            "CONTEXTE PROJET (le dossier porte sur CE projet précis — appuie-toi "
            "sur ces données réelles, n'invente rien) :\n"
            f"{project_context}\n\n"
        )
        project_instruction = (
            "\n- Pour toute section relative au projet (description, objectifs, "
            "impacts, budget, localisation), appuie-toi EXCLUSIVEMENT sur le "
            "CONTEXTE PROJET réel ci-dessus ; n'invente pas de données génériques."
        )

    prompt = f"""Tu es un expert en redaction de dossiers de candidature aux fonds verts pour les PME africaines francophones.

CONTEXTE ENTREPRISE :
{company_context}

{project_block}CONTEXTE FONDS :
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
- Integre les donnees de l'entreprise et du fonds disponibles.{project_instruction}
- Longueur visee : 300-800 mots selon la section.
- Ne mets pas de titre principal (il sera ajoute par l'interface).
- IMPORTANT : reponds UNIQUEMENT avec le HTML brut. N'entoure JAMAIS ta reponse
  de balises de bloc de code markdown (ni ```html, ni ```).

Ecris directement le contenu HTML de la section :"""

    return prompt


def build_company_context(profile) -> str:
    """F15 BUG-001 — Construit un contexte entreprise non-vide depuis le profil.

    Utilisé par :func:`generate_section` pour remplacer le hardcoded
    ``"Aucun profil d'entreprise disponible."`` par les vraies données
    PME. Si le profil est absent ou vide, lève ``ValueError``.
    """
    if profile is None:
        raise ValueError(
            "Profil entreprise introuvable : la PME doit compléter son "
            "profil avant de générer un dossier."
        )

    parts: list[str] = []
    if profile.company_name:
        parts.append(f"Nom : {profile.company_name}")
    sector = (
        profile.sector.value if hasattr(profile.sector, "value") else profile.sector
    )
    if sector:
        parts.append(f"Secteur : {sector}")
    if profile.country:
        parts.append(f"Pays : {profile.country}")
    if profile.city:
        parts.append(f"Ville : {profile.city}")
    if profile.employee_count:
        parts.append(f"Effectif : {profile.employee_count} employés")
    if getattr(profile, "annual_revenue_money", None) is not None:
        money = profile.annual_revenue_money
        parts.append(
            f"Chiffre d'affaires annuel : {money.amount} {money.currency}"
        )
    elif profile.annual_revenue_xof:
        parts.append(
            f"Chiffre d'affaires annuel : {profile.annual_revenue_xof:,} XOF"
        )
    if profile.year_founded:
        parts.append(f"Année de création : {profile.year_founded}")

    if not parts:
        raise ValueError(
            "Profil entreprise incomplet : champs critiques manquants "
            "(secteur, pays, taille). Veuillez compléter le profil."
        )

    return "\n".join(parts)


# Libellés français des énumérations Project (F06) pour le prompt LLM.
# Le modèle Project stocke des valeurs canoniques (anglais) ; le prompt étant
# rédigé en français, on les traduit pour un contexte naturel et précis.
_PROJECT_OBJECTIVE_ENV_LABELS: dict[str, str] = {
    # Libellés alignés sur le frontend (``types/project.ts`` OBJECTIVE_ENV_LABELS)
    # pour une terminologie cohérente entre le prompt LLM et l'UI.
    "mitigation": "Atténuation",
    "adaptation": "Adaptation",
    "biodiversity": "Biodiversité",
    "circular_economy": "Économie circulaire",
    "water": "Eau",
    "renewable_energy": "Énergie renouvelable",
    "sustainable_agriculture": "Agriculture durable",
    "mixed": "Mixte",
}

_PROJECT_MATURITY_LABELS: dict[str, str] = {
    "ideation": "Idéation",
    "pre_feasibility": "Pré-faisabilité",
    "pilot": "Pilote",
    "scale": "Mise à l'échelle",
    "replication": "Réplication",
}

_PROJECT_STATUS_LABELS: dict[str, str] = {
    "draft": "Brouillon",
    "seeking_funding": "En recherche de financement",
    "funded": "Financé",
    "in_execution": "En exécution",
    "closed": "Clôturé",
    "cancelled": "Annulé",
}

_PROJECT_FINANCING_STRUCTURE_LABELS: dict[str, str] = {
    "subvention": "Subvention",
    "pret_concessionnel": "Prêt concessionnel",
    "equity": "Fonds propres (equity)",
    "blending": "Financement mixte (blending)",
    "mixte": "Mixte",
}


def _fmt_num(value) -> str:
    """Formate un nombre (``Decimal``/``int``) pour le prompt LLM.

    Les colonnes ``Numeric`` renvoient des ``Decimal`` à l'échelle déclarée
    (ex. ``Numeric(20,2)`` → ``Decimal('75000000.00')``). On retire les zéros
    décimaux parasites et on ajoute un séparateur de milliers (espace) pour un
    contexte lisible : ``Decimal('75000000.00')`` → ``'75 000 000'``,
    ``Decimal('12.50')`` → ``'12.5'``.
    """
    s = format(value, "f") if isinstance(value, Decimal) else str(value)
    intpart, _, decpart = s.partition(".")
    decpart = decpart.rstrip("0")
    try:
        grouped = f"{int(intpart):,}".replace(",", " ")
    except ValueError:
        return s
    return f"{grouped}.{decpart}" if decpart else grouped


def build_project_context(project) -> str:
    """050 — Construit le bloc « CONTEXTE PROJET » injecté dans le prompt.

    Le dossier de candidature est lié 1:1 à un projet vert
    (:class:`~app.models.project.Project`, F06). Cette fonction restitue les
    VRAIES données du projet ciblé (nom, description, objectifs, budget Money
    typé, localisation, impacts attendus) afin que les sections générées par le
    LLM reflètent le projet et non des données génériques d'entreprise.

    Robuste au cas legacy : ``project`` à ``None`` (``project_id`` NULL en base
    SQLite de test ou antérieur à la migration 025) → chaîne vide, sans crash.
    Lit défensivement les attributs (``getattr``) pour tolérer des objets
    partiels.
    """
    if project is None:
        return ""

    parts: list[str] = []

    name = getattr(project, "name", None)
    if name:
        parts.append(f"Nom du projet : {name}")

    description = getattr(project, "description", None)
    if description:
        parts.append(f"Description : {description}")

    objective_env = getattr(project, "objective_env", None) or []
    if objective_env:
        labels = ", ".join(
            _PROJECT_OBJECTIVE_ENV_LABELS.get(o, o) for o in objective_env
        )
        parts.append(f"Objectifs environnementaux : {labels}")

    maturity = getattr(project, "maturity", None)
    if maturity:
        parts.append(
            f"Maturité : {_PROJECT_MATURITY_LABELS.get(maturity, maturity)}"
        )

    status = getattr(project, "status", None)
    if status:
        parts.append(f"Statut : {_PROJECT_STATUS_LABELS.get(status, status)}")

    # Budget cible — Money typé F04 (paire amount + currency, les deux requis).
    amount = getattr(project, "target_amount_amount", None)
    currency = getattr(project, "target_amount_currency", None)
    if amount is not None and currency:
        parts.append(f"Budget cible : {_fmt_num(amount)} {currency}")

    duration_months = getattr(project, "duration_months", None)
    if duration_months:
        parts.append(f"Durée prévue : {duration_months} mois")

    financing_structure = getattr(project, "financing_structure", None)
    if financing_structure:
        parts.append(
            "Structure de financement : "
            f"{_PROJECT_FINANCING_STRUCTURE_LABELS.get(financing_structure, financing_structure)}"
        )

    # Localisation (pays ISO + région éventuelle).
    location_bits = [
        b for b in (
            getattr(project, "location_region", None),
            getattr(project, "location_country", None),
        ) if b
    ]
    if location_bits:
        parts.append(f"Localisation : {', '.join(location_bits)}")

    # Impacts attendus mesurables (concaténés sur une ligne).
    impacts: list[str] = []
    tco2e = getattr(project, "expected_impact_tco2e", None)
    if tco2e is not None:
        impacts.append(f"{_fmt_num(tco2e)} tCO2e évitées/an")
    jobs = getattr(project, "expected_jobs_created", None)
    if jobs:
        impacts.append(f"{_fmt_num(jobs)} emplois créés")
    beneficiaries = getattr(project, "expected_beneficiaries", None)
    if beneficiaries:
        impacts.append(f"{_fmt_num(beneficiaries)} bénéficiaires")
    hectares = getattr(project, "expected_hectares_restored", None)
    if hectares is not None:
        impacts.append(f"{_fmt_num(hectares)} ha restaurés")
    if impacts:
        parts.append(f"Impacts attendus : {' ; '.join(impacts)}")

    return "\n".join(parts)


async def generate_section(
    db: AsyncSession,
    application: FundApplication,
    section_key: str,
) -> dict:
    """Generer le contenu d'une section via LLM + RAG.

    F15 BUG-001 : injection du profil entreprise réel via
    :func:`build_company_context` (remplace le hardcoded).
    """
    from app.modules.applications.templates import get_template_for_target
    from app.modules.company.service import get_or_create_profile

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

    # F15 BUG-001 — Construire le contexte entreprise réel
    profile = await get_or_create_profile(db, application.user_id)
    company_context = build_company_context(profile)

    # 050 — Construire le contexte PROJET réel (lien 1:1, F06). La relation
    # ``project`` est lazy="selectin" : déjà chargée quand le dossier provient
    # d'une requête (chemin router). Cas legacy (project_id NULL) → contexte vide.
    project_context = build_project_context(application.project)

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
        project_context=project_context,
    )

    # Appeler le LLM
    from app.graph.nodes import get_llm
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_llm()
    response = await llm.ainvoke([
        SystemMessage(content=prompt),
        HumanMessage(content=f"Genere la section '{section_config['title']}' du dossier."),
    ])

    # Nettoyer les fences markdown (```html … ```) que le LLM ajoute parfois,
    # sinon elles polluent la fiche dossier ET les exports PDF/Word.
    from app.modules.applications.export import strip_code_fences

    content = strip_code_fences(response.content)

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


# ---------------------------------------------------------------------
# 049 — Fourniture des documents de la checklist
# ---------------------------------------------------------------------


class ChecklistError(Exception):
    """Erreur de base pour les opérations de checklist documentaire (049)."""


class ApplicationItemNotFound(ChecklistError):
    """``item_key`` absent de la checklist du dossier → 404 (FR-016)."""


class DocumentNotFound(ChecklistError):
    """``document_id`` ne résout aucun document → 404."""


class DocumentCrossAccount(ChecklistError):
    """Document d'un autre compte que le dossier → 403 (FR-010, SC-003)."""


def _coerce_uuid(value) -> uuid.UUID | None:
    """Convertit une valeur (str/UUID/None) en UUID, ou None si invalide."""
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _document_belongs_to_application(document, application: FundApplication) -> bool:
    """Vrai si ``document`` est rattachable au dossier (même tenant).

    Règle (research D6) : si les deux ``account_id`` sont connus, ils doivent
    être égaux. Pour les documents legacy sans ``account_id`` (nullable), on
    exige au moins le même propriétaire (``user_id``) que le dossier. Garantit
    SC-003 (0 rattachement inter-comptes) tout en tolérant les documents legacy.
    """
    doc_account = getattr(document, "account_id", None)
    app_account = getattr(application, "account_id", None)
    if doc_account is not None and app_account is not None:
        return doc_account == app_account
    return document.user_id == application.user_id


async def _load_referenced_documents(
    db: AsyncSession,
    application: FundApplication,
    document_ids: list[uuid.UUID],
) -> dict[uuid.UUID, "Document"]:
    """Charge en une requête (anti-N+1) les documents référencés, filtrés au
    compte du dossier (défense en profondeur, research D3)."""
    from app.models.document import Document

    if not document_ids:
        return {}
    result = await db.execute(
        select(Document).where(Document.id.in_(document_ids))
    )
    resolved: dict[uuid.UUID, Document] = {}
    for doc in result.scalars().all():
        if _document_belongs_to_application(doc, application):
            resolved[doc.id] = doc
    return resolved


def _document_ref(document) -> dict:
    """Sous-objet ``document`` sérialisé pour un item « provided »."""
    status = document.status.value if hasattr(document.status, "value") else document.status
    return {
        "id": document.id,
        "original_filename": document.original_filename,
        "mime_type": document.mime_type,
        "status": status,
    }


def _serialize_item(item: dict, document) -> dict:
    """Construit la forme enrichie (``ChecklistItemOut``) d'un item.

    ``document`` est l'objet ``Document`` résolu (ou ``None``). Le statut renvoyé
    est EFFECTIF : « provided » ssi un document valide est résolu.
    """
    if document is not None:
        return {
            "key": item["key"],
            "name": item["name"],
            "status": "provided",
            "required_by": item.get("required_by", ""),
            "document_id": document.id,
            "document": _document_ref(document),
        }
    return {
        "key": item["key"],
        "name": item["name"],
        "status": "missing",
        "required_by": item.get("required_by", ""),
        "document_id": None,
        "document": None,
    }


async def serialize_checklist(
    db: AsyncSession,
    application: FundApplication,
) -> list[dict]:
    """Sérialise la checklist enrichie (statut effectif + sous-objet document).

    Chargement groupé des ``document_id`` non nuls (anti-N+1). Un document
    introuvable/supprimé ou d'un autre compte → item « missing », document null
    (research D3).
    """
    checklist = list(application.checklist or [])
    doc_ids: list[uuid.UUID] = []
    for item in checklist:
        did = _coerce_uuid(item.get("document_id"))
        if did is not None:
            doc_ids.append(did)
    documents = await _load_referenced_documents(db, application, doc_ids)
    return [
        _serialize_item(item, documents.get(_coerce_uuid(item.get("document_id"))))
        for item in checklist
    ]


async def attach_checklist_document(
    db: AsyncSession,
    application: FundApplication,
    item_key: str,
    document_id: uuid.UUID,
) -> dict:
    """Rattache (ou remplace) le document d'un item de checklist (US1/US2/US4).

    Atomique par item (FR-021) : verrou de ligne ``with_for_update()`` sur le
    dossier avant le read-modify-write du JSON ``checklist`` (research D11), de
    sorte qu'une écriture concurrente sur un autre item ne soit pas écrasée.

    Raises:
        DocumentNotFound: ``document_id`` inexistant.
        DocumentCrossAccount: document d'un autre compte (FR-010).
        ApplicationItemNotFound: ``item_key`` absent de la checklist.
    """
    from app.models.document import Document

    # Verrou de ligne + RELECTURE EFFECTIVE : `populate_existing=True` force la
    # ré-hydratation des attributs de l'instance déjà présente dans l'identity
    # map (chargée par le routeur via _get_user_application) depuis la ligne
    # re-verrouillée. Sans cela, l'ORM renverrait l'instance avec son `checklist`
    # périmé (pré-verrou) → le read-modify-write écraserait une écriture
    # concurrente committée entre-temps (last-write-wins), violant FR-021.
    locked = await db.execute(
        select(FundApplication)
        .where(FundApplication.id == application.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    app_locked = locked.scalar_one()

    document = await db.get(Document, document_id)
    if document is None:
        raise DocumentNotFound(str(document_id))
    if not _document_belongs_to_application(document, app_locked):
        raise DocumentCrossAccount(str(document_id))

    checklist = [dict(it) for it in (app_locked.checklist or [])]
    target = next((it for it in checklist if it.get("key") == item_key), None)
    if target is None:
        raise ApplicationItemNotFound(item_key)

    target["document_id"] = str(document.id)
    target["status"] = "provided"
    app_locked.checklist = checklist
    app_locked.updated_at = datetime.now(timezone.utc)
    await db.flush()

    from app.modules.applications.schemas import compute_checklist_progress

    return {
        "item": _serialize_item(target, document),
        "checklist_progress": compute_checklist_progress(checklist).model_dump(),
    }


async def detach_checklist_document(
    db: AsyncSession,
    application: FundApplication,
    item_key: str,
) -> dict:
    """Détache le document d'un item (US4) → item « missing ».

    Ne supprime PAS le document (réutilisable ailleurs — FR-011). Idempotent :
    détacher un item déjà « missing » renvoie l'item inchangé. Atomique par item
    (verrou de ligne, research D11).

    Raises:
        ApplicationItemNotFound: ``item_key`` absent de la checklist.
    """
    # Verrou + relecture effective (cf. attach : populate_existing évite de
    # repartir d'un `checklist` périmé → garantit l'atomicité par item FR-021).
    locked = await db.execute(
        select(FundApplication)
        .where(FundApplication.id == application.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    app_locked = locked.scalar_one()

    checklist = [dict(it) for it in (app_locked.checklist or [])]
    target = next((it for it in checklist if it.get("key") == item_key), None)
    if target is None:
        raise ApplicationItemNotFound(item_key)

    target["document_id"] = None
    target["status"] = "missing"
    app_locked.checklist = checklist
    app_locked.updated_at = datetime.now(timezone.utc)
    await db.flush()

    from app.modules.applications.schemas import compute_checklist_progress

    return {
        "item": _serialize_item(target, None),
        "checklist_progress": compute_checklist_progress(checklist).model_dump(),
    }


async def clear_document_references(
    db: AsyncSession,
    account_id: uuid.UUID | None,
    document_id: uuid.UUID,
) -> None:
    """Nettoyage eager des références à un document supprimé (FR-014, SC-005).

    Parcourt les dossiers du compte et réinitialise (``document_id=None``,
    ``status="missing"``) chaque item référençant ``document_id``. Appelé depuis
    ``documents.service.delete_document`` (dépendance unidirectionnelle
    documents → applications) AVANT la suppression de la ligne document.
    """
    target_id = _coerce_uuid(document_id)
    if target_id is None:
        return

    query = select(FundApplication)
    if account_id is not None:
        query = query.where(FundApplication.account_id == account_id)
    # populate_existing : rafraîchit les instances déjà chargées (la session de
    # delete_document peut en contenir) pour ne pas réécrire un `checklist` périmé.
    result = await db.execute(
        query.with_for_update().execution_options(populate_existing=True)
    )

    for app in result.scalars().all():
        checklist = [dict(it) for it in (app.checklist or [])]
        changed = False
        for item in checklist:
            if _coerce_uuid(item.get("document_id")) == target_id:
                item["document_id"] = None
                item["status"] = "missing"
                changed = True
        if changed:
            app.checklist = checklist
            app.updated_at = datetime.now(timezone.utc)

    await db.flush()
