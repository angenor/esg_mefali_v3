"""F13 — Tests unitaires du modèle SQLAlchemy ReferentialScore (T005)."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.esg import ESGAssessment, ESGStatusEnum
from app.models.referential_score import ComputedByEnum, ReferentialScore
from app.models.user import User
from tests.conftest import make_account


pytestmark = pytest.mark.asyncio


async def _make_minimal_assessment(db_session) -> tuple[Account, User, ESGAssessment]:
    """Crée un account/user/assessment minimal pour les tests."""
    account = Account(name=f"TestCo-{uuid.uuid4().hex[:6]}")
    db_session.add(account)
    await db_session.flush()

    user = User(
        email=f"u-{uuid.uuid4().hex[:6]}@t.com",
        hashed_password="x",
        full_name="T",
        company_name="T",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()

    assessment = ESGAssessment(
        user_id=user.id,
        account_id=account.id,
        sector="agriculture",
        status=ESGStatusEnum.completed,
        overall_score=72.5,
        environment_score=70.0,
        social_score=75.0,
        governance_score=72.5,
    )
    db_session.add(assessment)
    await db_session.flush()
    return account, user, assessment


async def _make_minimal_referential(db_session, account, user) -> uuid.UUID:
    """Crée une Source + un Referential minimal pour FK."""
    from datetime import date

    from app.models.referential import Referential
    from app.models.source import Source, VerificationStatus

    # Source 4-yeux : captured_by != verified_by, on crée un 2nd user pour vérification
    verifier = User(
        email=f"v-{uuid.uuid4().hex[:6]}@t.com",
        hashed_password="x",
        full_name="V",
        company_name="V",
        account_id=account.id,
    )
    db_session.add(verifier)
    await db_session.flush()

    from datetime import datetime, timezone

    source = Source(
        url=f"https://example.com/r-{uuid.uuid4().hex[:6]}",
        title="Source test",
        publisher="Test",
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
        code=f"test-{uuid.uuid4().hex[:6]}",
        label="Test Referential",
        description="Référentiel de test pour les unit tests F13.",
        source_id=source.id,
        publication_status="published",
        account_id=account.id,
        created_by_user_id=user.id,
    )
    db_session.add(referential)
    await db_session.flush()
    return referential.id


async def test_create_referential_score_with_all_fields(db_session):
    """T005 (a) — créer un ReferentialScore avec tous les champs."""
    account, user, assessment = await _make_minimal_assessment(db_session)
    ref_id = await _make_minimal_referential(db_session, account, user)

    score = ReferentialScore(
        account_id=account.id,
        assessment_id=assessment.id,
        referential_id=ref_id,
        referential_version="1.0",
        overall_score=72.5,
        pillar_scores={"environment": {"score": 70.0, "weight": 0.33, "criteria_count": 10, "criteria_renseignés": 8}},
        coverage_rate=0.85,
        covered_criteria=[],
        missing_criteria=[],
        gap_to_threshold=22.5,
        eligibility=True,
        computed_by=ComputedByEnum.AUTO,
    )
    db_session.add(score)
    await db_session.flush()

    assert score.id is not None
    assert score.account_id == account.id
    assert score.assessment_id == assessment.id
    assert score.referential_id == ref_id
    assert score.computed_by == ComputedByEnum.AUTO


async def test_referential_score_default_jsonb_values(db_session):
    """T005 (e) — defaults pillar_scores={}, covered_criteria=[], missing_criteria=[]."""
    account, user, assessment = await _make_minimal_assessment(db_session)
    ref_id = await _make_minimal_referential(db_session, account, user)

    score = ReferentialScore(
        account_id=account.id,
        assessment_id=assessment.id,
        referential_id=ref_id,
        referential_version="1.0",
        coverage_rate=0.0,
        computed_by=ComputedByEnum.MANUAL,
    )
    db_session.add(score)
    await db_session.flush()

    assert score.pillar_scores == {}
    assert score.covered_criteria == []
    assert score.missing_criteria == []


async def test_referential_score_superseded_by_self_reference(db_session):
    """T005 (c) — pattern superseded_by self-référent.

    Insère v1 (courante), pré-génère un UUID pour v2, marque v1.superseded_by=v2_uuid
    avant l'insert de v2 (l'index unique partiel ``WHERE superseded_by IS NULL``
    n'a alors qu'une seule ligne courante : v2).
    """
    account, user, assessment = await _make_minimal_assessment(db_session)
    ref_id = await _make_minimal_referential(db_session, account, user)

    s1 = ReferentialScore(
        account_id=account.id,
        assessment_id=assessment.id,
        referential_id=ref_id,
        referential_version="1.0",
        overall_score=70.0,
        coverage_rate=0.5,
        computed_by=ComputedByEnum.AUTO,
    )
    db_session.add(s1)
    await db_session.flush()

    # Pré-génère l'UUID de v2 ET marque v1.superseded_by avant l'insert de v2
    v2_uuid = uuid.uuid4()
    s1.superseded_by = v2_uuid
    await db_session.flush()  # v1 n'est plus « courante »

    s2 = ReferentialScore(
        id=v2_uuid,
        account_id=account.id,
        assessment_id=assessment.id,
        referential_id=ref_id,
        referential_version="1.1",
        overall_score=72.0,
        coverage_rate=0.6,
        computed_by=ComputedByEnum.AUTO,
    )
    db_session.add(s2)
    await db_session.flush()

    # Re-fetch
    rows = (await db_session.execute(
        select(ReferentialScore).where(ReferentialScore.assessment_id == assessment.id)
    )).scalars().all()
    assert len(rows) == 2

    superseded = [r for r in rows if r.superseded_by is not None]
    current = [r for r in rows if r.superseded_by is None]
    assert len(superseded) == 1
    assert len(current) == 1
    assert superseded[0].superseded_by == current[0].id


async def test_referential_score_computed_by_enum_values(db_session):
    """T005 (d) — valeurs ENUM ComputedByEnum (manual/llm/auto).

    Utilise 3 référentiels distincts pour éviter de heurter l'index unique
    partiel ``(assessment_id, referential_id) WHERE superseded_by IS NULL``.
    """
    account, user, assessment = await _make_minimal_assessment(db_session)

    for value in (ComputedByEnum.MANUAL, ComputedByEnum.LLM, ComputedByEnum.AUTO):
        ref_id = await _make_minimal_referential(db_session, account, user)
        score = ReferentialScore(
            account_id=account.id,
            assessment_id=assessment.id,
            referential_id=ref_id,
            referential_version="1.0",
            coverage_rate=0.0,
            computed_by=value,
        )
        db_session.add(score)
    await db_session.flush()

    rows = (await db_session.execute(
        select(ReferentialScore).where(ReferentialScore.assessment_id == assessment.id)
    )).scalars().all()
    values = {r.computed_by for r in rows}
    assert values == {ComputedByEnum.MANUAL, ComputedByEnum.LLM, ComputedByEnum.AUTO}
