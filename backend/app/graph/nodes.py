"""Nœuds du graphe de conversation LangGraph."""

import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.graph.state import ConversationState
from app.graph.tool_selector import select_tools_for_node
from app.modules.company.service import FIELD_LABELS, IDENTITY_FIELDS
from app.prompts.system import build_system_prompt

logger = logging.getLogger(__name__)


def _propagate_tools_offered(
    config: RunnableConfig | None,
    tools_offered: list[str],
) -> None:
    """Stocker `tools_offered` dans le RunnableConfig pour que log_tool_call
    le retrouve au moment d'ecrire dans tool_call_logs (story 10.2).

    Remplace `configurable` par un nouveau dict pour eviter toute mutation
    in-place qui pourrait corrompre le RunnableConfig partage entre tours.
    """
    if config is None:
        return
    existing = config.get("configurable", {}) or {}  # type: ignore[union-attr]
    config["configurable"] = {**existing, "tools_offered": tools_offered}  # type: ignore[index]


TITLE_PROMPT = (
    "Résume cette conversation en un titre court (5 mots maximum) en français. "
    "Réponds uniquement avec le titre, sans guillemets ni ponctuation finale."
)

# Heuristiques pour détecter des infos de profil dans un message
_PROFILE_KEYWORDS = [
    r"\bemploy[ée]s?\b", r"\bsalari[ée]s?\b", r"\beffectifs?\b",
    r"\bchiffre d'affaires\b", r"\brevenu\b", r"\b[Cc][Aa]\b",
    r"\bmillions?\b", r"\bFCFA\b", r"\bXOF\b",
    r"\bagriculture\b", r"\b[ée]nergie\b", r"\brecyclage\b",
    r"\btransport\b", r"\bconstruction\b", r"\btextile\b",
    r"\bagroalimentaire\b", r"\bcommerce\b", r"\bartisan",
    r"\bAbidjan\b", r"\bDakar\b", r"\bBamako\b", r"\bOuagadougou\b",
    r"\bLom[ée]\b", r"\bCotonou\b", r"\bNiamey\b", r"\bConakry\b",
    r"\bDouala\b", r"\bYaound[ée]\b", r"\bKinshasa\b",
    r"\bentreprise\b", r"\bsoci[ée]t[ée]\b", r"\bSARL\b", r"\bSA\b",
    r"\bcr[ée][ée]e?\s+en\b", r"\bfond[ée]e?\s+en\b",
    r"\bd[ée]chets?\b", r"\b[ée]nerg[ée]tique\b", r"\bformation\b",
    r"\bgouvernance\b", r"\benvironnement", r"\bgenre\b",
    r"\d+\s*personnes?\b", r"\d+\s*employ",
]
_PROFILE_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _PROFILE_KEYWORDS]

# Heuristiques pour détecter une demande de module spécifique (ESG, carbone, financement)
_MODULE_KEYWORDS = [
    r"\bscoring\s+ESG\b", r"\bscore\s+ESG\b", r"\banalyse\s+ESG\b",
    r"\bconformit[ée]\s+ESG\b", r"\baudit\s+ESG\b", r"\b[ée]valuation\s+ESG\b",
    r"\bempreinte\s+carbone\b", r"\bcarbone\b", r"\btCO2", r"\bCO2\b",
    r"\b[ée]missions?\s+de\s+gaz\b", r"\bgaz\s+[àa]\s+effet\b",
    r"\bfonds?\s+verts?\b", r"\bfinancement\s+vert\b", r"\bfonds?\s+climat\b",
    r"\bGCF\b", r"\bFEM\b", r"\bBOAD\b", r"\bBAD\b",
    r"\bsubvention", r"\bcr[ée]dit\s+vert\b",
    r"\bplan\s+d'action\b", r"\bfeuille\s+de\s+route\b",
    r"\bdossier\s+de\s+candidature\b",
]
_MODULE_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _MODULE_KEYWORDS]

# Heuristiques pour detecter une demande liee aux dossiers de candidature
_APPLICATION_KEYWORDS = [
    r"\bdossier\s+de\s+candidature\b", r"\bdossier\s+candidature\b",
    r"\bcandidat(?:ure)?\s+(?:au|aux)\s+fonds\b",
    r"\bmon\s+dossier\b", r"\bmes\s+dossiers\b",
    r"\betat\s+(?:du|de\s+mon)\s+dossier\b",
    r"\bsections?\s+(?:du|de\s+mon)\s+dossier\b",
    r"\bgenerer\s+(?:une|la|les)\s+section\b",
    r"\bexport(?:er)?\s+(?:le|mon)\s+dossier\b",
    r"\bpreparer\s+(?:le|mon)\s+dossier\b",
    r"\bsoumission\s+(?:du|de\s+mon)\s+dossier\b",
    r"\bfiche\s+de\s+preparation\b",
    r"\bsimul(?:er|ation)\s+(?:de\s+)?financement\b",
]
_APPLICATION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _APPLICATION_KEYWORDS]

# Heuristiques pour détecter une CONSULTATION ESG (lecture seule → chat_node)
# Ces patterns ne doivent PAS router vers esg_scoring_node
_ESG_QUERY_KEYWORDS = [
    r"\bmon\s+score\s+ESG\b", r"\bquel\s+est\s+mon\s+score\s+ESG\b",
    r"\bscore\s+ESG\s+actuel\b", r"\br[ée]sultat.*ESG\b",
    r"\bmontre.*(?:radar|chart|graphique).*ESG\b",
    r"\bradar.*ESG\b", r"\bESG.*radar\b",
    r"\baffiche.*score.*ESG\b", r"\bvoir.*score.*ESG\b",
]
_ESG_QUERY_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _ESG_QUERY_KEYWORDS]

# Heuristiques pour détecter une demande d'évaluation ESG (interactive → esg_scoring_node)
_ESG_KEYWORDS = [
    r"\b[ée]valuation\s+ESG\b", r"\b[ée]valuer\s+.*ESG\b",
    r"\bscoring\s+ESG\b",
    r"\banalyse\s+ESG\b", r"\baudit\s+ESG\b",
    r"\blancer\s+.*[ée]valuation\b.*\bESG\b",
    r"\bcriteres?\s+ESG\b",
    r"\bdiagnostic\s+ESG\b", r"\bbilan\s+ESG\b",
    r"\bcontinuer.*[ée]valuation.*ESG\b",
    r"\bfaire.*[ée]valuation.*ESG\b",
]
_ESG_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _ESG_KEYWORDS]

# Heuristiques pour detecter une demande de scoring credit vert
_CREDIT_KEYWORDS = [
    r"\bscore\s+(?:de\s+)?cr[ée]dit\s+vert\b",
    r"\bscoring\s+(?:de\s+)?cr[ée]dit\b",
    r"\bmon\s+score\s+(?:de\s+)?cr[ée]dit\b",
    r"\bnote\s+(?:de\s+)?cr[ée]dit\s+vert\b",
    r"\bscore\s+(?:de\s+)?solvabilit[ée]\b",
    r"\battestation\s+(?:de\s+)?cr[ée]dit\b",
    r"\bgen[eè]re[r]?\s+(?:mon\s+)?score\s+(?:de\s+)?cr[ée]dit\b",
    r"\bscoring\s+vert\b",
    r"\bcr[ée]dit\s+vert\s+(?:score|note|attestation)\b",
    r"\bscore\s+cr[ée]dit\b",
]
_CREDIT_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _CREDIT_KEYWORDS]

