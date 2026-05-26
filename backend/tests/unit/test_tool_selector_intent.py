"""T005 (F048 US1) — Sélecteur de tools piloté par l'intention (D1).

Réf. contracts/tool-selector.md (cas T1–T7).

Après refactor, ``select_tools_for_node`` doit UNIR les tools du nœud
LangGraph (= intention routée par F013) aux tools de la page, plus la
``GLOBAL_WHITELIST`` — de sorte que ``create_fund_application`` survive dès que
le routeur route vers ``application``/``financing``, quelle que soit la page.
"""

from __future__ import annotations

import pytest

from app.graph.tool_selector import select_tools_for_node
from app.graph.tool_selector_config import (
    GLOBAL_WHITELIST,
    MAX_TOOLS_PER_TURN,
    MODULE_TOOL_MAPPING,
)
from app.graph.tools.action_plan_tools import ACTION_PLAN_TOOLS
from app.graph.tools.application_tools import APPLICATION_TOOLS
from app.graph.tools.carbon_tools import CARBON_TOOLS
from app.graph.tools.chat_tools import CHAT_TOOLS
from app.graph.tools.credit_tools import CREDIT_TOOLS
from app.graph.tools.document_tools import DOCUMENT_TOOLS
from app.graph.tools.esg_tools import ESG_TOOLS
from app.graph.tools.financing_tools import FINANCING_TOOLS
from app.graph.tools.guided_tour_tools import GUIDED_TOUR_TOOLS
from app.graph.tools.interactive_tools import INTERACTIVE_TOOLS
from app.graph.tools.profiling_tools import PROFILING_TOOLS

pytestmark = pytest.mark.unit


def _all_tools() -> list:
    return (
        PROFILING_TOOLS
        + ESG_TOOLS
        + CARBON_TOOLS
        + FINANCING_TOOLS
        + APPLICATION_TOOLS
        + CREDIT_TOOLS
        + ACTION_PLAN_TOOLS
        + CHAT_TOOLS
        + DOCUMENT_TOOLS
        + INTERACTIVE_TOOLS
        + GUIDED_TOUR_TOOLS
    )


def _names(selected) -> set[str]:
    return {t.name for t in selected}


# --- T1 : régression du bug principal -------------------------------------


def test_t1_application_node_on_documents_page_exposes_create_fund_application() -> None:
    """node=application + page=/documents → create_fund_application présent."""
    selected, debug = select_tools_for_node(
        node_name="application",
        current_page="/documents",
        all_tools=_all_tools(),
    )
    assert "create_fund_application" in _names(selected)
    assert debug.get("node_tools_included") is True


def test_t2_financing_node_on_dashboard_exposes_create_fund_application() -> None:
    """node=financing + page=/dashboard → create_fund_application présent."""
    selected, _ = select_tools_for_node(
        node_name="financing",
        current_page="/dashboard",
        all_tools=_all_tools(),
    )
    assert "create_fund_application" in _names(selected)


def test_t3_chat_node_on_financing_page_keeps_page_tools() -> None:
    """node=chat + page=/financing → tools de page financing présents (pas de régression)."""
    selected, _ = select_tools_for_node(
        node_name="chat",
        current_page="/financing",
        all_tools=_all_tools(),
    )
    names = _names(selected)
    assert "search_compatible_funds" in names
    assert "create_fund_application" in names


def test_t4_application_node_on_applications_page_within_budget() -> None:
    """node=application + page=/applications → ≤ MAX_TOOLS_PER_TURN."""
    selected, _ = select_tools_for_node(
        node_name="application",
        current_page="/applications",
        all_tools=_all_tools(),
    )
    assert len(selected) <= MAX_TOOLS_PER_TURN


def test_t5_esg_node_tools_present_despite_documents_slug() -> None:
    """node=esg_scoring + page=/documents → tools ESG du nœud présents."""
    selected, _ = select_tools_for_node(
        node_name="esg_scoring",
        current_page="/documents",
        all_tools=_all_tools(),
    )
    names = _names(selected)
    esg_node_tools = MODULE_TOOL_MAPPING["esg_scoring"]
    available = {t.name for t in _all_tools()}
    expected = esg_node_tools & available
    assert expected, "le mapping esg_scoring doit exposer au moins un tool dispo"
    assert expected <= names


@pytest.mark.parametrize(
    "node_name,page",
    [
        ("application", "/documents"),
        ("financing", "/dashboard"),
        ("chat", "/financing"),
        ("esg_scoring", "/documents"),
        ("application", "/applications"),
        ("chat", None),
    ],
)
def test_t6_invariants_budget_and_whitelist(node_name: str, page: str | None) -> None:
    """Pour toute combinaison : ≤ borne ET GLOBAL_WHITELIST ⊆ selected."""
    all_tools = _all_tools()
    available = {t.name for t in all_tools}
    selected, _ = select_tools_for_node(
        node_name=node_name, current_page=page, all_tools=all_tools,
    )
    names = _names(selected)
    assert len(selected) <= MAX_TOOLS_PER_TURN
    assert (GLOBAL_WHITELIST & available) <= names


def test_t7_truncation_keeps_node_tools_before_page_tools(monkeypatch) -> None:
    """Troncature forcée : les tools du nœud sont conservés avant ceux de page."""
    from langchain_core.tools import StructuredTool

    from app.graph import tool_selector as selector
    from app.graph import tool_selector_config as cfg

    # Tools fictifs : un lot "node" et un lot "page", chacun dépassant la moitié
    # de la borne pour forcer la troncature de la base unie.
    n = cfg.MAX_TOOLS_PER_TURN
    node_names = frozenset(f"node_tool_{i:02d}" for i in range(n))
    page_names = frozenset(f"page_tool_{i:02d}" for i in range(n))
    fake_tools = [
        StructuredTool.from_function(
            func=lambda x=name: x, name=name, description=name,  # noqa: ARG005
        )
        for name in (sorted(node_names) + sorted(page_names))
    ]

    patched_module = {**cfg.MODULE_TOOL_MAPPING, "application": node_names}
    patched_page = {**cfg.PAGE_TOOL_MAPPING, "documents": page_names}
    monkeypatch.setattr(selector, "MODULE_TOOL_MAPPING", patched_module)
    monkeypatch.setattr(selector, "PAGE_TOOL_MAPPING", patched_page)

    selected, debug = select_tools_for_node(
        node_name="application",
        current_page="documents",
        all_tools=fake_tools,
    )
    names = _names(selected)
    assert debug["truncated"] is True
    assert len(selected) <= cfg.MAX_TOOLS_PER_TURN
    # Priorité : aucun tool de page ne doit survivre tant que des tools de
    # nœud sont évincés (les tools du nœud passent avant ceux de page).
    kept_page = names & page_names
    kept_node = names & node_names
    if kept_page:
        assert kept_node == node_names, (
            "des tools de page sont conservés alors que des tools de nœud "
            "sont évincés — la priorité nœud > page n'est pas respectée"
        )
