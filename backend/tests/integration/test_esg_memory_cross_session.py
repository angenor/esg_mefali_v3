"""T016 (F048 US2) — Mémoire ESG entre sessions (SC-002).

Après saisie de critères (session A), un NOUVEAU chargement de contexte
(session B) expose l'évaluation et son état couvert : le chatbot ne doit plus
présenter comme « manquants » des critères déjà remplis.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.api.chat import _load_full_context_for_state
from app.models.account import Account
from app.models.indicator import Criterion
from app.models.project import Project
from app.models.referential import Referential
from app.models.source import Source
from app.models.user import User
from app.modules.esg.project_schemas import ProjectEsgCriterionResponseSave
from app.modules.esg.project_service import (
    create_project_esg_assessment,
    save_project_esg_criterion_response,
)

pytestmark = pytest.mark.asyncio


async def test_criteria_saved_in_session_a_are_visible_in_session_b(db_session):
    """Saisie ≥ 2 critères → contexte rechargé expose l'évaluation couverte."""
    # --- Setup tenant + référentiel + 2 critères projet ---
    account = Account(name=f"PME-{uuid.uuid4().hex[:6]}")
    db_session.add(account)
    await db_session.flush()
    user = User(
        email=f"pme-{uuid.uuid4().hex[:6]}@test.com", hashed_password="x",
        full_name="PME", company_name="Co", role="PME", account_id=account.id,
    )
    a1 = User(email=f"a1-{uuid.uuid4().hex[:6]}@m.test", hashed_password="x",
              full_name="A1", company_name="M", role="ADMIN", account_id=None)
    a2 = User(email=f"a2-{uuid.uuid4().hex[:6]}@m.test", hashed_password="x",
              full_name="A2", company_name="M", role="ADMIN", account_id=None)
    db_session.add_all([user, a1, a2])
    await db_session.flush()

    source = Source(
        url=f"https://ex.test/{uuid.uuid4().hex[:6]}", title="S", publisher="P",
        version="1.0", date_publi=date.today(), captured_by=a1.id,
        created_by_user_id=a1.id, verified_by=a2.id,
        verified_at=datetime.now(timezone.utc), verification_status="verified",
    )
    db_session.add(source)
    await db_session.flush()

    ref = Referential(
        code="boad_ess", label="BOAD ESS", description="d", source_id=source.id,
        publication_status="published", created_by_user_id=a1.id,
    )
    db_session.add(ref)
    await db_session.flush()

    criteria = []
    for i in range(2):
        c = Criterion(
            code=f"ESS{i+1}-{uuid.uuid4().hex[:4]}", label=f"ESS {i+1}",
            expression={}, source_id=source.id, publication_status="published",
            created_by_user_id=a1.id, weight=Decimal("1.00"),
            is_required=True, applies_to_project=True, referential_id=ref.id,
        )
        db_session.add(c)
        criteria.append(c)
    await db_session.flush()

    project = Project(account_id=account.id, name="Solarisation Boulangerie Dakar", status="draft")
    db_session.add(project)
    await db_session.flush()

    # --- Session A : créer l'évaluation + saisir 2 critères ---
    assessment = await create_project_esg_assessment(
        db_session, account_id=account.id, user_id=user.id,
        project_id=project.id, referential_id=ref.id,
    )
    for crit in criteria:
        await save_project_esg_criterion_response(
            db_session, account_id=account.id, assessment_id=assessment.id,
            payload=ProjectEsgCriterionResponseSave(
                criterion_id=crit.id, response_type="qcu",
                response_value={"choice": "oui"}, unsourced=True,
            ),
        )

    # --- Session B : nouveau chargement de contexte ---
    ctx = await _load_full_context_for_state(db_session, user.id)

    items = ctx["project_esg_assessments"]
    assert len(items) == 1, "l'évaluation doit être exposée en session B"
    item = items[0]
    assert item["project_id"] == str(project.id)
    assert item["assessment_id"] == str(assessment.id)
    assert item["referential_code"] == "boad_ess"
    # SC-002 : les 2 critères saisis sont reconnus couverts (pas « manquants »).
    assert item["covered_count"] == 2
