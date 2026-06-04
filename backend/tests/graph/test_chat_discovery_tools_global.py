"""Tests 051 — tools de DÉCOUVERTE/STATUT (lecture seule) disponibles depuis
le chat flottant, sur N'IMPORTE QUELLE page.

Objectif métier : depuis /chat ou toute autre route, l'utilisateur peut demander
« génère mon score ESG » ou « où en est mon dossier ? » sans navigation manuelle.

Décision d'architecture (vs ajout à GLOBAL_WHITELIST) : on étend la base du
**nœud `chat`** (le chat est flottant = atteignable depuis toute page ; son
mapping est page-indépendant). `select_tools_for_node` ne surface un tool de la
whitelist que s'il est AUSSI dans le catalogue du nœud
(`GLOBAL_WHITELIST & available_names`) — l'ajouter à GLOBAL_WHITELIST seul ne le
rendrait donc pas transverse sans l'injecter dans chaque catalogue de nœud, et
gonflerait le budget statique des pages déjà pleines (profile_projects/financing
à 35/36) au-delà de MAX_TOOLS_PER_TURN. La base chat n'impacte aucun autre budget.

Verrouille trois invariants :
1. **Visibilité** : depuis node=chat, quelle que soit la page, le sélecteur
   expose les 4 tools de découverte/statut (`list_applications`,
   `get_application_checklist`, `get_esg_assessment_chat`,
   `get_user_dashboard_summary`), sans troncature et sous la borne.
2. **Lecture seule** : la base chat n'expose PAS les tools de mutation de
   checklist (`provide_checklist_document` / `detach_checklist_document`) — ils
   restent réservés aux nœuds application/financing (049).
3. **Exécutabilité** : le ToolNode `chat` du graphe compilé peut EXÉCUTER
   `list_applications` + `get_application_checklist` (un tool visible mais absent
   du ToolNode ferait halluciner « tool indisponible »).
4. **Routage / chevauchement détecteurs** : une demande ESG/dossier/crédit
   explicite atteint le bon nœud, sans détournement croisé.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.graph.graph import _route_after_router
from app.graph.prompt_fusion import select_tools_with_skills
from app.graph.nodes import (
    _detect_action_plan_request,
    _detect_application_request,
    _detect_carbon_request,
    _detect_credit_request,
    _detect_esg_request,
    _detect_financing_request,
)
from app.graph.tool_selector import select_tools_for_node
from app.graph.tool_selector_config import (
    MAX_TOOLS_PER_TURN,
    MODULE_TOOL_MAPPING,
    PAGE_TOOL_MAPPING,
)
from app.graph.tools.application_tools import APPLICATION_STATUS_TOOLS
from app.graph.tools.chat_tools import CHAT_TOOLS
from app.graph.tools.document_tools import DOCUMENT_TOOLS
from app.graph.tools.guided_tour_tools import GUIDED_TOUR_TOOLS
from app.graph.tools.interactive_tools import INTERACTIVE_TOOLS
from app.graph.tools.profiling_tools import PROFILING_TOOLS
from app.graph.tools.project_esg_tools import PROJECT_ESG_TOOLS
from app.graph.tools.project_tools import PROJECT_TOOLS
from app.graph.tools.sourcing_tools import SOURCING_TOOLS
from app.graph.tools.visualization_tools import VISUALIZATION_TOOLS

pytestmark = pytest.mark.unit


# Tools de découverte/statut en LECTURE SEULE attendus partout depuis le chat.
_DISCOVERY_TOOL_NAMES = {
    "list_applications",          # découverte des dossiers
    "get_application_checklist",  # statut documentaire d'un dossier
    "get_esg_assessment_chat",    # tool de score ESG (lecture)
    "get_user_dashboard_summary",  # état d'avancement transverse
}

# Tools de MUTATION qui NE doivent PAS rejoindre la base chat (scope lecture seule).
_MUTATION_TOOL_NAMES = {
    "provide_checklist_document",
    "detach_checklist_document",
}


def _chat_node_catalog() -> list:
    """Reproduit fidèlement le catalogue de visibilité du nœud chat (nodes.py).

    chat_node.all_tools = PROFILING + CHAT + DOCUMENT + INTERACTIVE + GUIDED_TOUR
    + SOURCING + PROJECT + PROJECT_ESG + VISUALIZATION + [rapports] +
    APPLICATION_STATUS_TOOLS (051).
    """
    from app.graph.tools.carbon_tools import generate_carbon_report
    from app.graph.tools.esg_tools import generate_esg_report

    return (
        list(PROFILING_TOOLS)
        + list(CHAT_TOOLS)
        + list(DOCUMENT_TOOLS)
        + list(INTERACTIVE_TOOLS)
        + list(GUIDED_TOUR_TOOLS)
        + list(SOURCING_TOOLS)
        + list(PROJECT_TOOLS)
        + list(PROJECT_ESG_TOOLS)
        + list(VISUALIZATION_TOOLS)
        + [generate_esg_report, generate_carbon_report]
        + list(APPLICATION_STATUS_TOOLS)
    )


# ---------------------------------------------------------------------------
# 1. Visibilité depuis node=chat, quelle que soit la page
# ---------------------------------------------------------------------------


class TestChatDiscoveryVisibility:
    """Le sélecteur expose les tools de découverte depuis le chat, partout."""

    @pytest.mark.parametrize(
        "current_page",
        [
            None,            # fallback (aucune page)
            "chat_global",   # slug canonique
            "/chat",         # route /chat
            "/",             # route racine
            "/carbon",       # autre page (bilan carbone)
            "/esg",          # page ESG
            "/profile",      # page profil
            "/financing",    # page financement
            "/dashboard",    # tableau de bord
            "/credit-score",  # page crédit
        ],
    )
    def test_discovery_tools_offered_from_chat_on_any_page(self, current_page) -> None:
        """Invariant central : depuis le nœud chat, quelle que soit la page, les
        4 tools de découverte/statut sont exposés et la borne est respectée."""
        selected, debug = select_tools_for_node(
            node_name="chat",
            current_page=current_page,
            all_tools=_chat_node_catalog(),
        )
        offered = set(debug["tools_offered"])
        assert _DISCOVERY_TOOL_NAMES <= offered, (
            f"Tools de découverte manquants pour page={current_page!r} : "
            f"{_DISCOVERY_TOOL_NAMES - offered}"
        )
        assert len(selected) <= MAX_TOOLS_PER_TURN

    @pytest.mark.parametrize("current_page", [None, "chat_global", "/chat", "/"])
    def test_no_truncation_on_primary_chat_surface(self, current_page) -> None:
        """Sur la surface d'origine du chat (/chat, /), la base unie tient sous la
        borne sans troncature."""
        _, debug = select_tools_for_node(
            node_name="chat",
            current_page=current_page,
            all_tools=_chat_node_catalog(),
        )
        assert debug["truncated"] is False, (
            f"Troncature inattendue sur la surface chat (page={current_page!r})."
        )

    @pytest.mark.parametrize("current_page", ["/financing", "/carbon", "/esg", "/profile"])
    def test_truncation_never_drops_chat_node_tools(self, current_page) -> None:
        """Cohérence de la troncature priorisée : sur les pages riches, la base
        unie peut dépasser la borne, mais la priorité (whitelist > nœud > page)
        garantit qu'AUCUN tool du nœud chat (dont les tools de découverte) n'est
        évincé — seuls des widgets de page surnuméraires sont coupés."""
        catalog = _chat_node_catalog()
        available = {t.name for t in catalog}
        _, debug = select_tools_for_node(
            node_name="chat",
            current_page=current_page,
            all_tools=catalog,
        )
        offered = set(debug["tools_offered"])
        chat_node_tools = set(MODULE_TOOL_MAPPING["chat"]) & available
        dropped = chat_node_tools - offered
        assert not dropped, (
            f"Des tools du nœud chat ont été évincés sur {current_page!r} : {dropped}"
        )
        assert _DISCOVERY_TOOL_NAMES <= offered

    def test_chat_base_is_read_only_no_mutation_tools(self) -> None:
        """La base chat (découverte/statut) reste LECTURE SEULE : pas de
        provide/detach_checklist_document (réservés aux nœuds application/financing)."""
        _, debug = select_tools_for_node(
            node_name="chat",
            current_page="chat_global",
            all_tools=_chat_node_catalog(),
        )
        offered = set(debug["tools_offered"])
        assert not (_MUTATION_TOOL_NAMES & offered), (
            f"Tools de mutation exposés à tort sur la base chat : "
            f"{_MUTATION_TOOL_NAMES & offered}"
        )


# ---------------------------------------------------------------------------
# 2. Configuration des mappings
# ---------------------------------------------------------------------------


class TestChatMappingConfig:
    def test_module_mapping_chat_includes_discovery(self) -> None:
        assert {"list_applications", "get_application_checklist"} <= MODULE_TOOL_MAPPING["chat"]
        # Les lectures ESG/dashboard y étaient déjà — on verrouille leur présence.
        assert {"get_esg_assessment_chat", "get_user_dashboard_summary"} <= MODULE_TOOL_MAPPING["chat"]

    def test_chat_global_page_includes_discovery(self) -> None:
        assert {"list_applications", "get_application_checklist"} <= PAGE_TOOL_MAPPING["chat_global"]

    def test_chat_mapping_excludes_checklist_mutations(self) -> None:
        """Scope lecture seule : pas de mutation de checklist dans la base chat."""
        assert not (_MUTATION_TOOL_NAMES & set(MODULE_TOOL_MAPPING["chat"]))
        assert not (_MUTATION_TOOL_NAMES & set(PAGE_TOOL_MAPPING["chat_global"]))

    def test_chat_global_projection_within_budget(self) -> None:
        """L'ajout ne fait pas dépasser MAX (invariant _validate_config)."""
        from app.graph.tool_selector_config import GLOBAL_WHITELIST

        projected = PAGE_TOOL_MAPPING["chat_global"] | GLOBAL_WHITELIST
        assert len(projected) <= MAX_TOOLS_PER_TURN


