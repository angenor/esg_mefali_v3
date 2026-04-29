"""Runner du golden set d'eval LLM tool-calling (story 10.3, epic M10).

Usage CLI :
    python -m tests.llm_eval.run_eval --golden tests/llm_eval/golden_set_v1.yaml \
        [--save-baseline] [--limit N] [--cases case_001,case_005]

Usage librairie :
    from tests.llm_eval.run_eval import run_eval
    result = run_eval(golden_path="tests/llm_eval/golden_set_v1.yaml")
    assert result.bon_tool_rate >= 0.90

Verrous (story 10.3 contexte §3, §4) :
    - On invoque le noeud LLM ISOLE (pas le graphe complet).
    - On capture seulement `AIMessage.tool_calls` (intent), aucun ToolNode.invoke.
    - Mock systematique de `get_db_and_user` et `log_tool_call` pour que rien
      ne touche la base.
    - On reutilise `select_tools_for_node` (story 10.2) pour batir la liste
      vue par le LLM, identique a la prod.
    - Pas de fallback : si `ask_qcu`, `show_*` etc apparaissent dans le YAML,
      le runner LEVE une erreur de configuration (verrou stories 10.1/10.2).
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("tests.llm_eval.run_eval")


# Tools INTERDITS dans le golden set (verrou stories 10.1 et 10.2).
_FORBIDDEN_TOOL_NAMES = frozenset({
    "ask_qcu",
    "ask_qcm",
    "ask_qcu_justification",
    "ask_qcm_justification",
})


# Noeuds qui font bind_tools en prod (cf. app/graph/nodes.py).
# `document_node` n'appelle pas bind_tools, donc volontairement exclu.
_NODE_NAMES = frozenset({
    "chat", "esg_scoring", "carbon", "financing",
    "application", "credit", "action_plan",
})


# ---------------------------------------------------------------------------
# Modeles de donnees
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GoldenCase:
    """Une entree du golden set v1."""

    id: str
    message: str
    current_page: str | None
    node_name: str
    expected_tool: str | None
    expected_payload_partial: dict[str, Any]
    notes: str = ""
    # Tools alternatifs juges acceptables (ex: lire avant ecrire). Un match sur
    # l'un d'eux compte comme `bon_tool=True` mais reste trace via `matched_alternative`.
    accepted_alternatives: tuple[str, ...] = ()


@dataclass
class CaseResult:
    """Resultat d'evaluation pour un cas."""

    id: str
    expected_tool: str | None
    got_tool: str | None
    got_args: dict[str, Any] | None
    bon_tool: bool
    payload_valide: bool | None
    payload_partial_match: bool | None
    fallback_texte: bool
    error: str | None = None
    notes: str = ""
    # True si bon_tool est obtenu via accepted_alternatives (et non expected_tool).
    matched_alternative: bool = False


@dataclass
class EvalResult:
    """Agregat sur l'ensemble du golden set."""

    cases: list[CaseResult]
    model_id: str
    golden_hash: str
    timestamp: str

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def bon_tool_rate(self) -> float:
        if not self.cases:
            return 0.0
        return sum(1 for c in self.cases if c.bon_tool) / len(self.cases)

    @property
    def fallback_text_rate(self) -> float:
        if not self.cases:
            return 0.0
        return sum(1 for c in self.cases if c.fallback_texte) / len(self.cases)

    @property
    def payload_valide_rate(self) -> float:
        denom = sum(1 for c in self.cases if c.payload_valide is not None)
        if denom == 0:
            return 0.0
        return sum(1 for c in self.cases if c.payload_valide) / denom

    @property
    def payload_partial_match_rate(self) -> float:
        denom = sum(1 for c in self.cases if c.payload_partial_match is not None)
        if denom == 0:
            return 0.0
        return sum(1 for c in self.cases if c.payload_partial_match) / denom


# ---------------------------------------------------------------------------
# Chargement du golden set
# ---------------------------------------------------------------------------


