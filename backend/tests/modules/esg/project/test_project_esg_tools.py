"""T060 [US4] — Tests des 5 tools LangChain ESG-projet (F047).

Vérifie que (a) les tools résolvent correctement `account_id` depuis le
RunnableConfig, (b) les wrappers délèguent au service, (c) les retours JSON
contiennent les champs minimaux attendus par le LLM.
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
from app.models.source import Source
from app.modules.esg.project_models import ProjectEsgAssessment
from app.graph.tools.project_esg_tools import (
    create_project_esg_assessment,
    finalize_project_esg_assessment,
    get_project_esg_assessment,
    list_project_esg_assessments,
    save_project_esg_criterion,
)


def _config(db_session, pme_user, account_id=None):
    return {
        "configurable": {
            "db": db_session,
            "user_id": str(pme_user.id),
            "account_id": str(account_id or pme_user.account_id),
        }
    }


async def _ifc_ref(db_session) -> Referential:
    return (
        await db_session.execute(
            select(Referential).where(Referential.code == "ifc_ps"),
        )
    ).scalar_one()


@pytest.mark.asyncio
class TestProjectEsgTools:
    async def test_create_returns_draft(self, db_session, pme_user, project):
        ref = await _ifc_ref(db_session)
        cfg = _config(db_session, pme_user)
        out = await create_project_esg_assessment.ainvoke(
            {"project_id": project.id, "referential_id": ref.id},
            config=cfg,
        )
        payload = json.loads(out)
        assert payload["ok"] is True
        assert payload["assessment"]["state"] == "draft"
        assert payload["assessment"]["project_id"] == str(project.id)

    async def test_save_then_finalize_full_flow(
        self, db_session, pme_user, project,
    ):
        ref = await _ifc_ref(db_session)
        cfg = _config(db_session, pme_user)

        created = json.loads(
            await create_project_esg_assessment.ainvoke(
                {"project_id": project.id, "referential_id": ref.id},
                config=cfg,
            )
        )
        assessment_id = uuid.UUID(created["assessment"]["id"])

        criteria = (
            await db_session.execute(
                select(Criterion).where(Criterion.referential_id == ref.id),
            )
        ).scalars().all()
        src = (await db_session.execute(select(Source).limit(1))).scalar_one()

        # Saisir un critère obligatoire (yes) — pour passer la finalisation
        # il faut couvrir tous les obligatoires.
        for c in criteria:
            if c.is_required:
                out = await save_project_esg_criterion.ainvoke(
                    {
                        "assessment_id": assessment_id,
                        "criterion_id": c.id,
                        "response_type": "qcu",
                        "response_value": {"choice": "yes"},
                        "source_id": src.id,
                        "unsourced": False,
                    },
                    config=cfg,
                )
                assert json.loads(out)["ok"] is True

        fin = json.loads(
            await finalize_project_esg_assessment.ainvoke(
                {"assessment_id": assessment_id}, config=cfg,
            )
        )
        assert fin["ok"] is True
        assert isinstance(fin["score"], int)
        assert 0 <= fin["score"] <= 100
        assert fin["assessment"]["state"] == "finalized"

    async def test_save_xor_violation_returns_error(
        self, db_session, pme_user, project,
    ):
        ref = await _ifc_ref(db_session)
        cfg = _config(db_session, pme_user)
        created = json.loads(
            await create_project_esg_assessment.ainvoke(
                {"project_id": project.id, "referential_id": ref.id},
                config=cfg,
            )
        )
        crit = (
            await db_session.execute(
                select(Criterion).where(Criterion.referential_id == ref.id).limit(1),
            )
        ).scalar_one()

        # Violation : source_id ET unsourced=True ensemble
        out = json.loads(
            await save_project_esg_criterion.ainvoke(
                {
                    "assessment_id": uuid.UUID(created["assessment"]["id"]),
                    "criterion_id": crit.id,
                    "response_type": "qcu",
                    "response_value": {"choice": "yes"},
                    "source_id": uuid.uuid4(),
                    "unsourced": True,
                },
                config=cfg,
            )
        )
        assert out["ok"] is False
        assert "exclusi" in out["error"].lower() or "xor" in out["error"].lower()

    async def test_list_returns_items(self, db_session, pme_user, project):
        ref = await _ifc_ref(db_session)
        cfg = _config(db_session, pme_user)
        await create_project_esg_assessment.ainvoke(
            {"project_id": project.id, "referential_id": ref.id},
            config=cfg,
        )
        out = json.loads(
            await list_project_esg_assessments.ainvoke(
                {"project_id": project.id, "state": "draft"}, config=cfg,
            )
        )
        assert out["ok"] is True
        assert out["count"] >= 1
        assert out["items"][0]["state"] == "draft"

    async def test_get_returns_detail(self, db_session, pme_user, project):
        ref = await _ifc_ref(db_session)
        cfg = _config(db_session, pme_user)
        created = json.loads(
            await create_project_esg_assessment.ainvoke(
                {"project_id": project.id, "referential_id": ref.id},
                config=cfg,
            )
        )
        out = json.loads(
            await get_project_esg_assessment.ainvoke(
                {"assessment_id": uuid.UUID(created["assessment"]["id"])},
                config=cfg,
            )
        )
        assert out["ok"] is True
        assert out["assessment"]["state"] == "draft"
        assert out["responses_count"] == 0

    async def test_resolve_account_id_fallback_via_user(
        self, db_session, pme_user, project,
    ):
        """Pattern F18 : si account_id absent du RunnableConfig, fallback
        sur ``User.account_id`` en base (cf. CLAUDE.md note opérationnelle)."""
        ref = await _ifc_ref(db_session)
        cfg = {
            "configurable": {
                "db": db_session,
                "user_id": str(pme_user.id),
                # account_id volontairement absent
            }
        }
        out = json.loads(
            await create_project_esg_assessment.ainvoke(
                {"project_id": project.id, "referential_id": ref.id},
                config=cfg,
            )
        )
        assert out["ok"] is True, out