# ---------------------------------------------------------------------------
# 3. Exécutabilité réelle (ToolNode du graphe compilé)
# ---------------------------------------------------------------------------


class TestChatToolNodeExecutability:
    """Le ToolNode `chat` du graphe compilé EXÉCUTE les tools de découverte."""

    @staticmethod
    def _tool_node_names(node_name: str) -> set[str]:
        from app.graph.graph import build_graph

        graph = build_graph()
        spec = graph.nodes[f"{node_name}_tools"]
        tool_node = getattr(spec, "runnable", spec)
        return set(getattr(tool_node, "tools_by_name", {}).keys())

    def test_chat_toolnode_can_execute_discovery_tools(self) -> None:
        names = self._tool_node_names("chat")
        required = {"list_applications", "get_application_checklist"}
        assert required <= names, f"Non exécutables sur chat : {required - names}"

    def test_chat_toolnode_keeps_existing_tools(self) -> None:
        """Anti-régression : l'ajout ne retire aucun tool chat existant."""
        names = self._tool_node_names("chat")
        assert {
            "get_user_dashboard_summary",
            "get_esg_assessment_chat",
            "update_company_profile",
            "generate_esg_report",
        } <= names


# ---------------------------------------------------------------------------
# 4. Routage / chevauchement de détecteurs (anti-détournement)
# ---------------------------------------------------------------------------