# Heuristiques pour detecter une demande de plan d'action
_ACTION_PLAN_KEYWORDS = [
    r"\bplan\s+d'action\b", r"\bfeuille\s+de\s+route\b",
    r"\bactions?\s+(?:ESG|vertes?|prioritaires?)\b",
    r"\bprochaines?\s+[ée]tapes?\b",
    r"\broadmap\b", r"\baction\s+plan\b",
    r"\bgen[eè]re[r]?\s+(?:un|mon|le)\s+plan\b",
    r"\bcreer?\s+(?:un|mon|le)\s+plan\b",
    r"\bmon\s+plan\s+(?:d'action|ESG)\b",
    r"\bprogression\s+(?:du|de\s+mon)\s+plan\b",
    r"\btaches?\s+(?:ESG|en\s+cours|prioritaires?)\b",
    # Mises a jour de statut d'actions
    r"\bmets?\s+.*(?:action|tache).*(?:en\s+cours|termin|fait)\b",
    r"\b(?:action|tache).*(?:en\s+cours|termin[ée]e?|fait)\b",
    r"\bcommenc[ée]\s+.*(?:audit|action|tache)\b",
    r"\bj'ai\s+commenc[ée]\b",
    r"\bj'ai\s+termin[ée]\b",
    r"\bj'ai\s+fait\b.*\b(?:action|audit|formation|charte)\b",
    r"\bstatut\s+(?:de\s+)?(?:l'|mon|une)\s+action\b",
    r"\bmettre?\s+[àa]\s+jour\s+.*action\b",
    r"\bpris\s+rendez-vous\b",
    r"\bj'attends?\s+(?:leur|une|la)\s+r[ée]ponse\b",
]
_ACTION_PLAN_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _ACTION_PLAN_KEYWORDS]

# Heuristiques pour detecter une demande de bilan carbone
_CARBON_KEYWORDS = [
    r"\bempreinte\s+carbone\b", r"\bbilan\s+carbone\b",
    r"\bcalcul.*carbone\b", r"\bcalculer.*carbone\b",
    r"\btCO2e?\b", r"\bCO2\b",
    r"\b[ée]missions?\s+de\s+gaz\b", r"\bgaz\s+[àa]\s+effet\b",
    r"\bempreinte\s+[ée]cologique\b", r"\bimpact\s+carbone\b",
    r"\br[ée]duction.*[ée]missions?\b",
]
_CARBON_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _CARBON_KEYWORDS]

# Heuristiques pour detecter une demande de financement vert
_FINANCING_KEYWORDS = [
    r"\bfinancement\s+vert\b", r"\bfonds?\s+verts?\b",
    r"\bfonds?\s+climat\b", r"\bfonds?\s+d'adaptation\b",
    r"\bSUNREF\b", r"\bGCF\b", r"\bFEM\b", r"\bBOAD\b", r"\bBAD\b",
    r"\bBIDC\b", r"\bFNDE\b", r"\bSEFA\b",
    r"\bGold\s+Standard\b", r"\bVerra\b", r"\bIFC\b", r"\bBCEAO\b",
    r"\bcr[ée]dit\s+carbone\b", r"\bcr[ée]dits?\s+verts?\b",
    r"\bsubvention.*vert\b", r"\bsubventions?\s+climat\b",
    r"\bbanque\s+partenaire\b", r"\bbanque\s+verte\b",
    r"\binterm[ée]diaire.*financ\b", r"\bfinancement.*interm[ée]diaire\b",
    r"\bdossier\s+de\s+candidature\b",
    r"\bacc[ée]der.*financement\b", r"\bfinancement.*acc[ée]der\b",
    r"\bobtenir.*financement\b", r"\bfinancement.*obtenir\b",
    r"\b[ée]ligibilit[ée].*fonds\b", r"\bfonds.*[ée]ligib\b",
    r"\bligne\s+de\s+cr[ée]dit\s+vert\b",
]
_FINANCING_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _FINANCING_KEYWORDS]


# Mapping module actif → flag de routing correspondant
_MODULE_ROUTE_FLAGS = {
    "esg_scoring": "_route_esg",
    "carbon": "_route_carbon",
    "financing": "_route_financing",
    "application": "_route_application",
    "credit": "_route_credit",
    "action_plan": "_route_action_plan",
}


async def _is_topic_continuation(message: str, active_module: str) -> bool:
    """Classification binaire LLM : le message continue-t-il dans le module actif ?

    Retourne True (rester dans le module) en cas d'erreur (defaut securitaire).
    """
    module_labels = {
        "esg_scoring": "évaluation ESG",
        "carbon": "bilan carbone",
        "financing": "financement vert",
        "application": "dossier de candidature",
        "credit": "scoring crédit vert",
        "action_plan": "plan d'action",
        "profiling": "profilage entreprise",
        "document": "analyse de documents",
    }
    module_label = module_labels.get(active_module, active_module)

    prompt = (
        f"L'utilisateur est actuellement dans un module de {module_label}. "
        f"Son message est : \"{message}\"\n\n"
        "Ce message est-il une continuation de la conversation dans ce module "
        "(réponse à une question, information complémentaire, confirmation, etc.) "
        "ou un changement de sujet vers un autre thème ?\n\n"
        "Réponds UNIQUEMENT par 'CONTINUER' ou 'CHANGER'."
    )

    try:
        llm = get_llm()
        response = await llm.ainvoke([
            SystemMessage(content="Tu es un classifieur de messages. Réponds uniquement par 'CONTINUER' ou 'CHANGER'."),
            HumanMessage(content=prompt),
        ])
        answer = response.content.strip().upper()
        return "CHANGER" not in answer
    except Exception:
        logger.exception("Erreur lors de la classification de continuation de sujet")
        return True  # Defaut securitaire : rester dans le module


def _detect_action_plan_request(text: str) -> bool:
    """Detecter si un message est une demande liee au plan d'action ESG."""
    return any(pattern.search(text) for pattern in _ACTION_PLAN_PATTERNS)


def _detect_credit_request(text: str) -> bool:
    """Detecter si un message est une demande de scoring credit vert."""
    return any(pattern.search(text) for pattern in _CREDIT_PATTERNS)


def _detect_financing_request(text: str) -> bool:
    """Detecter si un message est une demande de financement vert."""
    return any(pattern.search(text) for pattern in _FINANCING_PATTERNS)


def _detect_application_request(text: str) -> bool:
    """Detecter si un message est une demande liee aux dossiers de candidature."""
    return any(pattern.search(text) for pattern in _APPLICATION_PATTERNS)


def _detect_carbon_request(text: str) -> bool:
    """Detecter si un message est une demande de bilan carbone."""
    return any(pattern.search(text) for pattern in _CARBON_PATTERNS)


def _has_active_carbon_assessment(state: dict) -> bool:
    """Verifier si un bilan carbone est en cours dans le state."""
    carbon = state.get("carbon_data")
    if carbon is None:
        return False
    return carbon.get("status") == "in_progress"


def _detect_esg_query(text: str) -> bool:
    """Détecter si un message est une consultation ESG (lecture seule)."""
    return any(pattern.search(text) for pattern in _ESG_QUERY_PATTERNS)


def _detect_esg_request(text: str) -> bool:
    """Détecter si un message est une demande d'évaluation ESG (interactive).

    Exclut les consultations simples (score actuel, radar, résultats).
    """
    if _detect_esg_query(text):
        return False
    return any(pattern.search(text) for pattern in _ESG_PATTERNS)


def _has_active_esg_assessment(state: dict) -> bool:
    """Vérifier si une évaluation ESG est en cours dans le state."""
    esg = state.get("esg_assessment")
    if esg is None:
        return False
    return esg.get("status") == "in_progress"


def _detect_module_request(text: str) -> bool:
    """Détecter si un message est une demande de module spécifique."""
    return any(pattern.search(text) for pattern in _MODULE_PATTERNS)


