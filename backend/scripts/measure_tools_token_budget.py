"""Mesure du budget tokens (caracteres) des descriptions de tools LangChain.

Story 10.1 — Tool descriptions beton + schemas Pydantic stricts.
Gate AC6 : la variation Y/X doit rester <= +25% par rapport au baseline.

Usage :
    python -m scripts.measure_tools_token_budget [--baseline] [--report PATH]

Sans option : affiche le total courant.
Avec --baseline : ecrit le snapshot dans backend/tools/_tokens_baseline.json.
Avec --report PATH : compare baseline vs courant et ecrit un rapport markdown.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Importer depuis app.graph.tools — le script doit etre lance via
# `cd backend && python -m scripts.measure_tools_token_budget`
from app.graph.tools.application_tools import APPLICATION_TOOLS
from app.graph.tools.esg_tools import ESG_TOOLS
from app.graph.tools.interactive_tools import INTERACTIVE_TOOLS
from app.graph.tools.profiling_tools import PROFILING_TOOLS

# 14 tools du perimetre story 10.1
SCOPE_TOOLS = [
    *INTERACTIVE_TOOLS,
    *PROFILING_TOOLS,
    *ESG_TOOLS,
    *APPLICATION_TOOLS,
]


def measure() -> dict:
    """Retourne un snapshot {tool_name: {description_chars, args_schema_chars}}."""
    snapshot: dict = {"tools": {}, "total_description_chars": 0}
    for tool in SCOPE_TOOLS:
        desc = tool.description or ""
        try:
            schema_repr = json.dumps(tool.args_schema.model_json_schema(), ensure_ascii=False)
        except Exception:
            schema_repr = ""
        snapshot["tools"][tool.name] = {
            "description_chars": len(desc),
            "args_schema_chars": len(schema_repr),
        }
        snapshot["total_description_chars"] += len(desc)
    snapshot["total_args_schema_chars"] = sum(
        e["args_schema_chars"] for e in snapshot["tools"].values()
    )
    snapshot["tools_count"] = len(SCOPE_TOOLS)
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true", help="Ecrire le snapshot baseline.")
    parser.add_argument("--report", type=Path, default=None, help="Chemin du rapport markdown.")
    parser.add_argument(
        "--baseline-path",
        type=Path,
        default=Path("tools") / "_tokens_baseline.json",
        help="Chemin du baseline JSON.",
    )
    parser.add_argument(
        "--gate-pct",
        type=float,
        default=25.0,
        help="Gate strict : variation max en pourcentage (+25%% par defaut).",
    )
    args = parser.parse_args()

    current = measure()

    if args.baseline:
        args.baseline_path.parent.mkdir(parents=True, exist_ok=True)
        args.baseline_path.write_text(
            json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        print(f"Baseline ecrit dans {args.baseline_path}")
        print(f"Total descriptions : {current['total_description_chars']} caracteres")
        print(f"Tools mesures : {current['tools_count']}")
        return 0

    baseline = None
    if args.baseline_path.exists():
        baseline = json.loads(args.baseline_path.read_text(encoding="utf-8"))

    print("=== Mesure tokens descriptions de tools (story 10.1) ===")
    print(f"Tools mesures : {current['tools_count']}")
    print(f"Total descriptions : {current['total_description_chars']} caracteres")

    exit_code = 0
    if baseline is not None:
        before = baseline["total_description_chars"]
        after = current["total_description_chars"]
        delta = after - before
        pct = (delta / before * 100.0) if before > 0 else 0.0
        print(f"Avant : {before} | Apres : {after} | Delta : {delta:+d} ({pct:+.2f}%)")
        if pct > args.gate_pct:
            print(f"GATE FAILED : variation {pct:+.2f}% > +{args.gate_pct}%")
            exit_code = 1
        else:
            print(f"GATE OK : variation {pct:+.2f}% <= +{args.gate_pct}%")

    if args.report is not None:
        lines = [
            "# Rapport tokens — Story 10.1",
            "",
            f"Tools mesures : **{current['tools_count']}**",
            "",
            "## Total descriptions",
            "",
        ]
        if baseline is not None:
            before = baseline["total_description_chars"]
            after = current["total_description_chars"]
            delta = after - before
            pct = (delta / before * 100.0) if before > 0 else 0.0
            lines.extend([
                f"- Avant (baseline) : {before} caracteres",
                f"- Apres (courant)  : {after} caracteres",
                f"- Variation        : {delta:+d} caracteres ({pct:+.2f}%)",
                f"- Gate `<= +{args.gate_pct}%` : {'OK' if pct <= args.gate_pct else 'FAILED'}",
                "",
            ])
        else:
            lines.append(f"Total : {current['total_description_chars']} caracteres")
            lines.append("")

        lines.append("## Detail par tool")
        lines.append("")
        lines.append("| Tool | Avant | Apres | Delta |")
        lines.append("|---|---|---|---|")
        for name, entry in sorted(current["tools"].items()):
            after = entry["description_chars"]
            before = baseline["tools"].get(name, {}).get("description_chars") if baseline else None
            if before is None:
                lines.append(f"| {name} | n/a | {after} | n/a |")
            else:
                delta = after - before
                lines.append(f"| {name} | {before} | {after} | {delta:+d} |")
        lines.append("")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text("\n".join(lines), encoding="utf-8")
        print(f"Rapport ecrit dans {args.report}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
