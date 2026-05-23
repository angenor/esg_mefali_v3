"""T091 — Eval F23 du skill ``skill_project_esg_assessment``.

Valide SC-008 : le gating à la publication (≥ 90 % de réussite sur les
4 golden examples US1-US4). Les invocations LLM réelles sont mockées
pour rester déterministes en CI ; la publication finale (T092) reste
manuelle si l'eval live (LLM_API_KEY configurée) est requise.

Référence : ``app/modules/skills/eval_runner.py`` ; ``backend/app/modules/
skills/seed.py`` (``skill_project_esg_assessment`` golden_examples).
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.skill import Skill, SkillStatus
from app.models.user import User
from app.modules.skills.eval_runner import GATE_THRESHOLD, run_skill_eval
from app.modules.skills.seed import seed_skills


pytestmark = pytest.mark.asyncio


async def _ensure_admin(db_session) -> User:
    admin = (
        await db_session.execute(
            select(User).where(User.role == "ADMIN").limit(1)
        )
    ).scalar_one_or_none()
    if admin is not None:
        return admin
    u = User(
        email=f"admin-{uuid.uuid4().hex[:6]}@mefali",
        hashed_password="x",
        full_name="Admin Test",
        company_name="Mefali",
        role="ADMIN",
        account_id=None,
    )
    db_session.add(u)
    await db_session.flush()
    return u


async def _get_skill(db_session) -> Skill:
    return (
        await db_session.execute(
            select(Skill).where(Skill.name == "skill_project_esg_assessment")
        )
    ).scalar_one()


class TestSkillProjectEsgAssessment:
    """Eval gating à la publication du skill F047 (SC-008 ≥ 90 %)."""

    async def test_skill_seeded_as_draft(self, db_session) -> None:
        """Le skill est seedé en `status=draft` (DRAFT_ONLY) — gating eval
        ≥ 90 % attendu avant publication (cf. seed.py + spec 047 US4)."""
        await _ensure_admin(db_session)
        await seed_skills(db_session)
        skill = await _get_skill(db_session)
        assert skill.status == SkillStatus.DRAFT.value
        assert skill.name == "skill_project_esg_assessment"

    async def test_skill_has_four_golden_examples(self, db_session) -> None:
        """Le skill doit fournir au moins 4 golden examples (US1-US4)."""
        await _ensure_admin(db_session)
        await seed_skills(db_session)
        skill = await _get_skill(db_session)
        examples = skill.golden_examples or []
        assert len(examples) >= 4, (
            "Au moins 4 golden examples requis (un par user story US1-US4)."
        )
        # Vérifie l'ID format `project-esg-usX` documenté dans seed.py
        ids = {ex.get("id") for ex in examples}
        assert "project-esg-us1" in ids
        assert "project-esg-us2" in ids
        assert "project-esg-us3" in ids
        assert "project-esg-us4" in ids

    async def test_eval_passes_gate_when_llm_returns_expected_tools(
        self, db_session,
    ) -> None:
        """Mock LLM → 4/4 cas verts → success_rate = 1.0 ≥ 0.90 → gate ✓.

        Valide la mécanique du gating ; l'eval live nécessite LLM_API_KEY.
        """
        await _ensure_admin(db_session)
        await seed_skills(db_session)
        skill = await _get_skill(db_session)

        # Construit la map (case_id → expected tool) depuis les golden_examples
        expected_by_id: dict[str, str] = {
            ex["id"]: ex["expected"]["tool_called"]
            for ex in skill.golden_examples
        }

        async def fake_invoke(case: dict, _skill: Skill) -> tuple[str | None, dict[str, Any]]:
            return (expected_by_id.get(case.get("id"), None), {})

        with patch(
            "app.modules.skills.eval_runner._invoke_llm_for_case",
            side_effect=fake_invoke,
        ):
            report = await run_skill_eval(skill.id, db_session)

        assert report.total_cases == len(expected_by_id)
        assert report.passed == report.total_cases
        assert report.success_rate >= GATE_THRESHOLD
        assert report.gate_passed is True

    async def test_eval_fails_gate_when_llm_misses_one_case(
        self, db_session,
    ) -> None:
        """Mock LLM → 3/4 cas verts → success_rate = 0.75 < 0.90 → gate ✗.

        Vérifie que le gate refuse une eval insuffisante (publication bloquée).
        """
        await _ensure_admin(db_session)
        await seed_skills(db_session)
        skill = await _get_skill(db_session)
        examples = skill.golden_examples or []
        wrong_idx = {examples[0]["id"]}

        async def partial(case: dict, _skill: Skill) -> tuple[str | None, dict[str, Any]]:
            if case.get("id") in wrong_idx:
                return ("wrong_tool", {})
            return (case["expected"]["tool_called"], {})

        with patch(
            "app.modules.skills.eval_runner._invoke_llm_for_case",
            side_effect=partial,
        ):
            report = await run_skill_eval(skill.id, db_session)

        # 3 cas verts sur 4 → 0.75 < 0.90
        assert report.success_rate < GATE_THRESHOLD
        assert report.gate_passed is False
        assert report.failed >= 1
        # Vérifie qu'on identifie bien l'unique cas en échec
        assert any(
            fc.case_id in wrong_idx for fc in report.failed_cases
        )