def _compute_identity_completion(profile: dict | None) -> float:
    """Calculer le pourcentage de complétion identité/localisation."""
    if not profile:
        return 0.0
    filled = sum(
        1 for field in IDENTITY_FIELDS
        if profile.get(field) is not None and profile.get(field) != ""
    )
    return (filled / len(IDENTITY_FIELDS)) * 100 if IDENTITY_FIELDS else 0.0


def _build_profiling_instructions(profile: dict | None) -> str:
    """Construire les instructions de profilage avec les champs manquants."""
    missing_fields: list[str] = []
    for field in IDENTITY_FIELDS:
        value = profile.get(field) if profile else None
        if value is None or value == "":
            label = FIELD_LABELS.get(field, field)
            missing_fields.append(f"- {field} ({label})")

    if not missing_fields:
        return ""

    return (
        "PROFILAGE GUIDÉ : Le profil de l'entreprise est incomplet. "
        "Intègre naturellement UNE question sur un champ manquant dans ta réponse. "
        "Ne pose pas la question de façon abrupte, intègre-la dans le fil de la conversation.\n"
        "Champs manquants :\n" + "\n".join(missing_fields)
    )


def get_llm() -> ChatOpenAI:
    """Créer une instance du LLM configurée pour OpenRouter."""
    return ChatOpenAI(
        model=settings.openrouter_model,
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        streaming=True,
        max_tokens=4096,
        request_timeout=60,
    )


def _detect_profile_info(text: str) -> bool:
    """Détecter si un message contient potentiellement des infos de profil."""
    return any(pattern.search(text) for pattern in _PROFILE_PATTERNS)


async def router_node(state: ConversationState) -> ConversationState:
    """Nœud routeur : analyse le message et décide du routage.

    Logique de priorite :
    1. Si active_module est defini → classification binaire continuation/changement
       - Continuation → router vers active_module
       - Changement → reset active_module, classifier normalement
    2. Si active_module est null → classification normale par heuristiques
    """
    messages = state["messages"]
    user_profile = state.get("user_profile")
    active_module = state.get("active_module")
    active_module_data = state.get("active_module_data")

    # Récupérer le dernier message utilisateur
    last_user_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break

    # Si un module est actif, verifier si on continue ou on change de sujet
    if active_module and last_user_msg:
        try:
            is_continuation = await _is_topic_continuation(last_user_msg, active_module)
        except Exception:
            logger.exception("Erreur classification continuation, defaut = rester dans le module")
            is_continuation = True

        if is_continuation:
            # Rester dans le module actif : definir le flag de routing correspondant
            route_flags = {flag: False for flag in _MODULE_ROUTE_FLAGS.values()}
            route_flag = _MODULE_ROUTE_FLAGS.get(active_module)
            if route_flag:
                route_flags[route_flag] = True

            # Décider si on doit extraire des infos de profil
            should_extract = _detect_profile_info(last_user_msg) if last_user_msg else False

            return {
                "profile_updates": [] if should_extract else None,
                "profiling_instructions": None,
                "has_document": state.get("document_upload") is not None,
                "esg_assessment": state.get("esg_assessment"),
                "carbon_data": state.get("carbon_data"),
                "financing_data": state.get("financing_data"),
                "application_data": state.get("application_data"),
                "credit_data": state.get("credit_data"),
                "action_plan_data": state.get("action_plan_data"),
                "active_module": active_module,
                "active_module_data": active_module_data,
                **route_flags,
            }
        else:
            # Changement de sujet : reset active_module et classifier normalement
            active_module = None
            active_module_data = None

    # Classification normale (active_module est null ou changement de sujet)
    has_document = state.get("document_upload") is not None

    esg_assessment = state.get("esg_assessment")
    is_esg_request = _detect_esg_request(last_user_msg) if last_user_msg else False
    has_active_esg = _has_active_esg_assessment(state)

    carbon_data = state.get("carbon_data")
    is_carbon_request = _detect_carbon_request(last_user_msg) if last_user_msg else False
    has_active_carbon = _has_active_carbon_assessment(state)

    financing_data = state.get("financing_data")
    is_financing_request = _detect_financing_request(last_user_msg) if last_user_msg else False

    application_data = state.get("application_data")
    is_application_request = _detect_application_request(last_user_msg) if last_user_msg else False

    credit_data = state.get("credit_data")
    is_credit_request = _detect_credit_request(last_user_msg) if last_user_msg else False

    action_plan_data = state.get("action_plan_data")
    is_action_plan_request = _detect_action_plan_request(last_user_msg) if last_user_msg else False

    should_extract = _detect_profile_info(last_user_msg) if last_user_msg else False

    profiling_instructions: str | None = None
    identity_pct = _compute_identity_completion(user_profile)
    if identity_pct < 70.0 and last_user_msg and not _detect_module_request(last_user_msg) and not is_esg_request and not has_active_esg and not is_carbon_request and not has_active_carbon and not is_financing_request and not is_application_request and not is_credit_request and not is_action_plan_request:
        instructions = _build_profiling_instructions(user_profile)
        if instructions:
            profiling_instructions = instructions

    return {
        "profile_updates": [] if should_extract else None,
        "profiling_instructions": profiling_instructions,
        "has_document": has_document,
        "esg_assessment": esg_assessment,
        "_route_esg": is_esg_request or has_active_esg,
        "carbon_data": carbon_data,
        "_route_carbon": is_carbon_request or has_active_carbon,
        "financing_data": financing_data,
        "_route_financing": is_financing_request,
        "application_data": application_data,
        "_route_application": is_application_request,
        "credit_data": credit_data,
        "_route_credit": is_credit_request,
        "action_plan_data": action_plan_data,
        "_route_action_plan": is_action_plan_request,
        "active_module": active_module,
        "active_module_data": active_module_data,
    }


async def analyze_document_for_chat(
    document_id: str,
    user_id: str,
) -> tuple:
    """Analyser un document pour le contexte chat.

    Charge le document depuis la BDD, lance l'analyse, et retourne
    le document et l'analyse.
    """
    import uuid as uuid_mod

    from app.chains.analysis import analyze_document_text
    from app.core.database import async_session_factory
    from app.modules.documents.service import (
        analyze_document,
        get_document,
    )

    async with async_session_factory() as db:
        document = await get_document(db, uuid_mod.UUID(document_id))
        if document is None:
            raise ValueError(f"Document {document_id} introuvable")

        # Lancer l'analyse si pas encore faite
        if document.analysis is None:
            analysis = await analyze_document(db, document)
        else:
            analysis = document.analysis

        await db.commit()
        return document, analysis


async def document_node(state: ConversationState) -> ConversationState:
    """Nœud document : analyse le document uploadé et injecte le résumé.

    Appelé quand le routeur détecte un document uploadé.
    Analyse le document, stocke les résultats, et ajoute le résumé
    au state pour enrichir le contexte du chat_node.
    """
    doc_upload = state.get("document_upload")
    if not doc_upload:
        return {"document_analysis_summary": None}

    document_id = doc_upload.get("document_id")
    user_id = doc_upload.get("user_id")

    try:
        document, analysis = await analyze_document_for_chat(
            document_id=document_id,
            user_id=user_id,
        )

        # Construire le résumé pour injection dans le contexte
        summary_parts = [
            f"Document analysé : {doc_upload.get('filename', 'document')}",
            f"Type : {analysis.document_type.value if hasattr(analysis, 'document_type') else getattr(document, 'document_type', 'inconnu')}",
        ]

        if hasattr(analysis, "summary") and analysis.summary:
            summary_parts.append(f"Résumé : {analysis.summary}")

        if hasattr(analysis, "key_findings") and analysis.key_findings:
            findings = analysis.key_findings
            if isinstance(findings, list):
                findings_text = "\n".join(f"- {f}" for f in findings[:5])
                summary_parts.append(f"Points clés :\n{findings_text}")

        if hasattr(analysis, "esg_relevant_info") and analysis.esg_relevant_info:
            esg = analysis.esg_relevant_info
            if hasattr(esg, "model_dump"):
                esg = esg.model_dump()
            if isinstance(esg, dict):
                esg_parts = []
                for pillar, items in esg.items():
                    if items:
                        esg_parts.append(f"  {pillar}: {', '.join(items[:3])}")
                if esg_parts:
                    summary_parts.append("ESG :\n" + "\n".join(esg_parts))

        analysis_summary = "\n\n".join(summary_parts)

        return {"document_analysis_summary": analysis_summary}

    except Exception:
        logger.exception("Erreur lors de l'analyse du document dans le chat")
        return {
            "document_analysis_summary": (
                f"Document reçu : {doc_upload.get('filename', 'document')}. "
                "Une erreur est survenue lors de l'analyse. "
                "Veuillez réessayer ou uploader le document depuis la page Documents."
            ),
        }


