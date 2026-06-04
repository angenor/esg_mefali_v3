"""Tools LangChain pour le noeud dossiers de candidature.

Neuf tools exposes au LLM :
- create_fund_application : creer un nouveau dossier de candidature
- generate_application_section : generer une section du dossier
- update_application_section : modifier une section
- get_application_checklist : consulter la checklist
- simulate_financing : simulation financiere
- export_application : exporter en PDF/DOCX/JSON
- list_applications : lister les dossiers de l'utilisateur courant (decouverte, 049)
- provide_checklist_document : rattacher un document a un item de checklist (049)
- detach_checklist_document : detacher le document d'un item de checklist (049)
"""

import enum
import logging
import uuid

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.graph.tools.common import UUID_PATTERN, get_db_and_user, with_retry
from app.models.application import TargetType

logger = logging.getLogger(__name__)


_SECTION_KEY_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"
# 049 — Les `item_key` de checklist suivent la même convention que les section
# keys (ex. ``company_registration``, ``env_impact_study``) : minuscules,
# chiffres et underscores. Réutilisé pour valider provide/detach.
_ITEM_KEY_PATTERN = _SECTION_KEY_PATTERN


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

    # F048 — ``fund_id`` rendu optionnel : si ``offer_id`` est fourni, fund et
    # intermediary sont dérivés de l'offre côté service. Évite que le LLM doive
    # inventer un fund_id factice (source d'hallucination) quand il candidate à
    # une offre.
    fund_id: str | None = Field(
        None, min_length=36, max_length=36, pattern=UUID_PATTERN,
    )
    target_type: TargetType | None = None
    offer_id: str | None = Field(
        None, min_length=36, max_length=36, pattern=UUID_PATTERN,
    )
    project_id: str | None = Field(
        None, min_length=36, max_length=36, pattern=UUID_PATTERN,
    )

    @model_validator(mode="after")
    def _require_offer_or_fund(self) -> "CreateFundApplicationArgs":
        if self.offer_id is None and self.fund_id is None:
            raise ValueError(
                "Fournis un offer_id (recommandé) ou, à défaut, un fund_id."
            )
        return self


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


class ListApplicationsArgs(BaseModel):
    """Args pour list_applications (049) — filtre statut optionnel.

    Aucun argument requis : le tool liste les dossiers de l'utilisateur courant.
    """

    model_config = ConfigDict(extra="forbid")

    status: str | None = Field(
        None,
        max_length=64,
        description="Filtre optionnel par statut (draft, submitted_to_fund, …).",
    )


class ProvideChecklistDocumentArgs(BaseModel):
    """Args strict pour provide_checklist_document (049, US1/US2/US4)."""

    model_config = ConfigDict(extra="forbid")

    application_id: str = Field(..., min_length=36, max_length=36, pattern=UUID_PATTERN)
    item_key: str = Field(..., pattern=_ITEM_KEY_PATTERN)
    document_id: str = Field(..., min_length=36, max_length=36, pattern=UUID_PATTERN)


class DetachChecklistDocumentArgs(BaseModel):
    """Args strict pour detach_checklist_document (049, US4)."""

    model_config = ConfigDict(extra="forbid")

    application_id: str = Field(..., min_length=36, max_length=36, pattern=UUID_PATTERN)
    item_key: str = Field(..., pattern=_ITEM_KEY_PATTERN)


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


async def _export_application(
    db, application, fmt: str, *, user_id, account_id=None,
) -> dict:
    """F048 (D3) — Générer le fichier RÉEL, l'écrire sur disque et l'enregistrer.

    Remplace l'ancien stub qui retournait un chemin factice sans écrire de
    fichier. Appelle le vrai moteur ``applications/export.py`` (DOCX/PDF), écrit
    les bytes sous ``uploads/applications/{id}.{fmt}`` puis enregistre un
    ``Document`` utilisateur (visible dans ``/documents``, FR-004).

    Retourne ``{storage_path, filename, document_id}``.
    """
    import json as _json

    from app.models.document import DocumentType
    from app.modules.applications.export import export_application as _real_export
    from app.modules.documents import service as doc_service

    if fmt == "json":
        payload = {
            "id": str(application.id),
            "fund": getattr(application.fund, "name", None) if application.fund else None,
            "status": (
                application.status.value
                if hasattr(application.status, "value")
                else application.status
            ),
            "sections": application.sections or {},
        }
        file_bytes = _json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        content_type = "application/json"
        filename = f"dossier_{application.id}.json"
    else:
        file_bytes, content_type, filename = await _real_export(application, fmt)

    uploads_dir = doc_service.UPLOADS_DIR / "applications"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    file_path = uploads_dir / f"{application.id}.{fmt}"
    file_path.write_bytes(file_bytes)
    storage_path = str(file_path.relative_to(doc_service.UPLOADS_DIR.parent))

    document = await doc_service.register_generated_document(
        db,
        user_id=user_id,
        account_id=account_id,
        storage_path=storage_path,
        original_filename=filename,
        mime_type=content_type,
        file_size=len(file_bytes),
        document_type=DocumentType.autre,
    )
    logger.info(
        "Export dossier %s format=%s -> %s (document_id=%s)",
        application.id, fmt, storage_path, document.id,
    )
    return {
        "storage_path": storage_path,
        "filename": filename,
        "document_id": str(document.id),
    }


