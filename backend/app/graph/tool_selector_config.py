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

# Borne dure : le LLM ne doit jamais voir plus de N tools par tour.
# F01 ajoute cite_source/search_source/flag_unsourced en GLOBAL_WHITELIST (3 tools),
# F12 ajoute recall_history (1 tool transverse), d'ou la borne portee a 14
# (10 metiers + 4 globaux). F10 ajoute 7 widgets globaux (yes_no/select/number/
# date/date_range/rating/file_upload) ce qui requiert une elevation a 22.
# F14 ajoute 4 tools matching (list/compare/recompute/details) sur 3 noeuds → 26.
# F20 ajoute 3 tools resources globaux (search/get/recommend) → 29.
# F045 ajoute match_funds_for_project sur 4 mappings (financing/application
# modules + profile_projects/chat pages) → portee a 31 pour respecter la
# borne MAX_TOOLS_PER_TURN sans casser les pages existantes.
# F047 ajoute 6 tools ESG-projet (5 + show_comparison_table) sur le slug
# `profile_projects` → portee a 36 pour permettre au LLM de piloter
# l'évaluation depuis la fiche projet sans navigation manuelle.
# F047 (bugfix 2026-05-23, US3) : les 6 tools ESG-projet sont DEPLACES dans
# GLOBAL_WHITELIST (le chat est flottant, accessible depuis toute page) et
# RETIRES des PAGE_TOOL_MAPPING explicites pour respecter la borne 36.
# Compte transverse : 16 widgets/sourcing/memory/resources + 6 F047 = 22.
MAX_TOOLS_PER_TURN: int = 36

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
    # F10 — widgets transverses disponibles partout (FR-014, FR-015).
    # show_form / show_summary_card sont contextuels (ajoutés par MODULE_TOOL_MAPPING).
    # NB : ``ask_file_upload`` (widget d'upload) est VOLONTAIREMENT retiré — le
    # bouton natif d'ajout de fichier de la zone de saisie remplace ce widget.
    # Le LLM ne doit donc plus proposer de widget d'upload mais INVITER
    # l'utilisateur à utiliser ce bouton (cf. prompts/system.py & widget.py).
    "ask_yes_no",
    "ask_select",
    "ask_number",
    "ask_date",
    "ask_date_range",
    "ask_rating",
    # F20 — Bibliothèque Ressources : recherche transverse depuis tous les nœuds.
    "search_resources",
    "get_resource_content",
    "recommend_resources_for_user",
    # F047 — Évaluation ESG-projet : 6 tools transverses pour permettre au LLM
    # de piloter l'évaluation/finalisation/rapport ESG-projet depuis n'importe
    # quelle page du chat flottant. Le LLM doit appeler `list_projects` pour
    # retrouver le projet par nom AVANT toute action si l'URL n'est pas une
    # fiche projet. La directive _PROJECT_ESG_DIRECTIVE (nodes.py) guide la
    # séquence d'appels. F05 (skill_esg_diagnostic) reste isolé via son
    # tool_whitelist, mais le fallback prompt_fusion expose tout de même ces
    # 6 tools quand l'intersection est vide → l'utilisateur peut demander un
    # rapport projet depuis n'importe quel contexte.
    "create_project_esg_assessment",
    "save_project_esg_criterion",
    "finalize_project_esg_assessment",
    "get_project_esg_assessment",
    "list_project_esg_assessments",
    "generate_project_esg_report",
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
        # Génération de rapports accessible depuis le chat global —
        # l'utilisateur dit fréquemment « génère mon rapport ESG/carbone » sans
        # naviguer vers la page dédiée. Sans ces entrées le selecteur les
        # filtre et le LLM hallucine « tool indisponible ».
        "generate_esg_report",
        "generate_carbon_report",
    }),
    # Profil entreprise : edition de fiche + lecture profil.
    "profile": frozenset({
        "update_company_profile",
        "get_company_profile",
        "get_company_profile_chat",
        # F06 — accès lecture aux projets depuis /profile
        "list_projects",
        "get_project",
        # F11 — Map visible sur la page profil pour visualiser les sites projet
        "show_map",
        # F10 — formulaire pour création/édition profil rapide
        "show_form",
    }),
    # F06 — Page projets : tools projet exclusifs (F047 tools désormais dans
    # GLOBAL_WHITELIST, plus besoin de les lister ici).
    "profile_projects": frozenset({
        "list_projects",
        "get_project",
        "create_project",
        "update_project",
        "delete_project",
        "duplicate_project",
        "link_document_to_project",
        # F11 — Map pour visualiser les projets dans la zone UEMOA
        "show_map",
        # F10 — formulaire pour création projet en un seul écran
        "show_form",
        # F14 — Lecture matching depuis la page projets
        "list_matches_for_project",
        "compare_offers_for_fund_v2",
        "get_match_details",
        # F045 — Matching projet-centric depuis la page projets
        "match_funds_for_project",
        # F11 — table comparative critères couverts vs manquants (utilisée
        # par F047 et autres modules)
        "show_comparison_table",
    }),
    # Evaluation ESG entreprise (pages /esg, /esg/results). F047 tools
    # désormais transverses via GLOBAL_WHITELIST.
    "esg": frozenset({
        "create_esg_assessment",
        "save_esg_criterion_score",
        "batch_save_esg_criteria",
        "finalize_esg_assessment",
        "get_esg_assessment",
        "get_esg_assessment_chat",
        # Generation du rapport ESG Word (.docx) post-finalisation.
        "generate_esg_report",
        # F11 — KPICard pour synthèses ESG (score global, scores par pilier)
        "show_kpi_card",
        # F10 — summary card pour valider extractions critères ESG
        "show_summary_card",
    }),
    # F047 — Page dédiée évaluation ESG-projet : tools de contexte projet
    # uniquement (F047 tools désormais dans GLOBAL_WHITELIST).
    "profile_projects_esg": frozenset({
        # Projets contextuels en lecture (rappel du projet courant)
        "list_projects",
        "get_project",
        # F11 — visualisations (KPI score, table critères couverts vs manquants)
        "show_kpi_card",
        "show_comparison_table",
        # F10 — summary card pour récap finalisation
        "show_summary_card",
    }),
    # Bilan carbone (pages /carbon, /carbon/results).
    "carbon": frozenset({
        "create_carbon_assessment",
        "save_emission_entry",
        "finalize_carbon_assessment",
        "get_carbon_summary",
        "get_carbon_summary_chat",
        # Generation du rapport carbone Word (.docx) post-finalisation.
        "generate_carbon_report",
        # F11 — KPICard pour résumé tCO2e + delta vs année précédente
        "show_kpi_card",
        # F10 — formulaire pour saisie rapide d'un poste d'émission
        "show_form",
    }),
    # Catalogue de financement vert et fiches fonds.
    "financing": frozenset({
        "search_compatible_funds",
        "save_fund_interest",
        "get_fund_details",
        "create_fund_application",
        # F11 — Match/Comparison/Map pour matching projet↔offre
        "show_match_card",
        "show_comparison_table",
        "show_map",
        # F10 — summary card pour valider extractions de fond
        "show_summary_card",
        # F14 — Tools matching pleins
        "list_matches_for_project",
        "compare_offers_for_fund_v2",
        "recompute_matches_for_project",
        "get_match_details",
        # F045 — Matching projet-centric
        "match_funds_for_project",
        # F16 — Comparateur multi-offres sourcé
        "compare_simulations",
    }),
    # F16 — Page simulator dédiée
    "simulator": frozenset({
        "compare_simulations",
        "search_compatible_funds",
        "get_fund_details",
        "list_projects",
        "get_project",
        "show_comparison_table",
    }),
    # Dossiers de candidature (pages /applications, /applications/[id]).
    "candidatures": frozenset({
        "create_fund_application",
        "generate_application_section",
        "update_application_section",
        "get_application_checklist",
        "simulate_financing",
        "export_application",
        # 049 — Découverte des dossiers depuis l'onglet /applications.
        # provide/detach_checklist_document restent fournis via
        # MODULE_TOOL_MAPPING["application"] (nœud, priorité de troncature
        # supérieure) pour respecter la borne statique PAGE|GLOBAL ≤ MAX.
        "list_applications",
        # F11 — Match/Comparison pour comparer offres concurrentes
        "show_match_card",
        "show_comparison_table",
        # F10 — formulaire pour création candidature
        "show_form",
        # F14 — Tools matching (lecture + comparateur)
        "list_matches_for_project",
        "compare_offers_for_fund_v2",
        "get_match_details",
        # F16 — Comparateur multi-offres sourcé
        "compare_simulations",
    }),
    # Score credit alternatif.
    "credit": frozenset({
        "generate_credit_score",
        "get_credit_score",
        "generate_credit_certificate",
        # F11 — KPICard pour score crédit
        "show_kpi_card",
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
        # F11 — KPICard pour cartes de synthèse dashboard
        "show_kpi_card",
    }),
    # Documents : analyse + listing.
    "documents": frozenset({
        "analyze_uploaded_document",
        "get_document_analysis",
        "list_user_documents",
        # F10 — summary card pour valider l'extraction d'un document
        "show_summary_card",
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
        # Génération de rapports accessibles depuis le chat global
        # (évite que le LLM hallucine quand le routing reste sur chat).
        "generate_esg_report",
        "generate_carbon_report",
        # F11 — tools de visualisation tous disponibles dans le chat général.
        "show_kpi_card",
        "show_match_card",
        "show_comparison_table",
        "show_map",
        # F14 — Lecture matching depuis le chat global
        "list_matches_for_project",
        # F045 — Matching projet-centric depuis le chat global
        "match_funds_for_project",
    }),
    "esg_scoring": frozenset({
        "create_esg_assessment",
        "save_esg_criterion_score",
        "batch_save_esg_criteria",
        "finalize_esg_assessment",
        "get_esg_assessment",
        # Generation du rapport ESG Word (.docx) post-finalisation.
        "generate_esg_report",
        # F11 — KPICard pour résumés ESG
        "show_kpi_card",
        # F10 — summary card pour valider extractions critères ESG
        "show_summary_card",
        # F047 — Tools ESG-projet désormais transverses via GLOBAL_WHITELIST,
        # plus besoin de les lister ici. La branche projet (_score_project)
        # appelée par _route_esg_target reste fonctionnelle car les tools
        # sont injectés par le bind_tools final.
        # F047 — table comparative critères couverts vs manquants
        "show_comparison_table",
    }),
    "carbon": frozenset({
        "create_carbon_assessment",
        "save_emission_entry",
        "finalize_carbon_assessment",
        "get_carbon_summary",
        # Generation du rapport carbone Word (.docx) post-finalisation.
        "generate_carbon_report",
        # F11 — KPICard pour résumé tCO2e
        "show_kpi_card",
        # F10 — formulaire pour saisie rapide d'un poste d'émission
        "show_form",
    }),
    "financing": frozenset({
        "search_compatible_funds",
        "save_fund_interest",
        "get_fund_details",
        "create_fund_application",
        # 049 — Une demande de dossier existant (« mon dossier GCF ») est happée
        # par le nœud financing (mot-clé fonds prioritaire) : il doit pouvoir
        # lister les dossiers, lire la checklist et fournir un document.
        # `get_application_checklist` listé ici car absent de FINANCING_TOOLS.
        "list_applications",
        "get_application_checklist",
        "provide_checklist_document",
        "detach_checklist_document",
        "list_user_documents",
        # F11 — Match/Comparison/Map pour matching et géolocalisation
        "show_match_card",
        "show_comparison_table",
        "show_map",
        # F10 — summary card pour valider extractions de fond
        "show_summary_card",
        # F14 — Tools matching pleins (4)
        "list_matches_for_project",
        "compare_offers_for_fund_v2",
        "recompute_matches_for_project",
        "get_match_details",
        # F045 — Matching projet-centric
        "match_funds_for_project",
        # F16 — Comparateur multi-offres sourcé
        "compare_simulations",
    }),
    "application": frozenset({
        "create_fund_application",
        "generate_application_section",
        "update_application_section",
        "get_application_checklist",
        "simulate_financing",
        "export_application",
        # 049 — Découverte des dossiers + fourniture des documents de checklist.
        "list_applications",
        "provide_checklist_document",
        "detach_checklist_document",
        # 049 — list_user_documents visible ici (US2 : rattacher un document
        # déjà téléversé). Exécutable via DOCUMENT_TOOLS injecté au ToolNode.
        "list_user_documents",
        # F11 — Match/Comparison pour comparaison cross-offres
        "show_match_card",
        "show_comparison_table",
        # F10 — formulaire pour création candidature
        "show_form",
        # F14 — Tools matching pleins (4)
        "list_matches_for_project",
        "compare_offers_for_fund_v2",
        "recompute_matches_for_project",
        # F045 — Matching projet-centric
        "match_funds_for_project",
        # F16 — Comparateur multi-offres sourcé
        "compare_simulations",
        "get_match_details",
    }),
    "credit": frozenset({
        "generate_credit_score",
        "get_credit_score",
        "generate_credit_certificate",
        # F11 — KPICard pour score crédit
        "show_kpi_card",
    }),
    "action_plan": frozenset({
        "generate_action_plan",
        "update_action_item",
        "get_action_plan",
        # F11 — KPICard pour synthèse plan d'action
        "show_kpi_card",
    }),
    "document": frozenset({
        "analyze_uploaded_document",
        "get_document_analysis",
        "list_user_documents",
        # F10 — summary card pour valider l'extraction d'un document
        "show_summary_card",
    }),
}


# Patterns path Nuxt -> slug de page. L'ordre compte : la premiere regex qui
# matche gagne. Les patterns sont ancres avec `^`.
_PATH_TO_SLUG_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^/$"), "chat_global"),
    (re.compile(r"^/chat(?:/|$)"), "chat_global"),
    # F047 — `/profile/projects/{id}/esg` doit matcher AVANT
    # `/profile/projects` (l'ordre compte).
    (re.compile(r"^/profile/projects/[^/]+/esg(?:/|$)"), "profile_projects_esg"),
    # F06 — `/profile/projects` doit matcher AVANT `/profile` (l'ordre compte).
    (re.compile(r"^/profile/projects(?:/|$)"), "profile_projects"),
    (re.compile(r"^/profile(?:/|$)"), "profile"),
    (re.compile(r"^/esg(?:/|$)"), "esg"),
    (re.compile(r"^/carbon(?:/|$)"), "carbon"),
    # F16 — `/financing/simulator` AVANT `/financing` (l'ordre compte).
    (re.compile(r"^/financing/simulator(?:/|$)"), "simulator"),
    (re.compile(r"^/financing(?:/|$)"), "financing"),
    (re.compile(r"^/simulator(?:/|$)"), "simulator"),
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