async def _fetch_rag_context_for_esg(
    user_id: str,
    current_pillar: str,
) -> str:
    """Recuperer le contexte RAG pour le pilier ESG en cours d'evaluation."""
    import uuid as uuid_mod

    from app.core.database import async_session_factory
    from app.modules.esg.service import format_rag_context, search_rag_context_for_pillar

    try:
        async with async_session_factory() as db:
            rag_context = await search_rag_context_for_pillar(
                db=db,
                pillar=current_pillar,
                user_id=uuid_mod.UUID(user_id),
                limit_per_criterion=2,
            )
            return format_rag_context(rag_context)
    except Exception:
        logger.exception("Erreur lors de la recherche RAG pour le pilier %s", current_pillar)
        return ""


async def esg_scoring_node(
    state: ConversationState,
    config: RunnableConfig | None = None,
) -> ConversationState:
    """Noeud d'evaluation ESG : conduit l'evaluation conversationnelle avec tool calling.

    Gere l'etat de l'evaluation (creation, progression, finalisation)
    et utilise un prompt specialise ESG pour interagir avec l'utilisateur.
    Enrichit le contexte avec les documents de l'utilisateur via RAG.
    Le LLM dispose de tools pour creer, sauvegarder et finaliser les evaluations.
    """
    from app.graph.tools.esg_tools import ESG_TOOLS
    from app.prompts.esg_scoring import build_esg_prompt

    llm = get_llm()
    user_profile = state.get("user_profile") or {}
    esg_assessment = state.get("esg_assessment")
    messages = state["messages"]
    tool_call_count = state.get("tool_call_count", 0)

    # Construire le contexte entreprise pour le prompt ESG
    company_lines: list[str] = []
    if user_profile:
        for key, value in user_profile.items():
            if value is not None and value != "":
                company_lines.append(f"- {key}: {value}")
    company_context = "\n".join(company_lines) if company_lines else "Aucun profil disponible."

    # Contexte documentaire general (si disponible)
    doc_context = state.get("document_analysis_summary") or "Aucun document analyse."

    # Si pas d'evaluation en cours, chercher une evaluation a reprendre ou en creer une nouvelle
    if esg_assessment is None or esg_assessment.get("status") == "completed":
        from app.modules.esg.service import build_initial_esg_state

        # Tenter de reprendre une evaluation interrompue
        resumable = None
        user_id = state.get("user_id")
        if user_id:
            try:
                import uuid as uuid_mod

                from app.core.database import async_session_factory
                from app.modules.esg.service import get_resumable_assessment

                async with async_session_factory() as db:
                    resumable = await get_resumable_assessment(db, uuid_mod.UUID(str(user_id)))
            except Exception:
                logger.exception("Erreur lors de la recherche d'evaluation a reprendre")

        if resumable is not None:
            esg_assessment = {
                "assessment_id": str(resumable.id),
                "status": resumable.status.value if hasattr(resumable.status, "value") else resumable.status,
                "current_pillar": resumable.current_pillar or "environment",
                "evaluated_criteria": resumable.evaluated_criteria or [],
                "partial_scores": (resumable.assessment_data or {}).get("criteria_scores", {}),
            }
        else:
            esg_assessment = build_initial_esg_state(
                assessment_id="pending",
                sector=user_profile.get("sector", "services"),
            )

    # Recherche RAG par pilier en cours pour enrichir l'evaluation
    current_pillar = esg_assessment.get("current_pillar", "environment")
    user_id = state.get("user_id")
    rag_context = ""
    if user_id:
        rag_context = await _fetch_rag_context_for_esg(
            user_id=str(user_id),
            current_pillar=current_pillar,
        )

    # Fusionner les contextes documentaires
    if rag_context:
        doc_context = f"{doc_context}\n\n{rag_context}"

    # Construire le prompt ESG
    system_prompt = build_esg_prompt(
        company_context=company_context,
        document_context=doc_context,
        current_page=state.get("current_page"),
        guidance_stats=state.get("guidance_stats"),
    )

    # Instructions tool calling pour le LLM
    tool_instructions = (
        "\n\n## OUTILS DISPONIBLES\n"
        "- `get_esg_assessment` : recuperer une evaluation existante ou en cours\n"
        "- `create_esg_assessment` : creer une nouvelle evaluation\n"
        "- `save_esg_criterion_score` : sauvegarder le score d'un critere (0-10 + justification)\n"
        "- `batch_save_esg_criteria` : sauvegarder plusieurs criteres en un seul appel\n"
        "- `finalize_esg_assessment` : finaliser l'evaluation (UNIQUEMENT apres confirmation utilisateur)\n\n"
        "## REGLE ABSOLUE — TOOL CALLING OBLIGATOIRE\n"
        "Quand l'utilisateur repond a des questions ESG, tu DOIS appeler "
        "`batch_save_esg_criteria` (ou `save_esg_criterion_score`) AVANT de poser la question suivante.\n"
        "- Ne JAMAIS evaluer un critere sans sauvegarder le score via un tool.\n"
        "- Si le tool echoue, informe l'utilisateur et reessaie.\n\n"
        "Workflow obligatoire :\n"
        "1. Appelle get_esg_assessment pour verifier s'il existe une evaluation en cours\n"
        "2. Si aucune evaluation, appelle create_esg_assessment pour en creer une\n"
        "3. Pour chaque critere evalue, appelle batch_save_esg_criteria avec les scores et justifications\n"
        "4. AVANT de finaliser, demande TOUJOURS confirmation a l'utilisateur\n"
        "5. Apres confirmation, appelle finalize_esg_assessment\n"
    )

    # Injecter l'etat d'evaluation dans le prompt
    esg_state_context = (
        f"\n\nETAT DE L'EVALUATION EN COURS :\n"
        f"- Pilier actuel : {esg_assessment.get('current_pillar', 'environment')}\n"
        f"- Criteres evalues : {esg_assessment.get('evaluated_criteria', [])}\n"
        f"- Scores partiels : {esg_assessment.get('partial_scores', {})}\n"
    )
    full_prompt = system_prompt + tool_instructions + esg_state_context

    # Envoyer au LLM avec les tools ESG
    chat_messages = [SystemMessage(content=full_prompt), *[
        m for m in messages if not isinstance(m, SystemMessage)
    ]]

    from app.graph.tools.guided_tour_tools import GUIDED_TOUR_TOOLS
    from app.graph.tools.interactive_tools import INTERACTIVE_TOOLS
    full_catalog = ESG_TOOLS + INTERACTIVE_TOOLS + GUIDED_TOUR_TOOLS
    filtered_tools, debug_info = select_tools_for_node(
        node_name="esg_scoring",
        current_page=state.get("current_page"),
        all_tools=full_catalog,
        active_entities=state.get("active_entities"),
    )
    _propagate_tools_offered(config, debug_info["tools_offered"])
    llm_with_tools = llm.bind_tools(filtered_tools)
    response = await llm_with_tools.ainvoke(chat_messages)

    # Incrementer le compteur de tool calls si le LLM a demande des tools
    new_tool_call_count = tool_call_count
    if hasattr(response, "tool_calls") and response.tool_calls:
        new_tool_call_count = tool_call_count + 1

    # Gestion du cycle de vie active_module
    esg_status = esg_assessment.get("status", "in_progress")
    if esg_status == "completed":
        # Finalisation : desactiver le module actif
        new_active_module = None
        new_active_module_data = None
    else:
        # Activation/mise a jour du module actif
        new_active_module = "esg_scoring"
        new_active_module_data = {
            "assessment_id": esg_assessment.get("assessment_id"),
            "current_criterion": esg_assessment.get("current_pillar"),
            "criteria_evaluated": esg_assessment.get("evaluated_criteria", []),
            "criteria_remaining": [
                c for c in esg_assessment.get("partial_scores", {}).keys()
            ] if esg_assessment.get("partial_scores") else [],
        }

    return {
        "messages": [response],
        "esg_assessment": esg_assessment,
        "tool_call_count": new_tool_call_count,
        "active_module": new_active_module,
        "active_module_data": new_active_module_data,
    }


