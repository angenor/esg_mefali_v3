"""Tests du runner d'eval golden set (story 10.3, epic M10).

Deux niveaux :
- Tests unitaires (`@pytest.mark.unit`) : parsing YAML, subset_match, evaluation
  par cas en mode mock catalog (pas d'appel LLM, pas d'I/O reseau).
- Test marker `eval` : invoque le golden set complet via le LLM reel. Skippe
  par defaut, lance via `pytest -m eval`. Skip explicite si `OPENROUTER_API_KEY`
  absente pour ne pas casser CI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.llm_eval.run_eval import (
    GoldenCase,
    _evaluate_case,
    golden_hash,
    load_golden,
    run_eval,
    serialize_baseline,
    subset_match,
)

_GOLDEN_PATH = Path(__file__).parent / "golden_set_v1.yaml"


@dataclass
class _StubTool:
    """Tool minimal pour la matrice de test."""

    name: str
    args_schema: object | None = None


# ---------------------------------------------------------------------------
# Unit tests : subset_match
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_subset_match_empty_expected_is_true() -> None:
    assert subset_match({}, None) is True
    assert subset_match({}, {"foo": 1}) is True


@pytest.mark.unit
def test_subset_match_subset_is_true() -> None:
    assert subset_match({"a": 1}, {"a": 1, "b": 2}) is True


@pytest.mark.unit
def test_subset_match_value_mismatch_is_false() -> None:
    assert subset_match({"a": 1}, {"a": 2}) is False


@pytest.mark.unit
def test_subset_match_missing_key_is_false() -> None:
    assert subset_match({"a": 1}, {"b": 1}) is False


@pytest.mark.unit
def test_subset_match_actual_none_with_non_empty_expected_is_false() -> None:
    assert subset_match({"a": 1}, None) is False


# ---------------------------------------------------------------------------
# Unit tests : load_golden + verrous M10
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_golden_set_v1_30_cases() -> None:
    cases = load_golden(_GOLDEN_PATH)
    assert len(cases) == 30
    ids = [c.id for c in cases]
    assert ids == [f"case_{i:03d}" for i in range(1, 31)]
    pages = {c.current_page for c in cases}
    assert len(pages) >= 6


@pytest.mark.unit
def test_load_golden_rejects_forbidden_ask_qcu(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "- id: case_001\n"
        "  message: 'X'\n"
        "  current_page: '/profile'\n"
        "  node_name: 'chat'\n"
        "  expected_tool: 'ask_qcu'\n"
        "  expected_payload_partial: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="INTERDIT"):
        load_golden(bad)


@pytest.mark.unit
def test_load_golden_rejects_show_prefix(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "- id: case_001\n"
        "  message: 'X'\n"
        "  current_page: '/profile'\n"
        "  node_name: 'chat'\n"
        "  expected_tool: 'show_kpi_card'\n"
        "  expected_payload_partial: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="show_"):
        load_golden(bad)


@pytest.mark.unit
def test_load_golden_rejects_unknown_node_name(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "- id: case_001\n"
        "  message: 'X'\n"
        "  current_page: null\n"
        "  node_name: 'invalid_node'\n"
        "  expected_tool: null\n"
        "  expected_payload_partial: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="node_name"):
        load_golden(bad)


@pytest.mark.unit
def test_load_golden_rejects_duplicate_ids(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "- id: case_001\n"
        "  message: 'A'\n"
        "  current_page: null\n"
        "  node_name: 'chat'\n"
        "  expected_tool: null\n"
        "  expected_payload_partial: {}\n"
        "- id: case_001\n"
        "  message: 'B'\n"
        "  current_page: null\n"
        "  node_name: 'chat'\n"
        "  expected_tool: null\n"
        "  expected_payload_partial: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="dupliquee"):
        load_golden(bad)


@pytest.mark.unit
def test_golden_hash_is_deterministic() -> None:
    h1 = golden_hash(_GOLDEN_PATH)
    h2 = golden_hash(_GOLDEN_PATH)
    assert h1 == h2
    assert len(h1) == 64


# ---------------------------------------------------------------------------
# Unit tests : _evaluate_case (4 metriques)
# ---------------------------------------------------------------------------


def _case(
    *,
    expected_tool: str | None,
    payload_partial: dict | None = None,
    node_name: str = "chat",
) -> GoldenCase:
    return GoldenCase(
        id="case_test",
        message="msg",
        current_page="/profile",
        node_name=node_name,
        expected_tool=expected_tool,
        expected_payload_partial=payload_partial or {},
    )


@pytest.mark.unit
def test_evaluate_case_bon_tool_with_partial_match() -> None:
    catalog = {"chat": [_StubTool(name="update_company_profile", args_schema=None)]}
    case = _case(expected_tool="update_company_profile", payload_partial={"employee_count": 12})
    result = _evaluate_case(
        case,
        got_tool="update_company_profile",
        got_args={"employee_count": 12, "sector": "agroalimentaire"},
        error=None,
        catalog=catalog,
    )
    assert result.bon_tool is True
    assert result.payload_partial_match is True
    assert result.fallback_texte is False
    assert result.payload_valide is True


@pytest.mark.unit
def test_evaluate_case_wrong_tool_is_bon_tool_false() -> None:
    catalog = {"chat": [_StubTool(name="update_company_profile")]}
    case = _case(expected_tool="update_company_profile")
    result = _evaluate_case(
        case,
        got_tool="ask_interactive_question",
        got_args={"question_type": "qcu"},
        error=None,
        catalog=catalog,
    )
    assert result.bon_tool is False
    assert result.fallback_texte is False


@pytest.mark.unit
def test_evaluate_case_no_tool_when_expected_is_fallback() -> None:
    catalog = {"chat": [_StubTool(name="update_company_profile")]}
    case = _case(expected_tool="update_company_profile")
    result = _evaluate_case(
        case, got_tool=None, got_args=None, error=None, catalog=catalog
    )
    assert result.bon_tool is False
    assert result.fallback_texte is True


@pytest.mark.unit
def test_evaluate_case_piege_no_tool_expected_no_tool_got() -> None:
    case = _case(expected_tool=None)
    result = _evaluate_case(
        case, got_tool=None, got_args=None, error=None, catalog={}
    )
    assert result.bon_tool is True
    assert result.fallback_texte is False
    assert result.payload_valide is None
    assert result.payload_partial_match is None


@pytest.mark.unit
def test_evaluate_case_piege_with_tool_called_is_bon_tool_false() -> None:
    case = _case(expected_tool=None)
    result = _evaluate_case(
        case,
        got_tool="update_company_profile",
        got_args={},
        error=None,
        catalog={"chat": []},
    )
    assert result.bon_tool is False
    assert result.fallback_texte is False


@pytest.mark.unit
def test_evaluate_case_error_records_error_field() -> None:
    case = _case(expected_tool="update_company_profile")
    result = _evaluate_case(
        case, got_tool=None, got_args=None, error="TimeoutError: x", catalog={"chat": []}
    )
    assert result.bon_tool is False
    assert result.error == "TimeoutError: x"
    assert result.fallback_texte is True


# ---------------------------------------------------------------------------
# Unit test : serialize_baseline
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_node_catalog_excludes_document_node() -> None:
    """document_node ne fait pas bind_tools en prod (cf. nodes.py:487+)."""
    from tests.llm_eval.run_eval import _NODE_NAMES

    assert "document" not in _NODE_NAMES


@pytest.mark.unit
def test_node_catalog_application_excludes_guided_tour() -> None:
    """Verrou : application_node bind APPLICATION + INTERACTIVE seulement
    (cf. nodes.py:1318). Toute divergence cree un faux positif sur
    trigger_guided_tour."""
    pytest.importorskip("langchain_core")
    from tests.llm_eval.run_eval import _build_node_catalog

    catalog = _build_node_catalog()
    names = {getattr(t, "name", None) for t in catalog["application"]}
    assert "trigger_guided_tour" not in names, (
        "application_node ne doit pas exposer trigger_guided_tour "
        "(verrou cf. app/graph/nodes.py:1318)"
    )
    assert "document" not in catalog, (
        "document_node ne fait pas bind_tools — ne doit pas apparaitre "
        "dans le catalog (cf. _NODE_NAMES)"
    )


@pytest.mark.unit
def test_serialize_baseline_shape() -> None:
    from datetime import datetime, timezone

    from tests.llm_eval.run_eval import EvalResult

    result = EvalResult(
        cases=[],
        model_id="anthropic/claude-sonnet-4",
        golden_hash="abc123",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    payload = serialize_baseline(result, _GOLDEN_PATH)
    assert set(payload.keys()) == {"metadata", "summary", "cases"}
    assert payload["metadata"]["model_id"] == "anthropic/claude-sonnet-4"
    assert payload["metadata"]["golden_hash"] == "abc123"
    assert payload["summary"]["total"] == 0


# ---------------------------------------------------------------------------
# Eval test (marker eval) : skip si pas d'API key
# ---------------------------------------------------------------------------


# Seuils CI single-run (volontairement relaches vs cible epic).
# La cible epic >=90% bon_tool / <=10% fallback est verifiee EN MOYENNE sur
# 3 runs (cf. README §Limites, story 10.3 contexte §5). Sur 1 run, le
# determinisme imparfait d'OpenRouter (pas de seed garanti) peut faire
# basculer 1-2 cas — d'ou les seuils relaches ici. Le rapport markdown
# stdout affiche toujours le gate strict 90%/10% pour signal humain.
_CI_BON_TOOL_MIN = 0.85
_CI_FALLBACK_MAX = 0.15


@pytest.mark.eval
def test_golden_set_meets_baseline() -> None:
    """Lance le golden set complet via le LLM. Skippe si pas d'API key.

    Gate single-run relache (cf. _CI_BON_TOOL_MIN / _CI_FALLBACK_MAX).
    Le gate strict epic >=90% / <=10% est verifie en moyenne 3 runs.
    """
    if not os.environ.get("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY missing")

    result = run_eval(_GOLDEN_PATH)
    assert result.total == 30
    assert result.bon_tool_rate >= _CI_BON_TOOL_MIN, (
        f"bon_tool_rate={result.bon_tool_rate:.2%} < "
        f"{_CI_BON_TOOL_MIN:.0%} (single-run CI gate ; cible epic 90% sur 3 runs) "
        "— voir rapport stdout."
    )
    assert result.fallback_text_rate <= _CI_FALLBACK_MAX, (
        f"fallback_text_rate={result.fallback_text_rate:.2%} > "
        f"{_CI_FALLBACK_MAX:.0%} (single-run CI gate)."
    )
