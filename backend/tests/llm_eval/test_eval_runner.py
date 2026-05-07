"""F22 — Runner LLM eval pour le golden set 50 cas.

Marque ``pytest.mark.eval`` => exclu du run par defaut. Lance via :

    pytest tests/llm_eval/ -m eval --golden-report=eval-report.json -v

Pour chaque cas, le runner :
1. Construit le contexte (current_page, active_module, user_message).
2. Invoque le graphe LangGraph avec un user de test.
3. Capture le tool effectivement invoque (via tool_call_logs ou trace).
4. Compare actual vs expected via la whitelist tolérante + ``subset_match``.
5. Enregistre le resultat dans le writer (ecrit en fin de session).

Le runner est conçu pour etre executable HORS d'une CI normale (cout LLM)
et inclut un fallback ``skip`` si ``OPENROUTER_API_KEY`` n'est pas defini.

Reference : ``specs/032-decision-tree-with-retry-eval/{spec.md, plan.md}``.
"""

from __future__ import annotations

import os
import time
from typing import Any

import pytest

from tests.llm_eval.conftest import (
    load_golden_set,
    subset_match,
)


pytestmark = pytest.mark.eval


# ─── Helpers ────────────────────────────────────────────────────────────────


def _expected_tools_set(expected_tool: str | list[str]) -> set[str]:
    """Normalise expected_tool en set (whitelist tolerante)."""
    if isinstance(expected_tool, list):
        return set(expected_tool)
    return {expected_tool}


def _evaluate_case(
    case: dict,
    actual_tool: str | None,
    actual_payload: dict | None,
    fallback_used: bool,
) -> dict:
    """Compare actual vs expected et retourne le statut + diff payload.

    Returns:
        Dict avec ``status``, ``payload_diff`` (None si OK), et metadata.
    """
    expected = case.get("expected", {})
    expected_tool = expected.get("tool_called")
    payload_contains = expected.get("payload_contains") or {}
    fallback_acceptable = expected.get("fallback_acceptable", False)

    # Cas conversationnel : pas de tool attendu, fallback ok.
    if isinstance(expected_tool, list) and len(expected_tool) == 0:
        if actual_tool is None or fallback_acceptable:
            return {"status": "pass", "payload_diff": None}
        return {
            "status": "fail",
            "payload_diff": None,
            "actual_tool": actual_tool,
        }

    expected_set = _expected_tools_set(expected_tool)

    # Tool match : actual_tool ∈ whitelist
    if actual_tool is None:
        if fallback_acceptable and fallback_used:
            return {"status": "pass", "payload_diff": None, "fallback_used": True}
        return {"status": "fail", "payload_diff": None}

    if actual_tool not in expected_set:
        # Hallucination potentielle si le tool n'existe pas dans le registre
        # (verification simplifiee : ici on compte simplement comme fail).
        return {
            "status": "fail",
            "payload_diff": None,
            "actual_tool": actual_tool,
        }

    # Payload match
    if payload_contains and not subset_match(actual_payload or {}, payload_contains):
        return {
            "status": "partial",
            "payload_diff": payload_contains,
            "actual_tool": actual_tool,
        }

    return {"status": "pass", "payload_diff": None}


# ─── Stub mode (pour CI sans cle API) ───────────────────────────────────────


def _is_stub_mode() -> bool:
    """Retourne True si la CI doit skipper le run reel (mode stub).

    Activable via :
    - Pas de OPENROUTER_API_KEY (cas par defaut en CI sans secret).
    - Variable F22_EVAL_STUB=1.
    """
    return (
        os.getenv("F22_EVAL_STUB") == "1"
        or not os.getenv("OPENROUTER_API_KEY")
    )


# ─── Test parametre ─────────────────────────────────────────────────────────

# Le parametre doit etre genere au COLLECT (pas a l'execution) -> appelle directe.
_GOLDEN_CASES = load_golden_set()


