"""F15 — Tests du service ``template_service``."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill, SkillStatus
from app.models.source import Source
from app.models.template_dossier import (
    TemplateDossier,
    TemplateInstrumentType,
    TemplateLanguage,
    TemplateStatus,
)
from app.models.user import User
from app.modules.applications.template_service import (
    TemplateFourEyesError,
    create_template_draft,
    get_effective_template_for_offer,
    get_template,
    list_templates,
    publish_template,
    unpublish_template,
)

pytestmark = pytest.mark.asyncio


async def _make_user(db: AsyncSession, email: str) -> User:
    user = User(
        email=email,
        hashed_password="x",
        full_name="Admin Test",
        company_name="ACME",
        role="ADMIN",
    )
    db.add(user)
    await db.flush()
    return user


async def _make_source(db: AsyncSession, captured_by: uuid.UUID) -> Source:
    from datetime import date

    src = Source(
        url=f"https://example.com/{uuid.uuid4()}",
        title="Source test",
        publisher="Mefali",
        version="1.0",
        date_publi=date.today(),
        captured_by=captured_by,
        verification_status="pending",
        created_by_user_id=captured_by,
    )
    db.add(src)
    await db.flush()
    return src


async def _make_skill(db: AsyncSession, captured_by: uuid.UUID) -> Skill:
    skill = Skill(
        name=f"skill_test_{uuid.uuid4().hex[:8]}",
        domain="dossier",
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
    return skill


async def _seed_minimal(db: AsyncSession):
    """Crée un user admin + source + skill et retourne (user, source, skill)."""
    user = await _make_user(db, f"admin-{uuid.uuid4()}@x.test")
    source = await _make_source(db, user.id)
    skill = await _make_skill(db, user.id)
    return user, source, skill


async def test_create_and_get_template_draft(db_session: AsyncSession) -> None:
    user, source, skill = await _seed_minimal(db_session)

    template = await create_template_draft(
        db=db_session,
        name=f"Template test {uuid.uuid4().hex[:6]}",
        instrument_type=TemplateInstrumentType.SUBVENTION.value,
        language=TemplateLanguage.FR.value,
        sections=[{"key": "intro", "title": "Intro", "instructions": "x" * 20, "target_length": 200, "required": True}],
        required_documents=[{"title": "BP", "mandatory": True, "origin": "template"}],
        tone="formel",
        skill_id=skill.id,
        source_id=source.id,
        captured_by=user.id,
    )

    assert template.id is not None
    assert template.status == TemplateStatus.DRAFT.value
    fetched = await get_template(db_session, template.id)
    assert fetched is not None
    assert fetched.id == template.id


async def test_publish_template_four_eyes_violation(db_session: AsyncSession) -> None:
    user, source, skill = await _seed_minimal(db_session)
    template = await create_template_draft(
        db=db_session,
        name=f"Template 4yeux {uuid.uuid4().hex[:6]}",
        instrument_type=TemplateInstrumentType.SUBVENTION.value,
        language=TemplateLanguage.FR.value,
        sections=[{"key": "intro", "title": "Intro", "instructions": "x" * 20, "target_length": 200, "required": True}],
        required_documents=[],
        tone="formel",
        skill_id=skill.id,
        source_id=source.id,
        captured_by=user.id,
    )

    # Tentative de publish par le même user → violation 4-yeux
    with pytest.raises(TemplateFourEyesError):
        await publish_template(db_session, template, verified_by=user.id)


async def test_publish_unpublish_roundtrip(db_session: AsyncSession) -> None:
    creator, source, skill = await _seed_minimal(db_session)
    verifier = await _make_user(db_session, f"verif-{uuid.uuid4()}@x.test")

    template = await create_template_draft(
        db=db_session,
        name=f"Template pub {uuid.uuid4().hex[:6]}",
        instrument_type=TemplateInstrumentType.EQUITY.value,
        language=TemplateLanguage.FR.value,
        sections=[{"key": "intro", "title": "Intro", "instructions": "x" * 20, "target_length": 200, "required": True}],
        required_documents=[],
        tone="narratif",
        skill_id=skill.id,
        source_id=source.id,
        captured_by=creator.id,
    )

    await publish_template(db_session, template, verified_by=verifier.id)
    assert template.status == TemplateStatus.PUBLISHED.value
    assert template.verified_by == verifier.id

    await unpublish_template(db_session, template)
    assert template.status == TemplateStatus.DRAFT.value


async def test_get_effective_template_returns_offer_published(db_session: AsyncSession) -> None:
    creator, source, skill = await _seed_minimal(db_session)
    verifier = await _make_user(db_session, f"verif2-{uuid.uuid4()}@x.test")
    offer_id = uuid.uuid4()

    # On ne crée pas de vraie offre (RESTRICT FK). On teste la résolution
    # par offer_id sur un template fallback générique : offer_id absent
    # pour le template, fallback par instrument doit le retrouver.
    template = await create_template_draft(
        db=db_session,
        name=f"Fallback subvention {uuid.uuid4().hex[:6]}",
        instrument_type=TemplateInstrumentType.SUBVENTION.value,
        language=TemplateLanguage.FR.value,
        sections=[{"key": "intro", "title": "Intro", "instructions": "x" * 20, "target_length": 200, "required": True}],
        required_documents=[],
        tone="formel",
        skill_id=skill.id,
        source_id=source.id,
        captured_by=creator.id,
    )
    await publish_template(db_session, template, verified_by=verifier.id)

    # Résolution fallback par instrument : doit retrouver le template
    found = await get_effective_template_for_offer(
        db_session,
        offer_id=offer_id,  # offre inexistante côté template
        instrument_type=TemplateInstrumentType.SUBVENTION.value,
        language=TemplateLanguage.FR.value,
    )
    assert found is not None
    assert found.id == template.id


async def test_list_templates_filters(db_session: AsyncSession) -> None:
    creator, source, skill = await _seed_minimal(db_session)

    for instrument in (
        TemplateInstrumentType.SUBVENTION.value,
        TemplateInstrumentType.EQUITY.value,
    ):
        await create_template_draft(
            db=db_session,
            name=f"T-{instrument}-{uuid.uuid4().hex[:6]}",
            instrument_type=instrument,
            language=TemplateLanguage.FR.value,
            sections=[{"key": "intro", "title": "Intro", "instructions": "x" * 20, "target_length": 200, "required": True}],
            required_documents=[],
            tone="formel",
            skill_id=skill.id,
            source_id=source.id,
            captured_by=creator.id,
        )

    items, total = await list_templates(
        db_session,
        instrument_type=TemplateInstrumentType.SUBVENTION.value,
    )
    assert total >= 1
    assert all(t.instrument_type == TemplateInstrumentType.SUBVENTION.value for t in items)