def _destination_node(message: str) -> str:
    """Reproduit la décision de routage de router_node (active_module=None)
    puis applique la priorité de _route_after_router. (cf. test_application_checklist_wiring)
    """
    is_credit = _detect_credit_request(message)
    is_financing = _detect_financing_request(message)
    flags = {
        "_route_action_plan": _detect_action_plan_request(message),
        "_route_esg": _detect_esg_request(message) and not is_credit,
        "_route_carbon": _detect_carbon_request(message),
        "_route_financing": is_financing and not is_credit,
        "_route_application": _detect_application_request(message),
        "_route_credit": is_credit,
        "has_document": False,
    }
    return _route_after_router(flags)


class TestRoutingNoHijack:
    """Une demande explicite atteint son nœud sans détournement croisé."""

    def test_explicit_esg_eval_not_hijacked_to_financing_or_credit(self) -> None:
        """« lance mon évaluation ESG » → esg_scoring (pas financing/credit)."""
        assert _detect_esg_request("lance mon évaluation ESG") is True
        assert _destination_node("lance mon évaluation ESG") == "esg_scoring"

    def test_explicit_credit_not_hijacked_to_esg_or_financing(self) -> None:
        """« calcule mon score de crédit vert » déclenche aussi les détecteurs ESG
        (« calcul…score ») et financing (« crédit vert »), mais la demande crédit
        explicite prime → nœud credit (cf. routing-detecteurs-overlap)."""
        msg = "calcule mon score de crédit vert"
        assert _detect_credit_request(msg) is True
        assert _destination_node(msg) == "credit"

    @pytest.mark.parametrize(
        "msg",
        [
            "où en est mon dossier ?",                  # → application
            "où en est mon dossier de candidature ?",   # → financing (mot-clé partagé)
            "montre mes candidatures",                  # → application
        ],
    )
    def test_dossier_status_reaches_capable_node(self, msg) -> None:
        """Une demande de statut de dossier atteint un nœud CAPABLE (dont le
        mapping expose `list_applications`) : application OU financing (049).
        Le détecteur application matche, mais « dossier de candidature » est aussi
        un mot-clé financing prioritaire — les deux nœuds savent lister/lire les
        dossiers, donc le flux fonctionne quel que soit le gagnant de priorité."""
        dest = _destination_node(msg)
        assert "list_applications" in MODULE_TOOL_MAPPING[dest], (
            f"« {msg} » routé vers {dest!r} qui n'expose pas list_applications"
        )

    def test_generic_dossier_routes_to_application(self) -> None:
        """« où en est mon dossier ? » (sans « candidature ») → application."""
        msg = "où en est mon dossier ?"
        assert _detect_application_request(msg) is True
        assert _destination_node(msg) == "application"


