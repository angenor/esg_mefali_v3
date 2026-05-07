"""F11 — Test consolidé du golden set de questions de visualisation.

Approche : on ne mocke pas le LLM (coûteux et fragile dans la CI). Le test
vérifie la cohérence formelle du fichier golden set et que les schémas
Pydantic peuvent valider les `expected_min_args` listés (consistance entre
spec et schémas).

La validation runtime (LLM réel) sera vérifiée manuellement post-merge
avec un golden set étendu (cf. SC-001/002/003 ≥ 90 %).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


GOLDEN_SET_PATH = (
    Path(__file__).parent / "fixtures" / "visualization_golden_set.json"
)

EXPECTED_TOOLS_BY_CATEGORY = {
    "kpi": "show_kpi_card",
    "match": "show_match_card",
    "comparison": "show_comparison_table",
    "map": "show_map",
    "fallback_text": None,
}


def _load_golden_set() -> dict[str, Any]:
    return json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))


def test_golden_set_file_exists() -> None:
    """Le fichier golden set est présent et lisible."""
    assert GOLDEN_SET_PATH.exists(), f"Golden set manquant : {GOLDEN_SET_PATH}"


def test_golden_set_has_kpi_count() -> None:
    """Au moins 10 questions KPI (SC-001)."""
    data = _load_golden_set()
    kpi_count = sum(
        1 for q in data["questions"] if q["category"] == "kpi"
    )
    assert kpi_count >= 10, f"Trop peu de questions KPI : {kpi_count}"


def test_golden_set_has_match_count() -> None:
    """Au moins 5 questions match (SC-002)."""
    data = _load_golden_set()
    match_count = sum(
        1 for q in data["questions"] if q["category"] == "match"
    )
    assert match_count >= 5, f"Trop peu de questions match : {match_count}"


def test_golden_set_has_comparison_count() -> None:
    """Au moins 3 questions comparison (SC-003)."""
    data = _load_golden_set()
    comp_count = sum(
        1 for q in data["questions"] if q["category"] == "comparison"
    )
    assert comp_count >= 3, f"Trop peu de questions comparison : {comp_count}"


def test_golden_set_has_map_question() -> None:
    """Au moins 1 question map."""
    data = _load_golden_set()
    map_count = sum(
        1 for q in data["questions"] if q["category"] == "map"
    )
    assert map_count >= 1, f"Pas de question map dans le golden set"


def test_golden_set_has_fallback_questions() -> None:
    """Au moins 2 questions floues (fallback texte)."""
    data = _load_golden_set()
    fb_count = sum(
        1 for q in data["questions"] if q["category"] == "fallback_text"
    )
    assert fb_count >= 2, f"Trop peu de questions fallback : {fb_count}"


def test_each_question_has_required_fields() -> None:
    """Chaque question a id / user_message / expected_tool / context_page / category."""
    data = _load_golden_set()
    required = {
        "id",
        "user_message",
        "expected_tool",
        "context_page",
        "category",
        "expected_min_args",
    }
    for q in data["questions"]:
        missing = required - q.keys()
        assert not missing, f"Question {q.get('id', '?')} manque {missing}"


def test_each_question_category_matches_tool() -> None:
    """expected_tool de chaque question correspond à la category."""
    data = _load_golden_set()
    for q in data["questions"]:
        cat = q["category"]
        expected = EXPECTED_TOOLS_BY_CATEGORY.get(cat)
        assert q["expected_tool"] == expected, (
            f"Question {q['id']} : catégorie={cat}, "
            f"expected_tool={q['expected_tool']}, attendu={expected}"
        )


def test_question_ids_unique() -> None:
    data = _load_golden_set()
    ids = [q["id"] for q in data["questions"]]
    assert len(ids) == len(set(ids)), "Doublons dans les ids golden set"


def test_kpi_questions_match_kpicard_schema() -> None:
    """Les expected_min_args des questions KPI sont des champs valides KPICardArgs."""
    from app.schemas.visualization import KPICardArgs

    data = _load_golden_set()
    valid_fields = set(KPICardArgs.model_fields.keys())
    for q in data["questions"]:
        if q["category"] != "kpi":
            continue
        for arg in q["expected_min_args"]:
            assert arg in valid_fields, (
                f"Question {q['id']} : champ '{arg}' inconnu de KPICardArgs"
            )


def test_match_questions_match_schema() -> None:
    from app.schemas.visualization import MatchCardArgs

    data = _load_golden_set()
    valid_fields = set(MatchCardArgs.model_fields.keys())
    for q in data["questions"]:
        if q["category"] != "match":
            continue
        for arg in q["expected_min_args"]:
            assert arg in valid_fields, (
                f"Question {q['id']} : champ '{arg}' inconnu de MatchCardArgs"
            )


def test_comparison_questions_match_schema() -> None:
    from app.schemas.visualization import ComparisonTableArgs

    data = _load_golden_set()
    valid_fields = set(ComparisonTableArgs.model_fields.keys())
    for q in data["questions"]:
        if q["category"] != "comparison":
            continue
        for arg in q["expected_min_args"]:
            assert arg in valid_fields, (
                f"Question {q['id']} : champ '{arg}' inconnu de ComparisonTableArgs"
            )


def test_map_questions_match_schema() -> None:
    from app.schemas.visualization import MapArgs

    data = _load_golden_set()
    valid_fields = set(MapArgs.model_fields.keys())
    for q in data["questions"]:
        if q["category"] != "map":
            continue
        for arg in q["expected_min_args"]:
            assert arg in valid_fields, (
                f"Question {q['id']} : champ '{arg}' inconnu de MapArgs"
            )


def test_fallback_questions_have_no_expected_tool() -> None:
    """Les questions fallback_text doivent avoir expected_tool=null."""
    data = _load_golden_set()
    for q in data["questions"]:
        if q["category"] == "fallback_text":
            assert q["expected_tool"] is None, (
                f"Question {q['id']} fallback ne doit pas exiger un tool"
            )


def test_context_page_is_valid_slug() -> None:
    """Chaque context_page est un slug supporté."""
    from app.graph.tool_selector_config import PAGE_TOOL_MAPPING

    data = _load_golden_set()
    for q in data["questions"]:
        page = q["context_page"]
        assert page in PAGE_TOOL_MAPPING, (
            f"Question {q['id']} : page '{page}' inconnue"
        )
