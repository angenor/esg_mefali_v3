"""Tests TDD F22 — vérification que les 11 tools de mutation critique sont
décorés ``@with_retry(fallback_message=...)``.

Réf : ``specs/032-decision-tree-with-retry-eval/spec.md`` FR-004.
"""

from __future__ import annotations

import pytest

# Import direct des tools concernés
from app.graph.tools.action_plan_tools import generate_action_plan, update_action_item
from app.graph.tools.application_tools import create_fund_application
from app.graph.tools.carbon_tools import finalize_carbon_assessment
from app.graph.tools.credit_tools import generate_credit_certificate, generate_credit_score
from app.graph.tools.esg_tools import batch_save_esg_criteria, finalize_esg_assessment
from app.graph.tools.profiling_tools import update_company_profile
from app.graph.tools.project_tools import delete_project, update_project


pytestmark = pytest.mark.unit


# ─── 1. Liste des 11 tools attendus ─────────────────────────────────────────


CRITICAL_MUTATION_TOOLS = [
    update_company_profile,
    batch_save_esg_criteria,
    finalize_esg_assessment,
    finalize_carbon_assessment,
    create_fund_application,
    generate_credit_score,
    generate_credit_certificate,
    generate_action_plan,
    update_action_item,
    update_project,
    delete_project,
]


def _underlying_callable(tool_obj):
    """Retourne la fonction Python réelle derrière un ``@tool`` LangChain.

    Nécessaire car ``@tool`` enrobe la fonction dans un ``StructuredTool`` ;
    on accède au call interne via ``coroutine`` ou ``func``.
    """
    return getattr(tool_obj, "coroutine", None) or getattr(tool_obj, "func", None)


# ─── 2. Décorateur appliqué ─────────────────────────────────────────────────


@pytest.mark.parametrize("tool", CRITICAL_MUTATION_TOOLS, ids=lambda t: t.name)
def test_critical_tool_is_wrapped_with_retry(tool) -> None:
    """Chaque tool critique doit être enveloppé par with_retry.

    Détection : le wrapper ``with_retry`` ajoute un attribut ``__wrapped__``
    grâce à ``functools.wraps`` ; sinon on inspecte la closure.
    """
    underlying = _underlying_callable(tool)
    assert underlying is not None, (
        f"{tool.name}: impossible de récupérer la fonction sous-jacente"
    )
    # functools.wraps préserve __wrapped__ → indicateur fiable du décorateur.
    assert hasattr(underlying, "__wrapped__"), (
        f"{tool.name}: doit être décoré @with_retry (attribut __wrapped__ manquant)"
    )


# ─── 3. fallback_message non vide ───────────────────────────────────────────


@pytest.mark.parametrize("tool", CRITICAL_MUTATION_TOOLS, ids=lambda t: t.name)
def test_critical_tool_has_non_empty_fallback_message(tool) -> None:
    """Le décorateur doit fixer un fallback_message non vide pour les mutations.

    On vérifie indirectement que le tool retourne bien le format JSON
    structuré (cf. test plus poussé end-to-end ailleurs).
    """
    underlying = _underlying_callable(tool)
    assert underlying is not None
    # Closure introspection : la fonction wrapper référence ``fallback_message``.
    closure_vars = underlying.__closure__ or ()
    free_vars = underlying.__code__.co_freevars
    # `fallback_message` doit être nommé parmi les freevars + valoir str non vide.
    if "fallback_message" not in free_vars:
        pytest.fail(
            f"{tool.name}: fallback_message absent des freevars de with_retry"
        )
    idx = free_vars.index("fallback_message")
    cell_value = closure_vars[idx].cell_contents
    assert isinstance(cell_value, str) and cell_value.strip(), (
        f"{tool.name}: fallback_message doit être une chaîne non vide, "
        f"got {cell_value!r}"
    )
