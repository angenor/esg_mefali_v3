"""F13 — Tests d'intégration des endpoints REST referential-scores (T015)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

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


async def _setup_assessment_with_score(db_session) -> tuple[User, ESGAssessment, ReferentialScore]:
    """Crée un compte, user, assessment, source, referential, et un referential_score."""
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

    source = Source(
        url=f"https://ex.com/s-{uuid.uuid4().hex[:6]}",
        title="Source",
        publisher="Mefali",
        version="1.0",
        date_publi=date.today(),
        captured_by=user.id,
        verified_by=verifier.id,
        verified_at=datetime.now(timezone.utc),
        created_by_user_id=user.id,
        verification_status=VerificationStatus.VERIFIED.value,
    )
    db_session.add(source)
    await db_session.flush()

    referential = Referential(
        id=MEFALI_REFERENTIAL_UUID,
        code=MEFALI_REFERENTIAL_CODE,
        label="ESG Mefali",
        description="Test ref.",
        source_id=source.id,
        publication_status="published",
        account_id=None,
        created_by_user_id=user.id,
        version="1.0",
    )
    db_session.add(referential)
    await db_session.flush()

    assessment = ESGAssessment(
        user_id=user.id,
        account_id=account.id,
        sector="agriculture",
        status=ESGStatusEnum.completed,
        overall_score=70.0,
        environment_score=70.0,
        social_score=70.0,
        governance_score=70.0,
        assessment_data={
            "criteria_scores": {
                f"{p}{i}": {"score": 7, "justification": "ok"}
                for p in ("E", "S", "G")
                for i in range(1, 11)
            }
        },
    )
    db_session.add(assessment)
    await db_session.flush()

    score = ReferentialScore(
        account_id=account.id,
        assessment_id=assessment.id,
        referential_id=referential.id,
        referential_version="1.0",
        overall_score=70.0,
        pillar_scores={"environment": {"score": 70.0, "weight": 0.33, "criteria_count": 10, "criteria_renseignés": 10}},
        coverage_rate=1.0,
        covered_criteria=[],
        missing_criteria=[],
        gap_to_threshold=20.0,
        eligibility=True,
        computed_by=ComputedByEnum.AUTO,
    )
    db_session.add(score)
    await db_session.commit()

    return user, assessment, score


async def test_get_referential_scores_returns_list(client, db_session):
    """T015 (a) — endpoint retourne les scores courants."""
    user, assessment, score = await _setup_assessment_with_score(db_session)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        resp = await client.get(f"/api/esg/assessments/{assessment.id}/referential-scores")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["referential_code"] == MEFALI_REFERENTIAL_CODE
        assert data[0]["overall_score"] == 70.0
    finally:
        del app.dependency_overrides[get_current_user]


async def test_get_referential_scores_404_if_other_user(client, db_session):
    """T015 (c) — RLS multi-tenant : compte B → 404 sur assessment de A."""
    user_a, assessment, _ = await _setup_assessment_with_score(db_session)

    # Créer un user B dans un autre compte
    account_b = Account(name="OtherAccount")
    db_session.add(account_b)
    await db_session.flush()
    user_b = User(
        email=f"b-{uuid.uuid4().hex[:6]}@t.com",
        hashed_password="x",
        full_name="B",
        company_name="B",
        account_id=account_b.id,
    )
    db_session.add(user_b)
    await db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: user_b
    try:
        resp = await client.get(f"/api/esg/assessments/{assessment.id}/referential-scores")
        assert resp.status_code == 404
    finally:
        del app.dependency_overrides[get_current_user]


async def test_get_referential_scores_history_filtered(client, db_session):
    """T015 (b) — historique des versions supersédées."""
    user, assessment, current_score = await _setup_assessment_with_score(db_session)

    # Ajout d'un score historique (superseded_by → courant)
    historic = ReferentialScore(
        account_id=current_score.account_id,
        assessment_id=assessment.id,
        referential_id=current_score.referential_id,
        referential_version="1.0",
        overall_score=60.0,
        pillar_scores={},
        coverage_rate=0.5,
        covered_criteria=[],
        missing_criteria=[],
        gap_to_threshold=10.0,
        eligibility=True,
        computed_by=ComputedByEnum.AUTO,
        superseded_by=current_score.id,
    )
    db_session.add(historic)
    await db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        resp = await client.get(
            f"/api/esg/assessments/{assessment.id}/referential-scores/history"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1  # uniquement les supersédés
        assert data[0]["overall_score"] == 60.0
    finally:
        del app.dependency_overrides[get_current_user]


async def test_post_recompute_score_returns_202(client, db_session):
    """T015 — POST recompute-score retourne 202 + recompute_request_id."""
    user, assessment, _ = await _setup_assessment_with_score(db_session)

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        resp = await client.post(
            f"/api/esg/assessments/{assessment.id}/recompute-score"
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "accepted"
        assert "recompute_request_id" in body
        # Doit pouvoir parser comme UUID
        uuid.UUID(body["recompute_request_id"])
    finally:
        del app.dependency_overrides[get_current_user]


async def test_post_recompute_score_with_referentiel_id(client, db_session):
    """POST recompute-score avec referentiel_id ciblé."""
    user, assessment, score = await _setup_assessment_with_score(db_session)

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        resp = await client.post(
            f"/api/esg/assessments/{assessment.id}/recompute-score?referentiel_id={score.referential_id}"
        )
        assert resp.status_code == 202
        body = resp.json()
        assert str(score.referential_id) in body["referentials_to_recompute"]
    finally:
        del app.dependency_overrides[get_current_user]


async def test_post_recompute_score_404_on_unknown_assessment(client, db_session):
    """POST recompute-score retourne 404 si assessment inexistant."""
    user, _, _ = await _setup_assessment_with_score(db_session)
    fake_id = uuid.uuid4()

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        resp = await client.post(
            f"/api/esg/assessments/{fake_id}/recompute-score"
        )
        assert resp.status_code == 404
    finally:
        del app.dependency_overrides[get_current_user]