async def carbon_node(
    state: ConversationState,
    config: RunnableConfig | None = None,
) -> ConversationState:
    """Noeud de bilan carbone : conduit le questionnaire conversationnel.

    Gere l'etat du bilan (creation, progression par categorie, finalisation)
    et utilise un prompt specialise carbone pour interagir avec l'utilisateur.
    Genere des visualisations inline (chart, gauge, table, timeline).
    """
    from app.prompts.carbon import build_carbon_prompt

    llm = get_llm()
    user_profile = state.get("user_profile") or {}
    carbon_data = state.get("carbon_data")
    messages = state["messages"]

    # Construire le contexte entreprise pour le prompt carbone
    company_lines: list[str] = []
    if user_profile:
        for key, value in user_profile.items():
            if value is not None and value != "":
                company_lines.append(f"- {key}: {value}")
    company_context = "\n".join(company_lines) if company_lines else "Aucun profil disponible."

    # Si pas de bilan en cours, chercher un bilan a reprendre ou en creer un nouveau
    if carbon_data is None or carbon_data.get("status") == "completed":
        from app.modules.carbon.service import build_initial_carbon_state

        # Tenter de reprendre un bilan interrompu ; si absent, charger le
        # dernier bilan (meme completed) pour permettre la consultation.
        resumable = None
        latest = None
        user_id = state.get("user_id")
        if user_id:
            try:
                import uuid as uuid_mod

                from app.core.database import async_session_factory
                from app.modules.carbon.service import (
                    get_latest_assessment,
                    get_resumable_assessment,
                )

                async with async_session_factory() as db:
                    user_uuid = uuid_mod.UUID(str(user_id))
                    resumable = await get_resumable_assessment(db, user_uuid)
                    if resumable is None:
                        latest = await get_latest_assessment(db, user_uuid)
            except Exception:
                logger.exception("Erreur lors de la recherche de bilan carbone a reprendre")

        existing = resumable or latest
        if existing is not None:
            from app.modules.carbon.emission_factors import get_applicable_categories
            all_applicable = get_applicable_categories(existing.sector)
            completed_cats = list(existing.completed_categories or [])
            existing_status = existing.status.value if hasattr(existing.status, "value") else str(existing.status)

            # Determiner la categorie en cours (premiere non completee)
            current = all_applicable[0] if all_applicable else "energy"
            for cat in all_applicable:
                if cat not in completed_cats:
                    current = cat
                    break

            carbon_data = {
                "assessment_id": str(existing.id),
                "status": existing_status,
                "current_category": current,
                "completed_categories": completed_cats,
                "applicable_categories": all_applicable,
                "entries": [],
                "total_emissions_tco2e": existing.total_emissions_tco2e or 0.0,
                "sector": existing.sector,
                "year": existing.year,
            }
        else:
            sector = user_profile.get("sector", "services")
            if hasattr(sector, "value"):
                sector = sector.value
            carbon_data = build_initial_carbon_state(
                assessment_id="pending",
                sector=sector,
            )

    # Construire les categories applicables en texte
    applicable_text = ", ".join(carbon_data.get("applicable_categories", ["energy", "transport", "waste"]))

    # Construire le prompt carbone
    system_prompt = build_carbon_prompt(
        company_context=company_context,
        applicable_categories=applicable_text,
        current_page=state.get("current_page"),
        guidance_stats=state.get("guidance_stats"),
    )

    # Injecter l'etat du bilan dans le prompt
    assessment_id_ctx = carbon_data.get("assessment_id", "pending")
    status_ctx = carbon_data.get("status", "in_progress")
    year_ctx = carbon_data.get("year")
    header = (
        "ETAT DU BILAN CARBONE EN COURS"
        if status_ctx != "completed"
        else "BILAN CARBONE EXISTANT (finalise, disponible en consultation)"
    )
    year_line = f"- Annee : {year_ctx}\n" if year_ctx else ""
    carbon_state_context = (
        f"\n\n{header} :\n"
        f"- Identifiant bilan (assessment_id) : {assessment_id_ctx}\n"
        f"- Statut : {status_ctx}\n"
        f"{year_line}"
        f"- Categorie actuelle : {carbon_data.get('current_category', 'energy')}\n"
        f"- Categories completees : {carbon_data.get('completed_categories', [])}\n"
        f"- Categories applicables : {carbon_data.get('applicable_categories', [])}\n"
        f"- Emissions totales actuelles : {carbon_data.get('total_emissions_tco2e', 0)} tCO2e\n"
        f"- Entrees collectees : {len(carbon_data.get('entries', []))}\n"
        f"- Secteur : {carbon_data.get('sector', 'non defini')}\n"
    )
    full_prompt = system_prompt + carbon_state_context

    # Les instructions tool calling sont maintenant dans le template prompt

    # Envoyer au LLM avec tools
    from app.graph.tools.carbon_tools import CARBON_TOOLS
    from app.graph.tools.guided_tour_tools import GUIDED_TOUR_TOOLS
    from app.graph.tools.interactive_tools import INTERACTIVE_TOOLS

    chat_messages = [SystemMessage(content=full_prompt), *[
        m for m in messages if not isinstance(m, SystemMessage)
    ]]

    all_carbon_tools = (CARBON_TOOLS or []) + INTERACTIVE_TOOLS + GUIDED_TOUR_TOOLS
    filtered_tools, debug_info = select_tools_for_node(
        node_name="carbon",
        current_page=state.get("current_page"),
        all_tools=all_carbon_tools,
        active_entities=state.get("active_entities"),
    )
    _propagate_tools_offered(config, debug_info["tools_offered"])
    llm_with_tools = llm.bind_tools(filtered_tools)
    response = await llm_with_tools.ainvoke(chat_messages)

    # Gestion du cycle de vie active_module
    carbon_status = carbon_data.get("status", "in_progress")
    if carbon_status == "completed":
        new_active_module = None
        new_active_module_data = None
    else:
        new_active_module = "carbon"
        new_active_module_data = {
            "assessment_id": carbon_data.get("assessment_id"),
            "entries_collected": carbon_data.get("completed_categories", []),
            "current_category": carbon_data.get("current_category"),
        }

    return {
        "messages": [response],
        "carbon_data": carbon_data,
        "active_module": new_active_module,
        "active_module_data": new_active_module_data,
    }


