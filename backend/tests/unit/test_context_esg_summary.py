"""T015 (F048 US2) — Résumé ESG-projet proactif dans le contexte LangGraph (D2).

Réf. contracts/chat-context-esg.md T1–T4.

``_load_full_context_for_state`` doit retourner une clé ``project_esg_assessments``
(résumé léger joint aux projets actifs) :
- T1 : compteurs corrects pour une évaluation existante ;
- T2 : ``[]`` si aucune évaluation ;
- T3 : ``[]`` (pas d'exception) en cas d'erreur SQL ;
- T4 : scoping ``account_id`` (RLS F02) — uniquement les évaluations du tenant.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.api.chat import _load_full_context_for_state
from app.models.account import Account
from app.models.project import Project
from app.models.referential import Referential
from app.models.source import Source
from app.models.user import User
from app.modules.esg.project_models import (
    ProjectEsgAssessment,
    ProjectEsgCriterionResponse,
)

pytestmark = pytest.mark.asyncio


async def _make_account_user(db_session, *, name: str = "PME"):
    account = Account(name=f"{name}-{uuid.uuid4().hex[:6]}")
    db_session.add(account)
    await db_session.flush()
    user = User(
        email=f"u-{uuid.uuid4().hex[:6]}@test.com", hashed_password="x",
        full_name="U", company_name="Co", role="PME", account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()
    return account, user


async def _make_referential(db_session) -> Referential:
    a1 = User(email=f"a1-{uuid.uuid4().hex[:6]}@m.test", hashed_password="x",
              full_name="A1", company_name="M", role="ADMIN", account_id=None)
    a2 = User(email=f"a2-{uuid.uuid4().hex[:6]}@m.test", hashed_password="x",
              full_name="A2", company_name="M", role="ADMIN", account_id=None)
    db_session.add_all([a1, a2])
    await db_session.flush()
    src = Source(
        url=f"https://ex.test/{uuid.uuid4().hex[:6]}", title="S", publisher="P",
        version="1.0", date_publi=date.today(), captured_by=a1.id,
        created_by_user_id=a1.id, verified_by=a2.id,
        verified_at=datetime.now(timezone.utc), verification_status="verified",
    )
    db_session.add(src)
    await db_session.flush()
    ref = Referential(
        code="boad_ess", label="BOAD ESS", description="d", source_id=src.id,
        publication_status="published", created_by_user_id=a1.id,
    )
    db_session.add(ref)
    await db_session.flush()
    return ref


async def test_t1_summary_present_with_correct_counts(db_session):
    """T1 — évaluation existante : résumé présent, compteurs corrects."""
    account, user = await _make_account_user(db_session)
    ref = await _make_referential(db_session)
    project = Project(account_id=account.id, name="Projet Solaire", status="draft")
    db_session.add(project)
    await db_session.flush()

    assessment = ProjectEsgAssessment(
        account_id=account.id, project_id=project.id, referential_id=ref.id,
        referential_version="1.0", state="finalized", score=55,
        coverage_rate=Decimal("0.620"),
        covered_criteria=[str(uuid.uuid4()), str(uuid.uuid4())],
        missing_criteria=[str(uuid.uuid4())],
        finalized_at=datetime.now(timezone.utc), created_by=user.id,
    )
    db_session.add(assessment)
    await db_session.flush()
    # 2 réponses persistées → covered_count attendu = 2
    for _ in range(2):
        db_session.add(ProjectEsgCriterionResponse(
            account_id=account.id, assessment_id=assessment.id,
            criterion_id=uuid.uuid4(), response_type="qcu",
            response_value={"choice": "oui"}, normalized_score=Decimal("1.000"),
            source_id=None, unsourced=True,
        ))
    await db_session.flush()

    ctx = await _load_full_context_for_state(db_session, user.id)

    assert "project_esg_assessments" in ctx
    items = ctx["project_esg_assessments"]
    assert len(items) == 1
    item = items[0]
    assert item["project_id"] == str(project.id)
    assert item["assessment_id"] == str(assessment.id)
    assert item["referential_code"] == "boad_ess"
    assert item["state"] == "finalized"
    assert item["score"] == 55
    assert item["covered_count"] == 2
    assert item["missing_count"] == 1


async def test_t2_empty_when_no_assessment(db_session):
    """T2 — aucune évaluation : clé présente = []."""
    account, user = await _make_account_user(db_session)
    db_session.add(Project(account_id=account.id, name="P", status="draft"))
    await db_session.flush()

    ctx = await _load_full_context_for_state(db_session, user.id)
    assert ctx["project_esg_assessments"] == []


async def test_t3_sql_error_returns_empty_no_raise(db_session):
    """T3 — erreur SQL : retour [] sans exception propagée."""
    account, user = await _make_account_user(db_session)

    # On patche la fonction de résumé pour simuler une erreur SQL interne.
    with patch(
        "app.api.chat._load_project_esg_assessments_summary",
        new_callable=AsyncMock,
        side_effect=RuntimeError("DB down"),
    ):
        ctx = await _load_full_context_for_state(db_session, user.id)

    assert ctx["project_esg_assessments"] == []


async def test_t4_multitenant_scoping(db_session):
    """T4 — seules les évaluations de l'account du user sont retournées."""
    account_a, user_a = await _make_account_user(db_session, name="A")
    account_b, user_b = await _make_account_user(db_session, name="B")
    ref = await _make_referential(db_session)

    proj_b = Project(account_id=account_b.id, name="ProjB", status="draft")
    db_session.add(proj_b)
    await db_session.flush()
    db_session.add(ProjectEsgAssessment(
        account_id=account_b.id, project_id=proj_b.id, referential_id=ref.id,
        referential_version="1.0", state="draft", created_by=user_b.id,
    ))
    await db_session.flush()

    # user_a n'a aucune évaluation → ne doit PAS voir celle de l'account B.
    ctx = await _load_full_context_for_state(db_session, user_a.id)
    assert ctx["project_esg_assessments"] == []
