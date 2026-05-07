"""Configuration declarative du filtrage de tools par contexte de page.

Story 10.2 — ligne 2 de defense de l'epic M10. Le LLM doit voir au maximum
MAX_TOOLS_PER_TURN tools pertinents par tour, selectionnes en fonction de
la page courante (current_page transmis par le frontend) ou, en fallback,
du noeud LangGraph en cours.

Verrous d'architecture :
- Filtrage cote LLM uniquement (`bind_tools`) — le ToolNode garde toujours
  la liste complete pour pouvoir executer un tool eventuellement appele.
- Mapping declaratif et pur : pas d'I/O, pas d'appel LLM, deterministe.
- Les noms de tools sont les `tool.name` LangChain (= nom de fonction Python
  decoree par `@tool`).
"""

from __future__ import annotations

import re

# Borne dure : le LLM ne doit jamais voir plus de 14 tools par tour.
# F01 ajoute cite_source/search_source/flag_unsourced en GLOBAL_WHITELIST (3 tools),
# F12 ajoute recall_history (1 tool transverse), d'ou la borne portee a 14
# (10 metiers + 4 globaux).
MAX_TOOLS_PER_TURN: int = 14

# Whitelist transverse : tools toujours disponibles, ajoutes a chaque selection.
# Source de verite : seuls les tools EFFECTIVEMENT exposes par le code peuvent
# y figurer (cf. story 10.2 contexte §5 — pas de tools `show_*` ou `ask_qcu/qcm`).
GLOBAL_WHITELIST: frozenset[str] = frozenset({
    "ask_interactive_question",
    "trigger_guided_tour",
    # F01 — sourcing tools toujours disponibles pour respecter l'invariant
    # de citation obligatoire de chaque chiffre.
    "cite_source",
    "search_source",
    "flag_unsourced",
    # F12 — recall_history transverse pour permettre la recherche sémantique
    # dans l'historique depuis n'importe quel noeud spécialiste.
    "recall_history",
})


# Mapping page courante (slug) -> tools autorises pour cette page.
# Les slugs sont les valeurs canoniques retournees par `normalize_page`.
PAGE_TOOL_MAPPING: dict[str, frozenset[str]] = {
    # Page d'accueil / chat global : profilage + lecture dashboard + documents.
    "chat_global": frozenset({
        "update_company_profile",
        "get_company_profile",
        "get_user_dashboard_summary",
        "get_company_profile_chat",
        "get_esg_assessment_chat",
        "get_carbon_summary_chat",
        "list_user_documents",
        # F06 — accès lecture aux projets depuis le chat global
        "list_projects",
    }),
    # Profil entreprise : edition de fiche + lecture profil.
    "profile": frozenset({
        "update_company_profile",
        "get_company_profile",
        "get_company_profile_chat",
        # F06 — accès lecture aux projets depuis /profile
        "list_projects",
        "get_project",
    }),
    # F06 — Page projets : 7 tools projet exclusifs.
    "profile_projects": frozenset({
        "list_projects",
        "get_project",
        "create_project",
        "update_project",
        "delete_project",
        "duplicate_project",
        "link_document_to_project",
    }),
    # Evaluation ESG (pages /esg, /esg/results).
    "esg": frozenset({
        "create_esg_assessment",
        "save_esg_criterion_score",
        "batch_save_esg_criteria",
        "finalize_esg_assessment",
        "get_esg_assessment",
        "get_esg_assessment_chat",
    }),
    # Bilan carbone (pages /carbon, /carbon/results).
    "carbon": frozenset({
        "create_carbon_assessment",
        "save_emission_entry",
        "finalize_carbon_assessment",
        "get_carbon_summary",
        "get_carbon_summary_chat",
    }),
    # Catalogue de financement vert et fiches fonds.
    "financing": frozenset({
        "search_compatible_funds",
        "save_fund_interest",
        "get_fund_details",
        "create_fund_application",
    }),
    # Dossiers de candidature (pages /applications, /applications/[id]).
    "candidatures": frozenset({
        "create_fund_application",
        "generate_application_section",
        "update_application_section",
        "get_application_checklist",
        "simulate_financing",
        "export_application",
    }),
    # Score credit alternatif.
    "credit": frozenset({
        "generate_credit_score",
        "get_credit_score",
        "generate_credit_certificate",
    }),
    # Plan d'action.
    "action_plan": frozenset({
        "generate_action_plan",
        "update_action_item",
        "get_action_plan",
    }),
    # Tableau de bord : lecture seule, synthese transverse.
    "dashboard": frozenset({
        "get_user_dashboard_summary",
        "get_company_profile_chat",
        "get_esg_assessment_chat",
        "get_carbon_summary_chat",
        "get_action_plan",
    }),
    # Documents : analyse + listing.
    "documents": frozenset({
        "analyze_uploaded_document",
        "get_document_analysis",
        "list_user_documents",
    }),
    # Rapports PDF : lecture seule (pas de tools dedies — fallback profil + esg).
    "reports": frozenset({
        "get_esg_assessment_chat",
        "get_carbon_summary_chat",
        "get_company_profile_chat",
    }),
}