async def _fetch_rag_context_for_financing(query: str) -> str:
    """Recuperer le contexte RAG pour une question de financement."""
    from app.core.database import async_session_factory
    from app.modules.financing.service import search_financing_chunks

    try:
        async with async_session_factory() as db:
            chunks = await search_financing_chunks(db, query, limit=5)
            if not chunks:
                return ""
            parts = []
            for chunk in chunks:
                source_label = chunk.source_type.value if hasattr(chunk.source_type, "value") else str(chunk.source_type)
                parts.append(f"[{source_label}] {chunk.content}")
            return "\n\n".join(parts)
    except Exception:
        logger.exception("Erreur RAG financement")
        return ""


async def financing_node(
    state: ConversationState,
    config: RunnableConfig | None = None,
) -> ConversationState:
    """Noeud de conseil en financement vert avec tool calling.

    Utilise les tools search_compatible_funds, save_fund_interest, get_fund_details
    et create_fund_application pour interagir avec la base financement.
    Conserve le RAG pour le contexte enrichi.
    """
    from app.graph.tools.financing_tools import FINANCING_TOOLS
    from app.graph.tools.guided_tour_tools import GUIDED_TOUR_TOOLS
    from app.graph.tools.interactive_tools import INTERACTIVE_TOOLS
    from app.prompts.financing import build_financing_prompt

    llm = get_llm()

    # Lier les tools financement + interactif + guidage au LLM (filtres par contexte)
    full_catalog = (FINANCING_TOOLS or []) + INTERACTIVE_TOOLS + GUIDED_TOUR_TOOLS
    filtered_tools, debug_info = select_tools_for_node(
        node_name="financing",
        current_page=state.get("current_page"),
        all_tools=full_catalog,
        active_entities=state.get("active_entities"),
    )
    _propagate_tools_offered(config, debug_info["tools_offered"])
    llm = llm.bind_tools(filtered_tools)

    user_profile = state.get("user_profile") or {}
    financing_data = state.get("financing_data")
    messages = state["messages"]

    # Construire le contexte entreprise
    company_lines: list[str] = []
    if user_profile:
        for key, value in user_profile.items():
            if value is not None and value != "":
                company_lines.append(f"- {key}: {value}")
    company_context = "\n".join(company_lines) if company_lines else "Aucun profil disponible."

    # Recuperer le dernier message utilisateur pour le RAG
    last_user_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break

    # Recherche RAG sur les chunks financement
    rag_context = ""
    if last_user_msg:
        rag_context = await _fetch_rag_context_for_financing(last_user_msg)

    # Construire le prompt financement
    system_prompt = build_financing_prompt(
        company_context=company_context,
        rag_context=rag_context or "Aucune information supplementaire disponible.",
        current_page=state.get("current_page"),
        guidance_stats=state.get("guidance_stats"),
    )

    # Instructions tool calling
    tool_instructions = (
        "\n\n## OUTILS DISPONIBLES\n"
        "- `search_compatible_funds` : rechercher des fonds compatibles avec le profil\n"
        "- `save_fund_interest` : marquer un interet pour un fonds\n"
        "- `get_fund_details` : obtenir les details d'un fonds specifique\n"
        "- `create_fund_application` : creer une candidature pour un fonds\n\n"
        "## REGLE ABSOLUE — TOOL CALLING OBLIGATOIRE\n"
        "Ne cite JAMAIS un nom de fonds sans avoir d'abord appele `search_compatible_funds`.\n"
        "- Toute reponse sur les financements disponibles DOIT etre precedee d'un appel tool.\n"
        "- Ne reponds JAMAIS de memoire sur les fonds — consulte la base.\n"
        "- Tes connaissances generales sur les fonds sont INTERDITES.\n"
        "- Si le tool echoue, informe l'utilisateur et reessaie.\n"
    )

    full_prompt = system_prompt + tool_instructions

    # Envoyer au LLM
    chat_messages = [SystemMessage(content=full_prompt), *[
        m for m in messages if not isinstance(m, SystemMessage)
    ]]

    response = await llm.ainvoke(chat_messages)

    return {
        "messages": [response],
        "financing_data": financing_data,
        "active_module": "financing",
        "active_module_data": {
            "search_done": True,
            "selected_fund_id": (financing_data or {}).get("selected_fund_id"),
            "interest_expressed": (financing_data or {}).get("interest_expressed", False),
        },
    }


async def _fetch_credit_scoring_context(user_id: str | None) -> tuple[str, list[dict]]:
    """Recuperer le contexte de scoring credit pour le credit_node.

    Returns:
        (scoring_context_text, history_items)
    """
    if not user_id:
        return "Aucun score genere.", []

    import uuid as uuid_mod

    from app.core.database import async_session_factory
    from app.modules.credit.service import get_latest_score, get_score_history

    try:
        async with async_session_factory() as db:
            score = await get_latest_score(db, uuid_mod.UUID(str(user_id)))
            if score is None:
                return "Aucun score genere. Invitez l'utilisateur a generer un score via la page /credit-score.", []

            # Construire le contexte textuel
            confidence_label = score.confidence_label
            if hasattr(confidence_label, "value"):
                confidence_label = confidence_label.value

            # Detecter l'expiration
            from datetime import datetime, timezone
            now = datetime.now(tz=timezone.utc)
            is_expired = score.valid_until < now if score.valid_until else False

            parts = [
                f"Score combine: {score.combined_score}/100",
                f"Solvabilite: {score.solvability_score}/100",
                f"Impact vert: {score.green_impact_score}/100",
                f"Confiance: {confidence_label} ({score.confidence_level})",
                f"Version: {score.version}",
                f"Genere le: {score.generated_at.strftime('%d/%m/%Y') if score.generated_at else 'N/A'}",
                f"Valide jusqu'au: {score.valid_until.strftime('%d/%m/%Y') if score.valid_until else 'N/A'}",
            ]

            if is_expired:
                parts.append("\n⚠️ SCORE EXPIRE — Ce score n'est plus a jour. Invitez l'utilisateur a regenerer son score depuis la page /credit-score.")

            # Ajouter le breakdown si disponible
            if score.score_breakdown:
                breakdown = score.score_breakdown
                if "solvability" in breakdown and "factors" in breakdown["solvability"]:
                    parts.append("\nFacteurs solvabilite:")
                    for key, factor in breakdown["solvability"]["factors"].items():
                        parts.append(f"  - {key}: {factor.get('score', 0)}/100 (poids {factor.get('weight', 0)})")
                if "green_impact" in breakdown and "factors" in breakdown["green_impact"]:
                    parts.append("\nFacteurs impact vert:")
                    for key, factor in breakdown["green_impact"]["factors"].items():
                        parts.append(f"  - {key}: {factor.get('score', 0)}/100 (poids {factor.get('weight', 0)})")

            # Recommandations
            if score.recommendations:
                parts.append("\nRecommandations:")
                for rec in score.recommendations[:5]:
                    parts.append(f"  - [{rec.get('impact', 'medium')}] {rec.get('action', '')}")

            # Historique
            history_items: list[dict] = []
            scores, total = await get_score_history(db, uuid_mod.UUID(str(user_id)), limit=10)
            for s in scores:
                history_items.append({
                    "version": s.version,
                    "combined_score": s.combined_score,
                    "solvability_score": s.solvability_score,
                    "green_impact_score": s.green_impact_score,
                    "generated_at": s.generated_at.strftime("%d/%m/%Y") if s.generated_at else "",
                })

            if total > 1:
                parts.append(f"\nHistorique: {total} version(s) de score")

            # Data sources
            if score.data_sources and "sources" in score.data_sources:
                parts.append("\nCouverture des sources:")
                for src in score.data_sources["sources"]:
                    status = "disponible" if src.get("available") else "manquante"
                    completeness = int(src.get("completeness", 0) * 100)
                    parts.append(f"  - {src.get('name', '?')}: {status} ({completeness}%)")

            return "\n".join(parts), history_items

    except Exception:
        logger.exception("Erreur lors de la recuperation du contexte credit")
        return "Erreur lors de la recuperation du score.", []


