"""F13 — Tests sécurité RLS multi-tenant sur referential_scores (T024+T077).

Vérifie SC-009 : 100 % des tentatives d'accès cross-account sont bloquées.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.api.deps import get_current_user
from app.core.constants import MEFALI_REFERENTIAL_CODE, MEFALI_REFERENTIAL_UUID
from app.main import app
from app.models.account import Account
from app.models.esg import ESGAssessment, ESGStatusEnum
from app.models.referential import Referential
from app.models.referential_score import ComputedByEnum, ReferentialScore
from app.models.source import Source, VerificationStatus
from app.models.user import User


pytestmark = pytest.mark.asyncio


async def _make_account_with_score(db_session, suffix: str = "") -> tuple[Account, User, ESGAssessment, ReferentialScore]:
    account = Account(name=f"AC{suffix}-{uuid.uuid4().hex[:6]}")
    db_session.add(account)
    await db_session.flush()
    user = User(
        email=f"u{suffix}-{uuid.uuid4().hex[:6]}@t.com",
        hashed_password="x",
        full_name="T",
        company_name="T",
        account_id=account.id,
    )
    verifier = User(
        email=f"v{suffix}-{uuid.uuid4().hex[:6]}@t.com",
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

    # Référentiel Mefali (avec UUID stable, créé une seule fois sinon réutilise)
    existing = (
        await db_session.execute(
            select(Referential).where(Referential.code == MEFALI_REFERENTIAL_CODE)
        )
    ).scalar_one_or_none()
    if existing is None:
        ref = Referential(
            id=MEFALI_REFERENTIAL_UUID,
            code=MEFALI_REFERENTIAL_CODE,
            label="ESG Mefali",
            description="Mefali",
            source_id=src.id,
            publication_status="published",
            account_id=None,
            created_by_user_id=user.id,
            version="1.0",
        )
        db_session.add(ref)
        await db_session.flush()
    else:
        ref = existing

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

    score = ReferentialScore(
        account_id=account.id,
        assessment_id=a.id,
        referential_id=ref.id,
        referential_version="1.0",
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

    return account, user, a, score


async def test_user_b_cannot_see_user_a_scores(client, db_session):
    """SC-009 — un user B ne peut pas voir les scores d'un user A → 404 (pas 403)."""
    account_a, user_a, assessment_a, score_a = await _make_account_with_score(db_session, "A")
    account_b, user_b, _, _ = await _make_account_with_score(db_session, "B")

    app.dependency_overrides[get_current_user] = lambda: user_b
    try:
        resp = await client.get(
            f"/api/esg/assessments/{assessment_a.id}/referential-scores"
        )
        assert resp.status_code == 404, (
            f"Expected 404 for cross-tenant access, got {resp.status_code}"
        )
    finally:
        del app.dependency_overrides[get_current_user]


async def test_recompute_score_404_cross_tenant(client, db_session):
    """SC-009 — POST recompute-score retourne 404 cross-tenant."""
    account_a, user_a, assessment_a, _ = await _make_account_with_score(db_session, "A")
    account_b, user_b, _, _ = await _make_account_with_score(db_session, "B")

    app.dependency_overrides[get_current_user] = lambda: user_b
    try:
        resp = await client.post(
            f"/api/esg/assessments/{assessment_a.id}/recompute-score"
        )
        assert resp.status_code == 404
    finally:
        del app.dependency_overrides[get_current_user]


async def test_history_endpoint_404_cross_tenant(client, db_session):
    """SC-009 — GET history endpoint retourne 404 cross-tenant."""
    account_a, user_a, assessment_a, _ = await _make_account_with_score(db_session, "A")
    account_b, user_b, _, _ = await _make_account_with_score(db_session, "B")

    app.dependency_overrides[get_current_user] = lambda: user_b
    try:
        resp = await client.get(
            f"/api/esg/assessments/{assessment_a.id}/referential-scores/history"
        )
        assert resp.status_code == 404
    finally:
        del app.dependency_overrides[get_current_user]


async def test_cascade_on_delete_assessment(db_session):
    """Cascade ON DELETE : suppression de l'ESGAssessment → suppression des scores."""
    account, user, assessment, score = await _make_account_with_score(db_session)

    score_id = score.id
    await db_session.delete(assessment)
    await db_session.commit()

    # Le score doit avoir été supprimé en cascade
    res = (
        await db_session.execute(
            select(ReferentialScore).where(ReferentialScore.id == score_id)
        )
    ).scalar_one_or_none()
    assert res is None, "ReferentialScore aurait dû être supprimé via CASCADE"
