"""Tests du tool_selector_config pour F06.

Vérifie que les patterns d'URL résolvent correctement et que les mappings
de tools projet sont en place.
"""

from app.graph.tool_selector_config import (
    GLOBAL_WHITELIST,
    MAX_TOOLS_PER_TURN,
    MODULE_TOOL_MAPPING,
    PAGE_TOOL_MAPPING,
    normalize_page,
)


def test_profile_projects_in_page_mapping():
    assert "profile_projects" in PAGE_TOOL_MAPPING
    tools = PAGE_TOOL_MAPPING["profile_projects"]
    assert "list_projects" in tools
    assert "create_project" in tools
    assert "update_project" in tools
    assert "delete_project" in tools
    assert "duplicate_project" in tools
    assert "get_project" in tools
    assert "link_document_to_project" in tools
    # F11 ajoute show_map à la page profile_projects
    assert "show_map" in tools
    # F10 ajoute show_form à la page profile_projects
    assert "show_form" in tools
    assert len(tools) == 9


def test_profile_includes_read_only_project_tools():
    tools = PAGE_TOOL_MAPPING["profile"]
    assert "list_projects" in tools
    assert "get_project" in tools


def test_chat_module_includes_list_projects():
    assert "list_projects" in MODULE_TOOL_MAPPING["chat"]


def test_chat_global_includes_list_projects():
    assert "list_projects" in PAGE_TOOL_MAPPING["chat_global"]


def test_normalize_page_profile_projects():
    assert normalize_page("/profile/projects") == "profile_projects"
    assert normalize_page("/profile/projects/new") == "profile_projects"
    assert normalize_page("/profile/projects/abc-123") == "profile_projects"


def test_normalize_page_profile():
    assert normalize_page("/profile") == "profile"
    assert normalize_page("/profile/company") == "profile"


def test_max_tools_per_turn_respected():
    """Vérifier qu'aucun mapping ne dépasse MAX_TOOLS_PER_TURN."""
    for slug, tools in PAGE_TOOL_MAPPING.items():
        projected = tools | GLOBAL_WHITELIST
        assert len(projected) <= MAX_TOOLS_PER_TURN, (
            f"Page '{slug}' dépasse {MAX_TOOLS_PER_TURN} tools : "
            f"{len(projected)}"
        )
