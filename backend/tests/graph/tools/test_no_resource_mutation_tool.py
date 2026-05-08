"""F20 — Conformity test : aucun tool LLM ne mute la table ``resources``.

Garde-fou : si un futur dev ajoute un tool ``create_resource``, ``update_resource``,
``delete_resource``, ``publish_resource``, ``archive_resource``, ce test échoue.

Pattern identique à F23 (test_no_skill_mutation_tool.py).
"""

from __future__ import annotations

import re

import pytest

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
from app.graph.tools.memory_tools import MEMORY_TOOLS
from app.graph.tools.profiling_tools import PROFILING_TOOLS
from app.graph.tools.project_tools import PROJECT_TOOLS
from app.graph.tools.resource_tools import RESOURCE_TOOLS
from app.graph.tools.sourcing_tools import SOURCING_TOOLS
from app.graph.tools.visualization_tools import VISUALIZATION_TOOLS


# Pattern interdit : (create|update|delete|publish|unpublish|archive)_resource[s]?
FORBIDDEN_PATTERN = re.compile(
    r"^(create|update|delete|publish|unpublish|archive)_resource",
    re.IGNORECASE,
)


ALL_TOOL_GROUPS: dict[str, list] = {
    "ACTION_PLAN_TOOLS": ACTION_PLAN_TOOLS,
    "APPLICATION_TOOLS": APPLICATION_TOOLS,
    "CARBON_TOOLS": CARBON_TOOLS,
    "CHAT_TOOLS": CHAT_TOOLS,
    "CREDIT_TOOLS": CREDIT_TOOLS,
    "DOCUMENT_TOOLS": DOCUMENT_TOOLS,
    "ESG_TOOLS": ESG_TOOLS,
    "FINANCING_TOOLS": FINANCING_TOOLS,
    "GUIDED_TOUR_TOOLS": GUIDED_TOUR_TOOLS,
    "INTERACTIVE_TOOLS": INTERACTIVE_TOOLS,
    "MEMORY_TOOLS": MEMORY_TOOLS,
    "PROFILING_TOOLS": PROFILING_TOOLS,
    "PROJECT_TOOLS": PROJECT_TOOLS,
    "RESOURCE_TOOLS": RESOURCE_TOOLS,
    "SOURCING_TOOLS": SOURCING_TOOLS,
    "VISUALIZATION_TOOLS": VISUALIZATION_TOOLS,
}


class TestNoResourceMutationTool:
    """Aucun tool exposé au LLM ne doit pouvoir muter Resources (FR-022, SC-007)."""

    @pytest.mark.parametrize("group_name,tool_list", list(ALL_TOOL_GROUPS.items()))
    def test_group_has_no_resource_mutation_tool(
        self, group_name: str, tool_list: list
    ) -> None:
        offenders = []
        for t in tool_list:
            tool_name = getattr(t, "name", None) or getattr(t, "__name__", str(t))
            if FORBIDDEN_PATTERN.match(tool_name):
                offenders.append(tool_name)
        assert offenders == [], (
            f"Groupe {group_name} expose des tools mutants Resources : {offenders}. "
            "Les Resources ne doivent JAMAIS être mutées par le LLM (FR-022)."
        )

    def test_pattern_correctly_detects_a_fake_offender(self) -> None:
        fake_tool = type("FakeTool", (), {"name": "create_resource"})()
        assert FORBIDDEN_PATTERN.match(fake_tool.name) is not None

    def test_pattern_does_not_match_legitimate_names(self) -> None:
        for legit in (
            "create_fund_application",
            "search_resources",
            "get_resource_content",
            "recommend_resources_for_user",
            "publish_report",
        ):
            assert FORBIDDEN_PATTERN.match(legit) is None, legit
