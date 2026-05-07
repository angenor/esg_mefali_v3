"""F13 — Test d'égalité legacy : Mefali score == esg_assessments.overall_score (T023)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

from app.core.constants import MEFALI_REFERENTIAL_CODE, MEFALI_REFERENTIAL_UUID
from app.models.account import Account
from app.models.esg import ESGAssessment, ESGStatusEnum
from app.models.referential import Referential
from app.models.source import Source, VerificationStatus
from app.models.user import User
from app.modules.esg.multi_referential_service import compute_all_referential_scores


pytestmark = pytest.mark.asyncio


async def test_mefali_score_mirror_legacy_columns(db_session):
    """Après compute_all_referential_scores, Mefali score == assessment.overall_score."""
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
        description="Mefali",
        source_id=src.id,
        publication_status="published",
        account_id=None,
        created_by_user_id=user.id,
        version="1.0",
    )
    db_session.add(ref)
    await db_session.flush()

    a = ESGAssessment(
        user_id=user.id,
        account_id=account.id,
        sector="agriculture",
        status=ESGStatusEnum.in_progress,
        assessment_data={
            "criteria_scores": {
                f"{p}{i}": {"score": 7, "justification": "ok"}
                for p in ("E", "S", "G")
                for i in range(1, 11)
            }
        },
    )
    db_session.add(a)
    await db_session.commit()

    scores, failures = await compute_all_referential_scores(
        db_session, assessment_id=a.id,
    )
    await db_session.commit()
    await db_session.refresh(a)

    assert len(scores) == 1
    assert failures == []

    # Le score Mefali doit refléter assessment.overall_score (cohérence F11/F06)
    assert a.overall_score is not None
    assert scores[0].overall_score is not None
    diff = abs(float(a.overall_score) - float(scores[0].overall_score))
    assert diff < 0.5, (
        f"Diff trop grande entre legacy ({a.overall_score}) "
        f"et Mefali score ({scores[0].overall_score})"
    )

    # Pillar scores aussi
    pillars = scores[0].pillar_scores or {}
    assert "environment" in pillars
    assert abs(float(a.environment_score or 0) - float(pillars["environment"]["score"])) < 1.0