async def credit_node(
    state: ConversationState,
    config: RunnableConfig | None = None,
) -> ConversationState:
    """Noeud scoring credit vert avec tool calling.

    Utilise les tools generate_credit_score, get_credit_score et
    generate_credit_certificate pour calculer et consulter le score.
    """
    from app.graph.tools.credit_tools import CREDIT_TOOLS
    from app.graph.tools.guided_tour_tools import GUIDED_TOUR_TOOLS
    from app.graph.tools.interactive_tools import INTERACTIVE_TOOLS
    from app.prompts.credit import build_credit_prompt

    llm = get_llm()

    # Lier les tools credit + interactif + guidage au LLM (filtres par contexte)
    full_catalog = (CREDIT_TOOLS or []) + INTERACTIVE_TOOLS + GUIDED_TOUR_TOOLS
    filtered_tools, debug_info = select_tools_for_node(
        node_name="credit",
        current_page=state.get("current_page"),
        all_tools=full_catalog,
        active_entities=state.get("active_entities"),
    )
    _propagate_tools_offered(config, debug_info["tools_offered"])
    llm = llm.bind_tools(filtered_tools)

    user_profile = state.get("user_profile") or {}
    credit_data = state.get("credit_data")
    messages = state["messages"]

    # Construire le contexte entreprise
    company_lines: list[str] = []
    if user_profile:
        for key, value in user_profile.items():
            if value is not None and value != "":
                company_lines.append(f"- {key}: {value}")
    company_context = "\n".join(company_lines) if company_lines else "Aucun profil disponible."

    # Recuperer le contexte de scoring pour l'historique
    user_id = state.get("user_id")
    scoring_context, history_items = await _fetch_credit_scoring_context(user_id)

    # Construire le prompt credit
    system_prompt = build_credit_prompt(
        company_context=company_context,
        scoring_context=scoring_context,
        current_page=state.get("current_page"),
        guidance_stats=state.get("guidance_stats"),
    )

    # Ajouter le contexte historique si disponible
    if history_items and len(history_items) > 1:
        history_text = "\n\nDONNEES HISTORIQUE (pour le graphique ligne):\n"
        for item in history_items:
            history_text += (
                f"- v{item['version']} ({item['generated_at']}): "
                f"combine={item['combined_score']}, solv={item['solvability_score']}, "
                f"vert={item['green_impact_score']}\n"
            )
        system_prompt += history_text

    # Les instructions tool calling sont dans le template prompt
    full_prompt = system_prompt

    # Envoyer au LLM
    chat_messages = [SystemMessage(content=full_prompt), *[
        m for m in messages if not isinstance(m, SystemMessage)
    ]]

    response = await llm.ainvoke(chat_messages)

    return {
        "messages": [response],
        "credit_data": credit_data,
        "active_module": "credit",
        "active_module_data": {"session_id": None},
    }


async def chat_node(
    state: ConversationState,
    config: RunnableConfig | None = None,
) -> ConversationState:
    """Noeud principal avec tool calling : profilage + lecture temps reel.

    Lie les tools de profilage ET les tools de lecture (dashboard, ESG, carbone)
    pour permettre au LLM de mettre a jour le profil et consulter les donnees
    en temps reel depuis la base.
    """
    from app.graph.tools.chat_tools import CHAT_TOOLS
    from app.graph.tools.document_tools import DOCUMENT_TOOLS
    from app.graph.tools.guided_tour_tools import GUIDED_TOUR_TOOLS
    from app.graph.tools.interactive_tools import INTERACTIVE_TOOLS
    from app.graph.tools.profiling_tools import PROFILING_TOOLS

    llm = get_llm()

    # Combiner les tools de profilage, lecture, documents, widgets interactifs et guidage
    all_tools = PROFILING_TOOLS + CHAT_TOOLS + DOCUMENT_TOOLS + INTERACTIVE_TOOLS + GUIDED_TOUR_TOOLS
    if all_tools:
        filtered_tools, debug_info = select_tools_for_node(
            node_name="chat",
            current_page=state.get("current_page"),
            all_tools=all_tools,
            active_entities=state.get("active_entities"),
        )
        _propagate_tools_offered(config, debug_info["tools_offered"])
        llm = llm.bind_tools(filtered_tools)

    user_profile = state.get("user_profile")
    context_memory = state.get("context_memory", [])
    profiling_instructions = state.get("profiling_instructions")
    document_summary = state.get("document_analysis_summary")

    # Construire le prompt systeme dynamique
    system_prompt = build_system_prompt(
        user_profile, context_memory, profiling_instructions,
        document_analysis_summary=document_summary,
        current_page=state.get("current_page"),
        guidance_stats=state.get("guidance_stats"),
    )

    # Instructions consultation base temps reel
    tool_instructions = (
        "\n\nINSTRUCTIONS CONSULTATION BASE :\n"
        "- Pour les questions sur le profil, score ESG, bilan carbone, credit ou dashboard : "
        "utilise les tools de lecture pour consulter la base en temps reel.\n"
        "- Ne reponds JAMAIS de memoire — appelle le tool adapte pour obtenir les donnees actuelles.\n"
        "- Pour mettre a jour le profil : utilise update_company_profile avec les champs fournis.\n"
        "- Quand l'utilisateur demande un graphique, radar ou visuel de ses scores ESG/carbone/credit : "
        "appelle d'abord get_esg_assessment_chat (ou get_carbon_summary_chat) pour recuperer les scores "
        "existants, puis genere le bloc visuel avec les VRAIS scores. Ne relance JAMAIS une nouvelle "
        "evaluation juste pour afficher un graphique."
    )

    from app.prompts.widget import WIDGET_INSTRUCTION
    from app.prompts.system import build_page_context_instruction
    full_prompt = system_prompt + tool_instructions + "\n\n" + WIDGET_INSTRUCTION
    page_context = build_page_context_instruction(state.get("current_page"))
    if page_context:
        full_prompt += "\n\n" + page_context

    # Ajouter le prompt systeme en tete
    messages = state["messages"]
    chat_messages = [SystemMessage(content=full_prompt), *[
        m for m in messages if not isinstance(m, SystemMessage)
    ]]

    response = await llm.ainvoke(chat_messages)

    return {"messages": [response]}


async def profiling_node(state: ConversationState) -> ConversationState:
    """Nœud de profilage : extrait les infos d'entreprise du message.

    Appelé quand le routeur détecte des infos extractibles.
    Utilise la chaîne d'extraction structurée pour analyser le message
    et retourne les champs extraits dans profile_updates.
    """
    from app.chains.extraction import extract_profile_from_message
    from app.modules.company.service import FIELD_LABELS

    messages = state["messages"]
    user_profile = state.get("user_profile") or {}

    # Récupérer le dernier message utilisateur
    last_user_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break

    if not last_user_msg:
        return {"profile_updates": []}

    extraction = await extract_profile_from_message(last_user_msg, user_profile)

    # Convertir l'extraction en liste de mises à jour (dictionnaire plat)
    profile_updates: list[dict] = []
    for field, value in extraction.flat_dict().items():
        display_value = value.value if hasattr(value, "value") else value
        profile_updates.append({
            "field": field,
            "value": display_value,
            "label": FIELD_LABELS.get(field, field),
        })

    return {"profile_updates": profile_updates}


