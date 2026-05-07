"""F23 — Tests unitaires ``app.modules.skills.service`` (T036)."""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.skill import Skill, SkillStatus
from app.models.user import User
from app.modules.skills.exceptions import (
    EvalGatingFailedError,
    InsufficientGoldenExamplesError,
    SkillNotFoundError,
)
from app.modules.skills.schemas import (
    ActivationRules,
    GoldenContext,
    GoldenExample,
    GoldenExpected,
    SkillCreate,
    SkillEvalReport,
    SkillUpdate,
)
from app.modules.skills.service import SkillService


pytestmark = pytest.mark.asyncio


async def _seed_admin(db_session, name="Admin") -> User:
    a = User(
        email=f"{name.lower()}-{uuid.uuid4().hex[:6]}@m.com",
        hashed_password="x",
        full_name=name,
        company_name="Mefali",
        role="ADMIN",
        account_id=None,
    )
    db_session.add(a)
    await db_session.flush()
    return a


def _golden(case_id: str, expected_tool: str = "update_company_profile") -> GoldenExample:
    return GoldenExample(
        id=case_id,
        category="diagnostic_esg",
        context=GoldenContext(current_page="/esg", active_module="esg_scoring"),
        user_message=f"msg {case_id}",
        expected=GoldenExpected(tool_called=expected_tool),
    )


def _create_payload(name: str | None = None, **overrides) -> SkillCreate:
    base = dict(
        name=name or f"skill_test_{uuid.uuid4().hex[:6]}",
        domain="diagnostic_esg",
        prompt_expert=(
            "Tu es un expert ESG ouest-africain spécialisé en finance durable "
            "pour les PME. Aide à structurer un diagnostic clair et factuel."
        ),
        procedure=(
            "1) Demander le secteur d'activité. 2) Calculer le score ESG sur "
            "30 critères. 3) Restituer le rapport avec recommandations."
        ),
        tool_whitelist=["update_company_profile"],
        sources=[],
        activation_rules=ActivationRules(page_slugs=["/esg"]),
        golden_examples=[],
    )
    base.update(overrides)
    return SkillCreate(**base)


