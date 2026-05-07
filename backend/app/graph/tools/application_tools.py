"""Tools LangChain pour le noeud dossiers de candidature.

Six tools exposes au LLM :
- create_fund_application : creer un nouveau dossier de candidature
- generate_application_section : generer une section du dossier
- update_application_section : modifier une section
- get_application_checklist : consulter la checklist
- simulate_financing : simulation financiere
- export_application : exporter en PDF/DOCX/JSON
"""

import enum
import logging
import uuid

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field

from app.graph.tools.common import UUID_PATTERN, get_db_and_user
from app.models.application import TargetType

logger = logging.getLogger(__name__)


_SECTION_KEY_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"


class ExportFormat(str, enum.Enum):
    """Formats d'export d'un dossier de candidature."""

    pdf = "pdf"
    docx = "docx"
    json = "json"


# --- Args Schemas ---


class CreateFundApplicationArgs(BaseModel):
    """Args strict pour create_fund_application.

    F07 : ``offer_id`` accepté en priorité ; ``fund_id`` reste accepté pour
    compatibilité descendante (legacy 2 sprints).
    """

    model_config = ConfigDict(extra="forbid")

    fund_id: str = Field(..., min_length=36, max_length=36, pattern=UUID_PATTERN)
    target_type: TargetType | None = None
    offer_id: str | None = Field(
        None, min_length=36, max_length=36, pattern=UUID_PATTERN,
    )
    project_id: str | None = Field(
        None, min_length=36, max_length=36, pattern=UUID_PATTERN,
    )


class GenerateApplicationSectionArgs(BaseModel):
    """Args strict pour generate_application_section."""

    model_config = ConfigDict(extra="forbid")

    application_id: str = Field(..., min_length=36, max_length=36, pattern=UUID_PATTERN)
    section_key: str = Field(..., pattern=_SECTION_KEY_PATTERN)
    instructions: str | None = Field(None, min_length=1, max_length=2000)


class UpdateApplicationSectionArgs(BaseModel):
    """Args strict pour update_application_section."""

    model_config = ConfigDict(extra="forbid")

    application_id: str = Field(..., min_length=36, max_length=36, pattern=UUID_PATTERN)
    section_key: str = Field(..., pattern=_SECTION_KEY_PATTERN)
    content: str = Field(..., min_length=1, max_length=50_000)


class GetApplicationChecklistArgs(BaseModel):
    """Args strict pour get_application_checklist."""

    model_config = ConfigDict(extra="forbid")

    application_id: str = Field(..., min_length=36, max_length=36, pattern=UUID_PATTERN)


class SimulateFinancingArgs(BaseModel):
    """Args strict pour simulate_financing."""

    model_config = ConfigDict(extra="forbid")

    application_id: str = Field(..., min_length=36, max_length=36, pattern=UUID_PATTERN)


class ExportApplicationArgs(BaseModel):
    """Args strict pour export_application."""

    model_config = ConfigDict(extra="forbid")

    application_id: str = Field(..., min_length=36, max_length=36, pattern=UUID_PATTERN)
    format: ExportFormat


# --- Helpers ---


async def _simulate_financing(db, application) -> dict:
    """Simulation financiere pour un dossier de candidature.

    F04 : utilise les properties ``min_amount_money`` / ``max_amount_money``
    qui retombent sur ``min_amount_xof`` / ``max_amount_xof`` si la paire
    Money typée n'est pas renseignée. Plus d'AttributeError sur
    ``fund.max_amount`` (FR-050).
    """
    from decimal import Decimal

    from app.modules.financing.service import get_fund_by_id

    fund = await get_fund_by_id(db, application.fund_id)
    if not fund:
        return {"error": "Fonds introuvable pour cette candidature."}

    min_money = fund.min_amount_money
    max_money = fund.max_amount_money

    if min_money is not None and max_money is not None:
        eligible_amount = (min_money.amount + max_money.amount) / Decimal("2")
        currency = max_money.currency
    elif max_money is not None:
        eligible_amount = max_money.amount / Decimal("2")
        currency = max_money.currency
    elif min_money is not None:
        eligible_amount = min_money.amount * Decimal("2")
        currency = min_money.currency
    else:
        eligible_amount = Decimal("0")
        currency = "XOF"

    return {
        "eligible_amount": {
            "amount": str(eligible_amount.quantize(Decimal("0.01"))),
            "currency": currency,
        },
        "currency": currency,
        "roi_estimate": "12-18%",
        "timeline_months": 18,
        "fund_name": fund.name,
    }


async def _export_application(db, application, fmt: str) -> str:
    """Exporter un dossier en PDF, DOCX ou JSON. Retourne le chemin du fichier."""
    export_path = f"/uploads/applications/{application.id}.{fmt}"
    logger.info("Export dossier %s au format %s -> %s", application.id, fmt, export_path)
    return export_path


# --- Tools ---