async def application_node(
    state: ConversationState,
    config: RunnableConfig | None = None,
) -> ConversationState:
    """Noeud dossiers de candidature avec tool calling.

    Utilise les tools generate_application_section, update_application_section,
    get_application_checklist, simulate_financing et export_application.
    """
    from app.graph.tools.application_tools import APPLICATION_TOOLS
    from app.graph.tools.interactive_tools import INTERACTIVE_TOOLS
    from app.prompts.application import build_application_prompt

    llm = get_llm()

    # Lier les tools application + interactif au LLM (filtres par contexte)
    full_catalog = (APPLICATION_TOOLS or []) + INTERACTIVE_TOOLS
    filtered_tools, debug_info = select_tools_for_node(
        node_name="application",
        current_page=state.get("current_page"),
        all_tools=full_catalog,
        active_entities=state.get("active_entities"),
    )
    _propagate_tools_offered(config, debug_info["tools_offered"])
    llm = llm.bind_tools(filtered_tools)

    user_profile = state.get("user_profile") or {}
    application_data = state.get("application_data")
    messages = state["messages"]

    # Construire le contexte entreprise
    company_lines: list[str] = []
    if user_profile:
        for key, value in user_profile.items():
            if value is not None and value != "":
                company_lines.append(f"- {key}: {value}")
    company_context = "\n".join(company_lines) if company_lines else "Aucun profil disponible."

    # Construire le contexte dossier
    application_context = "Aucun dossier en cours."
    if application_data:
        parts = [
            f"Dossier : {application_data.get('fund_name', 'Inconnu')}",
            f"Statut : {application_data.get('status', 'inconnu')}",
        ]
        application_context = "\n".join(parts)

    # Construire le prompt
    system_prompt = build_application_prompt(
        company_context=company_context,
        application_context=application_context,
        current_page=state.get("current_page"),
    )

    # Les instructions tool calling sont dans le template prompt
    full_prompt = system_prompt

    # Envoyer au LLM
    chat_messages = [SystemMessage(content=full_prompt), *[
        m for m in messages if not isinstance(m, SystemMessage)
    ]]

    response = await llm.ainvoke(chat_messages)

    return {
        "messages": [response],
        "application_data": application_data,
        "active_module": "application",
        "active_module_data": {"session_id": None},
    }


async def action_plan_node(
    state: ConversationState,
    config: RunnableConfig | None = None,
) -> ConversationState:
    """Noeud plan d'action avec tool calling.

    Utilise les tools generate_action_plan, update_action_item et get_action_plan
    pour generer, modifier et consulter les plans d'action en base.
    """
    from app.graph.tools.action_plan_tools import ACTION_PLAN_TOOLS
    from app.graph.tools.guided_tour_tools import GUIDED_TOUR_TOOLS
    from app.graph.tools.interactive_tools import INTERACTIVE_TOOLS
    from app.prompts.action_plan import build_action_plan_prompt

    llm = get_llm()

    # Lier les tools action plan + interactif + guidage au LLM (filtres par contexte)
    full_catalog = (ACTION_PLAN_TOOLS or []) + INTERACTIVE_TOOLS + GUIDED_TOUR_TOOLS
    filtered_tools, debug_info = select_tools_for_node(
        node_name="action_plan",
        current_page=state.get("current_page"),
        all_tools=full_catalog,
        active_entities=state.get("active_entities"),
    )
    _propagate_tools_offered(config, debug_info["tools_offered"])
    llm = llm.bind_tools(filtered_tools)

    user_profile = state.get("user_profile") or {}
    action_plan_data = state.get("action_plan_data")
    messages = state["messages"]

    # Construire le contexte entreprise
    company_lines: list[str] = []
    if user_profile:
        for key, value in user_profile.items():
            if value is not None and value != "":
                company_lines.append(f"- {key}: {value}")
    company_context = "\n".join(company_lines) if company_lines else "Aucun profil disponible."

    # Recuperer le contexte reel depuis la BDD pour enrichir le prompt
    user_id = state.get("user_id")
    esg_context = "Aucune evaluation ESG disponible."
    carbon_context = "Aucun bilan carbone disponible."
    financing_context = "Aucun matching financement disponible."
    intermediaries_context = "Aucun intermediaire identifie."

    if user_id:
        try:
            import uuid as uuid_mod

            from sqlalchemy import select as sa_select

            from app.core.database import async_session_factory

            async with async_session_factory() as db:
                uid = uuid_mod.UUID(str(user_id))

                # Contexte ESG — dernier assessment
                from app.models.esg import ESGAssessment
                esg_result = await db.execute(
                    sa_select(ESGAssessment)
                    .where(ESGAssessment.user_id == uid)
                    .order_by(ESGAssessment.created_at.desc())
                    .limit(1)
                )
                esg = esg_result.scalar_one_or_none()
                if esg:
                    esg_context = (
                        f"Score ESG global : {esg.overall_score or 'N/A'}/100. "
                        f"E={esg.environment_score or 'N/A'}, S={esg.social_score or 'N/A'}, "
                        f"G={esg.governance_score or 'N/A'}. "
                        f"Statut : {esg.status.value if hasattr(esg.status, 'value') else esg.status}."
                    )

                # Contexte Carbone — dernier assessment
                from app.models.carbon import CarbonAssessment
                carbon_result = await db.execute(
                    sa_select(CarbonAssessment)
                    .where(CarbonAssessment.user_id == uid)
                    .order_by(CarbonAssessment.created_at.desc())
                    .limit(1)
                )
                carbon = carbon_result.scalar_one_or_none()
                if carbon:
                    carbon_context = (
                        f"Bilan carbone {carbon.year} : {carbon.total_emissions_tco2e or 0:.1f} tCO2e. "
                        f"Statut : {carbon.status.value if hasattr(carbon.status, 'value') else carbon.status}."
                    )

                # Contexte Financement — matches existants
                from app.models.financing import FundMatch
                matches_result = await db.execute(
                    sa_select(FundMatch)
                    .where(FundMatch.user_id == uid)
                    .order_by(FundMatch.compatibility_score.desc())
                    .limit(5)
                )
                matches = list(matches_result.scalars().all())
                if matches:
                    # Charger les noms de fonds
                    parts = []
                    for m in matches:
                        await db.refresh(m, ["fund"])
                        if m.fund:
                            parts.append(f"{m.fund.name} ({m.compatibility_score}%)")
                    financing_context = f"{len(matches)} fonds matches : {', '.join(parts)}."

        except Exception:
            logger.exception("Erreur lors de la recuperation du contexte pour le plan d'action")

    # Construire le prompt plan d'action avec les donnees reelles
    system_prompt = build_action_plan_prompt(
        company_context=company_context,
        esg_context=esg_context,
        carbon_context=carbon_context,
        financing_context=financing_context,
        intermediaries_context=intermediaries_context,
        timeframe=12,
        current_page=state.get("current_page"),
        guidance_stats=state.get("guidance_stats"),
    )

    # Les instructions tool calling sont dans le template prompt
    full_prompt = system_prompt

    # Envoyer au LLM
    chat_messages = [SystemMessage(content=full_prompt), *[
        m for m in messages if not isinstance(m, SystemMessage)
    ]]

    response = await llm.ainvoke(chat_messages)

    return {
        "messages": [response],
        "action_plan_data": action_plan_data,
        "active_module": "action_plan",
        "active_module_data": {"session_id": None},
    }


async def generate_title(user_content: str, assistant_content: str) -> str:
    """Générer un titre court pour une conversation à partir du premier échange."""
    llm = get_llm()
    context = f"Message utilisateur : {user_content[:200]}\nRéponse assistant : {assistant_content[:200]}"
    try:
        response = await llm.ainvoke([
            SystemMessage(content=TITLE_PROMPT),
            HumanMessage(content=context),
        ])
        title = response.content.strip().rstrip(".")
        return title[:50] if title else "Conversation"
    except Exception:
        logger.exception("Erreur lors de la génération du titre")
        return "Conversation"
