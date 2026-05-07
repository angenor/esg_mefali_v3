"""F13 — Tests unitaires des tools LangChain multi-référentiels (T071)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from langchain_core.runnables import RunnableConfig

from app.core.constants import MEFALI_REFERENTIAL_CODE, MEFALI_REFERENTIAL_UUID
from app.graph.tools.esg_tools import (
    compare_referentials,
    finalize_esg_assessment_multi_ref,
    recompute_score,
)
from app.models.account import Account
from app.models.esg import ESGAssessment, ESGStatusEnum
from app.models.referential import Referential
from app.models.referential_score import ComputedByEnum, ReferentialScore
from app.models.source import Source, VerificationStatus
from app.models.user import User


pytestmark = pytest.mark.asyncio


async def _setup(db_session) -> tuple[User, Referential, ESGAssessment]:
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
    return user, ref, a


async def test_finalize_multi_ref_returns_summary(db_session):
    """finalize_esg_assessment_multi_ref calcule les référentiels."""
    user, ref, a = await _setup(db_session)

    config: RunnableConfig = {
        "configurable": {"db": db_session, "user_id": str(user.id)},
    }

    result = await finalize_esg_assessment_multi_ref.ainvoke(
        {"assessment_id": str(a.id)}, config=config,
    )
    assert "finalisée" in result
    assert "1 référentiel" in result or "Mefali" in result.lower() or "scores :" in result


async def test_finalize_multi_ref_with_specific_codes(db_session):
    """Filtre les référentiels par codes."""
    user, ref, a = await _setup(db_session)

    config: RunnableConfig = {
        "configurable": {"db": db_session, "user_id": str(user.id)},
    }

    result = await finalize_esg_assessment_multi_ref.ainvoke(
        {
            "assessment_id": str(a.id),
            "referentials_to_compute": [MEFALI_REFERENTIAL_CODE],
        },
        config=config,
    )
    assert "finalisée" in result


async def test_finalize_multi_ref_unknown_assessment(db_session):
    """Erreur structurée si assessment introuvable."""
    user, _, _ = await _setup(db_session)
    config: RunnableConfig = {
        "configurable": {"db": db_session, "user_id": str(user.id)},
    }
    fake_id = str(uuid.uuid4())
    result = await finalize_esg_assessment_multi_ref.ainvoke(
        {"assessment_id": fake_id}, config=config,
    )
    assert "introuvable" in result.lower()


async def test_recompute_score_returns_id(db_session):
    """recompute_score retourne le score recalculé."""
    user, ref, a = await _setup(db_session)
    config: RunnableConfig = {
        "configurable": {"db": db_session, "user_id": str(user.id)},
    }
    result = await recompute_score.ainvoke(
        {"entity_id": str(a.id), "referentiel_id": str(ref.id)},
        config=config,
    )
    assert "recalculé" in result
    assert "Recompute request id" in result


async def test_recompute_score_unknown_referential(db_session):
    """Erreur structurée si référentiel introuvable."""
    user, ref, a = await _setup(db_session)
    config: RunnableConfig = {
        "configurable": {"db": db_session, "user_id": str(user.id)},
    }
    fake_ref = str(uuid.uuid4())
    result = await recompute_score.ainvoke(
        {"entity_id": str(a.id), "referentiel_id": fake_ref},
        config=config,
    )
    assert "introuvable" in result.lower()


async def test_compare_referentials_no_scores(db_session):
    """compare_referentials retourne un message clair si aucun score n'est calculé."""
    user, ref, a = await _setup(db_session)
    config: RunnableConfig = {
        "configurable": {"db": db_session, "user_id": str(user.id)},
    }
    result = await compare_referentials.ainvoke(
        {"assessment_id": str(a.id), "referentials": [MEFALI_REFERENTIAL_CODE]},
        config=config,
    )
    assert "Aucun score calculé" in result


async def test_compare_referentials_with_scores(db_session):
    """compare_referentials retourne la comparaison entre 2 référentiels."""
    user, ref, a = await _setup(db_session)

    # Pré-calculer un score
    score = ReferentialScore(
        account_id=a.account_id,
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

    config: RunnableConfig = {
        "configurable": {"db": db_session, "user_id": str(user.id)},
    }
    result = await compare_referentials.ainvoke(
        {"assessment_id": str(a.id), "referentials": [MEFALI_REFERENTIAL_CODE]},
        config=config,
    )
    assert "mefali" in result.lower()
    assert "70" in result


async def test_recompute_score_args_schema_validation():
    """Validation Pydantic v2 stricte sur les args."""
    from app.graph.tools.esg_tools import RecomputeScoreArgs
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RecomputeScoreArgs(entity_id="not-a-uuid", referentiel_id=str(uuid.uuid4()))


async def test_compare_referentials_args_schema_min_length():
    """compare_referentials exige au moins 1 référentiel."""
    from app.graph.tools.esg_tools import CompareReferentialsArgs
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CompareReferentialsArgs(
            assessment_id=str(uuid.uuid4()), referentials=[],
        )