def load_golden(path: str | Path) -> list[GoldenCase]:
    """Parser le golden YAML et valider la coherence avec les verrous M10."""
    import yaml

    raw = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, list):
        raise ValueError(f"Golden set malforme : la racine doit etre une liste ({path}).")

    cases: list[GoldenCase] = []
    seen_ids: set[str] = set()
    for entry in data:
        if not isinstance(entry, dict):
            raise ValueError(f"Entree non-dict dans {path} : {entry!r}")

        case_id = entry.get("id")
        if not case_id or not isinstance(case_id, str):
            raise ValueError(f"Entree sans `id` valide : {entry!r}")
        if case_id in seen_ids:
            raise ValueError(f"Id dupliquee dans le golden set : {case_id}")
        seen_ids.add(case_id)

        node_name = entry.get("node_name")
        if node_name not in _NODE_NAMES:
            raise ValueError(
                f"{case_id}: node_name '{node_name}' invalide (attendu : {sorted(_NODE_NAMES)})"
            )

        expected_tool = entry.get("expected_tool")
        if expected_tool is not None:
            if not isinstance(expected_tool, str):
                raise ValueError(f"{case_id}: expected_tool doit etre str ou null.")
            if expected_tool in _FORBIDDEN_TOOL_NAMES:
                raise ValueError(
                    f"{case_id}: expected_tool '{expected_tool}' INTERDIT "
                    "(stories 10.1/10.2 — pas de ask_qcu/qcm ni show_*)."
                )
            if expected_tool.startswith("show_"):
                raise ValueError(
                    f"{case_id}: tools `show_*` n'existent pas (verrou story 10.1)."
                )

        payload_partial = entry.get("expected_payload_partial") or {}
        if not isinstance(payload_partial, dict):
            raise ValueError(f"{case_id}: expected_payload_partial doit etre un mapping.")

        raw_alts = entry.get("accepted_alternatives") or []
        if not isinstance(raw_alts, list):
            raise ValueError(f"{case_id}: accepted_alternatives doit etre une liste.")
        alts: list[str] = []
        for alt in raw_alts:
            if not isinstance(alt, str):
                raise ValueError(f"{case_id}: accepted_alternatives doit contenir des str.")
            if alt in _FORBIDDEN_TOOL_NAMES or alt.startswith("show_"):
                raise ValueError(
                    f"{case_id}: alternative '{alt}' INTERDITE (verrou stories 10.1/10.2)."
                )
            if alt == expected_tool:
                raise ValueError(
                    f"{case_id}: alternative '{alt}' identique a expected_tool (redondant)."
                )
            alts.append(alt)

        cases.append(
            GoldenCase(
                id=case_id,
                message=str(entry.get("message", "")),
                current_page=entry.get("current_page"),
                node_name=node_name,
                expected_tool=expected_tool,
                expected_payload_partial=payload_partial,
                notes=str(entry.get("notes", "") or ""),
                accepted_alternatives=tuple(alts),
            )
        )

    return cases


