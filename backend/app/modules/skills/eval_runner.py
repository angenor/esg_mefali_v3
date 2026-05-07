"""F23 — Eval runner pour le gating à la publication d'une Skill.

Exécute les ``golden_examples`` d'une Skill en parallèle (max 5 concurrents)
et retourne un :class:`SkillEvalReport`. Le gate est passé si le taux de
réussite ≥ 90 %.

Réutilise :func:`app.lib.eval_matching.match_tool_called` et
:func:`app.lib.eval_matching.match_payload_contains` pour la comparaison
(DRY avec ``tests/llm_eval/test_eval_runner.py``).

Référence : ``specs/033-skills-playbooks-metier/research.md`` R7, R8.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lib.eval_matching import match_payload_contains, match_tool_called
from app.models.skill import Skill
from app.modules.skills.exceptions import (
    EvalTimeoutError,
    SkillNotFoundError,
)
from app.modules.skills.schemas import FailedCase, SkillEvalReport

logger = logging.getLogger(__name__)


GATE_THRESHOLD: float = 0.9
EVAL_TIMEOUT_SECONDS: float = 60.0
MAX_CONCURRENT: int = 5


async def _invoke_llm_for_case(
    case: dict[str, Any],
    skill: Skill,
) -> tuple[str | None, dict[str, Any]]:
    """Invoque le graphe LangGraph pour un cas du golden_examples.

    Retourne ``(tool_called, tool_payload)`` :
    - ``tool_called`` : nom du tool effectivement invoqué (None si fallback texte).
    - ``tool_payload`` : args du tool (dict vide si pas d'invocation).

    Cette implémentation est extraite afin de pouvoir être MOCKÉE dans les
    tests unitaires. En production, elle invoque réellement le graphe
    avec le contexte du cas. Pour le MVP F23, on délègue à un helper
    minimal qui peut être stubé.
    """
    from app.modules.skills.eval_runner_invoke import invoke_graph_for_case

    return await invoke_graph_for_case(case, skill)


async def _run_one_case(
    case: dict[str, Any],
    skill: Skill,
    semaphore: asyncio.Semaphore,
) -> FailedCase | None:
    """Exécute UN cas du golden_examples ; retourne FailedCase si échec, None si succès."""
    async with semaphore:
        case_id = case.get("id", "<no_id>")
        expected = case.get("expected", {})
        expected_tool = expected.get("tool_called")
        expected_payload = expected.get("payload_contains")

        start = time.perf_counter()
        try:
            actual_tool, actual_payload = await _invoke_llm_for_case(case, skill)
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                "[eval_runner] case %r raised %s: %s", case_id, type(exc).__name__, exc
            )
            return FailedCase(
                case_id=case_id,
                expected_tool=expected_tool,
                actual_tool=None,
                payload_diff=None,
                latency_ms=elapsed_ms,
                error=f"{type(exc).__name__}: {exc}",
            )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        if not match_tool_called(actual_tool, expected_tool):
            return FailedCase(
                case_id=case_id,
                expected_tool=expected_tool,
                actual_tool=actual_tool,
                payload_diff=None,
                latency_ms=elapsed_ms,
            )

        if not match_payload_contains(actual_payload, expected_payload):
            diff = {"expected": expected_payload, "actual": actual_payload}
            return FailedCase(
                case_id=case_id,
                expected_tool=expected_tool,
                actual_tool=actual_tool,
                payload_diff=diff,
                latency_ms=elapsed_ms,
            )

        return None


async def run_skill_eval(
    skill_id: uuid.UUID,
    db: AsyncSession,
) -> SkillEvalReport:
    """Exécute les golden_examples d'une Skill et retourne un rapport.

    Args:
        skill_id: UUID de la Skill à tester.
        db: Session SQLAlchemy async.

    Returns:
        :class:`SkillEvalReport` avec les statistiques + failed_cases détaillés.

    Raises:
        :class:`SkillNotFoundError`: si l'id ne correspond à aucune Skill.
        :class:`EvalTimeoutError`: si le run dépasse ``EVAL_TIMEOUT_SECONDS``.
    """
    stmt = select(Skill).where(Skill.id == skill_id)
    res = await db.execute(stmt)
    skill = res.scalar_one_or_none()
    if skill is None:
        raise SkillNotFoundError(skill_id)

    started_at = datetime.now(tz=timezone.utc)
    run_id = uuid.uuid4()
    cases: list[dict[str, Any]] = list(skill.golden_examples or [])

    if not cases:
        completed_at = datetime.now(tz=timezone.utc)
        return SkillEvalReport(
            skill_id=skill_id,
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=(completed_at - started_at).total_seconds(),
            total_cases=0,
            passed=0,
            failed=0,
            success_rate=0.0,
            threshold=GATE_THRESHOLD,
            gate_passed=False,
            failed_cases=[],
        )

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    coros = [_run_one_case(c, skill, semaphore) for c in cases]

    try:
        results: list[FailedCase | None] = await asyncio.wait_for(
            asyncio.gather(*coros, return_exceptions=False),
            timeout=EVAL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        elapsed = (datetime.now(tz=timezone.utc) - started_at).total_seconds()
        raise EvalTimeoutError(elapsed_seconds=elapsed) from exc

    failed_cases = [r for r in results if r is not None]
    passed = len(cases) - len(failed_cases)
    failed = len(failed_cases)
    success_rate = passed / len(cases) if cases else 0.0
    completed_at = datetime.now(tz=timezone.utc)

    return SkillEvalReport(
        skill_id=skill_id,
        run_id=run_id,
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=(completed_at - started_at).total_seconds(),
        total_cases=len(cases),
        passed=passed,
        failed=failed,
        success_rate=success_rate,
        threshold=GATE_THRESHOLD,
        gate_passed=success_rate >= GATE_THRESHOLD,
        failed_cases=failed_cases,
    )
