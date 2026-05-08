"""F15 — Garde-fou : aucun tool LLM ne mute ``TemplateDossier``.

Le catalogue Templates est admin-only ; tout tool LangChain dont le
nom matche ``^(create|update|delete|publish|unpublish)_template$``
serait une violation de cette règle.
"""

from __future__ import annotations

import re

import pytest

pytestmark = pytest.mark.unit

_FORBIDDEN = re.compile(r"^(create|update|delete|publish|unpublish)_template(s|_dossier)?$")


def test_no_template_mutation_tool() -> None:
    """Aucun tool exposé au LLM ne doit pouvoir muter Templates."""
    from app.graph.tools.action_plan_tools import ACTION_PLAN_TOOLS
    from app.graph.tools.application_tools import APPLICATION_TOOLS
    from app.graph.tools.carbon_tools import CARBON_TOOLS
    from app.graph.tools.chat_tools import CHAT_TOOLS
    from app.graph.tools.credit_tools import CREDIT_TOOLS
    from app.graph.tools.document_tools import DOCUMENT_TOOLS
    from app.graph.tools.esg_tools import ESG_TOOLS
    from app.graph.tools.financing_tools import FINANCING_TOOLS
    from app.graph.tools.profiling_tools import PROFILING_TOOLS
    from app.graph.tools.project_tools import PROJECT_TOOLS
    from app.graph.tools.template_tools import TEMPLATE_TOOLS

    all_tools = (
        ACTION_PLAN_TOOLS
        + APPLICATION_TOOLS
        + CARBON_TOOLS
        + CHAT_TOOLS
        + CREDIT_TOOLS
        + DOCUMENT_TOOLS
        + ESG_TOOLS
        + FINANCING_TOOLS
        + PROFILING_TOOLS
        + PROJECT_TOOLS
        + TEMPLATE_TOOLS
    )

    violations = [t.name for t in all_tools if _FORBIDDEN.match(t.name)]
    assert violations == [], (
        f"F15 conformity violation : tools de mutation Template détectés : "
        f"{violations}. Le catalogue Templates est admin-only."
    )


def test_template_tools_are_read_only() -> None:
    """Les noms des TEMPLATE_TOOLS sont en lecture seule (list/get/...)."""
    from app.graph.tools.template_tools import TEMPLATE_TOOLS

    names = {t.name for t in TEMPLATE_TOOLS}
    assert names == {"list_templates", "get_effective_template"}
