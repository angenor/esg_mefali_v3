"""T052 [US3] — Tests du pipeline rapport ESIA-light PDF (F047).

Validations :
- (a) PDF binaire retourné (bytes non vide, magic header)
- (b) Le HTML intermédiaire contient les 7 sections obligatoires
- (c) Annexe sources F01 présente avec ≥ 1 source
- (d) ≥ 1 graphique SVG/PNG embarqué (donut couverts vs manquants)
- (e) Sans GENERATE_REPORT_BENCHMARK, on n'exécute pas pytest-benchmark
  ici (SC-003 < 30 s p95 validé en T085 dédié).
"""

from __future__ import annotations

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
from app.modules.esg.project_report import (
    generate_project_esg_report,
    render_project_esg_html,
)


async def _finalized_assessment_with_responses(
    db_session, *, pme_user, project,
) -> ProjectEsgAssessment:
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
        state="finalized",
        score=72,
        pillar_scores={"IFCPS1": 80, "IFCPS2": 70},
        covered_criteria=[],
        missing_criteria=[],
        coverage_rate=Decimal("0.875"),
        finalized_at=datetime.now(timezone.utc),
        created_by=pme_user.id,
        snapshot_data={"scoring_formula": "weighted_avg"},
    )
    db_session.add(a)
    await db_session.flush()

    crits = (
        await db_session.execute(
            select(Criterion).where(Criterion.referential_id == ref.id).limit(5),
        )
    ).scalars().all()
    # Source F01 (la 1re seedée) pour citer sur les réponses.
    from app.models.source import Source
    src = (await db_session.execute(select(Source).limit(1))).scalar_one()

    for c in crits:
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
    return a


@pytest.mark.asyncio
class TestEsiaReportPipeline:
    async def test_render_html_contains_seven_sections(
        self, db_session, pme_user, project,
    ):
        a = await _finalized_assessment_with_responses(
            db_session, pme_user=pme_user, project=project,
        )
        html = await render_project_esg_html(
            db_session,
            account_id=pme_user.account_id,
            assessment_id=a.id,
            include_appendix_sources=True,
        )
        for section_title in (
            "Résumé exécutif",
            "Description du projet",
            "Diagnostic E&amp;S",
            "Impacts identifiés",
            "Mesures d'atténuation",
            "Engagement des parties prenantes",
            "Indicateurs de suivi",
        ):
            assert section_title in html, (
                f"Section manquante : {section_title!r} dans HTML rendu"
            )
        assert "Annexe" in html and "Sources" in html
        assert "<svg" in html or "data:image" in html, (
            "Au moins un graphique attendu dans le HTML"
        )

    async def test_generate_pdf_returns_bytes(
        self, db_session, pme_user, project,
    ):
        a = await _finalized_assessment_with_responses(
            db_session, pme_user=pme_user, project=project,
        )
        out = await generate_project_esg_report(
            db_session,
            account_id=pme_user.account_id,
            assessment_id=a.id,
            include_appendix_sources=True,
        )
        assert isinstance(out["pdf_bytes"], bytes)
        assert len(out["pdf_bytes"]) > 1024  # PDF minimum plausible
        assert out["pdf_bytes"][:4] == b"%PDF"  # magic header
        assert out["section_count"] == 7
        assert out["chart_count"] >= 1
        assert out["sources_cited"] >= 1
        assert out["template_version"] == "esia_v1"
