"""T053 [US3] — Refus rapport ESIA pour évaluation `draft` (FR-019).

L'évaluation doit être `finalized` pour pouvoir générer un rapport
ESIA-light : sinon HTTP 422 avec message FR explicite.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.referential import Referential
from app.modules.esg.project_models import ProjectEsgAssessment
from app.modules.esg.project_report import generate_project_esg_report


@pytest.mark.asyncio
async def test_generate_report_refused_on_draft(
    db_session, pme_user, project,
):
    ref = (
        await db_session.execute(
            select(Referential).where(Referential.code == "ifc_ps"),
        )
    ).scalar_one()
    a = ProjectEsgAssessment(
        account_id=pme_user.account_id,
        project_id=project.id,
        referential_id=ref.id,
        referential_version=str(ref.version or "1.0"),
        state="draft",
        score=None,
        pillar_scores={},
        covered_criteria=[],
        missing_criteria=[],
        coverage_rate=None,
        finalized_at=None,
        created_by=pme_user.id,
    )
    db_session.add(a)
    await db_session.flush()

    with pytest.raises(HTTPException) as exc:
        await generate_project_esg_report(
            db_session,
            account_id=pme_user.account_id,
            assessment_id=a.id,
        )
    assert exc.value.status_code == 422
    detail = exc.value.detail
    # Détail peut être un dict structuré ou un message brut.
    text = detail["message"] if isinstance(detail, dict) else str(detail)
    assert "finalis" in text.lower()  # « finaliser » / « finalisée »
