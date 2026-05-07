"""F23 — Tests unitaires ``app.modules.skills.eval_runner`` (T030)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date
from unittest.mock import patch

import pytest

from app.models.skill import Skill, SkillDomain, SkillStatus
from app.models.user import User
from app.modules.skills.eval_runner import (
    EVAL_TIMEOUT_SECONDS,
    GATE_THRESHOLD,
    run_skill_eval,
)
from app.modules.skills.exceptions import (
    EvalTimeoutError,
    SkillNotFoundError,
)


pytestmark = pytest.mark.asyncio


async def _seed_admin(db_session) -> User:
    a = User(
        email=f"admin-{uuid.uuid4().hex[:6]}@m.com",
        hashed_password="x",
        full_name="A",
        company_name="Mefali",
        role="ADMIN",
        account_id=None,
    )
    db_session.add(a)
    await db_session.flush()
    return a


def _golden(case_id: str, expected_tool: str, payload: dict | None = None) -> dict:
    return {
        "id": case_id,
        "category": "diagnostic_esg",
        "context": {"current_page": "/esg", "active_module": "esg_scoring"},
        "user_message": f"Test message {case_id}",
        "expected": {
            "tool_called": expected_tool,
            "payload_contains": payload or {},
        },
    }


async def _seed_skill(
    db_session,
    *,
    name: str = "skill_test",
    golden_examples: list[dict] | None = None,
) -> Skill:
    admin = await _seed_admin(db_session)
    s = Skill(
        name=name,
        domain=SkillDomain.DIAGNOSTIC_ESG.value,
        prompt_expert="Tu es un expert ESG ouest-africain.",
        procedure="1) Demander secteur. 2) Calculer score. 3) Restituer.",
        tool_whitelist=["update_company_profile"],
        sources=[],
        activation_rules={"page_slugs": ["/esg"]},
        golden_examples=golden_examples or [],
        status=SkillStatus.DRAFT.value,
        created_by=admin.id,
    )
    db_session.add(s)
    await db_session.flush()
    return s


class TestRunSkillEvalSuccess:
    """Cas de succès (mock LLM retourne le bon tool)."""

    async def test_all_passing_gate_passed(self, db_session) -> None:
        cases = [_golden(f"c{i}", "update_company_profile") for i in range(5)]
        skill = await _seed_skill(db_session, golden_examples=cases)

        async def fake_run(case: dict, _skill: Skill) -> tuple[str | None, dict]:
            return ("update_company_profile", {})

        with patch(
            "app.modules.skills.eval_runner._invoke_llm_for_case",
            side_effect=fake_run,
        ):
            report = await run_skill_eval(skill.id, db_session)
        assert report.total_cases == 5
        assert report.passed == 5
        assert report.success_rate == 1.0
        assert report.gate_passed is True
        assert report.threshold == GATE_THRESHOLD


class TestRunSkillEvalFailure:
    """Cas où le gate échoue."""

    async def test_below_threshold(self, db_session) -> None:
        cases = [_golden(f"c{i}", "update_company_profile") for i in range(5)]
        skill = await _seed_skill(db_session, golden_examples=cases)

        call_idx = {"n": 0}

        async def partial_fail(case: dict, _skill: Skill) -> tuple[str | None, dict]:
            call_idx["n"] += 1
            if call_idx["n"] <= 4:
                return ("update_company_profile", {})
            return ("wrong_tool", {})

        with patch(
            "app.modules.skills.eval_runner._invoke_llm_for_case",
            side_effect=partial_fail,
        ):
            report = await run_skill_eval(skill.id, db_session)
        assert report.passed == 4
        assert report.failed == 1
        assert report.success_rate == 0.8
        assert report.gate_passed is False
        assert len(report.failed_cases) == 1


class TestRunSkillEvalEdgeCases:
    """Edge cases : skill inconnue, payload diff, mauvais tool."""

    async def test_unknown_skill_raises(self, db_session) -> None:
        with pytest.raises(SkillNotFoundError):
            await run_skill_eval(uuid.uuid4(), db_session)

    async def test_zero_cases_gate_failed(self, db_session) -> None:
        skill = await _seed_skill(db_session, golden_examples=[])
        report = await run_skill_eval(skill.id, db_session)
        assert report.total_cases == 0
        assert report.gate_passed is False

    async def test_payload_diff_detected(self, db_session) -> None:
        cases = [
            _golden("c1", "update_company_profile", {"sector": "agriculture"}),
        ] * 5
        # Re-id chaque cas (sinon doublon)
        for i, c in enumerate(cases):
            c["id"] = f"c{i}"
        skill = await _seed_skill(db_session, golden_examples=cases)

        async def wrong_payload(case, _skill) -> tuple[str | None, dict]:
            return ("update_company_profile", {"sector": "transport"})

        with patch(
            "app.modules.skills.eval_runner._invoke_llm_for_case",
            side_effect=wrong_payload,
        ):
            report = await run_skill_eval(skill.id, db_session)
        assert report.failed == 5
        assert all(fc.payload_diff is not None for fc in report.failed_cases)

    async def test_llm_raises_recorded_as_failed(self, db_session) -> None:
        cases = [_golden(f"c{i}", "update_company_profile") for i in range(5)]
        skill = await _seed_skill(db_session, golden_examples=cases)

        async def boom(case, _skill):
            raise RuntimeError("LLM down")

        with patch(
            "app.modules.skills.eval_runner._invoke_llm_for_case",
            side_effect=boom,
        ):
            report = await run_skill_eval(skill.id, db_session)
        assert report.failed == 5
        # Erreur capturée dans error
        assert all(fc.error is not None for fc in report.failed_cases)
