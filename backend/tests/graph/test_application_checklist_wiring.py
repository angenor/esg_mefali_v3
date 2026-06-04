"""Tests de câblage 049 — découverte des dossiers + fourniture de documents.

Verrouille deux invariants qui font fonctionner le flux depuis le chat :

1. **Visibilité** : `select_tools_for_node` expose bien `list_applications`,
   `get_application_checklist`, `provide_checklist_document`,
   `detach_checklist_document` et `list_user_documents` — sur le nœud
   `application` ET sur le nœud `financing` (car « mon dossier GCF » y est
   routé par la priorité du mot-clé fonds).
2. **Routage** : les phrases de gestion de checklist (« rattache … à l'item … »,
   « checklist », « documents manquants ») sont détectées comme demandes
   `application`, sans happer le flux projet `link_document_to_project`.
"""

import pytest

from app.graph.tool_selector import select_tools_for_node
from app.graph.tools.application_tools import (
    APPLICATION_DISCOVERY_TOOLS,
    APPLICATION_TOOLS,
    create_fund_application,
)
from app.graph.tools.document_tools import DOCUMENT_TOOLS
from app.graph.tools.financing_tools import FINANCING_TOOLS
from app.graph.tools.guided_tour_tools import GUIDED_TOUR_TOOLS
from app.graph.tools.interactive_tools import INTERACTIVE_TOOLS
from app.graph.tools.simulation_tools import SIMULATION_TOOLS
from app.graph.tools.sourcing_tools import SOURCING_TOOLS
from app.graph.tools.visualization_tools import VISUALIZATION_TOOLS
from app.graph.graph import _route_after_router
from app.graph.nodes import (
    _detect_action_plan_request,
    _detect_application_request,
    _detect_carbon_request,
    _detect_credit_request,
    _detect_esg_request,
    _detect_financing_request,
)


def _destination_node(message: str) -> str:
    """Reproduit la décision de routage du router_node (active_module=None).

    Compose les détecteurs explicites comme `router_node`, puis applique la
    priorité de `_route_after_router`. Permet d'asserter le NŒUD de destination
    réel d'un message sans instancier le graphe / la BDD.
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


_CHECKLIST_TOOL_NAMES = {
    "list_applications",
    "get_application_checklist",
    "provide_checklist_document",
    "detach_checklist_document",
    "list_user_documents",
}


def _application_full_catalog():
    """Reproduit le catalogue de visibilité du nœud application (nodes.py)."""
    return (
        list(APPLICATION_TOOLS)
        + list(DOCUMENT_TOOLS)
        + list(INTERACTIVE_TOOLS)
        + list(SOURCING_TOOLS)
        + list(VISUALIZATION_TOOLS)
        + list(SIMULATION_TOOLS)
    )


def _financing_full_catalog():
    """Reproduit le catalogue de visibilité du nœud financing (nodes.py)."""
    return (
        list(FINANCING_TOOLS)
        + [create_fund_application]
        + list(APPLICATION_DISCOVERY_TOOLS)
        + list(DOCUMENT_TOOLS)
        + list(INTERACTIVE_TOOLS)
        + list(GUIDED_TOUR_TOOLS)
        + list(SOURCING_TOOLS)
        + list(VISUALIZATION_TOOLS)
        + list(SIMULATION_TOOLS)
    )


class TestSelectorVisibility:
    """Le sélecteur expose les tools checklist sur application + financing."""

    def test_application_node_exposes_checklist_tools(self):
        selected, debug = select_tools_for_node(
            node_name="application",
            current_page="/applications",
            all_tools=_application_full_catalog(),
        )
        offered = set(debug["tools_offered"])
        assert _CHECKLIST_TOOL_NAMES <= offered, (
            f"Tools manquants sur application : {_CHECKLIST_TOOL_NAMES - offered}"
        )
        # Pas de troncature inattendue (la base doit tenir sous la borne).
        assert debug["truncated"] is False

    def test_financing_node_exposes_checklist_tools(self):
        """« mon dossier GCF » → nœud financing : il doit voir les tools dossier."""
        selected, debug = select_tools_for_node(
            node_name="financing",
            current_page="/applications",
            all_tools=_financing_full_catalog(),
        )
        offered = set(debug["tools_offered"])
        assert _CHECKLIST_TOOL_NAMES <= offered, (
            f"Tools manquants sur financing : {_CHECKLIST_TOOL_NAMES - offered}"
        )
        assert debug["truncated"] is False


class TestToolNodeExecutability:
    """Le graphe compilé EXÉCUTE bien les tools checklist (source de vérité).

    Un tool visible (bind_tools) mais absent du ToolNode ferait halluciner
    « tool indisponible » : on vérifie donc l'exécutabilité réelle, pas seulement
    la reconstruction manuelle des catalogues de visibilité.
    """

    @staticmethod
    def _tool_node_names(node_name: str) -> set[str]:
        from app.graph.graph import build_graph

        graph = build_graph()
        spec = graph.nodes[f"{node_name}_tools"]
        tool_node = getattr(spec, "runnable", spec)
        return set(getattr(tool_node, "tools_by_name", {}).keys())

    def test_application_toolnode_can_execute_checklist_tools(self):
        names = self._tool_node_names("application")
        assert _CHECKLIST_TOOL_NAMES <= names, (
            f"Non exécutables sur application : {_CHECKLIST_TOOL_NAMES - names}"
        )

    def test_financing_toolnode_can_execute_checklist_tools(self):
        names = self._tool_node_names("financing")
        assert _CHECKLIST_TOOL_NAMES <= names, (
            f"Non exécutables sur financing : {_CHECKLIST_TOOL_NAMES - names}"
        )
        # Garde anti-régression : les tools de FINANCING_TOOLS restent exécutables
        # (l'ajout du bundle 049 + DOCUMENT_TOOLS ne doit rien retirer).
        assert {"search_compatible_funds", "get_fund_details"} <= names


class TestRoutingApplicationManagement:
    """Les phrases de gestion de checklist atteignent un nœud CAPABLE."""

    @pytest.mark.parametrize(
        "message",
        [
            "rattache mon RCCM à l'item registre",
            "détache le document de l'item company_registration",
            "où en est mon dossier et que manque-t-il ?",
            "montre-moi la checklist de mon dossier",
            "quels documents manquants pour mon dossier ?",
            "il reste des pièces manquantes ?",
            "montre mes candidatures",
            # « dossier GCF » est happé par l'exclusion project-ESG (bailleur),
            # donc financing est supprimé → application gagne. Le nœud application
            # est capable → le flux fonctionne.
            "où en est mon dossier GCF et que manque-t-il ?",
        ],
    )
    def test_management_phrases_route_to_application(self, message):
        assert _detect_application_request(message) is True
        assert _destination_node(message) == "application"

    def test_candidature_au_fonds_routes_to_financing(self):
        """« candidature au fonds vert » → nœud financing (mot-clé fonds
        prioritaire). Le nœud financing étant désormais CAPABLE (discovery +
        checklist), le flux fonctionne tout de même."""
        msg = "où en est ma candidature au fonds vert ?"
        assert _detect_financing_request(msg) is True
        assert _destination_node(msg) == "financing"

    def test_does_not_hijack_project_document_link(self):
        """« rattacher un document à un projet » NE doit PAS être happé (flux PROJECT)."""
        msg = "rattacher un document à un projet"
        assert _detect_application_request(msg) is False
        assert _destination_node(msg) != "application"
