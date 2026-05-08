"""F15 BUG-003 — Garde-fou : un seul tool ``create_fund_application``.

L'orchestration LangGraph requiert des noms de tools uniques. Avant F15,
``create_fund_application`` existait à la fois dans ``application_tools``
et ``financing_tools``, ce qui rendait l'orchestration imprévisible.

Ce test bloque toute régression : la fonction doit être exportée par
``application_tools`` uniquement, et son nom ne doit apparaître qu'une
fois dans la concaténation des groupes de tools.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_create_fund_application_single_definition() -> None:
    """Le tool est défini une seule fois (dans application_tools)."""
    from app.graph.tools.application_tools import APPLICATION_TOOLS
    from app.graph.tools.financing_tools import FINANCING_TOOLS

    app_names = [t.name for t in APPLICATION_TOOLS]
    fin_names = [t.name for t in FINANCING_TOOLS]

    assert app_names.count("create_fund_application") == 1, (
        "create_fund_application doit être déclaré exactement une fois "
        "dans APPLICATION_TOOLS"
    )
    assert fin_names.count("create_fund_application") == 0, (
        "F15 BUG-003 : create_fund_application a été retiré de "
        "FINANCING_TOOLS pour éviter le doublon avec application_tools"
    )


def test_create_fund_application_not_exported_from_financing_module() -> None:
    """L'import direct depuis ``financing_tools`` doit échouer."""
    import app.graph.tools.financing_tools as fin_mod

    assert not hasattr(fin_mod, "create_fund_application"), (
        "F15 BUG-003 : la fonction ne doit plus être exportée depuis "
        "le module financing_tools"
    )


def test_unique_tool_name_across_groups() -> None:
    """Aucun nom de tool n'apparaît plus d'une fois sur l'ensemble des groupes."""
    from app.graph.tools.application_tools import APPLICATION_TOOLS
    from app.graph.tools.financing_tools import FINANCING_TOOLS

    all_names = [t.name for t in APPLICATION_TOOLS + FINANCING_TOOLS]
    duplicates = {n for n in all_names if all_names.count(n) > 1}
    assert duplicates == set(), (
        f"Doublons détectés entre APPLICATION_TOOLS et FINANCING_TOOLS : "
        f"{duplicates}"
    )