@tool(args_schema=CreateFundApplicationArgs)
async def create_fund_application(
    fund_id: str,
    config: RunnableConfig,
    target_type: str | None = None,
    offer_id: str | None = None,
    project_id: str | None = None,
) -> str:
    """Cree un nouveau dossier de candidature pour une offre/fonds vert (statut draft).

    F07 : si ``offer_id`` est fourni, il est utilisé en priorité (l'offre
    contient déjà fund_id et intermediary_id). Sinon, ``fund_id`` est utilisé
    en mode legacy (2 sprints).

    Use when:
    - l'utilisateur valide candidater a une offre/fonds (uuid valide).
    - apres matching d'une offre, "je candidate".
    Don't use when:
    - aucune offre/fonds identifie (cf. `module financing`).
    - simple consultation (cf. `module financing`).
    Exemple: "Je candidate à cette offre" -> create_fund_application(offer_id='<uuid>').
    Anti: "Quels fonds existent ?" -> NE PAS appeler.
    """
    from app.modules.applications.service import create_application
    from app.models.offer import Offer

    try:
        db, user_id = get_db_and_user(config)

        # F07 — Priorité à offer_id si fourni
        target_offer_id = uuid.UUID(offer_id) if offer_id else None
        target_fund_id = uuid.UUID(fund_id)
        target_intermediary_id = None
        target_project_id = uuid.UUID(project_id) if project_id else None

        if target_offer_id is not None:
            offer = await db.get(Offer, target_offer_id)
            if offer is None:
                return f"Offre introuvable (id={offer_id})."
            target_fund_id = offer.fund_id
            target_intermediary_id = offer.intermediary_id

        application = await create_application(
            db=db,
            user_id=user_id,
            fund_id=target_fund_id,
            intermediary_id=target_intermediary_id,
        )

        # F07 — Lier offer_id si fourni
        if target_offer_id is not None:
            application.offer_id = target_offer_id
            await db.flush()

        # F06 — Lier project_id si fourni
        if target_project_id is not None:
            application.project_id = target_project_id
            await db.flush()

        return (
            f"Dossier de candidature cree avec succes.\n"
            f"- ID : {application.id}\n"
            f"- Statut : {application.status}\n"
            f"- Offre : {application.offer_id or 'N/A (mode legacy)'}\n"
            f"- Fonds : {application.fund_id}"
        )
    except Exception as e:
        logger.exception("Erreur lors de la creation du dossier de candidature")
        return f"Erreur lors de la creation du dossier : {e}"


@tool(args_schema=GenerateApplicationSectionArgs)
async def generate_application_section(
    application_id: str,
    section_key: str,
    config: RunnableConfig,
    instructions: str | None = None,
) -> str:
    """Genere par IA le contenu d'une section du dossier (presentation, budget, impact).

    Use when:
    - "redige", "genere", "ecris" une section.
    - section_key + application_id connus.
    Don't use when:
    - texte deja fourni (utiliser `update_application_section`).
    - voir checklist (utiliser `get_application_checklist`).
    Exemple: "Genere la presentation" -> generate_application_section(section_key='company_presentation').
    Anti: "Voici mon budget" -> NE PAS appeler.
    """
    from app.modules.applications.service import generate_section, get_application_by_id

    try:
        db, _user_id = get_db_and_user(config)

        application = await get_application_by_id(db=db, application_id=uuid.UUID(application_id))
        if application is None:
            return f"Dossier de candidature introuvable (id={application_id})."

        section = await generate_section(db=db, application=application, section_key=section_key)

        content_preview = str(section.get("content", ""))[:300]

        return (
            f"Section '{section_key}' generee avec succes.\n"
            f"- Statut : {section.get('status', 'generated')}\n"
            f"- Apercu : {content_preview}..."
        )
    except Exception as e:
        logger.exception("Erreur lors de la generation de la section %s", section_key)
        return f"Erreur lors de la generation de la section : {e}"


@tool(args_schema=UpdateApplicationSectionArgs)
async def update_application_section(
    application_id: str,
    section_key: str,
    content: str,
    config: RunnableConfig,
) -> str:
    """Remplace le contenu textuel d'une section existante du dossier.

    Use when:
    - texte explicite fourni par l'utilisateur.
    - persister un contenu collecte sur plusieurs tours.
    Don't use when:
    - generation IA (utiliser `generate_application_section`).
    - pas de dossier (utiliser `create_fund_application`).
    Exemple: "Mon budget 50M FCFA" -> update_application_section(section_key='budget', content='...').
    Anti: "Genere mon budget" -> NE PAS appeler.
    """
    from app.modules.applications.service import get_application_by_id, update_section

    try:
        db, _user_id = get_db_and_user(config)

        application = await get_application_by_id(db=db, application_id=uuid.UUID(application_id))
        if application is None:
            return f"Dossier de candidature introuvable (id={application_id})."

        result = await update_section(
            db=db,
            application=application,
            section_key=section_key,
            content=content,
        )

        return (
            f"Section '{section_key}' mise a jour avec succes.\n"
            f"- Statut : {result.get('status', 'edited')}"
        )
    except Exception as e:
        logger.exception("Erreur lors de la mise a jour de la section %s", section_key)
        return f"Erreur lors de la mise a jour de la section : {e}"


