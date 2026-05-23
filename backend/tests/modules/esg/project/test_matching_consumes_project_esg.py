"""T043 [US2] — _compute_project_score consomme `ProjectEsgAssessment.score`.

Le matching projet-centric F045 doit choisir automatiquement le référentiel
selon le fonds ciblé :
- nom contenant "GCF" ou "Green Climate Fund" → `gcf_ess`
- nom contenant "BOAD" ou "Banque Ouest Africaine" → `boad_ess`
- sinon → `ifc_ps` (fallback universel, `is_fallback=True`)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.indicator import Criterion
from app.models.referential import Referential
from app.modules.esg.project_models import (
    ProjectEsgAssessment,
    ProjectEsgCriterionResponse,
)
from app.modules.financing.matching_service import (
    _get_project_esg_subscore,
)


async def _persist_finalized(
    db_session,
    *,
    account_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    ref_code: str,
    score: int,
) -> ProjectEsgAssessment:
    ref = (
        await db_session.execute(
            select(Referential).where(Referential.code == ref_code),
        )
    ).scalar_one()
    a = ProjectEsgAssessment(
        account_id=account_id,
        project_id=project_id,
        referential_id=ref.id,
        referential_version=str(ref.version or "1.0"),
        state="finalized",
        score=score,
        pillar_scores={},
        covered_criteria=[],
        missing_criteria=[],
        coverage_rate=Decimal("1.000"),
        finalized_at=datetime.now(timezone.utc),
        created_by=user_id,
    )
    db_session.add(a)
    await db_session.flush()
    return a


@pytest.mark.asyncio
class TestSubScoreSelectsReferentialByFund:
    async def test_fund_gcf_consumes_gcf_ess_score(
        self, db_session, pme_user, project,
    ):
        await _persist_finalized(
            db_session,
            account_id=pme_user.account_id,
            project_id=project.id,
            user_id=pme_user.id,
            ref_code="gcf_ess",
            score=60,
        )
        await _persist_finalized(
            db_session,
            account_id=pme_user.account_id,
            project_id=project.id,
            user_id=pme_user.id,
            ref_code="ifc_ps",
            score=75,
        )
        fund = SimpleNamespace(
            name="Green Climate Fund",
            organization="GCF",
        )

        score, meta = await _get_project_esg_subscore(
            db_session,
            account_id=pme_user.account_id,
            project_id=project.id,
            fund=fund,
        )

        assert score == 60, "Le matching GCF doit prioriser GCF ESS (60)"
        assert meta["source_kind"] == "calculated"
        assert meta["is_fallback"] is False
        assert meta["unsourced"] is False
        assert meta["referential_used"]["code"] == "gcf_ess"

    async def test_fund_boad_consumes_boad_ess_score(
        self, db_session, pme_user, project,
    ):
        await _persist_finalized(
            db_session,
            account_id=pme_user.account_id,
            project_id=project.id,
            user_id=pme_user.id,
            ref_code="boad_ess",
            score=55,
        )
        fund = SimpleNamespace(
            name="BOAD Ligne Climat",
            organization="Banque Ouest Africaine de Développement",
        )

        score, meta = await _get_project_esg_subscore(
            db_session,
            account_id=pme_user.account_id,
            project_id=project.id,
            fund=fund,
        )

        assert score == 55
        assert meta["source_kind"] == "calculated"
        assert meta["is_fallback"] is False
        assert meta["referential_used"]["code"] == "boad_ess"
