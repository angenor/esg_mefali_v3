"""F13 — Tests unitaires du cron check_referential_versions_evolution (T065)."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone

import pytest
from unittest.mock import patch

from app.core.constants import MEFALI_REFERENTIAL_CODE, MEFALI_REFERENTIAL_UUID
from app.models.account import Account
from app.models.action_plan import Reminder, ReminderType
from app.models.esg import ESGAssessment, ESGStatusEnum
from app.models.referential import Referential
from app.models.referential_score import ComputedByEnum, ReferentialScore
from app.models.source import Source, VerificationStatus
from app.models.user import User
from scripts.check_referential_versions_evolution import (
    REMINDER_KIND_REFERENTIAL_VERSION_EVOLVED,
    check_referential_versions_evolution,
)


pytestmark = pytest.mark.asyncio


async def _setup(db_session) -> tuple[Account, User, Referential, ReferentialScore]:
    account = Account(name=f"AC-{uuid.uuid4().hex[:6]}")
    db_session.add(account)
    await db_session.flush()
    user = User(
        email=f"u-{uuid.uuid4().hex[:6]}@t.com",
        hashed_password="x",
        full_name="T",
        company_name="T",
        account_id=account.id,
    )
    verifier = User(
        email=f"v-{uuid.uuid4().hex[:6]}@t.com",
        hashed_password="x",
        full_name="V",
        company_name="V",
        account_id=account.id,
    )
    db_session.add_all([user, verifier])
    await db_session.flush()
    src = Source(
        url=f"https://ex.com/s-{uuid.uuid4().hex[:6]}",
        title="S",
        publisher="M",
        version="1.0",
        date_publi=date.today(),
        captured_by=user.id,
        verified_by=verifier.id,
        verified_at=datetime.now(timezone.utc),
        created_by_user_id=user.id,
        verification_status=VerificationStatus.VERIFIED.value,
    )
    db_session.add(src)
    await db_session.flush()
    ref = Referential(
        id=MEFALI_REFERENTIAL_UUID,
        code=MEFALI_REFERENTIAL_CODE,
        label="ESG Mefali",
        description="Test",
        source_id=src.id,
        publication_status="published",
        account_id=None,
        created_by_user_id=user.id,
        version="1.1",  # nouvelle version
    )
    db_session.add(ref)
    await db_session.flush()
    a = ESGAssessment(
        user_id=user.id,
        account_id=account.id,
        sector="agriculture",
        status=ESGStatusEnum.completed,
        overall_score=70.0,
        environment_score=70.0,
        social_score=70.0,
        governance_score=70.0,
    )
    db_session.add(a)
    await db_session.flush()
    # Score avec version antérieure
    score = ReferentialScore(
        account_id=account.id,
        assessment_id=a.id,
        referential_id=ref.id,
        referential_version="1.0",  # version antérieure
        overall_score=70.0,
        pillar_scores={},
        coverage_rate=1.0,
        covered_criteria=[],
        missing_criteria=[],
        gap_to_threshold=20.0,
        eligibility=True,
        computed_by=ComputedByEnum.AUTO,
    )
    db_session.add(score)
    await db_session.commit()
    return account, user, ref, score


async def test_cron_creates_reminder_on_version_evolution(db_session):
    """T065 (a)+(b) — détecte évolution de version + crée reminder."""
    from app.core.database import async_session_factory as orig_factory

    account, user, ref, score = await _setup(db_session)

    # Patch l'async_session_factory pour utiliser db_session via une factory
    # adaptée (le cron crée sa propre session). En test, on monkeypatch :
    from unittest.mock import AsyncMock, MagicMock

    @patch(
        "scripts.check_referential_versions_evolution.async_session_factory"
    )
    async def _run(mock_factory):
        # Le mock retourne un context manager qui yield notre db_session
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        return await check_referential_versions_evolution(dry_run=False)

    stats = await _run()
    assert stats["referentials_checked"] >= 1
    assert stats["reminders_created"] >= 1


async def test_cron_idempotent(db_session):
    """T065 (c) — 2ème exécution ne crée pas de doublon."""
    from unittest.mock import AsyncMock, MagicMock

    account, user, ref, score = await _setup(db_session)

    @patch("scripts.check_referential_versions_evolution.async_session_factory")
    async def _run(mock_factory):
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        return await check_referential_versions_evolution(dry_run=False)

    stats1 = await _run()
    stats2 = await _run()

    # 1ère exec : crée des reminders ; 2ème exec : skip
    assert stats1["reminders_created"] >= 1
    assert stats2["skipped"] >= 1


async def test_reminder_metadata_structure(db_session):
    """T065 (d) — le reminder a une metadata structurée correctement."""
    from sqlalchemy import select
    from unittest.mock import AsyncMock, MagicMock

    account, user, ref, score = await _setup(db_session)

    @patch("scripts.check_referential_versions_evolution.async_session_factory")
    async def _run(mock_factory):
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        return await check_referential_versions_evolution(dry_run=False)

    await _run()

    # Inspection du reminder
    rem_q = await db_session.execute(
        select(Reminder).where(
            Reminder.account_id == account.id,
            Reminder.type == ReminderType.custom,
        )
    )
    rem = rem_q.scalars().first()
    assert rem is not None
    assert rem.message
    payload = json.loads(rem.message)
    assert payload["kind"] == REMINDER_KIND_REFERENTIAL_VERSION_EVOLVED
    md = payload["metadata"]
    assert md["referential_id"] == str(ref.id)
    assert md["new_version"] == "1.1"
    assert md["old_version"] == "1.0"


async def test_cron_dry_run_does_not_create_reminders(db_session):
    """dry_run=True : aucun reminder n'est inséré."""
    from sqlalchemy import select
    from unittest.mock import AsyncMock, MagicMock

    account, user, ref, score = await _setup(db_session)

    @patch("scripts.check_referential_versions_evolution.async_session_factory")
    async def _run(mock_factory):
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        return await check_referential_versions_evolution(dry_run=True)

    stats = await _run()
    assert stats["reminders_created"] >= 1  # comptés mais non insérés

    rem_q = await db_session.execute(
        select(Reminder).where(Reminder.account_id == account.id)
    )
    assert rem_q.scalars().first() is None
