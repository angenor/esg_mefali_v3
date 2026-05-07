"""F23 — Tests unitaires ``app.graph.skill_loader`` (T014, US1).

Vérifie le score de spécificité multi-critères et la sélection top-2.

Référence : ``specs/033-skills-playbooks-metier/research.md`` R1.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from app.graph.skill_loader import (
    _specificity_score,
    load_skills_for_context,
)
from app.models.skill import Skill, SkillDomain, SkillStatus
from app.models.user import User


pytestmark = pytest.mark.asyncio


async def _seed_admin(db_session) -> User:
    admin = User(
        email=f"admin-{uuid.uuid4().hex[:6]}@m.com",
        hashed_password="x",
        full_name="Admin",
        company_name="Mefali",
        role="ADMIN",
        account_id=None,
    )
    db_session.add(admin)
    await db_session.flush()
    return admin


def _make_skill(
    *,
    name: str,
    domain: str,
    activation_rules: dict,
    status: str = SkillStatus.PUBLISHED.value,
    valid_to: date | None = None,
    created_by: uuid.UUID,
) -> Skill:
    return Skill(
        name=name,
        domain=domain,
        prompt_expert=f"Prompt {name}",
        procedure=f"Proc {name}",
        tool_whitelist=["create_fund_application"],
        sources=[],
        activation_rules=activation_rules,
        golden_examples=[],
        status=status,
        valid_to=valid_to,
        created_by=created_by,
    )


class TestSpecificityScore:
    """Vérifie le calcul du score de spécificité (helper privé)."""

    def test_offer_id_match_scores_4(self) -> None:
        offer_id = str(uuid.uuid4())
        skill = type("S", (), {"activation_rules": {"offer_id": offer_id}})()
        score = _specificity_score(skill, {"offer_id": offer_id})
        assert score >= 4.0

    def test_fund_intermediary_combo_scores_3(self) -> None:
        fund = str(uuid.uuid4())
        inter = str(uuid.uuid4())
        skill = type(
            "S",
            (),
            {
                "activation_rules": {
                    "fund_id": fund,
                    "intermediary_id": inter,
                }
            },
        )()
        score = _specificity_score(
            skill, {"fund_id": fund, "intermediary_id": inter}
        )
        # +3 (combo) + 2 (fund_id seul) + 2 (intermediary seul) = 7
        assert score >= 3.0

    def test_page_slug_match_scores_1(self) -> None:
        skill = type(
            "S", (), {"activation_rules": {"page_slugs": ["/esg"]}}
        )()
        score = _specificity_score(skill, {"page_slug": "/esg"})
        assert score >= 1.0

    def test_intent_keywords_scores_05(self) -> None:
        skill = type(
            "S", (), {"activation_rules": {"intent_keywords": ["GCF"]}}
        )()
        score = _specificity_score(skill, {"intent": "Je cherche un fonds GCF"})
        assert score >= 0.5

    def test_no_match_returns_zero(self) -> None:
        skill = type(
            "S", (), {"activation_rules": {"page_slugs": ["/other"]}}
        )()
        score = _specificity_score(skill, {"page_slug": "/esg"})
        assert score == 0


class TestLoadSkillsForContext:
    """Vérifie la sélection contextuelle (DB → top 2)."""

    async def test_page_slug_match(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        s = _make_skill(
            name="skill_esg_diagnostic",
            domain=SkillDomain.DIAGNOSTIC_ESG.value,
            activation_rules={"page_slugs": ["/esg"]},
            created_by=admin.id,
        )
        db_session.add(s)
        await db_session.flush()

        result = await load_skills_for_context(
            page_slug="/esg",
            active_module=None,
            intent=None,
            offer_id=None,
            fund_id=None,
            intermediary_id=None,
            db=db_session,
        )
        names = [r.name for r in result]
        assert "skill_esg_diagnostic" in names

    async def test_combo_fund_intermediary_wins(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        fund = str(uuid.uuid4())
        inter = str(uuid.uuid4())
        s_combo = _make_skill(
            name="skill_dossier_gcf_via_boad",
            domain=SkillDomain.DOSSIER.value,
            activation_rules={
                "page_slugs": ["/applications"],
                "fund_id": fund,
                "intermediary_id": inter,
            },
            created_by=admin.id,
        )
        s_simple = _make_skill(
            name="skill_application_basic",
            domain=SkillDomain.DOSSIER.value,
            activation_rules={"page_slugs": ["/applications"]},
            created_by=admin.id,
        )
        db_session.add_all([s_combo, s_simple])
        await db_session.flush()

        result = await load_skills_for_context(
            page_slug="/applications",
            active_module="application",
            intent=None,
            offer_id=None,
            fund_id=fund,
            intermediary_id=inter,
            db=db_session,
        )
        # combo doit être en tête.
        assert result[0].name == "skill_dossier_gcf_via_boad"

    async def test_max_two_skills_returned(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        for i in range(4):
            s = _make_skill(
                name=f"skill_multi_{i}",
                domain=SkillDomain.DIAGNOSTIC_ESG.value,
                activation_rules={"page_slugs": ["/esg"]},
                created_by=admin.id,
            )
            db_session.add(s)
        await db_session.flush()

        result = await load_skills_for_context(
            page_slug="/esg",
            active_module=None,
            intent=None,
            offer_id=None,
            fund_id=None,
            intermediary_id=None,
            db=db_session,
        )
        assert len(result) <= 2

    async def test_draft_skills_excluded(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        s = _make_skill(
            name="skill_draft_excluded",
            domain=SkillDomain.DIAGNOSTIC_ESG.value,
            activation_rules={"page_slugs": ["/esg"]},
            status=SkillStatus.DRAFT.value,
            created_by=admin.id,
        )
        db_session.add(s)
        await db_session.flush()

        result = await load_skills_for_context(
            page_slug="/esg",
            active_module=None,
            intent=None,
            offer_id=None,
            fund_id=None,
            intermediary_id=None,
            db=db_session,
        )
        names = [r.name for r in result]
        assert "skill_draft_excluded" not in names

    async def test_expired_skills_excluded(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        yesterday = date.today() - timedelta(days=1)
        s = _make_skill(
            name="skill_expired",
            domain=SkillDomain.DIAGNOSTIC_ESG.value,
            activation_rules={"page_slugs": ["/esg"]},
            valid_to=yesterday,
            created_by=admin.id,
        )
        db_session.add(s)
        await db_session.flush()

        result = await load_skills_for_context(
            page_slug="/esg",
            active_module=None,
            intent=None,
            offer_id=None,
            fund_id=None,
            intermediary_id=None,
            db=db_session,
        )
        names = [r.name for r in result]
        assert "skill_expired" not in names

    async def test_no_match_returns_empty(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        s = _make_skill(
            name="skill_other",
            domain=SkillDomain.DIAGNOSTIC_ESG.value,
            activation_rules={"page_slugs": ["/something_else"]},
            created_by=admin.id,
        )
        db_session.add(s)
        await db_session.flush()

        result = await load_skills_for_context(
            page_slug="/no_skill_here",
            active_module=None,
            intent=None,
            offer_id=None,
            fund_id=None,
            intermediary_id=None,
            db=db_session,
        )
        assert result == []

    async def test_intent_keywords_match(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        s = _make_skill(
            name="skill_with_keywords",
            domain=SkillDomain.DOSSIER.value,
            activation_rules={"intent_keywords": ["GCF", "BOAD"]},
            created_by=admin.id,
        )
        db_session.add(s)
        await db_session.flush()

        result = await load_skills_for_context(
            page_slug=None,
            active_module=None,
            intent="Je veux préparer un dossier GCF",
            offer_id=None,
            fund_id=None,
            intermediary_id=None,
            db=db_session,
        )
        names = [r.name for r in result]
        assert "skill_with_keywords" in names

    async def test_deterministic_ordering_same_score(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        for name in ("skill_b_zzz", "skill_a_aaa"):
            s = _make_skill(
                name=name,
                domain=SkillDomain.DIAGNOSTIC_ESG.value,
                activation_rules={"page_slugs": ["/esg"]},
                created_by=admin.id,
            )
            db_session.add(s)
        await db_session.flush()

        result = await load_skills_for_context(
            page_slug="/esg",
            active_module=None,
            intent=None,
            offer_id=None,
            fund_id=None,
            intermediary_id=None,
            db=db_session,
        )
        names = [r.name for r in result]
        # Tri alphabétique stable parmi équités de score.
        assert names == sorted(names)