class TestSkillCRUD:
    async def test_create_skill_returns_draft(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        service = SkillService(db_session)
        skill = await service.create_skill(_create_payload(), creator_id=admin.id)
        assert skill.status == SkillStatus.DRAFT.value
        assert skill.created_by == admin.id

    async def test_get_skill_not_found(self, db_session) -> None:
        service = SkillService(db_session)
        with pytest.raises(SkillNotFoundError):
            await service.get_skill(uuid.uuid4())

    async def test_get_skill_found(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        service = SkillService(db_session)
        created = await service.create_skill(_create_payload(), creator_id=admin.id)
        fetched = await service.get_skill(created.id)
        assert fetched.id == created.id

    async def test_list_skills_filters_by_domain(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        service = SkillService(db_session)
        await service.create_skill(_create_payload(domain="diagnostic_esg"), creator_id=admin.id)
        await service.create_skill(_create_payload(domain="dossier"), creator_id=admin.id)
        items, total = await service.list_skills(domain="dossier", page=1, limit=20)
        assert total == 1
        assert items[0].domain == "dossier"

    async def test_update_draft_in_place(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        service = SkillService(db_session)
        created = await service.create_skill(_create_payload(), creator_id=admin.id)
        new_prompt = (
            "Tu es un expert ESG, version mise à jour avec mécanique 4-yeux "
            "renforcée et focus pleinement opérationnel sur l'audit ESG."
        )
        updated = await service.update_skill(
            created.id,
            SkillUpdate(prompt_expert=new_prompt),
            updater_id=admin.id,
        )
        assert updated.id == created.id  # in-place
        assert "version mise à jour" in updated.prompt_expert

    async def test_delete_draft_soft_delete(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        service = SkillService(db_session)
        created = await service.create_skill(_create_payload(), creator_id=admin.id)
        await service.delete_skill_draft(created.id)
        await db_session.commit()
        # On vérifie que valid_to a été défini.
        result = await db_session.execute(
            select(Skill).where(Skill.id == created.id)
        )
        s = result.scalar_one()
        assert s.valid_to is not None


class TestSkillPublish:
    async def test_publish_insufficient_golden_examples(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        service = SkillService(db_session)
        skill = await service.create_skill(
            _create_payload(golden_examples=[_golden("c1"), _golden("c2")]),
            creator_id=admin.id,
        )
        with pytest.raises(InsufficientGoldenExamplesError):
            await service.publish_skill(skill.id, admin.id)

    async def test_publish_gate_failed_keeps_draft(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        service = SkillService(db_session)
        cases = [_golden(f"c{i}") for i in range(5)]
        skill = await service.create_skill(
            _create_payload(golden_examples=cases),
            creator_id=admin.id,
        )

        # Mock report avec gate_passed=False
        from datetime import datetime, timezone

        async def fake_eval(skill_id, db):
            return SkillEvalReport(
                skill_id=skill_id,
                run_id=uuid.uuid4(),
                started_at=datetime.now(tz=timezone.utc),
                completed_at=datetime.now(tz=timezone.utc),
                duration_seconds=0.5,
                total_cases=5,
                passed=2,
                failed=3,
                success_rate=0.4,
                threshold=0.9,
                gate_passed=False,
                failed_cases=[],
            )

        with patch(
            "app.modules.skills.service.run_skill_eval", side_effect=fake_eval
        ):
            with pytest.raises(EvalGatingFailedError):
                await service.publish_skill(skill.id, admin.id)
        # Skill reste draft
        fetched = await service.get_skill(skill.id)
        assert fetched.status == SkillStatus.DRAFT.value

    async def test_publish_gate_passed(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        service = SkillService(db_session)
        cases = [_golden(f"c{i}") for i in range(5)]
        skill = await service.create_skill(
            _create_payload(golden_examples=cases),
            creator_id=admin.id,
        )

        from datetime import datetime, timezone

        async def fake_eval(skill_id, db):
            return SkillEvalReport(
                skill_id=skill_id,
                run_id=uuid.uuid4(),
                started_at=datetime.now(tz=timezone.utc),
                completed_at=datetime.now(tz=timezone.utc),
                duration_seconds=0.5,
                total_cases=5,
                passed=5,
                failed=0,
                success_rate=1.0,
                threshold=0.9,
                gate_passed=True,
                failed_cases=[],
            )

        with patch(
            "app.modules.skills.service.run_skill_eval", side_effect=fake_eval
        ):
            published, report = await service.publish_skill(skill.id, admin.id)
        assert published.status == SkillStatus.PUBLISHED.value
        assert report.gate_passed is True


class TestVersioning:
    async def test_update_published_creates_new_version(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        service = SkillService(db_session)
        cases = [_golden(f"c{i}") for i in range(5)]
        skill = await service.create_skill(
            _create_payload(golden_examples=cases),
            creator_id=admin.id,
        )

        from datetime import datetime, timezone

        async def fake_eval_passing(skill_id, db):
            return SkillEvalReport(
                skill_id=skill_id,
                run_id=uuid.uuid4(),
                started_at=datetime.now(tz=timezone.utc),
                completed_at=datetime.now(tz=timezone.utc),
                duration_seconds=0.5,
                total_cases=5,
                passed=5,
                failed=0,
                success_rate=1.0,
                threshold=0.9,
                gate_passed=True,
                failed_cases=[],
            )

        with patch(
            "app.modules.skills.service.run_skill_eval", side_effect=fake_eval_passing
        ):
            await service.publish_skill(skill.id, admin.id)
            await db_session.commit()

        # Update une skill published → nouvelle version draft
        new_prompt = (
            "Tu es un expert ESG version 2, mise à jour avec une approche "
            "encore plus structurée pour les PME ouest-africaines en agroalimentaire."
        )
        new_version = await service.update_skill(
            skill.id,
            SkillUpdate(prompt_expert=new_prompt),
            updater_id=admin.id,
        )
        assert new_version.id != skill.id
        assert new_version.status == SkillStatus.DRAFT.value
        # semver patch+1 attendu
        assert new_version.version == "1.0.1"


class TestQueryMatching:
    async def test_query_skills_matching_returns_published_only(self, db_session) -> None:
        admin = await _seed_admin(db_session)
        service = SkillService(db_session)
        # 1 draft + 1 published
        await service.create_skill(_create_payload(name="skill_q_draft"), creator_id=admin.id)
        published = await service.create_skill(
            _create_payload(name="skill_q_published", golden_examples=[_golden(f"c{i}") for i in range(5)]),
            creator_id=admin.id,
        )
        # Force le status à published manuellement (bypass gate)
        published.status = SkillStatus.PUBLISHED.value
        await db_session.flush()

        items = await service.query_skills_matching(domain=None)
        names = [s.name for s in items]
        assert "skill_q_published" in names
        assert "skill_q_draft" not in names
