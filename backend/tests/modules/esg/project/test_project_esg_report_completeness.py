"""[fix F047 US3] — Verrou de complétude du rapport ESIA-light.

Bug observé live : les rapports ESIA-light étaient très courts car le workflow
ne collectait QUE les ~4 critères ``is_required=True`` (sur 15-16 applicables),
et la Section 5 « Mesures d'atténuation » se réduisait à un paragraphe
générique dès que ces obligatoires étaient couverts (``missing_required`` vide).

Ce test verrouille deux garanties du fix :

(A) La Section 5 du rapport liste TOUS les critères applicables non couverts
    (et pas seulement les obligatoires), pour matérialiser les axes restants
    même quand les 4 obligatoires sont renseignés.

(B) Le workflow exposé au LLM (``create_project_esg_assessment``) instruit la
    collecte de TOUS les critères applicables, pas seulement ``is_required``.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.indicator import Criterion
from app.models.referential import Referential
from app.modules.esg.project_models import (
    ProjectEsgAssessment,
    ProjectEsgCriterionResponse,
)
from app.modules.esg.project_report import render_project_esg_html


async def _ifc_criteria(db_session) -> tuple[Referential, list[Criterion]]:
    ref = (
        await db_session.execute(
            select(Referential).where(Referential.code == "ifc_ps"),
        )
    ).scalar_one()
    crits = (
        await db_session.execute(
            select(Criterion).where(
                Criterion.referential_id == ref.id,
                Criterion.applies_to_project.is_(True),
            )
        )
    ).scalars().all()
    return ref, list(crits)


@pytest.mark.asyncio
class TestReportListsAllUncoveredCriteria:
    """(A) Section 5 doit lister tous les critères non couverts."""

    async def test_section5_lists_non_required_uncovered_criteria(
        self, db_session, pme_user, project,
    ):
        ref, crits = await _ifc_criteria(db_session)
        required = [c for c in crits if c.is_required]
        non_required = [c for c in crits if not c.is_required]
        assert required, "Le référentiel IFC PS doit avoir des critères requis."
        assert non_required, (
            "Le référentiel IFC PS doit avoir des critères non requis "
            "(sinon le test n'est pas discriminant)."
        )

        a = ProjectEsgAssessment(
            account_id=pme_user.account_id,
            project_id=project.id,
            referential_id=ref.id,
            referential_version=str(ref.version or "1.0"),
            state="finalized",
            score=55,
            pillar_scores={"IFCPS1": 60},
            covered_criteria=[str(c.id) for c in required],
            missing_criteria=[str(c.id) for c in non_required],
            coverage_rate=Decimal("0.267"),
            finalized_at=datetime.now(timezone.utc),
            created_by=pme_user.id,
            snapshot_data={"scoring_formula": "weighted_avg"},
        )
        db_session.add(a)
        await db_session.flush()

        # On ne couvre QUE les critères obligatoires (reproduit le bug live).
        from app.models.source import Source
        src = (await db_session.execute(select(Source).limit(1))).scalar_one()
        for c in required:
            db_session.add(
                ProjectEsgCriterionResponse(
                    account_id=pme_user.account_id,
                    assessment_id=a.id,
                    criterion_id=c.id,
                    response_type="qcu",
                    response_value={"choice": "yes"},
                    normalized_score=Decimal("1.000"),
                    source_id=src.id,
                    unsourced=False,
                )
            )
        await db_session.flush()

        html = await render_project_esg_html(
            db_session,
            account_id=pme_user.account_id,
            assessment_id=a.id,
            include_appendix_sources=False,
        )

        # Avant le fix : seuls les obligatoires manquants apparaissaient en
        # Section 5 → ici aucun (tous couverts) → paragraphe générique.
        # Après le fix : tous les non couverts (dont non-requis) sont listés.
        missing_sample = non_required[0]
        assert missing_sample.code in html, (
            "La Section 5 doit lister les critères non requis non couverts "
            f"(attendu : {missing_sample.code!r})."
        )


@pytest.mark.unit
class TestWorkflowCollectsAllApplicableCriteria:
    """(B) Le workflow doit instruire la collecte de tous les critères."""

    @pytest.mark.asyncio
    async def test_create_next_step_targets_all_criteria(
        self, db_session, pme_user, project,
    ):
        from app.graph.tools.project_esg_tools import create_project_esg_assessment

        ref = (
            await db_session.execute(
                select(Referential).where(Referential.code == "ifc_ps"),
            )
        ).scalar_one()
        cfg = {
            "configurable": {
                "db": db_session,
                "user_id": str(pme_user.id),
                "account_id": str(pme_user.account_id),
            }
        }
        out = json.loads(
            await create_project_esg_assessment.ainvoke(
                {"project_id": project.id, "referential_id": ref.id},
                config=cfg,
            )
        )
        next_step = out["next_step"].lower()
        assert "tous" in next_step, (
            "Le next_step doit instruire de collecter TOUS les critères "
            f"applicables, pas seulement les obligatoires. Reçu : {out['next_step']!r}"
        )
        # La collecte doit explicitement s'étendre aux critères recommandés
        # (non obligatoires) — c'est ce qui étoffe le rapport ESIA-light.
        assert "recommand" in next_step, (
            "Le next_step doit mentionner la collecte des critères recommandés "
            f"(non obligatoires). Reçu : {out['next_step']!r}"
        )
