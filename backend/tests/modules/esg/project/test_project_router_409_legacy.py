"""T072 [US5] — PATCH /projects/{id} rejette `project_esg_score` quand une
évaluation finalisée existe (FR-033).
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
from app.modules.projects import service as projects_service
from app.modules.projects.schemas import ProjectUpdate


@pytest.mark.asyncio
class TestPatchProjectEsgScoreLegacy:
    async def test_patch_score_accepted_without_assessment(
        self, db_session, pme_user, project,
    ):
        """Aucune évaluation finalisée → PATCH accepté."""
        payload = ProjectUpdate(project_esg_score=42)
        updated = await projects_service.update_project(
            db_session,
            account_id=pme_user.account_id,
            project_id=project.id,
            payload=payload,
        )
        assert updated is not None
        assert updated.project_esg_score == 42

    async def test_patch_score_refused_409_when_finalized_exists(
        self, db_session, pme_user, project,
    ):
        ref = (
            await db_session.execute(
                select(Referential).where(Referential.code == "ifc_ps"),
            )
        ).scalar_one()
        db_session.add(
            ProjectEsgAssessment(
                account_id=pme_user.account_id,
                project_id=project.id,
                referential_id=ref.id,
                referential_version="1.0",
                state="finalized",
                score=70,
                pillar_scores={}, covered_criteria=[], missing_criteria=[],
                coverage_rate=Decimal("1.000"),
                finalized_at=datetime.now(timezone.utc),
                created_by=pme_user.id,
            )
        )
        await db_session.flush()

        payload = ProjectUpdate(project_esg_score=12)
        with pytest.raises(HTTPException) as exc:
            await projects_service.update_project(
                db_session,
                account_id=pme_user.account_id,
                project_id=project.id,
                payload=payload,
            )
        assert exc.value.status_code == 409
        detail = exc.value.detail
        text = detail["message"] if isinstance(detail, dict) else str(detail)
        assert "évaluation" in text.lower() or "evaluation" in text.lower()
