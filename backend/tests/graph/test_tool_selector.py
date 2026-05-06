"""Tests unitaires du selecteur de tools par contexte de page (story 10.2)."""

from __future__ import annotations

import pytest

from app.graph.tool_selector import select_tools_for_node
from app.graph.tool_selector_config import (
    GLOBAL_WHITELIST,
    MAX_TOOLS_PER_TURN,
    MODULE_TOOL_MAPPING,
    PAGE_TOOL_MAPPING,
    normalize_page,
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
    """Catalogue complet des tools du backend (union de toutes les listes)."""
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


# ---------------------------------------------------------------------------
# Selection par page (5 pages testees)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("page_slug,node_name", [
    ("profile", "chat"),
    ("esg", "esg_scoring"),
    ("carbon", "carbon"),
    ("financing", "financing"),
    ("candidatures", "application"),
])
def test_select_tools_by_page_exact_match(page_slug: str, node_name: str) -> None:
    """Pour une page connue, la liste retournee doit etre exactement
    PAGE_TOOL_MAPPING[slug] inter available_tools, plus la GLOBAL_WHITELIST.
    Couvre des combinaisons (page, node_name) reelles pour eviter de masquer
    le fallback module-level."""
    all_tools = _all_tools()
    available_names = {t.name for t in all_tools}

    selected, debug = select_tools_for_node(
        node_name=node_name,
        current_page=page_slug,
        all_tools=all_tools,
    )

    expected = (PAGE_TOOL_MAPPING[page_slug] | GLOBAL_WHITELIST) & available_names
    actual = {t.name for t in selected}

    assert actual == expected, f"Page {page_slug}: attendu {expected}, recu {actual}"
    assert debug["page_slug"] == page_slug
    assert debug["fallback_used"] is False
    assert debug["truncated"] is False
    assert debug["tools_offered"] == [t.name for t in selected]


def test_select_tools_fallback_when_page_none() -> None:
    all_tools = _all_tools()
    available_names = {t.name for t in all_tools}

    selected, debug = select_tools_for_node(
        node_name="esg_scoring",
        current_page=None,
        all_tools=all_tools,
    )

    expected = (MODULE_TOOL_MAPPING["esg_scoring"] | GLOBAL_WHITELIST) & available_names
    actual = {t.name for t in selected}

    assert actual == expected
    assert debug["page_slug"] is None
    assert debug["fallback_used"] is True


def test_select_tools_fallback_when_page_unknown() -> None:
    all_tools = _all_tools()
    available_names = {t.name for t in all_tools}

    selected, debug = select_tools_for_node(
        node_name="financing",
        current_page="/route_inexistante",
        all_tools=all_tools,
    )

    expected = (MODULE_TOOL_MAPPING["financing"] | GLOBAL_WHITELIST) & available_names
    actual = {t.name for t in selected}

    assert actual == expected
    assert debug["page_slug"] is None
    assert debug["fallback_used"] is True


def test_invariant_max_tools_per_turn_for_all_pages() -> None:
    """Aucune page configuree ne doit depasser MAX_TOOLS_PER_TURN."""
    for slug, tools in PAGE_TOOL_MAPPING.items():
        projected = tools | GLOBAL_WHITELIST
        assert len(projected) <= MAX_TOOLS_PER_TURN, (
            f"Page '{slug}' configuree avec {len(projected)} tools "
            f"(>{MAX_TOOLS_PER_TURN}). Reduire le mapping."
        )


def test_select_tools_runtime_invariant_le_10() -> None:
    all_tools = _all_tools()
    for slug in PAGE_TOOL_MAPPING:
        selected, _debug = select_tools_for_node(
            node_name="chat",
            current_page=slug,
            all_tools=all_tools,
        )
        assert len(selected) <= MAX_TOOLS_PER_TURN


def test_select_tools_resolves_path_to_slug() -> None:
    all_tools = _all_tools()
    selected_path, debug_path = select_tools_for_node(
        node_name="esg_scoring",
        current_page="/esg/results",
        all_tools=all_tools,
    )
    selected_slug, _ = select_tools_for_node(
        node_name="esg_scoring",
        current_page="esg",
        all_tools=all_tools,
    )

    assert {t.name for t in selected_path} == {t.name for t in selected_slug}
    assert debug_path["page_slug"] == "esg"
    assert debug_path["fallback_used"] is False


def test_select_tools_returns_basetools_not_just_names() -> None:
    all_tools = _all_tools()
    selected, _ = select_tools_for_node(
        node_name="chat",
        current_page="/profile",
        all_tools=all_tools,
    )
    for tool in selected:
        assert hasattr(tool, "name")
        assert hasattr(tool, "invoke") or hasattr(tool, "ainvoke")


