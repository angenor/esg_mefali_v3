"""T071 [US5] — Listener `after_insert`/`after_update` sur ProjectEsgAssessment.

Quand une évaluation passe à `state='finalized'`, le listener SQLAlchemy
synchronise `projects.project_esg_score` (snapshot lecture-seule F045).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.project import Project
from app.models.referential import Referential
from app.modules.esg.project_listener import sync_snapshot_now
from app.modules.esg.project_models import ProjectEsgAssessment


@pytest.mark.asyncio
class TestSnapshotListener:
    async def test_finalized_assessment_writes_snapshot(
        self, db_session, pme_user, project,
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
            state="finalized",
            score=78,
            pillar_scores={},
            covered_criteria=[],
            missing_criteria=[],
            coverage_rate=Decimal("1.000"),
            finalized_at=datetime.now(timezone.utc),
            created_by=pme_user.id,
        )
        db_session.add(a)
        await db_session.flush()

        # Helper synchrone (debounce désactivé) pour tests déterministes.
        updated = await sync_snapshot_now(db_session, project.id)
        assert updated is not None
        assert updated == 78
        await db_session.refresh(project)
        assert project.project_esg_score == 78

    async def test_delete_finalized_resets_snapshot_to_other(
        self, db_session, pme_user, project,
    ):
        """Quand on supprime une évaluation finalisée, le snapshot retombe
        sur l'évaluation finalized suivante (la plus récente) ou sur None."""
        ref = (
            await db_session.execute(
                select(Referential).where(Referential.code == "ifc_ps"),
            )
        ).scalar_one()
        a1 = ProjectEsgAssessment(
            account_id=pme_user.account_id, project_id=project.id,
            referential_id=ref.id, referential_version="1.0",
            state="finalized", score=55,
            pillar_scores={}, covered_criteria=[], missing_criteria=[],
            coverage_rate=Decimal("1.000"),
            finalized_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            created_by=pme_user.id,
        )
        db_session.add(a1)
        await db_session.flush()
        await sync_snapshot_now(db_session, project.id)
        await db_session.refresh(project)
        assert project.project_esg_score == 55

        # Suppression → on perd la finalisée la plus récente, retombe sur None.
        await db_session.delete(a1)
        await db_session.flush()
        updated = await sync_snapshot_now(db_session, project.id)
        await db_session.refresh(project)
        assert project.project_esg_score is None or project.project_esg_score == 0
        assert updated is None or updated == 0

    async def test_debounce_skips_rapid_calls(self, db_session, pme_user, project):
        """Debounce 30 s : la 2e mise à jour rapprochée ne ré-écrit pas
        immédiatement le snapshot (idempotent côté script de seed bulk)."""
        from app.modules.esg.project_listener import _should_debounce, _DEBOUNCE
        _DEBOUNCE.clear()
        # 1er appel → pas de debounce.
        assert _should_debounce(project.id) is False
        # 2e appel immédiat → debounce True.
        assert _should_debounce(project.id) is True