def golden_hash(path: str | Path) -> str:
    """Hash SHA-256 deterministe du golden YAML (cf. AC5 story 10.3)."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Metriques
# ---------------------------------------------------------------------------


def subset_match(expected: dict[str, Any], actual: dict[str, Any] | None) -> bool:
    """Vrai si tous les couples (k,v) de `expected` sont dans `actual`.

    `expected` vide retourne True (rien a comparer). `actual=None` retourne
    False sauf si `expected` est vide.
    """
    if not expected:
        return True
    if not isinstance(actual, dict):
        return False
    for key, value in expected.items():
        if key not in actual:
            return False
        if actual[key] != value:
            return False
    return True


def validate_payload_with_pydantic(tool_obj: Any, args: dict[str, Any]) -> tuple[bool, str | None]:
    """Valider `args` avec le `args_schema` Pydantic du tool.

    Retourne `(ok, message)` ou `message` = None si ok.
    """
    schema = getattr(tool_obj, "args_schema", None)
    if schema is None:
        return True, None
    try:
        from pydantic import ValidationError
    except ImportError:  # pragma: no cover
        ValidationError = Exception  # type: ignore[assignment,misc]
    try:
        schema(**args)
        return True, None
    except ValidationError as exc:
        return False, str(exc)[:200]


# ---------------------------------------------------------------------------
# Catalogue de tools par noeud (miroir de nodes.py)
# ---------------------------------------------------------------------------


def _build_node_catalog() -> dict[str, list[Any]]:
    """Construire `node_name -> liste de tools BaseTool` (miroir des binds dans
    `app/graph/nodes.py`).

    Importe localement pour que ce module reste importable hors environnement
    backend (ex : test unitaire de subset_match sans dependances LangChain).
    """
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
    from app.graph.tools.profiling_tools import PROFILING_TOOLS

    # Miroir EXACT de app/graph/nodes.py (verifie ligne par ligne contre les
    # `full_catalog = ... + bind_tools(filtered_tools)` de chaque noeud) :
    #   - chat            : nodes.py:1209 (PROFILING + CHAT + DOCUMENT + INTERACTIVE + GUIDED_TOUR)
    #   - esg_scoring     : nodes.py:696  (ESG + INTERACTIVE + GUIDED_TOUR)
    #   - carbon          : nodes.py:871  (CARBON + INTERACTIVE + GUIDED_TOUR)
    #   - financing       : nodes.py:941  (FINANCING + INTERACTIVE + GUIDED_TOUR)
    #   - application     : nodes.py:1318 (APPLICATION + INTERACTIVE)  <-- PAS de GUIDED_TOUR
    #   - credit          : nodes.py:1127 (CREDIT + INTERACTIVE + GUIDED_TOUR)
    #   - action_plan     : nodes.py:1391 (ACTION_PLAN + INTERACTIVE + GUIDED_TOUR)
    # Toute divergence ici cree un faux positif : l'eval expose au LLM un tool
    # absent en prod. Garder ce commentaire synchronise si nodes.py change.
    base_with_tour = INTERACTIVE_TOOLS + GUIDED_TOUR_TOOLS

    return {
        "chat": PROFILING_TOOLS + CHAT_TOOLS + DOCUMENT_TOOLS + base_with_tour,
        "esg_scoring": ESG_TOOLS + base_with_tour,
        "carbon": CARBON_TOOLS + base_with_tour,
        "financing": FINANCING_TOOLS + base_with_tour,
        "application": APPLICATION_TOOLS + INTERACTIVE_TOOLS,  # pas de GUIDED_TOUR
        "credit": CREDIT_TOOLS + base_with_tour,
        "action_plan": ACTION_PLAN_TOOLS + base_with_tour,
    }


# ---------------------------------------------------------------------------
# Invocation LLM par cas
# ---------------------------------------------------------------------------


_CASE_TIMEOUT_S = 30.0
_MAX_RETRIES = 1
_RETRY_BACKOFF_S = 2.0


async def _invoke_llm_for_case(
    case: GoldenCase,
    catalog: dict[str, list[Any]],
) -> tuple[str | None, dict[str, Any] | None, str | None]:
    """Invoquer le LLM pour un cas et retourner `(tool_name, args, error)`.

    `tool_name=None` signifie reponse en texte libre (pas de tool_call).
    """
    from langchain_core.messages import HumanMessage

    from app.graph.nodes import get_llm
    from app.graph.tool_selector import select_tools_for_node

    all_tools = catalog.get(case.node_name)
    if all_tools is None:
        return None, None, f"node_name inconnu : {case.node_name}"

    filtered, _debug = select_tools_for_node(
        node_name=case.node_name,
        current_page=case.current_page,
        all_tools=all_tools,
    )

    llm = get_llm()
    llm_with_tools = llm.bind_tools(filtered) if filtered else llm

    last_exc: BaseException = RuntimeError("aucune tentative LLM aboutie")
    for attempt in range(_MAX_RETRIES + 1):
        try:
            ai_msg = await asyncio.wait_for(
                llm_with_tools.ainvoke([HumanMessage(content=case.message)]),
                timeout=_CASE_TIMEOUT_S,
            )
            tool_calls = getattr(ai_msg, "tool_calls", None) or []
            if not tool_calls:
                return None, None, None
            first = tool_calls[0]
            name = first.get("name") if isinstance(first, dict) else getattr(first, "name", None)
            args = first.get("args") if isinstance(first, dict) else getattr(first, "args", None)
            return name, dict(args or {}), None
        except asyncio.TimeoutError:
            last_exc = TimeoutError(f"timeout > {_CASE_TIMEOUT_S}s")
        except Exception as exc:
            last_exc = exc

        if attempt < _MAX_RETRIES:
            await asyncio.sleep(_RETRY_BACKOFF_S)

    return None, None, f"{type(last_exc).__name__}: {str(last_exc)[:200]}"


def _evaluate_case(
    case: GoldenCase,
    got_tool: str | None,
    got_args: dict[str, Any] | None,
    error: str | None,
    catalog: dict[str, list[Any]],
) -> CaseResult:
    """Calculer les 4 metriques pour un cas."""
    if error:
        return CaseResult(
            id=case.id,
            expected_tool=case.expected_tool,
            got_tool=got_tool,
            got_args=got_args,
            bon_tool=False,
            payload_valide=None,
            payload_partial_match=None,
            fallback_texte=case.expected_tool is not None,
            error=error,
            notes=case.notes,
        )

    matched_alternative = False
    if case.expected_tool is None:
        bon_tool = got_tool is None
        fallback_texte = False
    else:
        if got_tool == case.expected_tool:
            bon_tool = True
        elif got_tool is not None and got_tool in case.accepted_alternatives:
            bon_tool = True
            matched_alternative = True
        else:
            bon_tool = False
        fallback_texte = got_tool is None

    payload_valide: bool | None = None
    payload_partial: bool | None = None
    # Validation Pydantic uniquement sur match exact (alternative = schema different).
    if case.expected_tool is not None and got_tool == case.expected_tool:
        tool_obj = None
        for tool in catalog.get(case.node_name, []):
            if getattr(tool, "name", None) == case.expected_tool:
                tool_obj = tool
                break
        if tool_obj is not None and got_args is not None:
            ok, _ = validate_payload_with_pydantic(tool_obj, got_args)
            payload_valide = ok
        else:
            payload_valide = False
        payload_partial = subset_match(case.expected_payload_partial, got_args)

    return CaseResult(
        id=case.id,
        expected_tool=case.expected_tool,
        got_tool=got_tool,
        got_args=got_args,
        bon_tool=bon_tool,
        payload_valide=payload_valide,
        payload_partial_match=payload_partial,
        fallback_texte=fallback_texte,
        notes=case.notes,
        matched_alternative=matched_alternative,
    )


def _slugify_model_id(model_id: str) -> str:
    """Slugifier le model_id pour nom de fichier."""
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", model_id).strip("-")
    return s or "unknown-model"


def _resolve_model_id() -> str:
    """Lire le model id courant (settings.openrouter_model)."""
    try:
        from app.core.config import settings
        return getattr(settings, "openrouter_model", None) or "unknown-model"
    except Exception:
        return os.environ.get("OPENROUTER_MODEL", "unknown-model")


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------


async def _run_eval_async(
    cases: list[GoldenCase],
    catalog: dict[str, list[Any]],
) -> list[CaseResult]:
    """Iterer chaque cas en sequence (pour limiter les rate-limits)."""
    results: list[CaseResult] = []
    for case in cases:
        try:
            got_tool, got_args, error = await _invoke_llm_for_case(case, catalog)
        except Exception as exc:  # pragma: no cover - filet de securite
            logger.exception("Cas %s : crash inattendu", case.id)
            got_tool, got_args, error = None, None, f"{type(exc).__name__}: {exc}"
        results.append(_evaluate_case(case, got_tool, got_args, error, catalog))
    return results


def run_eval(
    golden_path: str | Path,
    *,
    limit: int | None = None,
    only_ids: set[str] | None = None,
    catalog: dict[str, list[Any]] | None = None,
) -> EvalResult:
    """Charger le golden set et lancer l'eval.

    `catalog` est injectable pour les tests unitaires (skip de la dependance
    LangChain). En prod, il est construit via `_build_node_catalog`.
    """
    cases = load_golden(golden_path)
    if only_ids:
        cases = [c for c in cases if c.id in only_ids]
    if limit is not None:
        cases = cases[:limit]

    if catalog is None:
        catalog = _build_node_catalog()

    _patch_no_side_effect()

    started = time.monotonic()
    results = asyncio.run(_run_eval_async(cases, catalog))
    duration = time.monotonic() - started
    logger.info("Eval termine en %.1fs (%d cas)", duration, len(results))

    return EvalResult(
        cases=results,
        model_id=_resolve_model_id(),
        golden_hash=golden_hash(golden_path),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _patch_no_side_effect() -> None:
    """Neutraliser `get_db_and_user` et `log_tool_call` au cas ou un tool
    serait quand meme execute (le runner ne le fait pas mais defense en
    profondeur — story 10.3 contexte §4)."""
    try:
        from app.graph.tools import common as _common

        async def _noop_log(*_args: Any, **_kwargs: Any) -> None:
            return None

        def _stub_get_db_and_user(_config: Any) -> tuple[Any, Any]:
            raise RuntimeError(
                "Eval runner : tool execution interdite (cas detecte). "
                "Verifier qu'aucun ToolNode n'est invoque."
            )

        _common.log_tool_call = _noop_log  # type: ignore[assignment]
        _common.get_db_and_user = _stub_get_db_and_user  # type: ignore[assignment]
    except Exception:
        logger.debug("Patch no-side-effect impossible (module common absent ?)", exc_info=True)


# ---------------------------------------------------------------------------
# Rapport markdown / baseline JSON
# ---------------------------------------------------------------------------


def render_report(result: EvalResult, golden_path: str | Path) -> str:
    """Imprimer le rapport markdown stdout (cf. AC3 story 10.3)."""
    _ = golden_path
    total = result.total
    bon = sum(1 for c in result.cases if c.bon_tool)
    bon_via_alt = sum(1 for c in result.cases if c.bon_tool and c.matched_alternative)
    payload_ok_denom = sum(1 for c in result.cases if c.payload_valide is not None)
    payload_ok = sum(1 for c in result.cases if c.payload_valide is True)
    subset_denom = sum(1 for c in result.cases if c.payload_partial_match is not None)
    subset_ok = sum(1 for c in result.cases if c.payload_partial_match is True)
    fallback_n = sum(1 for c in result.cases if c.fallback_texte)
    error_n = sum(1 for c in result.cases if c.error)

    date_short = result.timestamp[:10]
    lines: list[str] = []
    lines.append(f"# Eval golden_set_v1 — {date_short} — modele={result.model_id}")
    lines.append(f"Cas : {total}")
    bon_ok = (bon / total >= 0.90) if total else False
    bon_line = (
        f"- Bon tool       : {bon}/{total} ({_pct(bon, total)})  "
        f"{_gate(bon_ok, '>=90%')}"
    )
    if bon_via_alt:
        bon_line += f" [dont {bon_via_alt} via accepted_alternatives]"
    lines.append(bon_line)
    uuid_tools = {"create_fund_application", "batch_save_esg_criteria"}
    has_uuid_case = any(c.expected_tool in uuid_tools for c in result.cases)
    payload_line = (
        f"- Payload valide : {payload_ok}/{payload_ok_denom} "
        f"({_pct(payload_ok, payload_ok_denom)})"
    )
    if has_uuid_case:
        payload_line += (
            "  [note: cas create_fund_application/batch_save_esg_criteria "
            "requierent un UUID — voir README §Limites]"
        )
    lines.append(payload_line)
    lines.append(
        f"- Subset match   : {subset_ok}/{subset_denom} "
        f"({_pct(subset_ok, subset_denom)})"
    )
    fb_ok = (fallback_n / total <= 0.10) if total else True
    lines.append(
        f"- Fallback texte : {fallback_n}/{total} ({_pct(fallback_n, total)})  "
        f"{_gate(fb_ok, '<=10%')}"
    )
    if error_n:
        lines.append(f"- Erreurs LLM    : {error_n}/{total} ({_pct(error_n, total)})")
    lines.append(f"- Hash golden    : {result.golden_hash[:12]}...")

    fails = [c for c in result.cases if not c.bon_tool]
    if fails:
        lines.append("\n## Echecs detailles")
        for c in fails:
            if c.error:
                lines.append(f"- {c.id} : erreur {c.error}")
            elif c.expected_tool is None:
                lines.append(
                    f"- {c.id} : expected=texte_libre, got={c.got_tool} args={c.got_args}"
                )
            else:
                lines.append(
                    f"- {c.id} : expected={c.expected_tool}, got={c.got_tool}"
                )

    return "\n".join(lines)


def _pct(n: int, d: int) -> str:
    if d == 0:
        return "n/a"
    return f"{(n / d) * 100:.1f}%"


def _gate(ok: bool, label: str) -> str:
    return f"OK {label}" if ok else f"ECHEC {label}"


def baseline_path(result: EvalResult, base_dir: str | Path) -> Path:
    """Construire le chemin du fichier baseline (`<YYYY-MM-DD>_<modele>.json`)."""
    date_short = result.timestamp[:10]
    slug = _slugify_model_id(result.model_id)
    return Path(base_dir) / f"{date_short}_{slug}.json"


def serialize_baseline(result: EvalResult, golden_path: str | Path) -> dict[str, Any]:
    """Serialiser pour le fichier JSON baseline (cf. AC5)."""
    return {
        "metadata": {
            "timestamp": result.timestamp,
            "model_id": result.model_id,
            "golden_hash": result.golden_hash,
            "golden_path": str(golden_path),
        },
        "summary": {
            "total": result.total,
            "bon_tool_rate": result.bon_tool_rate,
            "payload_valide_rate": result.payload_valide_rate,
            "payload_partial_match_rate": result.payload_partial_match_rate,
            "fallback_text_rate": result.fallback_text_rate,
        },
        "cases": [dataclasses.asdict(c) for c in result.cases],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Eval LLM tool-calling (golden set v1).")
    default_golden = Path(__file__).parent / "golden_set_v1.yaml"
    parser.add_argument("--golden", default=str(default_golden), help="Chemin du golden YAML.")
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="Ecrire la baseline JSON dans tests/llm_eval/baselines/.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Limite N premiers cas.")
    parser.add_argument(
        "--cases",
        default=None,
        help="Liste d'ids separes par ',' (ex: case_001,case_005).",
    )
    parser.add_argument(
        "--strict-gate",
        action="store_true",
        help="Exit 1 si bon_tool < 90%% ou fallback > 10%% (cible epic, 1 run). "
             "Par defaut, gate relache aligne sur le test pytest (85%% / 15%%) "
             "pour eviter le bruit de determinisme single-run.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _parse_args(argv)

    only_ids: set[str] | None = None
    if args.cases:
        only_ids = {x.strip() for x in args.cases.split(",") if x.strip()}

    result = run_eval(args.golden, limit=args.limit, only_ids=only_ids)
    report = render_report(result, args.golden)
    print(report)

    if args.save_baseline:
        out_dir = Path(__file__).parent / "baselines"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = baseline_path(result, out_dir)
        out_path.write_text(
            json.dumps(serialize_baseline(result, args.golden), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nBaseline ecrite : {out_path}")

    if args.strict_gate:
        bon_min, fb_max = 0.90, 0.10
    else:
        bon_min, fb_max = 0.85, 0.15
    return 0 if (result.bon_tool_rate >= bon_min and result.fallback_text_rate <= fb_max) else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
