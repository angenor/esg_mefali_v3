"""F21 — Tests unitaires du service carbon report (validation préalable)."""

from __future__ import annotations

import uuid

import pytest

from app.models.account import Account
from app.models.carbon import CarbonAssessment, CarbonStatusEnum
from app.models.report import Report, ReportStatusEnum, ReportTypeEnum
from app.models.user import User
from app.modules.reports.carbon.exceptions import (
    AssessmentNotFinalizedError,
    AssessmentNotFoundError,
    ConcurrentGenerationError,
)
from app.modules.reports.carbon.service import (
    _check_no_concurrent_generation,
    _load_assessment,
    generate_carbon_report,
)

pytestmark = pytest.mark.asyncio


async def _make_user(db_session, completed: bool = True):
    account = Account(name=f"Acc-{uuid.uuid4().hex[:6]}")
    db_session.add(account)
    await db_session.flush()
    user = User(
        email=f"u-{uuid.uuid4().hex[:6]}@t.com",
        hashed_password="x",
        full_name="PME Test",
        company_name="PME Test SA",
        is_active=True,
        role="PME",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _make_assessment(db_session, user, status: CarbonStatusEnum = CarbonStatusEnum.completed):
    a = CarbonAssessment(
        user_id=user.id,
        account_id=user.account_id,
        year=2025,
        status=status,
        total_emissions_tco2e=12.5,
    )
    db_session.add(a)
    await db_session.flush()
    return a


class TestLoadAssessment:
    async def test_returns_assessment_when_completed(self, db_session) -> None:
        user = await _make_user(db_session)
        a = await _make_assessment(db_session, user)
        out = await _load_assessment(db_session, a.id, user.id)
        assert out.id == a.id

    async def test_raises_not_found_when_missing(self, db_session) -> None:
        user = await _make_user(db_session)
        with pytest.raises(AssessmentNotFoundError):
            await _load_assessment(db_session, uuid.uuid4(), user.id)

    async def test_raises_not_found_when_other_user(self, db_session) -> None:
        u1 = await _make_user(db_session)
        u2 = await _make_user(db_session)
        a = await _make_assessment(db_session, u1)
        with pytest.raises(AssessmentNotFoundError):
            await _load_assessment(db_session, a.id, u2.id)

    async def test_raises_when_not_finalized(self, db_session) -> None:
        user = await _make_user(db_session)
        a = await _make_assessment(db_session, user, status=CarbonStatusEnum.in_progress)
        with pytest.raises(AssessmentNotFinalizedError):
            await _load_assessment(db_session, a.id, user.id)


class TestCheckNoConcurrentGeneration:
    async def test_allows_when_no_existing(self, db_session) -> None:
        # Aucune exception attendue.
        await _check_no_concurrent_generation(db_session, uuid.uuid4())

    async def test_raises_when_existing_generating(self, db_session) -> None:
        user = await _make_user(db_session)
        a = await _make_assessment(db_session, user)
        # Créer un Report en cours.
        existing = Report(
            user_id=user.id,
            account_id=user.account_id,
            assessment_id=a.id,
            report_type=ReportTypeEnum.carbon,
            status=ReportStatusEnum.generating,
            file_path="dummy.pdf",
        )
        db_session.add(existing)
        await db_session.flush()

        with pytest.raises(ConcurrentGenerationError):
            await _check_no_concurrent_generation(db_session, a.id)

    async def test_allows_when_existing_completed(self, db_session) -> None:
        user = await _make_user(db_session)
        a = await _make_assessment(db_session, user)
        existing = Report(
            user_id=user.id,
            account_id=user.account_id,
            assessment_id=a.id,
            report_type=ReportTypeEnum.carbon,
            status=ReportStatusEnum.completed,
            file_path="done.pdf",
        )
        db_session.add(existing)
        await db_session.flush()

        # Pas d'exception : on peut régénérer.
        await _check_no_concurrent_generation(db_session, a.id)


class TestGenerateCarbonReport:
    async def test_creates_pending_report(self, db_session) -> None:
        user = await _make_user(db_session)
        a = await _make_assessment(db_session, user)
        report = await generate_carbon_report(
            db_session, a.id, user.id, source="manual"
        )
        assert report.report_type == ReportTypeEnum.carbon
        assert report.status == ReportStatusEnum.generating
        assert report.assessment_id == a.id
        assert report.user_id == user.id
        assert report.file_path.endswith(".pdf")

    async def test_refuses_when_not_finalized(self, db_session) -> None:
        user = await _make_user(db_session)
        a = await _make_assessment(db_session, user, status=CarbonStatusEnum.in_progress)
        with pytest.raises(AssessmentNotFinalizedError):
            await generate_carbon_report(db_session, a.id, user.id)

    async def test_refuses_when_concurrent(self, db_session) -> None:
        user = await _make_user(db_session)
        a = await _make_assessment(db_session, user)
        await generate_carbon_report(db_session, a.id, user.id)
        with pytest.raises(ConcurrentGenerationError):
            await generate_carbon_report(db_session, a.id, user.id)

    async def test_refuses_when_other_user(self, db_session) -> None:
        u1 = await _make_user(db_session)
        u2 = await _make_user(db_session)
        a = await _make_assessment(db_session, u1)
        with pytest.raises(AssessmentNotFoundError):
            await generate_carbon_report(db_session, a.id, u2.id)
