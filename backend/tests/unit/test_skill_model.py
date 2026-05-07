"""F23 — Tests unitaires modèle SQLAlchemy ``Skill`` (T008).

Couvre :
- Création avec champs minimums.
- Contraintes CheckConstraint (domain, status, four_eyes).
- Unicité ``name``.
- Self-FK ``superseded_by``.
- Default semver.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.skill import Skill, SkillDomain, SkillStatus
from app.models.user import User
from tests.conftest import make_account


pytestmark = pytest.mark.asyncio


async def _make_two_admins(db_session):
    """Crée 2 admins distincts pour le 4-yeux check."""
    admin1 = User(
        email=f"admin1-{uuid.uuid4().hex[:6]}@admin.com",
        hashed_password="x",
        full_name="Admin1",
        company_name="Mefali",
        role="ADMIN",
        account_id=None,
    )
    admin2 = User(
        email=f"admin2-{uuid.uuid4().hex[:6]}@admin.com",
        hashed_password="x",
        full_name="Admin2",
        company_name="Mefali",
        role="ADMIN",
        account_id=None,
    )
    db_session.add_all([admin1, admin2])
    await db_session.flush()
    return admin1, admin2


def _minimal_payload(**overrides):
    base = dict(
        name=f"skill_test_{uuid.uuid4().hex[:6]}",
        domain=SkillDomain.DIAGNOSTIC_ESG.value,
        prompt_expert="Test prompt",
        procedure="Test procedure",
        tool_whitelist=["create_fund_application"],
        sources=[],
        activation_rules={"page_slugs": ["/esg"]},
        golden_examples=[],
        status=SkillStatus.DRAFT.value,
    )
    base.update(overrides)
    return base


async def test_skill_creation_minimal(db_session) -> None:
    admin1, admin2 = await _make_two_admins(db_session)
    skill = Skill(
        **_minimal_payload(),
        created_by=admin1.id,
        verified_by=admin2.id,
    )
    db_session.add(skill)
    await db_session.flush()
    assert skill.id is not None
    assert skill.name.startswith("skill_test_")
    assert skill.version == "1.0.0"
    assert skill.status == SkillStatus.DRAFT.value


async def test_default_version_is_semver(db_session) -> None:
    admin1, _ = await _make_two_admins(db_session)
    skill = Skill(**_minimal_payload(), created_by=admin1.id)
    db_session.add(skill)
    await db_session.flush()
    assert skill.version == "1.0.0"


async def test_default_status_is_draft(db_session) -> None:
    admin1, _ = await _make_two_admins(db_session)
    payload = _minimal_payload()
    payload.pop("status")  # use server_default
    skill = Skill(**payload, created_by=admin1.id)
    db_session.add(skill)
    await db_session.flush()
    await db_session.refresh(skill)
    assert skill.status == SkillStatus.DRAFT.value


async def test_unique_name_violation(db_session) -> None:
    admin1, _ = await _make_two_admins(db_session)
    name = f"skill_dup_{uuid.uuid4().hex[:6]}"
    s1 = Skill(**_minimal_payload(name=name), created_by=admin1.id)
    db_session.add(s1)
    await db_session.flush()

    s2 = Skill(**_minimal_payload(name=name), created_by=admin1.id)
    db_session.add(s2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_invalid_domain_violation(db_session) -> None:
    admin1, _ = await _make_two_admins(db_session)
    skill = Skill(**_minimal_payload(domain="unknown_domain"), created_by=admin1.id)
    db_session.add(skill)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_invalid_status_violation(db_session) -> None:
    admin1, _ = await _make_two_admins(db_session)
    skill = Skill(**_minimal_payload(status="bogus"), created_by=admin1.id)
    db_session.add(skill)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_four_eyes_violation(db_session) -> None:
    """``verified_by`` doit être différent de ``created_by``."""
    admin1, _ = await _make_two_admins(db_session)
    skill = Skill(
        **_minimal_payload(),
        created_by=admin1.id,
        verified_by=admin1.id,  # même utilisateur → violation
    )
    db_session.add(skill)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_verified_by_nullable(db_session) -> None:
    """``verified_by`` peut être NULL (skill draft non encore validée)."""
    admin1, _ = await _make_two_admins(db_session)
    skill = Skill(
        **_minimal_payload(),
        created_by=admin1.id,
        verified_by=None,
    )
    db_session.add(skill)
    await db_session.flush()
    assert skill.verified_by is None


async def test_superseded_by_self_fk(db_session) -> None:
    """Une skill peut référencer une autre via ``superseded_by``."""
    admin1, _ = await _make_two_admins(db_session)
    s_old = Skill(**_minimal_payload(name="skill_v1"), created_by=admin1.id)
    db_session.add(s_old)
    await db_session.flush()

    s_new = Skill(**_minimal_payload(name="skill_v2"), created_by=admin1.id)
    db_session.add(s_new)
    await db_session.flush()

    s_old.superseded_by = s_new.id
    s_old.valid_to = date.today()
    await db_session.flush()

    fetched = (
        await db_session.execute(select(Skill).where(Skill.name == "skill_v1"))
    ).scalar_one()
    assert fetched.superseded_by == s_new.id


async def test_jsonb_fields_stored(db_session) -> None:
    """tool_whitelist / sources / activation_rules / golden_examples sont des JSON."""
    admin1, _ = await _make_two_admins(db_session)
    payload = _minimal_payload(
        tool_whitelist=["a", "b"],
        sources=["uuid-1", "uuid-2"],
        activation_rules={"page_slugs": ["/esg"], "intent_keywords": ["ESG"]},
        golden_examples=[{"id": "ex1", "user_message": "test"}],
    )
    skill = Skill(**payload, created_by=admin1.id)
    db_session.add(skill)
    await db_session.flush()
    await db_session.refresh(skill)
    assert skill.tool_whitelist == ["a", "b"]
    assert skill.sources == ["uuid-1", "uuid-2"]
    assert skill.activation_rules["page_slugs"] == ["/esg"]
    assert skill.golden_examples[0]["id"] == "ex1"