async def _check_esg_gating(
    db, *, account_id, project_id, offer_id,
) -> dict | None:
    """F048 (D4) — Garde de gating ESG avant génération du dossier.

    Vérifie que les critères ESG ``is_required`` du référentiel applicable à
    l'offre sont couverts par l'évaluation ESG-projet du projet cible.

    Le référentiel est résolu via
    ``multi_referential_service.resolve_offer_referential_id`` (pas de FK
    offre→référentiel, fallback Mefali — research D4/U1). La couverture est
    dérivée des réponses persistées (robuste pour les évaluations ``draft``
    comme ``finalized``).

    Retourne ``None`` si la génération est AUTORISÉE (aucun critère requis
    manquant, ou gating inapplicable), sinon un dict
    ``{ok:false, blocked:true, missing_criteria:[...], message:str}``.
    """
    if project_id is None or offer_id is None or account_id is None:
        # Gating inapplicable sans cible projet/offre OU sans tenant résolu
        # (ne JAMAIS requêter avec account_id=None → éviterait le scoping RLS).
        return None

    from sqlalchemy import select as _select

    from app.models.indicator import Criterion
    from app.modules.esg.multi_referential_service import (
        resolve_offer_referential_id,
    )
    from app.modules.esg.project_models import (
        ProjectEsgAssessment,
        ProjectEsgCriterionResponse,
    )

    referential_id = await resolve_offer_referential_id(db, offer_id=offer_id)
    if referential_id is None:
        return None  # référentiel non résolu → mode dégradé permissif

    required = (
        await db.execute(
            _select(Criterion).where(
                Criterion.referential_id == referential_id,
                Criterion.applies_to_project.is_(True),
                Criterion.is_required.is_(True),
            )
        )
    ).scalars().all()
    if not required:
        return None  # aucun critère requis → rien à bloquer

    assessments = (
        await db.execute(
            _select(ProjectEsgAssessment)
            .where(
                ProjectEsgAssessment.account_id == account_id,
                ProjectEsgAssessment.project_id == project_id,
                ProjectEsgAssessment.referential_id == referential_id,
            )
            .order_by(ProjectEsgAssessment.created_at.desc())
        )
    ).scalars().all()

    chosen = next((a for a in assessments if a.state == "finalized"), None)
    if chosen is None and assessments:
        chosen = assessments[0]  # draft le plus récent

    covered_ids: set[str] = set()
    if chosen is not None:
        resp_ids = (
            await db.execute(
                _select(ProjectEsgCriterionResponse.criterion_id).where(
                    ProjectEsgCriterionResponse.assessment_id == chosen.id
                )
            )
        ).scalars().all()
        covered_ids = {str(cid) for cid in resp_ids}

    missing = [c for c in required if str(c.id) not in covered_ids]
    if not missing:
        return None

    return {
        "ok": False,
        "blocked": True,
        "missing_criteria": [
            {"id": str(c.id), "code": c.code, "label": c.label} for c in missing
        ],
        "message": (
            "Génération du dossier bloquée : l'évaluation ESG-projet ne couvre "
            "pas encore tous les critères requis du référentiel de cette offre. "
            "Complétez les critères manquants (via l'évaluation ESG-projet) "
            "avant de produire le document."
        ),
    }


# --- Tools ---


