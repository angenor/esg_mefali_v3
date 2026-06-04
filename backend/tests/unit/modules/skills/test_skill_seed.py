"""F23 — Tests unitaires ``app.modules.skills.seed`` (T038)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.skill import Skill, SkillStatus
from app.models.user import User
from app.modules.skills.seed import (
    SEED_SKILL_NAMES,
    _build_seeds,
    seed_skills,
    sync_seed_tool_whitelists,
)


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
    async def test_seed_creates_all_skills_with_expected_status(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        await seed_skills(db_session, default_creator_id=admin.id)
        result = await db_session.execute(select(Skill))
        items = list(result.scalars().all())
        # 5 skills seedées : 3 publiées (MVP) + 2 draft (F045/F047, gating eval).
        assert len(items) == len(SEED_SKILL_NAMES) == 5
        names = {s.name for s in items}
        assert names == set(SEED_SKILL_NAMES)
        published = {s.name for s in items if s.status == SkillStatus.PUBLISHED.value}
        draft = {s.name for s in items if s.status == SkillStatus.DRAFT.value}
        assert published == {"skill_esg_diagnostic", "skill_score_gcf", "skill_dossier_gcf_via_boad"}
        assert draft == {"skill_match_project_funds", "skill_project_esg_assessment"}

    async def test_seed_idempotent(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        await seed_skills(db_session, default_creator_id=admin.id)
        await seed_skills(db_session, default_creator_id=admin.id)
        result = await db_session.execute(select(Skill))
        items = list(result.scalars().all())
        assert len(items) == 5  # toujours 5, pas 10

    async def test_seed_names_match_constants(self) -> None:
        assert "skill_esg_diagnostic" in SEED_SKILL_NAMES
        assert "skill_score_gcf" in SEED_SKILL_NAMES
        assert "skill_dossier_gcf_via_boad" in SEED_SKILL_NAMES


class TestDiscoveryToolsWhitelisted:
    """051 — Les skills des contextes dossier/financement doivent autoriser les
    tools de découverte/statut en LECTURE SEULE. Sinon l'intersection F23
    (`select_tools_with_skills`) les masque et « où en est mon dossier ? » échoue
    quand un de ces skills est actif (en complément de la protection générique
    SKILL_PROTECTED_READONLY_TOOLS)."""

    _DISCOVERY = {"list_applications", "get_application_checklist"}

    async def test_dossier_and_score_skills_whitelist_discovery_tools(self) -> None:
        seeds = {s["name"]: s for s in _build_seeds(uuid.uuid4())}
        for name in ("skill_dossier_gcf_via_boad", "skill_score_gcf"):
            wl = set(seeds[name]["tool_whitelist"])
            assert self._DISCOVERY <= wl, (
                f"{name} ne whiteliste pas les tools de découverte : {wl}"
            )

    async def test_dossier_skill_keeps_existing_whitelist_tools(self) -> None:
        """Anti-régression : l'ajout n'enlève pas create_fund_application."""
        seeds = {s["name"]: s for s in _build_seeds(uuid.uuid4())}
        wl = set(seeds["skill_dossier_gcf_via_boad"]["tool_whitelist"])
        assert "create_fund_application" in wl

    async def test_sync_updates_existing_skill_whitelist_idempotent(self, db_session) -> None:
        """sync_seed_tool_whitelists met à jour les rows DÉJÀ seedées (seed_skills
        étant insert-only) et est idempotent."""
        admin = await _seed_admin(db_session)
        await seed_skills(db_session, default_creator_id=admin.id)

        # Simule une row existante avec un whitelist obsolète (pré-051).
        skill = (
            await db_session.execute(
                select(Skill).where(Skill.name == "skill_dossier_gcf_via_boad")
            )
        ).scalar_one()
        skill.tool_whitelist = ["create_fund_application", "update_company_profile", "get_company_profile"]
        await db_session.flush()

        updated = await sync_seed_tool_whitelists(db_session)
        assert updated >= 1

        refreshed = (
            await db_session.execute(
                select(Skill).where(Skill.name == "skill_dossier_gcf_via_boad")
            )
        ).scalar_one()
        assert {"list_applications", "get_application_checklist"} <= set(refreshed.tool_whitelist)

        # Idempotence : un 2e appel ne modifie plus rien.
        assert await sync_seed_tool_whitelists(db_session) == 0
