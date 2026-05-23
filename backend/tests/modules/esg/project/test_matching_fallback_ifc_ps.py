"""T044 [US2] — Fallback IFC PS pour les fonds sans ESS déclaré.

Lorsqu'un fonds ne déclare ni « GCF » ni « BOAD » dans son nom/organisation,
le matching doit utiliser l'évaluation IFC PS (référentiel universel) si elle
existe, avec `is_fallback=True` pour transparence UI.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.referential import Referential
from app.modules.esg.project_models import ProjectEsgAssessment
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
class TestFallbackIfcPs:
    async def test_fund_without_ess_uses_ifc_ps_with_flag(
        self, db_session, pme_user, project,
    ):
        await _persist_finalized(
            db_session,
            account_id=pme_user.account_id,
            project_id=project.id,
            user_id=pme_user.id,
            ref_code="ifc_ps",
            score=82,
        )
        fund = SimpleNamespace(
            name="Crédit Bilateral Pays-Bas",
            organization="Bilateral Agency",
        )

        score, meta = await _get_project_esg_subscore(
            db_session,
            account_id=pme_user.account_id,
            project_id=project.id,
            fund=fund,
        )

        assert score == 82
        assert meta["source_kind"] == "calculated"
        assert meta["is_fallback"] is True
        assert meta["referential_used"]["code"] == "ifc_ps"

    async def test_no_assessment_no_fallback_returns_zero_unsourced(
        self, db_session, pme_user, project,
    ):
        fund = SimpleNamespace(
            name="Crédit Bilateral",
            organization="Bilateral Agency",
        )
        # Aucune évaluation, project.project_esg_score absent (legacy F045)
        project.project_esg_score = None

        score, meta = await _get_project_esg_subscore(
            db_session,
            account_id=pme_user.account_id,
            project_id=project.id,
            fund=fund,
        )

        assert score == 0
        assert meta["source_kind"] == "unsourced"
        assert meta["unsourced"] is True
        assert meta["referential_used"]["code"] == "ifc_ps"
        # CTA hint contient le référentiel attendu pour démarrage rapide.
        assert "ifc" in meta["cta_hint"].lower() or "ESG" in meta["cta_hint"]

    async def test_legacy_f045_score_used_when_no_assessment(
        self, db_session, pme_user, project,
    ):
        """Rétrocompat : si pas d'évaluation finalisée, on tombe sur le
        ``projects.project_esg_score`` legacy F045 (saisie manuelle PME)."""
        project.project_esg_score = 42
        await db_session.flush()

        fund = SimpleNamespace(name="Bilateral X", organization="X")

        score, meta = await _get_project_esg_subscore(
            db_session,
            account_id=pme_user.account_id,
            project_id=project.id,
            fund=fund,
        )

        assert score == 42
        assert meta["source_kind"] == "manual_f045"
        assert meta["assessment_id"] is None
        assert meta["unsourced"] is False
