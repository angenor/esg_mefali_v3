"""Audit du filtrage de tools par contexte (story 10.2 — AC8).

Lit `tool_call_logs` et imprime un rapport markdown agregeant :
- nombre de tours par noeud LangGraph,
- moyenne et max de `len(tools_offered)`,
- gate : 0 conversation avec un tour > MAX_TOOLS_PER_TURN.

Usage :
    python backend/scripts/audit_tools_offered.py
    python backend/scripts/audit_tools_offered.py --conversations 100

Code de sortie :
    0 — gate respectee.
    1 — au moins une conversation a un tour > 10 tools (gate violee).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import defaultdict
from pathlib import Path

# Permettre l'execution directe depuis backend/.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select  # noqa: E402

from app.core.database import async_session_factory  # noqa: E402
from app.graph.tool_selector_config import MAX_TOOLS_PER_TURN  # noqa: E402
from app.models.tool_call_log import ToolCallLog  # noqa: E402

REPORT_PATH = ROOT / "tools" / "_tools_offered_report.md"


async def _fetch_logs(limit_conversations: int) -> list[ToolCallLog]:
    async with async_session_factory() as db:
        # Recuperer les N derniers conversation_id distincts par MAX(created_at)
        # — UUID v4 n'est pas ordonnable temporellement.
        recent_convs_q = (
            select(ToolCallLog.conversation_id)
            .where(ToolCallLog.conversation_id.is_not(None))
            .group_by(ToolCallLog.conversation_id)
            .order_by(func.max(ToolCallLog.created_at).desc())
            .limit(limit_conversations)
        )
        result = await db.execute(recent_convs_q)
        conv_ids = [row[0] for row in result.all()]

        if not conv_ids:
            return []

        logs_q = (
            select(ToolCallLog)
            .where(ToolCallLog.conversation_id.in_(conv_ids))
            .order_by(ToolCallLog.created_at.asc())
        )
        result = await db.execute(logs_q)
        return list(result.scalars().all())


def _aggregate(logs: list[ToolCallLog]) -> tuple[dict[str, dict], int]:
    """Aggrege par node_name. Retourne (stats, violations).

    Chaque ligne tool_call_log avec `tools_offered` non vide compte comme un
    tour distinct : deduper par (conv_id, tools_offered) elidait les tours
    successifs ayant le meme set, masquant des violations possibles du gate.
    On dedupe uniquement par log.id pour eviter les doubles comptages
    accidentels en cas de logs identiques.
    """
    by_node: dict[str, list[int]] = defaultdict(list)
    violations = 0
    seen_ids: set = set()
    for log in logs:
        if not log.tools_offered:
            continue
        if log.id in seen_ids:
            continue
        seen_ids.add(log.id)
        size = len(log.tools_offered)
        by_node[log.node_name].append(size)
        if size > MAX_TOOLS_PER_TURN:
            violations += 1

    stats: dict[str, dict] = {}
    for node, sizes in by_node.items():
        stats[node] = {
            "turns": len(sizes),
            "avg": sum(sizes) / len(sizes) if sizes else 0,
            "max": max(sizes) if sizes else 0,
        }
    return stats, violations


def _render_markdown(stats: dict[str, dict], violations: int) -> str:
    lines = [
        "# Rapport audit tools_offered (story 10.2)",
        "",
        f"Borne LLM par tour : MAX_TOOLS_PER_TURN={MAX_TOOLS_PER_TURN}",
        "",
        "| Noeud | Tours | Moy tools_offered | Max |",
        "| --- | --- | --- | --- |",
    ]
    for node in sorted(stats):
        s = stats[node]
        lines.append(f"| {node} | {s['turns']} | {s['avg']:.1f} | {s['max']} |")
    lines.append("")
    if violations == 0:
        lines.append(f"Conversations > {MAX_TOOLS_PER_TURN} tools : 0 (gate OK)")
    else:
        lines.append(
            f"Conversations > {MAX_TOOLS_PER_TURN} tools : {violations} (GATE VIOLEE)"
        )
    return "\n".join(lines) + "\n"


async def main() -> int:
    parser = argparse.ArgumentParser(description="Audit tools_offered")
    parser.add_argument("--conversations", type=int, default=50)
    args = parser.parse_args()

    logs = await _fetch_logs(args.conversations)
    stats, violations = _aggregate(logs)
    report = _render_markdown(stats, violations)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nRapport ecrit dans {REPORT_PATH}")

    return 0 if violations == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
