"""F23 — Tests intégration ``apply_skills_to_node`` (T019-T021 simplifiés).

On teste le helper d'intégration directement sans invoquer le graphe complet,
ce qui est suffisant pour valider la sémantique attendue par les nœuds.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.graph.skill_integration import apply_skills_to_node
from app.graph.state import ConversationState
from app.models.skill import Skill, SkillDomain, SkillStatus
from app.models.user import User


pytestmark = pytest.mark.asyncio


async def _seed_admin(db_session) -> User:
    a = User(
        email=f"a-{uuid.uuid4().hex[:6]}@m.com",
        hashed_password="x",
        full_name="A",
        company_name="Mefali",
        role="ADMIN",
        account_id=None,
    )
    db_session.add(a)
    await db_session.flush()
    return a


async def _seed_skill(db_session, *, name: str, page: str, tools: list[str]) -> Skill:
    admin = await _seed_admin(db_session)
    s = Skill(
        name=name,
        domain=SkillDomain.DIAGNOSTIC_ESG.value,
        prompt_expert=f"Tu es expert {name}, réponds en français pour les PME UEMOA.",
        procedure="1) X. 2) Y. 3) Z. (procédure de test)",
        tool_whitelist=tools,
        sources=[],
        activation_rules={"page_slugs": [page]},
        golden_examples=[],
        status=SkillStatus.PUBLISHED.value,
        created_by=admin.id,
    )
    db_session.add(s)
    await db_session.flush()
    return s


def _make_state(**overrides) -> ConversationState:
    base: dict = {
        "messages": [],
        "user_id": "u1",
        "user_profile": None,
        "context_memory": [],
        "profile_updates": None,
        "profiling_instructions": None,
        "document_upload": None,
        "document_analysis_summary": None,
        "has_document": False,
        "esg_assessment": None,
        "_route_esg": False,
        "carbon_data": None,
        "_route_carbon": False,
        "financing_data": None,
        "_route_financing": False,
        "application_data": None,
        "_route_application": False,
        "credit_data": None,
        "_route_credit": False,
        "action_plan_data": None,
        "_route_action_plan": False,
        "tool_call_count": 0,
        "active_module": None,
        "active_module_data": None,
        "current_page": None,
        "guidance_stats": None,
        "active_entities": None,
    }
    base.update(overrides)
    return base  # type: ignore[return-value]


def _tool(name: str):
    return SimpleNamespace(name=name)


class TestApplySkillsToNode:
    async def test_no_db_returns_base(self, db_session) -> None:
        state = _make_state()
        out_prompt, out_tools, snap = await apply_skills_to_node(
            base_prompt="BASE",
            base_tools=[_tool("a")],
            state=state,
            intent=None,
            db=None,
        )
        assert out_prompt == "BASE"
        assert [t.name for t in out_tools] == ["a"]
        assert snap is None

    async def test_skill_loaded_and_fused(self, db_session) -> None:
        await _seed_skill(
            db_session,
            name="skill_esg_diagnostic",
            page="/esg",
            tools=["update_company_profile"],
        )
        state = _make_state(current_page="/esg")
        out_prompt, out_tools, snap = await apply_skills_to_node(
            base_prompt="BASE_PROMPT",
            base_tools=[_tool("update_company_profile"), _tool("other")],
            state=state,
            intent="diagnostic ESG",
            db=db_session,
        )
        assert "## SKILL ACTIVE" in out_prompt
        assert "skill_esg_diagnostic" in out_prompt
        # Intersection : seul update_company_profile reste
        assert [t.name for t in out_tools] == ["update_company_profile"]
        assert snap is not None
        assert snap[0]["name"] == "skill_esg_diagnostic"

    async def test_no_skills_match_returns_base(self, db_session) -> None:
        await _seed_skill(
            db_session,
            name="skill_unrelated",
            page="/applications",
            tools=["create_fund_application"],
        )
        state = _make_state(current_page="/no_match_page")
        out_prompt, out_tools, snap = await apply_skills_to_node(
            base_prompt="BASE",
            base_tools=[_tool("a")],
            state=state,
            intent=None,
            db=db_session,
        )
        assert out_prompt == "BASE"
        assert [t.name for t in out_tools] == ["a"]
        assert snap is None

    async def test_load_failure_falls_back_safely(self, db_session) -> None:
        state = _make_state(current_page="/esg")

        async def boom(**kwargs):
            raise RuntimeError("DB down")

        with patch(
            "app.graph.skill_integration.load_skills_for_context",
            side_effect=boom,
        ):
            out_prompt, out_tools, snap = await apply_skills_to_node(
                base_prompt="BASE",
                base_tools=[_tool("a")],
                state=state,
                intent=None,
                db=db_session,
            )
        # Pas d'erreur propagée, comportement identique à pas de skills.
        assert out_prompt == "BASE"
        assert snap is None
