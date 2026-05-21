"""F045 T009 - Test seed du skill ``skill_match_project_funds`` (F23).

Verifie :
- Presence du skill en BDD apres seed.
- 4 golden_examples FR (US1-US4).
- tool_whitelist contient au moins 12 tools (8 projet + match_funds_for_project,
  + 3 sources globaux + visualization, suivant R8).
- activation_rules valides : intent_keywords FR, priority 80.
- status initial = draft (gating F23 standard).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill, SkillStatus
from app.models.user import User
from app.modules.skills.seed import seed_skills


async def _make_admin(db: AsyncSession) -> User:
    admin = User(
        email=f"admin-{uuid.uuid4().hex[:6]}@mefali-system",
        hashed_password="x",
        full_name="Seed Admin",
        company_name="Mefali System",
        account_id=None,
        role="ADMIN",
    )
    db.add(admin)
    await db.flush()
    return admin


@pytest.mark.asyncio
async def test_skill_match_project_funds_seeded(
    db_session: AsyncSession,
) -> None:
    admin = await _make_admin(db_session)
    await seed_skills(db_session, default_creator_id=admin.id)
    await db_session.flush()

    result = await db_session.execute(
        select(Skill).where(Skill.name == "skill_match_project_funds")
    )
    skill = result.scalar_one_or_none()
    assert skill is not None, "skill_match_project_funds doit etre seede"
    assert skill.status == SkillStatus.DRAFT.value
    assert len(skill.golden_examples) == 4
    # Tools whitelist non vide et contient match_funds_for_project
    assert "match_funds_for_project" in skill.tool_whitelist
    # Au moins 12 tools (cf R8 : 21 visee, minimum pragmatique 12)
    assert len(skill.tool_whitelist) >= 12
    # Activation rules
    assert isinstance(skill.activation_rules, dict)
    assert "intent_keywords" in skill.activation_rules
    keywords = skill.activation_rules["intent_keywords"]
    assert any(k.lower() in {"matching", "fonds", "financement", "gcf"} for k in keywords)
    assert skill.activation_rules.get("priority") == 80


@pytest.mark.asyncio
async def test_seed_skills_idempotent_with_match_project_funds(
    db_session: AsyncSession,
) -> None:
    admin = await _make_admin(db_session)
    first = await seed_skills(db_session, default_creator_id=admin.id)
    await db_session.flush()
    second = await seed_skills(db_session, default_creator_id=admin.id)
    await db_session.flush()
    assert first >= 1
    assert second == 0
