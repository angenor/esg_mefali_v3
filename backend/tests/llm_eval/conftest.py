"""Fixtures et helpers pour le runner LLM eval F22.

Charge le golden set, fournit ``subset_match`` (matching tolerant), et un
hook ``pytest_sessionfinish`` qui ecrit le rapport ``eval-report.json``.

Le runner reel est dans ``tests/llm_eval/test_eval_runner.py`` ; ce module
ne contient que les fixtures partagees.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"
EVAL_REPORT_DEFAULT = Path(__file__).parent.parent.parent / "eval-report.json"


# ─── Loaders ────────────────────────────────────────────────────────────────


def load_golden_set(path: Path | None = None) -> list[dict]:
    """Charge le golden set 50 cas et retourne la liste des cas.

    Validation du format : ``version`` et ``cases`` requis. La validation
    JSON Schema complete est faite par le runner si la lib est dispo
    (``jsonschema``) — sinon validation legere uniquement.
    """
    target = path or GOLDEN_SET_PATH
    if not target.exists():
        return []
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Golden set invalide ({target}) : {exc}") from exc
    cases = data.get("cases", [])
    if not isinstance(cases, list):
        raise RuntimeError(f"Golden set : 'cases' doit etre une liste, got {type(cases)}")
    return cases


# ─── subset_match ───────────────────────────────────────────────────────────


def subset_match(actual: dict | list, expected: dict | list) -> bool:
    """Retourne True si ``expected`` est un sous-ensemble de ``actual``.

    - Pour un dict : toutes les cles d'``expected`` doivent exister dans
      ``actual`` avec une valeur identique (recursion sur dict imbriques).
    - Pour une liste : ``expected`` doit avoir la meme longueur et chaque
      element doit matcher (recursivement).
    - Pour les valeurs primitives : egalite stricte.
    - ``None`` cote ``actual`` ET ``expected`` -> True.
    """
    if expected is None:
        return True
    if actual is None:
        return False
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        for k, v in expected.items():
            if k not in actual:
                return False
            if not subset_match(actual[k], v):
                return False
        return True
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return False
        return all(subset_match(a, e) for a, e in zip(actual, expected))
    return actual == expected


# ─── Pytest fixtures ────────────────────────────────────────────────────────


def pytest_addoption(parser):
    parser.addoption(
        "--golden-report",
        action="store",
        default=None,
        help="Chemin du rapport JSON eval (default = backend/eval-report.json).",
    )


@pytest.fixture(scope="session")
def golden_set() -> list[dict]:
    """Charge le golden set une seule fois par session."""
    return load_golden_set()


@pytest.fixture(scope="session")
def eval_report_writer(request) -> dict:
    """Fixture session-scoped qui collecte les resultats du runner.

    Le runner remplit ``writer["results"].append({...})`` apres chaque cas ;
    a la fin de la session, ``pytest_sessionfinish`` calcule les metriques
    agregees et serialise dans le fichier choisi.
    """
    writer: dict[str, Any] = {
        "run_id": str(uuid.uuid4()),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "model": os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4.5"),
        "results": [],
        "_path": request.config.getoption("--golden-report")
        or str(EVAL_REPORT_DEFAULT),
    }
    return writer


# ─── Metrics aggregation ────────────────────────────────────────────────────


def compute_metrics(results: list[dict]) -> dict:
    """Calcule les 4 metriques globales + by_category.

    Definitions (cf. spec.md SC-001..SC-004) :
    - tool_match_rate : actual_tool ∈ expected_tool (str ou whitelist).
    - payload_valid_rate : subset_match(actual_payload, expected.payload_contains).
    - hallucination_rate : actual_tool n'existe pas dans le registre.
    - fallback_rate : retour {success: false, fallback_message: ...}.
    """
    if not results:
        return {
            "tool_match_rate": 0.0,
            "payload_valid_rate": 0.0,
            "hallucination_rate": 0.0,
            "fallback_rate": 0.0,
            "by_category": {},
        }

    n = len(results)
    matched = sum(1 for r in results if r.get("status") == "pass")
    payload_ok = sum(1 for r in results if r.get("payload_diff") in (None, {}))
    hallucinated = sum(1 for r in results if r.get("status") == "hallucination")
    fallback = sum(1 for r in results if r.get("fallback_used"))

    by_category: dict[str, dict] = {}
    for r in results:
        cat = r.get("category", "unknown")
        bucket = by_category.setdefault(
            cat, {"cases": 0, "passed": 0, "payload_ok": 0}
        )
        bucket["cases"] += 1
        if r.get("status") == "pass":
            bucket["passed"] += 1
        if r.get("payload_diff") in (None, {}):
            bucket["payload_ok"] += 1

    by_category_out: dict[str, dict] = {}
    for cat, b in by_category.items():
        cases = b["cases"] or 1
        by_category_out[cat] = {
            "cases": b["cases"],
            "tool_match_rate": round(b["passed"] / cases, 3),
            "payload_valid_rate": round(b["payload_ok"] / cases, 3),
        }

    return {
        "tool_match_rate": round(matched / n, 3),
        "payload_valid_rate": round(payload_ok / n, 3),
        "hallucination_rate": round(hallucinated / n, 3),
        "fallback_rate": round(fallback / n, 3),
        "by_category": by_category_out,
    }


def write_eval_report(writer: dict) -> None:
    """Serialise ``writer`` dans le fichier rapport JSON."""
    started = datetime.fromisoformat(writer["started_at"])
    completed = datetime.now(timezone.utc)
    results = list(writer.get("results", []))

    payload = {
        "run_id": writer["run_id"],
        "started_at": writer["started_at"],
        "completed_at": completed.isoformat(),
        "duration_seconds": round((completed - started).total_seconds(), 2),
        "model": writer["model"],
        "total_cases": len(results),
        "passed": sum(1 for r in results if r.get("status") == "pass"),
        "failed": sum(1 for r in results if r.get("status") == "fail"),
        "results": [
            {
                "case_id": r.get("case_id"),
                "status": r.get("status"),
                "actual_tool": r.get("actual_tool"),
                "expected_tool": r.get("expected_tool"),
                "payload_diff": r.get("payload_diff"),
                "latency_ms": int(r.get("latency_ms", 0)),
                **({"tokens_used": r["tokens_used"]} if "tokens_used" in r else {}),
                **({"error": r["error"]} if r.get("error") else {}),
            }
            for r in results
        ],
        "metrics": compute_metrics(results),
    }
    out = Path(writer["_path"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ─── Session hooks ──────────────────────────────────────────────────────────


def pytest_sessionfinish(session, exitstatus):  # noqa: ANN001
    """Si le writer a ete utilise, serialise le rapport en fin de session."""
    # On accede au writer via la fixture cache ; sinon no-op.
    cache = getattr(session, "_eval_report_writer", None)
    if cache is None:
        return
    write_eval_report(cache)
