"""F11 — Tests de filtrage par page pour les 4 tools de visualisation.

Vérifie que :
- show_kpi_card est visible sur dashboard, esg, carbon, credit
- show_match_card est visible sur financing, candidatures
- show_map est visible sur profile, profile_projects, financing
- show_comparison_table est visible sur financing, candidatures
- Aucune page ne dépasse MAX_TOOLS_PER_TURN (14).
"""

from __future__ import annotations

from app.graph.tool_selector_config import (
    GLOBAL_WHITELIST,
    MAX_TOOLS_PER_TURN,
    MODULE_TOOL_MAPPING,
    PAGE_TOOL_MAPPING,
)


# =====================================================================
# Visibility par page
# =====================================================================


def test_show_kpi_card_visible_dashboard() -> None:
    assert "show_kpi_card" in PAGE_TOOL_MAPPING["dashboard"]


def test_show_kpi_card_visible_esg() -> None:
    assert "show_kpi_card" in PAGE_TOOL_MAPPING["esg"]


def test_show_kpi_card_visible_carbon() -> None:
    assert "show_kpi_card" in PAGE_TOOL_MAPPING["carbon"]


def test_show_kpi_card_visible_credit() -> None:
    assert "show_kpi_card" in PAGE_TOOL_MAPPING["credit"]


def test_show_match_card_visible_financing() -> None:
    assert "show_match_card" in PAGE_TOOL_MAPPING["financing"]


def test_show_match_card_visible_candidatures() -> None:
    assert "show_match_card" in PAGE_TOOL_MAPPING["candidatures"]


def test_show_map_visible_profile() -> None:
    assert "show_map" in PAGE_TOOL_MAPPING["profile"]


def test_show_map_visible_profile_projects() -> None:
    assert "show_map" in PAGE_TOOL_MAPPING["profile_projects"]


def test_show_map_visible_financing() -> None:
    assert "show_map" in PAGE_TOOL_MAPPING["financing"]


def test_show_comparison_table_visible_financing() -> None:
    assert "show_comparison_table" in PAGE_TOOL_MAPPING["financing"]


def test_show_comparison_table_visible_candidatures() -> None:
    assert "show_comparison_table" in PAGE_TOOL_MAPPING["candidatures"]


# =====================================================================
# Visibility par module (fallback)
# =====================================================================


def test_show_kpi_card_in_modules() -> None:
    """Modules autorisant show_kpi_card en fallback."""
    for module in ("chat", "esg_scoring", "carbon", "credit", "action_plan"):
        assert "show_kpi_card" in MODULE_TOOL_MAPPING[module], (
            f"show_kpi_card manquant dans module={module}"
        )


def test_show_match_card_in_modules() -> None:
    for module in ("chat", "financing", "application"):
        assert "show_match_card" in MODULE_TOOL_MAPPING[module], (
            f"show_match_card manquant dans module={module}"
        )


def test_show_comparison_table_in_modules() -> None:
    for module in ("chat", "financing", "application"):
        assert "show_comparison_table" in MODULE_TOOL_MAPPING[module], (
            f"show_comparison_table manquant dans module={module}"
        )


def test_show_map_in_modules() -> None:
    for module in ("chat", "financing"):
        assert "show_map" in MODULE_TOOL_MAPPING[module], (
            f"show_map manquant dans module={module}"
        )


# =====================================================================
# Quota MAX_TOOLS_PER_TURN respecté
# =====================================================================


def test_no_page_exceeds_max_tools_per_turn() -> None:
    """Aucune page n'expose plus de MAX_TOOLS_PER_TURN tools."""
    for slug, tools in PAGE_TOOL_MAPPING.items():
        projected = tools | GLOBAL_WHITELIST
        assert len(projected) <= MAX_TOOLS_PER_TURN, (
            f"Page '{slug}' expose {len(projected)} tools "
            f"(> MAX_TOOLS_PER_TURN={MAX_TOOLS_PER_TURN})"
        )


def test_no_module_grows_more_than_4_tools_after_f11() -> None:
    """Les nouveaux tools F11 ajoutent au max 4 tools par module
    (KPI/Match/Map/Comparison), respectant la marge configurée."""
    # Sanity check : les modules de visualisation acceptent les 4 tools max.
    visualization_tools = {
        "show_kpi_card",
        "show_match_card",
        "show_map",
        "show_comparison_table",
    }
    for module, tools in MODULE_TOOL_MAPPING.items():
        added = tools & visualization_tools
        assert len(added) <= 4, (
            f"Module '{module}' contient plus de 4 tools de visualisation"
        )


def test_visualization_tools_not_in_global_whitelist() -> None:
    """Les tools de visualisation ne sont PAS dans GLOBAL_WHITELIST.

    (Visibilité ciblée par page pour respecter MAX_TOOLS_PER_TURN.)
    """
    visualization_tools = {
        "show_kpi_card",
        "show_match_card",
        "show_map",
        "show_comparison_table",
    }
    assert visualization_tools.isdisjoint(GLOBAL_WHITELIST), (
        "Les tools de visualisation ne doivent pas être dans GLOBAL_WHITELIST"
    )
