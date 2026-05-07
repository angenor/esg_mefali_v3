"""F23 — Tests unitaires ``app.modules.skills.seed`` (T038)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.skill import Skill, SkillStatus
from app.models.user import User
from app.modules.skills.seed import SEED_SKILL_NAMES, seed_skills


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


class TestSeedSkills:
    async def test_seed_creates_three_published_skills(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        await seed_skills(db_session, default_creator_id=admin.id)
        result = await db_session.execute(select(Skill))
        items = list(result.scalars().all())
        assert len(items) == 3
        names = {s.name for s in items}
        assert names == set(SEED_SKILL_NAMES)
        # Toutes en published.
        for s in items:
            assert s.status == SkillStatus.PUBLISHED.value

    async def test_seed_idempotent(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        await seed_skills(db_session, default_creator_id=admin.id)
        await seed_skills(db_session, default_creator_id=admin.id)
        result = await db_session.execute(select(Skill))
        items = list(result.scalars().all())
        assert len(items) == 3  # toujours 3, pas 6

    async def test_seed_names_match_constants(self) -> None:
        assert "skill_esg_diagnostic" in SEED_SKILL_NAMES
        assert "skill_score_gcf" in SEED_SKILL_NAMES
        assert "skill_dossier_gcf_via_boad" in SEED_SKILL_NAMES