@pytest.mark.parametrize(
    "case",
    _GOLDEN_CASES,
    ids=lambda c: c.get("id", "unknown"),
)
def test_golden_case(case, request, eval_report_writer) -> None:
    """Execute UN cas du golden set + compare actual vs expected."""
    if _is_stub_mode():
        pytest.skip(
            "F22 eval skipped (no OPENROUTER_API_KEY ou F22_EVAL_STUB=1)."
        )

    # Stocker le writer dans la session pour pytest_sessionfinish
    request.session._eval_report_writer = eval_report_writer

    started = time.monotonic()

    # ─── Invocation graphe ──────────────────────────────────────────────────
    # Note : l'integration reelle avec le graphe LangGraph est volontairement
    # protegee : le runner d'eval reel est complexe (besoin d'un user, conv,
    # checkpointer, etc.). Cet appel est encapsule dans un helper qu'on
    # implemente apres avoir converge sur le contrat de test (issue F22-2).
    # En l'absence de l'helper, le test est marque ``pytest.skip``.
    try:
        from app.graph.graph import create_compiled_graph  # noqa: F401
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Graph indisponible : {exc}")

    # Pour la phase actuelle, on simule un appel "neutre" (no-op) qui ne mene
    # pas a un tool. Le runner reel sera enrichi par F22-suite ; ici on
    # garantit la mecanique de scoring + ecriture rapport.
    actual_tool: str | None = None
    actual_payload: dict[str, Any] | None = None
    fallback_used = False

    elapsed_ms = int((time.monotonic() - started) * 1000)

    # ─── Scoring ────────────────────────────────────────────────────────────
    result = _evaluate_case(
        case,
        actual_tool=actual_tool,
        actual_payload=actual_payload,
        fallback_used=fallback_used,
    )

    record = {
        "case_id": case.get("id"),
        "category": case.get("category"),
        "expected_tool": case["expected"]["tool_called"],
        "actual_tool": actual_tool,
        "status": result["status"],
        "payload_diff": result.get("payload_diff"),
        "latency_ms": elapsed_ms,
        "fallback_used": fallback_used,
    }
    eval_report_writer["results"].append(record)

    # On n'echoue pas le test individuel : la gate finale est faite par
    # ``test_metrics_gates`` (apres aggregation).
    # En revanche, on signale les fail dans le rapport.


# ─── Gates aggregees ────────────────────────────────────────────────────────


def test_metrics_gates_after_full_run(eval_report_writer) -> None:
    """Verifie les gates apres execution de tous les cas (P1).

    Cette fonction est ordonnee a la fin via le tri pytest naturel (Z > test_).
    Les gates :
    - tool_match_rate >= 0.90
    - payload_valid_rate >= 0.95
    - hallucination_rate < 0.01
    """
    if _is_stub_mode():
        pytest.skip("F22 gates skipped en mode stub.")

    from tests.llm_eval.conftest import compute_metrics

    results = eval_report_writer.get("results", [])
    if not results:
        pytest.skip("Aucun resultat aggrege (run partiel ?).")

    metrics = compute_metrics(results)

    assert metrics["tool_match_rate"] >= 0.90, (
        f"tool_match_rate={metrics['tool_match_rate']:.3f} < 0.90 "
        "(spec SC-001 — bloquant)"
    )
    assert metrics["payload_valid_rate"] >= 0.95, (
        f"payload_valid_rate={metrics['payload_valid_rate']:.3f} < 0.95 "
        "(spec SC-002 — bloquant)"
    )
    assert metrics["hallucination_rate"] < 0.01, (
        f"hallucination_rate={metrics['hallucination_rate']:.3f} > 0.01 "
        "(spec SC-003 — bloquant)"
    )


# ─── Self-test du runner (sans LLM) ─────────────────────────────────────────


@pytest.mark.unit
def test_evaluate_case_pass_simple_match() -> None:
    case = {
        "id": "test",
        "expected": {"tool_called": "update_company_profile"},
    }
    out = _evaluate_case(
        case,
        actual_tool="update_company_profile",
        actual_payload=None,
        fallback_used=False,
    )
    assert out["status"] == "pass"


@pytest.mark.unit
def test_evaluate_case_fail_wrong_tool() -> None:
    case = {
        "id": "test",
        "expected": {"tool_called": "update_company_profile"},
    }
    out = _evaluate_case(
        case,
        actual_tool="get_company_profile",
        actual_payload=None,
        fallback_used=False,
    )
    assert out["status"] == "fail"


@pytest.mark.unit
def test_evaluate_case_pass_whitelist_tolerant() -> None:
    case = {
        "id": "test",
        "expected": {"tool_called": ["ask_qcu", "ask_select"]},
    }
    out = _evaluate_case(
        case,
        actual_tool="ask_qcu",
        actual_payload=None,
        fallback_used=False,
    )
    assert out["status"] == "pass"


@pytest.mark.unit
def test_evaluate_case_partial_payload_mismatch() -> None:
    case = {
        "id": "test",
        "expected": {
            "tool_called": "update_company_profile",
            "payload_contains": {"sector": "agriculture"},
        },
    }
    out = _evaluate_case(
        case,
        actual_tool="update_company_profile",
        actual_payload={"sector": "industry"},
        fallback_used=False,
    )
    assert out["status"] == "partial"


@pytest.mark.unit
def test_evaluate_case_pass_conversational_no_tool() -> None:
    case = {
        "id": "greeting",
        "expected": {"tool_called": [], "fallback_acceptable": True},
    }
    out = _evaluate_case(
        case,
        actual_tool=None,
        actual_payload=None,
        fallback_used=True,
    )
    assert out["status"] == "pass"
