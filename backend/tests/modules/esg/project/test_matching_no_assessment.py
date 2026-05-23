"""T045 [US2] — Sans évaluation pour le référentiel cible, retourne 0+unsourced + CTA.

Quand un fonds GCF est ciblé alors qu'aucune évaluation GCF ESS n'existe et que
le projet ne possède pas non plus d'évaluation IFC PS de repli, le sub-score
projet_esg doit valoir 0 avec `unsourced=true` et un CTA hint « démarrer
évaluation GCF ESS ».
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.modules.financing.matching_service import (
    _get_project_esg_subscore,
)


@pytest.mark.asyncio
class TestNoAssessmentCta:
    async def test_gcf_target_without_any_assessment_returns_cta(
        self, db_session, pme_user, project,
    ):
        fund = SimpleNamespace(
            name="Green Climate Fund",
            organization="GCF",
        )
        project.project_esg_score = None

        score, meta = await _get_project_esg_subscore(
            db_session,
            account_id=pme_user.account_id,
            project_id=project.id,
            fund=fund,
        )

        assert score == 0
        assert meta["unsourced"] is True
        assert meta["source_kind"] == "unsourced"
        assert meta["referential_used"]["code"] == "gcf_ess"
        # Le CTA mentionne le référentiel cible attendu pour le fonds.
        assert "GCF" in meta["cta_hint"] or "gcf" in meta["cta_hint"].lower()
        assert "démarr" in meta["cta_hint"].lower() or "lanc" in meta["cta_hint"].lower()

    async def test_boad_target_without_assessment_returns_cta_boad(
        self, db_session, pme_user, project,
    ):
        fund = SimpleNamespace(
            name="BOAD Ligne Climat",
            organization="Banque Ouest Africaine de Développement",
        )
        project.project_esg_score = None

        score, meta = await _get_project_esg_subscore(
            db_session,
            account_id=pme_user.account_id,
            project_id=project.id,
            fund=fund,
        )

        assert score == 0
        assert meta["unsourced"] is True
        assert meta["referential_used"]["code"] == "boad_ess"
        assert "BOAD" in meta["cta_hint"]
