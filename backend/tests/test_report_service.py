"""Tests unitaires du service de generation de rapports ESG (T013).

Verifie la logique metier : validation, generation complete avec mock LLM.
"""

import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.esg import ESGAssessment, ESGStatusEnum
from app.models.report import Report, ReportStatusEnum
from app.models.user import User
from tests.conftest import make_unique_email


async def create_test_user(db: AsyncSession) -> User:
    """Creer un utilisateur de test (F02 : Account requis)."""
    from app.models.account import Account

    account = Account(name="GreenTech SARL")
    db.add(account)
    await db.flush()
    user = User(
        email=make_unique_email(),
        hashed_password="fakehash",
        full_name="Aminata Toure",
        company_name="GreenTech SARL",
        account_id=account.id,
    )
    db.add(user)
    await db.flush()
    return user


async def create_completed_assessment(db: AsyncSession, user_id: uuid.UUID) -> ESGAssessment:
    """Creer une evaluation ESG completee avec donnees realistes."""
    assessment = ESGAssessment(
        user_id=user_id,
        status=ESGStatusEnum.completed,
        sector="agriculture",
        overall_score=71.7,
        environment_score=72.0,
        social_score=58.0,
        governance_score=85.0,
        assessment_data={
            "criteria_scores": {
                "E1": {"score": 7, "justification": "Bonne gestion", "sources": []},
                "E2": {"score": 5, "justification": "Peut mieux faire", "sources": []},
                "S1": {"score": 6, "justification": "Correct", "sources": []},
                "G1": {"score": 9, "justification": "Excellent", "sources": []},
            },
            "pillar_details": {
                "environment": {"raw_score": 6.0, "weighted_score": 72.0, "weights_applied": {}},
                "social": {"raw_score": 5.8, "weighted_score": 58.0, "weights_applied": {}},
                "governance": {"raw_score": 8.5, "weighted_score": 85.0, "weights_applied": {}},
            },
        },
        recommendations=[
            {
                "priority": 1,
                "criteria_code": "E2",
                "pillar": "environment",
                "title": "Ameliorer l'efficacite energetique",
                "description": "Investir dans les energies renouvelables",
                "impact": "high",
                "effort": "medium",
                "timeline": "6 mois",
            }
        ],
        strengths=[
            {
                "criteria_code": "G1",
                "pillar": "governance",
                "title": "Gouvernance exemplaire",
                "description": "Structure de gouvernance solide",
                "score": 9,
            }
        ],
        gaps=[
            {"criteria_code": "E2", "pillar": "environment", "title": "Energie", "score": 5}
        ],
        sector_benchmark={
            "sector": "agriculture",
            "averages": {
                "environment": 55.0,
                "social": 60.0,
                "governance": 50.0,
                "overall": 55.0,
            },
            "position": "above_average",
            "percentile": 75,
        },
    )
    db.add(assessment)
    await db.flush()
    return assessment