# ---------------------------------------------------------------------------
# 5. Couche skills (F23) — l'intersection ne masque pas les tools de découverte
# ---------------------------------------------------------------------------


class TestSkillLayerPreservesDiscovery:
    """Pipeline complet sélecteur → intersection skills. Régression : le skill
    `skill_dossier_gcf_via_boad` (activé par le mot-clé « dossier ») a un
    tool_whitelist sans list_applications/get_application_checklist ; sans
    protection, l'intersection les retire APRÈS la sélection, défaisant 051."""

    @staticmethod
    def _dossier_skill():
        # Réplique le tool_whitelist réel du skill seedé (seed.py).
        return SimpleNamespace(
            id="00000000-0000-0000-0000-000000000001",
            name="skill_dossier_gcf_via_boad",
            version="1.0.0",
            tool_whitelist=[
                "create_fund_application",
                "update_company_profile",
                "get_company_profile",
            ],
        )

    def test_discovery_survives_dossier_skill_on_chat(self) -> None:
        selected, _ = select_tools_for_node(
            node_name="chat",
            current_page="/dashboard",
            all_tools=_chat_node_catalog(),
        )
        # Pré-condition : la sélection expose bien les tools de découverte.
        assert {"list_applications", "get_application_checklist"} <= {t.name for t in selected}

        after = select_tools_with_skills(selected, [self._dossier_skill()], allow_fallback=True)
        after_names = {t.name for t in after}
        assert {"list_applications", "get_application_checklist"} <= after_names, (
            "La couche skill a masqué les tools de découverte — régression 051."
        )
        # Le tool expert du skill présent dans le catalogue chat reste aussi.
        assert "update_company_profile" in after_names