@tool(args_schema=CreateFundApplicationArgs)
@with_retry(
    max_retries=1,
    node_name="application_node",
    fallback_message=(
        "Je n'arrive pas à créer ce dossier de candidature. "
        "Pouvez-vous me redonner l'identifiant du fonds ou de l'offre ?"
    ),
)
async def create_fund_application(
    fund_id: str | None,
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
    from app.graph.tools.common import _coerce_uuid
    from app.modules.applications.service import create_application

    try:
        db, user_id = get_db_and_user(config)
        configurable = (config or {}).get("configurable", {}) or {}
        account_id = _coerce_uuid(configurable.get("account_id"))

        # F048 (D5) — Chemin de création PARTAGÉ avec l'endpoint REST (parité
        # FR-016) : le service résout fund/intermediary depuis l'offre et
        # dédoublonne le dossier draft (FR-006). Plus d'assignation directe
        # offer_id/project_id post-create.
        application = await create_application(
            db=db,
            user_id=user_id,
            fund_id=uuid.UUID(fund_id) if fund_id else None,
            offer_id=uuid.UUID(offer_id) if offer_id else None,
            project_id=uuid.UUID(project_id) if project_id else None,
            account_id=account_id,
        )

        return (
            f"Dossier de candidature cree avec succes.\n"
            f"- ID : {application.id}\n"
            f"- Statut : {application.status}\n"
            f"- Offre : {application.offer_id or 'N/A (mode legacy)'}\n"
            f"- Fonds : {application.fund_id}"
        )
    except ValueError as e:
        # Offre/fonds introuvable, ou aucune cible fournie (404 amont côté REST).
        logger.warning("create_fund_application — entrée invalide : %s", e)
        return f"Impossible de créer le dossier : {e}"
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
        db, user_id = get_db_and_user(config)

        application = await get_application_by_id(db=db, application_id=uuid.UUID(application_id))
        # F048 (sécurité) — garde de propriété : un dossier d'un autre utilisateur
        # est traité comme « introuvable » (pas de fuite d'existence, anti-IDOR).
        if application is None or application.user_id != user_id:
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
        db, user_id = get_db_and_user(config)

        application = await get_application_by_id(db=db, application_id=uuid.UUID(application_id))
        # F048 (sécurité) — garde de propriété : un dossier d'un autre utilisateur
        # est traité comme « introuvable » (pas de fuite d'existence, anti-IDOR).
        if application is None or application.user_id != user_id:
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
        db, user_id = get_db_and_user(config)

        application = await get_application_by_id(db=db, application_id=uuid.UUID(application_id))
        # F048 (sécurité) — garde de propriété : un dossier d'un autre utilisateur
        # est traité comme « introuvable » (pas de fuite d'existence, anti-IDOR).
        if application is None or application.user_id != user_id:
            return f"Dossier de candidature introuvable (id={application_id})."

        checklist = await get_checklist(db=db, application=application)

        if not checklist:
            return "Aucun element dans la checklist."

        lines: list[str] = ["Checklist du dossier :"]
        provided_count = 0
        for item in checklist:
            # 049 (FR-019) — parité : on lit la forme réelle des items stockés
            # (`{key, name, status, document_id, required_by}`). « fourni » ⇔
            # status == "provided" ; tous les items du catalogue sont requis,
            # ce que signale la présence de `required_by`.
            provided = item.get("status") == "provided"
            status_icon = "[X]" if provided else "[ ]"
            required_label = " (requis)" if item.get("required_by") else ""
            # L'``item_key`` DOIT être exposé : c'est l'argument attendu par
            # provide_checklist_document / detach_checklist_document. Sans lui,
            # le LLM ne peut pas rattacher un document (il ne voit que le libellé).
            item_key = item.get("key", "?")
            lines.append(
                f"  {status_icon} {item.get('name', 'N/A')}{required_label} "
                f"— item_key: `{item_key}`"
            )
            if provided:
                provided_count += 1

        lines.append(f"\nProgression : {provided_count}/{len(checklist)} documents fournis.")
        lines.append(
            "Pour fournir (ou remplacer) le document d'un item « manquant », appelle "
            "provide_checklist_document(application_id, item_key, document_id) en "
            "utilisant l'item_key exact affiché ci-dessus."
        )

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
        db, user_id = get_db_and_user(config)

        application = await get_application_by_id(db=db, application_id=uuid.UUID(application_id))
        # F048 (sécurité) — garde de propriété : un dossier d'un autre utilisateur
        # est traité comme « introuvable » (pas de fuite d'existence, anti-IDOR).
        if application is None or application.user_id != user_id:
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
    import json as _json

    from app.graph.tools.common import _coerce_uuid
    from app.modules.applications.service import get_application_by_id

    try:
        db, user_id = get_db_and_user(config)
        configurable = (config or {}).get("configurable", {}) or {}

        application = await get_application_by_id(db=db, application_id=uuid.UUID(application_id))
        # F048 (sécurité) — garde de propriété AVANT toute génération de fichier :
        # empêche d'exporter (et d'enregistrer comme document) le dossier d'un
        # autre utilisateur (anti-IDOR, amplifié par la génération réelle D3).
        if application is None or application.user_id != user_id:
            return f"Dossier de candidature introuvable (id={application_id})."

        if format not in ("pdf", "docx", "json"):
            return f"Format non supporte : '{format}'. Utilisez 'pdf', 'docx' ou 'json'."

        # F048 (D4) — Gating ESG : ne pas générer si des critères requis du
        # référentiel de l'offre manquent dans l'évaluation ESG-projet.
        account_id = (
            getattr(application, "account_id", None)
            or _coerce_uuid(configurable.get("account_id"))
        )
        gating = await _check_esg_gating(
            db,
            account_id=account_id,
            project_id=getattr(application, "project_id", None),
            offer_id=getattr(application, "offer_id", None),
        )
        if gating is not None:
            return _json.dumps(gating, ensure_ascii=False)

        # F048 (D3) — Génération RÉELLE : écrit le fichier + enregistre le Document.
        result = await _export_application(
            db, application, format, user_id=user_id, account_id=account_id,
        )

        return (
            f"Dossier exporte avec succes au format {format.upper()}.\n"
            f"- Fichier : {result['filename']}\n"
            f"- Disponible dans vos documents (/documents).\n"
            f"- Chemin : /{result['storage_path']}"
        )
    except Exception as e:
        logger.exception("Erreur lors de l'export du dossier")
        return f"Erreur lors de l'export : {e}"


# ---------------------------------------------------------------------
# 049 — Découverte des dossiers + fourniture des documents de checklist
# ---------------------------------------------------------------------


@tool(args_schema=ListApplicationsArgs)
async def list_applications(
    config: RunnableConfig,
    status: str | None = None,
) -> str:
    """Liste les dossiers de candidature de l'utilisateur courant (sans argument requis).

    Use when:
    - "mes dossiers", "où en est mon dossier", "mon dossier GCF", "que manque-t-il".
    - identifier LE bon dossier avant de lire sa checklist ou fournir un document.
    Don't use when:
    - créer un nouveau dossier (utiliser `create_fund_application`).
    - lister des fonds à financer (cf. module financing).
    Exemple: "Où en est mon dossier GCF ?" -> list_applications().
    Anti: "Quels fonds verts existent ?" -> NE PAS appeler.

    Args:
        status: Filtre optionnel par statut (draft, submitted_to_fund, …).
    """
    from app.models.application import ApplicationStatus
    from app.modules.applications.schemas import (
        compute_checklist_progress,
        compute_sections_progress,
        get_status_label,
    )
    from app.modules.applications.service import get_applications

    try:
        db, user_id = get_db_and_user(config)

        # Garde robustesse : ``status`` est un texte libre côté LLM ; un filtre
        # hors enum (ex. « en cours ») provoquerait une DataError PostgreSQL sur
        # la colonne ``application_status_enum`` (transaction avortée → cascade).
        # On ignore silencieusement un statut invalide plutôt que d'échouer.
        valid_status: str | None = None
        if status and status in {s.value for s in ApplicationStatus}:
            valid_status = status

        # Garde anti-IDOR : get_applications est scopé au user_id du config —
        # un utilisateur ne voit JAMAIS les dossiers d'un autre (F02).
        applications, total = await get_applications(
            db=db, user_id=user_id, status=valid_status,
        )

        if not applications:
            return (
                "Vous n'avez aucun dossier de candidature pour le moment. "
                "Dites-moi à quelle offre ou quel fonds vous souhaitez candidater "
                "pour en créer un."
            )

        lines: list[str] = [f"Vos dossiers de candidature ({total}) :"]
        for application in applications:
            fund_name = (
                application.fund.name
                if getattr(application, "fund", None)
                else "Fonds inconnu"
            )
            project_name = (
                application.project.name
                if getattr(application, "project", None)
                else None
            )
            status_val = (
                application.status.value
                if hasattr(application.status, "value")
                else application.status
            )
            target_val = (
                application.target_type.value
                if hasattr(application.target_type, "value")
                else application.target_type
            )
            sections_progress = compute_sections_progress(application.sections or {})
            # 049 — Progression sur le statut STOCKÉ (comme l'endpoint REST de
            # liste ``_build_application_summary`` / les cartes UI) : pas de N+1
            # de chargement des documents sur une liste. L'invariant
            # « provided ⟺ document valide » est maintenu eager par
            # ``clear_document_references`` à la suppression d'un document
            # (FR-014). La vue DÉTAIL (get_application_checklist / onglet UI)
            # recalcule le statut effectif via ``serialize_checklist``.
            checklist = list(application.checklist or [])
            checklist_progress = compute_checklist_progress(checklist)
            missing = [
                it.get("name")
                for it in checklist
                if it.get("status") != "provided"
            ]

            header = f"  - {fund_name}"
            if project_name:
                header += f" — projet « {project_name} »"
            header += f" [{get_status_label(status_val)}]"
            lines.append(header)
            lines.append(f"      id : {application.id} · destinataire : {target_val}")
            lines.append(
                f"      Sections : {sections_progress.generated}/{sections_progress.total} générées"
                f" · Documents : {checklist_progress.provided}/{checklist_progress.total} fournis"
            )
            if missing:
                preview = ", ".join(name for name in missing[:4] if name)
                suffix = " …" if len(missing) > 4 else ""
                lines.append(f"      À fournir : {preview}{suffix}")

        return "\n".join(lines)
    except Exception as e:
        logger.exception("Erreur lors de la liste des dossiers de candidature")
        return f"Erreur lors de la consultation de vos dossiers : {e}"


@tool(args_schema=ProvideChecklistDocumentArgs)
async def provide_checklist_document(
    application_id: str,
    item_key: str,
    document_id: str,
    config: RunnableConfig,
) -> str:
    """Rattache un document déjà téléversé à un item « Manquant » de la checklist.

    Réutilise la validation 049 (service ``attach_checklist_document``) : 403 si
    le document appartient à un autre compte, 404 si le document ou l'item est
    introuvable. L'item passe à « Fourni » et la progression est recalculée.

    Use when:
    - "rattache mon RCCM à l'item registre", "fournis ce document pour …".
    - après `list_applications` → `get_application_checklist` → `list_user_documents`.
    Don't use when:
    - le document n'existe pas encore (inviter à utiliser le bouton d'ajout de fichier / trombone, PAS de widget).
    - retirer un document d'un item (utiliser `detach_checklist_document`).
    Exemple: provide_checklist_document(application_id='…', item_key='company_registration', document_id='…').
    Anti: "Téléverse un fichier" -> NE PAS proposer de widget ; inviter à utiliser le bouton d'ajout de fichier.

    Args:
        application_id: UUID du dossier de candidature.
        item_key: Clé de l'item de checklist (cf. get_application_checklist).
        document_id: UUID du document à rattacher.
    """
    from app.modules.applications.service import (
        ApplicationItemNotFound,
        DocumentCrossAccount,
        DocumentNotFound,
        attach_checklist_document,
        get_application_by_id,
    )

    try:
        db, user_id = get_db_and_user(config)

        application = await get_application_by_id(
            db=db, application_id=uuid.UUID(application_id),
        )
        # Garde de propriété (anti-IDOR) : le dossier d'un autre utilisateur est
        # traité comme « introuvable » (pas de fuite d'existence, ni de mutation).
        if application is None or application.user_id != user_id:
            return f"Dossier de candidature introuvable (id={application_id})."

        try:
            result = await attach_checklist_document(
                db=db,
                application=application,
                item_key=item_key,
                document_id=uuid.UUID(document_id),
            )
        except ApplicationItemNotFound:
            return (
                f"Aucun item « {item_key} » dans la checklist de ce dossier. "
                "Appelle get_application_checklist pour voir les item_key valides."
            )
        except DocumentNotFound:
            return (
                f"Document introuvable (id={document_id}) : impossible de le rattacher."
            )
        except DocumentCrossAccount:
            return (
                "Ce document n'appartient pas à votre compte (organisation) : "
                "rattachement refusé."
            )

        item = result["item"]
        progress = result["checklist_progress"]
        name = item.get("name", item_key)
        return (
            f"Document rattaché à l'item « {name} » : il est désormais « fourni ».\n"
            f"Progression documentaire : "
            f"{progress['provided']}/{progress['total']} documents fournis."
        )
    except Exception as e:
        logger.exception("Erreur lors du rattachement du document à la checklist")
        return f"Erreur lors du rattachement du document : {e}"


@tool(args_schema=DetachChecklistDocumentArgs)
async def detach_checklist_document(
    application_id: str,
    item_key: str,
    config: RunnableConfig,
) -> str:
    """Détache le document d'un item « Fourni » (l'item repasse « Manquant »).

    Ne supprime PAS le document (réutilisable ailleurs — FR-011). Idempotent sur
    un item déjà « Manquant ». Réutilise le service 049 ``detach_checklist_document``.

    Use when:
    - "retire / détache le document de l'item …".
    - corriger un mauvais rattachement avant d'en fournir un autre.
    Don't use when:
    - remplacer par un autre document (utiliser `provide_checklist_document`).
    - supprimer définitivement le fichier (il reste listé par `list_user_documents`).
    Exemple: detach_checklist_document(application_id='…', item_key='company_registration').
    Anti: "Supprime mon document" -> NE PAS appeler (le fichier reste dans /documents).

    Args:
        application_id: UUID du dossier de candidature.
        item_key: Clé de l'item de checklist (cf. get_application_checklist).
    """
    from app.modules.applications.service import (
        ApplicationItemNotFound,
        detach_checklist_document as detach_doc,
        get_application_by_id,
    )

    try:
        db, user_id = get_db_and_user(config)

        application = await get_application_by_id(
            db=db, application_id=uuid.UUID(application_id),
        )
        if application is None or application.user_id != user_id:
            return f"Dossier de candidature introuvable (id={application_id})."

        try:
            result = await detach_doc(
                db=db, application=application, item_key=item_key,
            )
        except ApplicationItemNotFound:
            return (
                f"Aucun item « {item_key} » dans la checklist de ce dossier. "
                "Appelle get_application_checklist pour voir les item_key valides."
            )

        item = result["item"]
        progress = result["checklist_progress"]
        name = item.get("name", item_key)
        return (
            f"Document détaché de l'item « {name} » : il est désormais « manquant ».\n"
            f"Progression documentaire : "
            f"{progress['provided']}/{progress['total']} documents fournis."
        )
    except Exception as e:
        logger.exception("Erreur lors du détachement du document de la checklist")
        return f"Erreur lors du détachement du document : {e}"


APPLICATION_TOOLS = [
    create_fund_application,
    generate_application_section,
    update_application_section,
    get_application_checklist,
    simulate_financing,
    export_application,
    # 049 — découverte + fourniture de documents de checklist depuis le chat.
    list_applications,
    provide_checklist_document,
    detach_checklist_document,
]


# 049 — Bundle « découverte + checklist » ré-injecté dans le ToolNode du nœud
# `financing` (cf. graph.py) pour que ce nœud puisse EXÉCUTER ces tools quand le
# routeur y dirige une demande de dossier nommant un fonds (ex. « candidature au
# fonds vert » est happée par financing). Le nœud `application` les possède déjà
# via APPLICATION_TOOLS. `get_application_checklist` y figure car il n'est PAS
# dans FINANCING_TOOLS.
APPLICATION_DISCOVERY_TOOLS = [
    list_applications,
    get_application_checklist,
    provide_checklist_document,
    detach_checklist_document,
]


# 051 — Sous-ensemble LECTURE SEULE (découverte + statut) destiné à la base du
# chat flottant : injecté dans le catalogue ET le ToolNode du nœud `chat` (cf.
# nodes.py / graph.py) pour qu'une demande « où en est mon dossier ? » fonctionne
# depuis N'IMPORTE QUELLE page sans navigation manuelle. Volontairement SANS les
# tools de mutation (`provide_checklist_document`/`detach_checklist_document`),
# qui restent réservés aux nœuds application/financing (049). Les deux tools sont
# scopés au `user_id` du config (garde anti-IDOR F02) : aucune fuite cross-tenant.
APPLICATION_STATUS_TOOLS = [
    list_applications,
    get_application_checklist,
]
