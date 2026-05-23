"""T017+T018+T019 — Tests service US1 (create / save_criterion / finalize)."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.indicator import Criterion
from app.models.referential import Referential
from app.models.source import PublicationStatus
from app.modules.esg.project_models import ProjectEsgAssessment
from app.modules.esg.project_schemas import ProjectEsgCriterionResponseSave
from app.modules.esg.project_service import (
    create_project_esg_assessment,
    finalize_project_esg_assessment,
    save_project_esg_criterion_response,
)


async def _ifc_referential_id(db_session) -> uuid.UUID:
    ref = (
        await db_session.execute(
            select(Referential).where(Referential.code == "ifc_ps")
        )
    ).scalar_one()
    return ref.id


async def _ifc_criteria(db_session) -> list[Criterion]:
    return list(
        (
            await db_session.execute(
                select(Criterion)
                .join(Referential, Criterion.referential_id == Referential.id)
                .where(Referential.code == "ifc_ps")
            )
        )
        .scalars()
        .all()
    )


class TestCreate:
    async def test_create_draft_ok(self, db_session, pme_user, project):
        ref_id = await _ifc_referential_id(db_session)
        a = await create_project_esg_assessment(
            db_session,
            account_id=pme_user.account_id,
            user_id=pme_user.id,
            project_id=project.id,
            referential_id=ref_id,
        )
        assert a.state == "draft"
        assert a.score is None
        assert a.referential_version is not None

    async def test_second_draft_refused_409(self, db_session, pme_user, project):
        ref_id = await _ifc_referential_id(db_session)
        await create_project_esg_assessment(
            db_session,
            account_id=pme_user.account_id,
            user_id=pme_user.id,
            project_id=project.id,
            referential_id=ref_id,
        )
        with pytest.raises(HTTPException) as exc:
            await create_project_esg_assessment(
                db_session,
                account_id=pme_user.account_id,
                user_id=pme_user.id,
                project_id=project.id,
                referential_id=ref_id,
            )
        assert exc.value.status_code == 409

    async def test_unpublished_referential_refused_422(
        self, db_session, pme_user, project,
    ):
        ref_id = await _ifc_referential_id(db_session)
        ref = await db_session.get(Referential, ref_id)
        ref.publication_status = PublicationStatus.DRAFT.value
        await db_session.flush()

        with pytest.raises(HTTPException) as exc:
            await create_project_esg_assessment(
                db_session,
                account_id=pme_user.account_id,
                user_id=pme_user.id,
                project_id=project.id,
                referential_id=ref_id,
            )
        assert exc.value.status_code == 422


class TestSaveCriterion:
    async def test_create_then_update_same_criterion(
        self, db_session, pme_user, project,
    ):
        ref_id = await _ifc_referential_id(db_session)
        a = await create_project_esg_assessment(
            db_session,
            account_id=pme_user.account_id,
            user_id=pme_user.id,
            project_id=project.id,
            referential_id=ref_id,
        )
        crit = (await _ifc_criteria(db_session))[0]
        payload = ProjectEsgCriterionResponseSave(
            criterion_id=crit.id,
            response_type="qcu",
            response_value={"choice": "yes"},
            source_id=None,
            unsourced=True,
        )
        r1 = await save_project_esg_criterion_response(
            db_session,
            account_id=pme_user.account_id,
            assessment_id=a.id,
            payload=payload,
        )
        assert float(r1.normalized_score) == 1.0

        # Révision draft : update même critère
        payload2 = ProjectEsgCriterionResponseSave(
            criterion_id=crit.id,
            response_type="qcu",
            response_value={"choice": "no"},
            source_id=None,
            unsourced=True,
        )
        r2 = await save_project_esg_criterion_response(
            db_session,
            account_id=pme_user.account_id,
            assessment_id=a.id,
            payload=payload2,
        )
        assert r1.id == r2.id  # UPSERT, pas un nouveau row
        assert float(r2.normalized_score) == 0.0

    async def test_finalized_refuses_save_409(self, db_session, pme_user, project):
        ref_id = await _ifc_referential_id(db_session)
        a = await create_project_esg_assessment(
            db_session,
            account_id=pme_user.account_id,
            user_id=pme_user.id,
            project_id=project.id,
            referential_id=ref_id,
        )
        a.state = "finalized"
        a.score = 50
        from datetime import datetime, timezone
        a.finalized_at = datetime.now(timezone.utc)
        await db_session.flush()

        crit = (await _ifc_criteria(db_session))[0]
        payload = ProjectEsgCriterionResponseSave(
            criterion_id=crit.id,
            response_type="qcu",
            response_value={"choice": "yes"},
            source_id=None,
            unsourced=True,
        )
        with pytest.raises(HTTPException) as exc:
            await save_project_esg_criterion_response(
                db_session,
                account_id=pme_user.account_id,
                assessment_id=a.id,
                payload=payload,
            )
        assert exc.value.status_code == 409

    async def test_criterion_other_referential_refused_422(
        self, db_session, pme_user, project,
    ):
        ifc_ref = await _ifc_referential_id(db_session)
        a = await create_project_esg_assessment(
            db_session,
            account_id=pme_user.account_id,
            user_id=pme_user.id,
            project_id=project.id,
            referential_id=ifc_ref,
        )
        # Critère du référentiel GCF (pas IFC)
        gcf_crit = (
            await db_session.execute(
                select(Criterion)
                .join(Referential, Criterion.referential_id == Referential.id)
                .where(Referential.code == "gcf_ess")
                .limit(1)
            )
        ).scalar_one()
        payload = ProjectEsgCriterionResponseSave(
            criterion_id=gcf_crit.id,
            response_type="qcu",
            response_value={"choice": "yes"},
            source_id=None,
            unsourced=True,
        )
        with pytest.raises(HTTPException) as exc:
            await save_project_esg_criterion_response(
                db_session,
                account_id=pme_user.account_id,
                assessment_id=a.id,
                payload=payload,
            )
        assert exc.value.status_code == 422


class TestFinalize:
    async def test_finalize_refused_when_required_missing(
        self, db_session, pme_user, project,
    ):
        ref_id = await _ifc_referential_id(db_session)
        a = await create_project_esg_assessment(
            db_session,
            account_id=pme_user.account_id,
            user_id=pme_user.id,
            project_id=project.id,
            referential_id=ref_id,
        )
        # Aucune réponse → critères obligatoires manquants
        with pytest.raises(HTTPException) as exc:
            await finalize_project_esg_assessment(
                db_session,
                account_id=pme_user.account_id,
                assessment_id=a.id,
            )
        assert exc.value.status_code == 422
        assert "missing_required" in exc.value.detail

    async def test_finalize_ok_when_all_required_answered(
        self, db_session, pme_user, project,
    ):
        ref_id = await _ifc_referential_id(db_session)
        a = await create_project_esg_assessment(
            db_session,
            account_id=pme_user.account_id,
            user_id=pme_user.id,
            project_id=project.id,
            referential_id=ref_id,
        )
        criteria = await _ifc_criteria(db_session)
        # Répondre "yes" à tous les critères obligatoires
        for crit in criteria:
            if not crit.is_required:
                continue
            payload = ProjectEsgCriterionResponseSave(
                criterion_id=crit.id,
                response_type="qcu",
                response_value={"choice": "yes"},
                source_id=None,
                unsourced=True,
            )
            await save_project_esg_criterion_response(
                db_session,
                account_id=pme_user.account_id,
                assessment_id=a.id,
                payload=payload,
            )

        result = await finalize_project_esg_assessment(
            db_session, account_id=pme_user.account_id, assessment_id=a.id,
        )
        assert result["score"] >= 0 and result["score"] <= 100
        assert result["assessment"].state == "finalized"
        assert result["assessment"].finalized_at is not None
        assert result["assessment"].snapshot_data is not None

    async def test_double_finalize_refused_409(self, db_session, pme_user, project):
        ref_id = await _ifc_referential_id(db_session)
        a = await create_project_esg_assessment(
            db_session,
            account_id=pme_user.account_id,
            user_id=pme_user.id,
            project_id=project.id,
            referential_id=ref_id,
        )
        # Répondre aux requis
        for crit in await _ifc_criteria(db_session):
            if not crit.is_required:
                continue
            await save_project_esg_criterion_response(
                db_session,
                account_id=pme_user.account_id,
                assessment_id=a.id,
                payload=ProjectEsgCriterionResponseSave(
                    criterion_id=crit.id,
                    response_type="qcu",
                    response_value={"choice": "yes"},
                    source_id=None,
                    unsourced=True,
                ),
            )
        await finalize_project_esg_assessment(
            db_session, account_id=pme_user.account_id, assessment_id=a.id,
        )
        with pytest.raises(HTTPException) as exc:
            await finalize_project_esg_assessment(
                db_session, account_id=pme_user.account_id, assessment_id=a.id,
            )
        assert exc.value.status_code == 409


class TestScoringWeighted:
    """T020 — Pondération `criterion.weight` F13 (research.md D9)."""

    async def test_weighted_average_is_correct(self, db_session, pme_user, project):
        from app.modules.esg.project_scoring import compute_score

        ref_id = await _ifc_referential_id(db_session)
        a = await create_project_esg_assessment(
            db_session,
            account_id=pme_user.account_id,
            user_id=pme_user.id,
            project_id=project.id,
            referential_id=ref_id,
        )
        criteria = await _ifc_criteria(db_session)
        # Réponses : moitié yes (score 1.0), moitié no (score 0.0)
        half = len(criteria) // 2
        for crit in criteria[:half]:
            await save_project_esg_criterion_response(
                db_session,
                account_id=pme_user.account_id,
                assessment_id=a.id,
                payload=ProjectEsgCriterionResponseSave(
                    criterion_id=crit.id,
                    response_type="qcu",
                    response_value={"choice": "yes"},
                    source_id=None,
                    unsourced=True,
                ),
            )
        for crit in criteria[half:]:
            await save_project_esg_criterion_response(
                db_session,
                account_id=pme_user.account_id,
                assessment_id=a.id,
                payload=ProjectEsgCriterionResponseSave(
                    criterion_id=crit.id,
                    response_type="qcu",
                    response_value={"choice": "no"},
                    source_id=None,
                    unsourced=True,
                ),
            )
        result = await compute_score(db_session, a.id)
        # Score doit être strictement entre 0 et 100 (mélange yes/no)
        assert 0 < result["score"] < 100
        assert result["coverage_rate"] == 1
        assert result["missing_criteria"] == []