# Mapping noeud LangGraph -> tools du module (fallback quand la page est
# inconnue ou absente). Doit refleter strictement les tools effectivement
# binds dans `nodes.py`.
MODULE_TOOL_MAPPING: dict[str, frozenset[str]] = {
    "chat": frozenset({
        "update_company_profile",
        "get_company_profile",
        "get_user_dashboard_summary",
        "get_company_profile_chat",
        "get_esg_assessment_chat",
        "get_carbon_summary_chat",
        "analyze_uploaded_document",
        "get_document_analysis",
        "list_user_documents",
        # F06 — lecture projets depuis le noeud chat
        "list_projects",
    }),
    "esg_scoring": frozenset({
        "create_esg_assessment",
        "save_esg_criterion_score",
        "batch_save_esg_criteria",
        "finalize_esg_assessment",
        "get_esg_assessment",
    }),
    "carbon": frozenset({
        "create_carbon_assessment",
        "save_emission_entry",
        "finalize_carbon_assessment",
        "get_carbon_summary",
    }),
    "financing": frozenset({
        "search_compatible_funds",
        "save_fund_interest",
        "get_fund_details",
        "create_fund_application",
    }),
    "application": frozenset({
        "create_fund_application",
        "generate_application_section",
        "update_application_section",
        "get_application_checklist",
        "simulate_financing",
        "export_application",
    }),
    "credit": frozenset({
        "generate_credit_score",
        "get_credit_score",
        "generate_credit_certificate",
    }),
    "action_plan": frozenset({
        "generate_action_plan",
        "update_action_item",
        "get_action_plan",
    }),
    "document": frozenset({
        "analyze_uploaded_document",
        "get_document_analysis",
        "list_user_documents",
    }),
}


# Patterns path Nuxt -> slug de page. L'ordre compte : la premiere regex qui
# matche gagne. Les patterns sont ancres avec `^`.
_PATH_TO_SLUG_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^/$"), "chat_global"),
    (re.compile(r"^/chat(?:/|$)"), "chat_global"),
    # F06 — `/profile/projects` doit matcher AVANT `/profile` (l'ordre compte).
    (re.compile(r"^/profile/projects(?:/|$)"), "profile_projects"),
    (re.compile(r"^/profile(?:/|$)"), "profile"),
    (re.compile(r"^/esg(?:/|$)"), "esg"),
    (re.compile(r"^/carbon(?:/|$)"), "carbon"),
    (re.compile(r"^/financing(?:/|$)"), "financing"),
    (re.compile(r"^/applications(?:/|$)"), "candidatures"),
    (re.compile(r"^/candidatures(?:/|$)"), "candidatures"),
    (re.compile(r"^/credit-score(?:/|$)"), "credit"),
    (re.compile(r"^/credit(?:/|$)"), "credit"),
    (re.compile(r"^/action-plan(?:/|$)"), "action_plan"),
    (re.compile(r"^/dashboard(?:/|$)"), "dashboard"),
    (re.compile(r"^/documents(?:/|$)"), "documents"),
    (re.compile(r"^/reports(?:/|$)"), "reports"),
)


def normalize_page(current_page: str | None) -> str | None:
    """Convertir un path Nuxt brut (ex `/esg/results`) en slug canonique.

    Retourne None si l'entree est None/vide ou si aucun pattern ne correspond.
    Si la chaine est deja un slug connu de PAGE_TOOL_MAPPING, elle est
    retournee telle quelle.
    """
    if not current_page:
        return None

    value = current_page.strip()
    if not value:
        return None

    # Slug deja canonique (passage direct, evite double normalisation).
    if value in PAGE_TOOL_MAPPING:
        return value

    for pattern, slug in _PATH_TO_SLUG_PATTERNS:
        if pattern.match(value):
            return slug

    return None


# Noeuds LangGraph reconnus (gate de configuration).
_KNOWN_NODE_NAMES: frozenset[str] = frozenset({
    "chat", "esg_scoring", "carbon", "financing",
    "application", "credit", "action_plan", "document",
})


def _validate_config() -> None:
    """Validation au load-time. Utilise `raise ValueError` plutot que `assert`
    pour rester actif sous `python -O` (ou les assertions sont supprimees)."""
    unknown_nodes = set(MODULE_TOOL_MAPPING.keys()) - _KNOWN_NODE_NAMES
    if unknown_nodes:
        raise ValueError(
            f"MODULE_TOOL_MAPPING contient des noeuds inconnus : {unknown_nodes}"
        )

    for slug, tools in PAGE_TOOL_MAPPING.items():
        projected = tools | GLOBAL_WHITELIST
        if len(projected) > MAX_TOOLS_PER_TURN:
            raise ValueError(
                f"Page '{slug}' aurait {len(projected)} tools "
                f"(>{MAX_TOOLS_PER_TURN}) — reduire le mapping."
            )


_validate_config()
