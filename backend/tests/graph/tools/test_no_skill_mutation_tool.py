"""F23 — Conformity test : aucun tool LLM ne mute la table ``skills`` (T018, US6).

Garde-fou : si un futur dev ajoute par mégarde un tool ``create_skill``,
``update_skill``, ``delete_skill`` ou ``publish_skill`` exposé au LLM, ce
test échoue immédiatement et bloque le merge.

Référence : ``specs/033-skills-playbooks-metier/spec.md`` US6.
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
from app.graph.tools.sourcing_tools import SOURCING_TOOLS
from app.graph.tools.visualization_tools import VISUALIZATION_TOOLS


# Pattern interdit : (create|update|delete|publish|unpublish)_skill[s]?
FORBIDDEN_PATTERN = re.compile(
    r"^(create|update|delete|publish|unpublish)_skill",
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
    "SOURCING_TOOLS": SOURCING_TOOLS,
    "VISUALIZATION_TOOLS": VISUALIZATION_TOOLS,
}


class TestNoSkillMutationTool:
    """Aucun tool exposé au LLM ne doit pouvoir muter Skills."""

    @pytest.mark.parametrize("group_name,tool_list", list(ALL_TOOL_GROUPS.items()))
    def test_group_has_no_skill_mutation_tool(
        self,
        group_name: str,
        tool_list: list,
    ) -> None:
        """Vérifie pour chaque groupe que le pattern interdit n'apparaît pas."""
        offenders = []
        for tool in tool_list:
            tool_name = getattr(tool, "name", None) or getattr(
                tool, "__name__", str(tool)
            )
            if FORBIDDEN_PATTERN.match(tool_name):
                offenders.append(tool_name)
        assert offenders == [], (
            f"Groupe {group_name} expose des tools mutants Skills : {offenders}. "
            "Les Skills ne doivent JAMAIS être mutées par le LLM (US6)."
        )

    def test_pattern_correctly_detects_a_fake_offender(self) -> None:
        """Sanity check : le regex matche bien un tool create_skill simulé."""
        fake_tool = type("FakeTool", (), {"name": "create_skill"})()
        assert FORBIDDEN_PATTERN.match(fake_tool.name) is not None

    def test_pattern_does_not_match_legitimate_names(self) -> None:
        """Sanity check : le regex ne matche pas des noms légitimes."""
        for legit in (
            "create_fund_application",
            "update_company_profile",
            "publish_report",  # publish_report n'est pas publish_skill
            "delete_carbon_entry",
        ):
            # publish_report ne doit pas matcher car il n'est pas suivi de "skill"
            assert FORBIDDEN_PATTERN.match(legit) is None, legit