@tool(args_schema=GetApplicationChecklistArgs)
async def get_application_checklist(
    application_id: str,
    config: RunnableConfig,
) -> str:
    """Consulte la checklist des documents requis pour un dossier (lecture seule).

    Use when:
    - "quels documents", "que manque-t-il".
    - decider si l'export est possible.
    Don't use when:
    - generer du contenu (utiliser `generate_application_section`).
    - score ESG (utiliser `get_esg_assessment`).
    Exemple: "Que manque-t-il ?" -> get_application_checklist(application_id='...').
    Anti: "Genere mon budget" -> NE PAS appeler.
    """
    from app.modules.applications.service import get_application_by_id, get_checklist

    try:
        db, _user_id = get_db_and_user(config)

        application = await get_application_by_id(db=db, application_id=uuid.UUID(application_id))
        if application is None:
            return f"Dossier de candidature introuvable (id={application_id})."

        checklist = await get_checklist(db=db, application=application)

        if not checklist:
            return "Aucun element dans la checklist."

        lines: list[str] = ["Checklist du dossier :"]
        provided_count = 0
        for item in checklist:
            status_icon = "[X]" if item.get("provided") else "[ ]"
            required_label = " (requis)" if item.get("required") else ""
            lines.append(f"  {status_icon} {item.get('label', 'N/A')}{required_label}")
            if item.get("provided"):
                provided_count += 1

        lines.append(f"\nProgression : {provided_count}/{len(checklist)} documents fournis.")

        return "\n".join(lines)
    except Exception as e:
        logger.exception("Erreur lors de la consultation de la checklist")
        return f"Erreur lors de la consultation de la checklist : {e}"


@tool(args_schema=SimulateFinancingArgs)
async def simulate_financing(
    application_id: str,
    config: RunnableConfig,
) -> str:
    """Calcule une simulation financiere (montant eligible, ROI, timeline) du dossier.

    Use when:
    - estimation financiere d'un dossier (montant, ROI, duree).
    - comparatif avant export.
    Don't use when:
    - comparer plusieurs fonds avant candidature (utiliser module financing).
    - pas de dossier (utiliser `create_fund_application`).
    Exemple: "Quel montant esperer ?" -> simulate_financing(application_id='...').
    Anti: "Liste les fonds" -> NE PAS appeler.
    """
    from app.modules.applications.service import get_application_by_id

    try:
        db, _user_id = get_db_and_user(config)

        application = await get_application_by_id(db=db, application_id=uuid.UUID(application_id))
        if application is None:
            return f"Dossier de candidature introuvable (id={application_id})."

        simulation = await _simulate_financing(db, application)

        if "error" in simulation:
            return f"Erreur de simulation : {simulation['error']}"

        # F04 — eligible_amount peut être un dict Money typé OU un nombre legacy
        # (cohabitation phase 1, FR-070 + FR-050).
        eligible = simulation["eligible_amount"]
        if isinstance(eligible, dict):
            eligible_str = f"{eligible.get('amount', '0')} {eligible.get('currency', 'XOF')}"
        else:
            eligible_str = (
                f"{eligible:,} {simulation.get('currency', 'USD')}"
                if isinstance(eligible, (int, float))
                else f"{eligible} {simulation.get('currency', 'USD')}"
            )
        return (
            f"Simulation financiere :\n"
            f"- Fonds : {simulation.get('fund_name', 'N/A')}\n"
            f"- Montant eligible estime : {eligible_str}\n"
            f"- ROI estime : {simulation['roi_estimate']}\n"
            f"- Timeline : {simulation['timeline_months']} mois"
        )
    except Exception as e:
        logger.exception("Erreur lors de la simulation financiere")
        return f"Erreur lors de la simulation : {e}"


@tool(args_schema=ExportApplicationArgs)
async def export_application(
    application_id: str,
    format: str,
    config: RunnableConfig,
) -> str:
    """Exporte le dossier au format pdf|docx|json et retourne l'URL.

    Use when:
    - confirmation de telecharger/envoyer le dossier.
    - dossier complet (cf. `get_application_checklist`).
    Don't use when:
    - dossier incomplet (utiliser `get_application_checklist`).
    - preparer du contenu (utiliser `generate_application_section`).
    Exemple: "Exporte en PDF" -> export_application(format='pdf').
    Anti: "Genere ma presentation" -> NE PAS appeler.
    """
    from app.modules.applications.service import get_application_by_id

    try:
        db, _user_id = get_db_and_user(config)

        application = await get_application_by_id(db=db, application_id=uuid.UUID(application_id))
        if application is None:
            return f"Dossier de candidature introuvable (id={application_id})."

        if format not in ("pdf", "docx", "json"):
            return f"Format non supporte : '{format}'. Utilisez 'pdf', 'docx' ou 'json'."

        export_path = await _export_application(db, application, format)

        return (
            f"Dossier exporte avec succes au format {format.upper()}.\n"
            f"- URL de telechargement : {export_path}"
        )
    except Exception as e:
        logger.exception("Erreur lors de l'export du dossier")
        return f"Erreur lors de l'export : {e}"


APPLICATION_TOOLS = [
    create_fund_application,
    generate_application_section,
    update_application_section,
    get_application_checklist,
    simulate_financing,
    export_application,
]