def test_select_tools_active_entities_ignored_v1() -> None:
    """En V1, active_entities est accepte mais ignore."""
    all_tools = _all_tools()
    selected_a, _ = select_tools_for_node(
        node_name="chat",
        current_page="esg",
        all_tools=all_tools,
        active_entities=None,
    )
    selected_b, _ = select_tools_for_node(
        node_name="chat",
        current_page="esg",
        all_tools=all_tools,
        active_entities={"company_id": "abc", "assessment_id": "xyz"},
    )
    assert {t.name for t in selected_a} == {t.name for t in selected_b}


def test_select_tools_truncation_on_oversized_catalog(monkeypatch) -> None:
    """Quand un mapping configure plus de MAX_TOOLS_PER_TURN tools,
    `select_tools_for_node` tronque deterministiquement et signale
    `truncated=True`."""
    from langchain_core.tools import StructuredTool

    from app.graph import tool_selector_config as cfg

    # Catalogue synthetique de 15 tools fictifs (echo).
    fake_tools = [
        StructuredTool.from_function(
            func=lambda x=i: x,  # noqa: ARG005
            name=f"fake_tool_{i:02d}",
            description=f"fake tool {i}",
        )
        for i in range(15)
    ]
    fake_names = frozenset(t.name for t in fake_tools)

    # Patch d'une page existante avec ce catalogue surdimensionne.
    patched_mapping = {**cfg.PAGE_TOOL_MAPPING, "chat_global": fake_names}
    monkeypatch.setattr(cfg, "PAGE_TOOL_MAPPING", patched_mapping)
    # Selecteur lit la valeur courante via le module — re-import dynamique.
    monkeypatch.setattr(
        "app.graph.tool_selector.PAGE_TOOL_MAPPING", patched_mapping
    )

    selected, debug = select_tools_for_node(
        node_name="chat",
        current_page="chat_global",
        all_tools=fake_tools,
    )

    assert debug["truncated"] is True
    assert len(selected) == cfg.MAX_TOOLS_PER_TURN
    # Determinisme : les 10 retenus sont les 10 premiers en ordre alphabetique
    # des noms (preservant la whitelist si presente — ici aucune).
    expected = sorted(t.name for t in fake_tools)[: cfg.MAX_TOOLS_PER_TURN]
    assert [t.name for t in selected] == expected


def test_select_tools_filters_unavailable_tools() -> None:
    selected, _ = select_tools_for_node(
        node_name="esg_scoring",
        current_page="esg",
        all_tools=INTERACTIVE_TOOLS,
    )
    names = {t.name for t in selected}
    assert names <= {"ask_interactive_question"}


# ---------------------------------------------------------------------------
# Normalisation des paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path,expected_slug", [
    ("/esg/results", "esg"),
    ("/esg", "esg"),
    ("/dashboard", "dashboard"),
    ("/financing/abc-123", "financing"),
    ("/applications", "candidatures"),
    ("/applications/42", "candidatures"),
    ("/credit-score", "credit"),
    ("/action-plan", "action_plan"),
    ("/profile", "profile"),
    ("/", "chat_global"),
    ("/carbon/results", "carbon"),
    ("/documents", "documents"),
    ("/reports", "reports"),
])
def test_normalize_page_path_to_slug(path: str, expected_slug: str) -> None:
    assert normalize_page(path) == expected_slug


@pytest.mark.parametrize("value", [None, "", "  ", "/route_inexistante", "/foo/bar"])
def test_normalize_page_returns_none_for_unknown(value: str | None) -> None:
    assert normalize_page(value) is None


def test_normalize_page_passthrough_known_slug() -> None:
    for slug in PAGE_TOOL_MAPPING:
        assert normalize_page(slug) == slug


# ---------------------------------------------------------------------------
# Sanity checks de configuration
# ---------------------------------------------------------------------------


def test_module_tool_mapping_keys_are_valid_node_names() -> None:
    expected = {"chat", "esg_scoring", "carbon", "financing",
                "application", "credit", "action_plan", "document"}
    assert set(MODULE_TOOL_MAPPING.keys()) <= expected


def test_global_whitelist_is_frozenset() -> None:
    assert isinstance(GLOBAL_WHITELIST, frozenset)
    # F01 ajoute les sourcing tools en GLOBAL_WHITELIST.
    assert GLOBAL_WHITELIST == frozenset({
        "ask_interactive_question",
        "trigger_guided_tour",
        "cite_source",
        "search_source",
        "flag_unsourced",
    })


def test_page_tool_mapping_covers_required_slugs() -> None:
    """Epic M10 — 8 slugs minimum."""
    required = {"profile", "candidatures", "chat_global", "esg",
                "carbon", "financing", "dashboard", "action_plan"}
    assert required <= set(PAGE_TOOL_MAPPING.keys())
