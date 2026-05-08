"""F15 — Tests du seed des templates MVP."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill, SkillStatus
from app.models.template_dossier import TemplateDossier
from app.models.user import User
from app.modules.applications.seed_templates import (
    SeedResult,
    seed_templates,
)

pytestmark = pytest.mark.asyncio


async def _make_admin(db: AsyncSession, email: str) -> User:
    user = User(
        email=email,
        hashed_password="x",
        full_name="Admin",
        company_name="ACME",
        role="ADMIN",
    )
    db.add(user)
    await db.flush()
    return user


async def _ensure_skill(db: AsyncSession, captured_by: uuid.UUID) -> None:
    skill = Skill(
        name="skill_esg_diagnostic",
        domain="diagnostic_esg",
        prompt_expert="prompt",
        procedure="procedure",
        tool_whitelist=[],
        sources=[],
        activation_rules={},
        golden_examples=[],
        status=SkillStatus.PUBLISHED.value,
        created_by=captured_by,
    )
    db.add(skill)
    await db.flush()


async def test_seed_templates_inserts_5_seeds(db_session: AsyncSession) -> None:
    """Le seed insère les 5 templates MVP (4 FR + 1 EN)."""
    captured = await _make_admin(db_session, f"cap-{uuid.uuid4()}@x.test")
    verified = await _make_admin(db_session, f"ver-{uuid.uuid4()}@x.test")
    await _ensure_skill(db_session, captured.id)

    result = await seed_templates(
        db_session,
        captured_by=captured.id,
        verified_by=verified.id,
    )
    assert isinstance(result, SeedResult)
    assert result.inserted_templates == 5
    assert result.inserted_source is True

    rows = (await db_session.execute(select(TemplateDossier))).scalars().all()
    assert len(rows) == 5
    # 4 FR + 1 EN
    fr = [r for r in rows if r.language == "fr"]
    en = [r for r in rows if r.language == "en"]
    assert len(fr) == 4
    assert len(en) == 1
    # Tous publiés (verifier fourni)
    assert all(r.status == "published" for r in rows)


async def test_seed_templates_idempotent(db_session: AsyncSession) -> None:
    """Deuxième appel : 0 nouveau template inséré."""
    captured = await _make_admin(db_session, f"cap-{uuid.uuid4()}@x.test")
    verified = await _make_admin(db_session, f"ver-{uuid.uuid4()}@x.test")
    await _ensure_skill(db_session, captured.id)

    r1 = await seed_templates(
        db_session, captured_by=captured.id, verified_by=verified.id,
    )
    r2 = await seed_templates(
        db_session, captured_by=captured.id, verified_by=verified.id,
    )
    assert r1.inserted_templates == 5
    assert r2.inserted_templates == 0
    assert r2.inserted_source is False


async def test_seed_templates_rejects_same_user_for_4_eyes(
    db_session: AsyncSession,
) -> None:
    """captured_by == verified_by → ValueError (4-yeux)."""
    captured = await _make_admin(db_session, f"cap-{uuid.uuid4()}@x.test")
    await _ensure_skill(db_session, captured.id)

    with pytest.raises(ValueError, match="4-yeux"):
        await seed_templates(
            db_session, captured_by=captured.id, verified_by=captured.id,
        )


async def test_seed_templates_without_verifier_creates_drafts(
    db_session: AsyncSession,
) -> None:
    """Sans verified_by, les templates restent en draft."""
    captured = await _make_admin(db_session, f"cap-{uuid.uuid4()}@x.test")
    await _ensure_skill(db_session, captured.id)

    await seed_templates(db_session, captured_by=captured.id, verified_by=None)
    rows = (await db_session.execute(select(TemplateDossier))).scalars().all()
    assert len(rows) == 5
    assert all(r.status == "draft" for r in rows)


async def test_seed_templates_fails_without_skill(db_session: AsyncSession) -> None:
    """Pas de Skill F23 en BDD → RuntimeError."""
    captured = await _make_admin(db_session, f"cap-{uuid.uuid4()}@x.test")
    verified = await _make_admin(db_session, f"ver-{uuid.uuid4()}@x.test")
    # Pas de skill créée

    with pytest.raises(RuntimeError, match="Skill"):
        await seed_templates(
            db_session, captured_by=captured.id, verified_by=verified.id,
        )