class TestGenerateReport:
    """Tests de la fonction generate_report."""

    @pytest.mark.asyncio
    async def test_generate_report_success(self, db_session: AsyncSession) -> None:
        """T013-01 : Generation reussie d'un rapport PDF."""
        user = await create_test_user(db_session)
        assessment = await create_completed_assessment(db_session, user.id)
        await db_session.commit()

        mock_weasyprint = MagicMock()

        def _fake_write_pdf(path):
            """Creer un faux fichier PDF sur disque pour que stat() fonctionne."""
            from pathlib import Path

            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(b"%PDF-1.4 fake content")

        mock_weasyprint.HTML.return_value.write_pdf.side_effect = _fake_write_pdf

        with (
            patch(
                "app.modules.reports.service.generate_executive_summary",
                new_callable=AsyncMock,
                return_value="Resume executif de test genere par IA.",
            ),
            patch.dict(sys.modules, {"weasyprint": mock_weasyprint}),
        ):
            from app.modules.reports.service import generate_report

            report = await generate_report(db_session, assessment.id, user.id)

        assert report is not None
        assert report.status == ReportStatusEnum.completed
        assert report.assessment_id == assessment.id
        assert report.user_id == user.id
        assert report.file_size is not None
        assert report.file_size > 0
        assert report.generated_at is not None

    @pytest.mark.asyncio
    async def test_generate_report_rejects_draft_assessment(self, db_session: AsyncSession) -> None:
        """T013-02 : Rejet si l'evaluation n'est pas completee."""
        from app.modules.reports.service import generate_report

        user = await create_test_user(db_session)
        assessment = ESGAssessment(
            user_id=user.id,
            status=ESGStatusEnum.draft,
            sector="agriculture",
        )
        db_session.add(assessment)
        await db_session.commit()

        with pytest.raises(ValueError, match="completed"):
            await generate_report(db_session, assessment.id, user.id)

    @pytest.mark.asyncio
    async def test_generate_report_rejects_nonexistent_assessment(
        self, db_session: AsyncSession
    ) -> None:
        """T013-03 : Rejet si l'evaluation n'existe pas."""
        from app.modules.reports.service import generate_report

        user = await create_test_user(db_session)
        await db_session.commit()

        fake_id = uuid.uuid4()
        with pytest.raises(ValueError, match="introuvable"):
            await generate_report(db_session, fake_id, user.id)

    @pytest.mark.asyncio
    async def test_collect_mobilized_sources_returns_empty_without_conversation(
        self, db_session: AsyncSession
    ) -> None:
        """F01 - retourner [] si pas de conversation_id sur l'assessment."""
        from app.modules.reports.service import _collect_mobilized_sources

        user = await create_test_user(db_session)
        assessment = ESGAssessment(
            user_id=user.id,
            status=ESGStatusEnum.completed,
            sector="agriculture",
        )
        db_session.add(assessment)
        await db_session.commit()

        sources = await _collect_mobilized_sources(db_session, assessment)
        assert sources == []

    def test_render_html_includes_sources_appendix_when_provided(self) -> None:
        """F01 - le template inclut l'annexe Sources si mobilized_sources non vide."""
        from app.modules.reports.service import _render_html

        # Stub minimal d'assessment et user pour le rendu
        assessment = MagicMock()
        assessment.sector = "agriculture"
        assessment.overall_score = 70
        assessment.environment_score = 70
        assessment.social_score = 60
        assessment.governance_score = 80
        assessment.strengths = []
        assessment.gaps = []
        assessment.recommendations = []
        assessment.sector_benchmark = {}

        user = MagicMock()
        user.company_name = "TestCorp"

        mobilized = [
            {
                "index": 1,
                "title": "ADEME Base Carbone v23",
                "publisher": "ADEME",
                "version": "v23",
                "date_publi": "2024-01-15",
                "page": None,
                "section": "",
                "url": "https://example.com/ademe",
                "verification_status": "verified",
            }
        ]

        html = _render_html(
            assessment=assessment,
            user=user,
            executive_summary="Test summary",
            radar_svg="<svg/>",
            pillar_bar_charts={"environment": "", "social": "", "governance": ""},
            benchmark_svg=None,
            pillar_criteria={"environment": [], "social": [], "governance": []},
            mobilized_sources=mobilized,
        )
        assert "Sources et references" in html
        assert "ADEME Base Carbone v23" in html
        assert "[1]" in html
        assert "https://example.com/ademe" in html

    def test_render_html_shows_no_sources_message_when_empty(self) -> None:
        """F01 - le template affiche le message vide si mobilized_sources vide."""
        from app.modules.reports.service import _render_html

        assessment = MagicMock()
        assessment.sector = "agriculture"
        assessment.overall_score = 70
        assessment.environment_score = 70
        assessment.social_score = 60
        assessment.governance_score = 80
        assessment.strengths = []
        assessment.gaps = []
        assessment.recommendations = []
        assessment.sector_benchmark = {}

        user = MagicMock()
        user.company_name = "TestCorp"

        html = _render_html(
            assessment=assessment,
            user=user,
            executive_summary="Test summary",
            radar_svg="<svg/>",
            pillar_bar_charts={"environment": "", "social": "", "governance": ""},
            benchmark_svg=None,
            pillar_criteria={"environment": [], "social": [], "governance": []},
            mobilized_sources=[],
        )
        assert "Sources et references" in html
        assert "Aucune source mobilisee" in html
