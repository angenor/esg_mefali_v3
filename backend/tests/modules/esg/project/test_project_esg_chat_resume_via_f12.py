"""T094 [US4] — Reprise d'une évaluation ESG-projet via mémoire F12.

Valide les FR-026 + FR-038 + acceptance scenario US4 #6 (cf. spec 047) :

(a) Une évaluation ``draft`` à mi-parcours (N réponses persistées) est
    correctement récupérée via ``recall_history`` quand la PME rouvre une
    conversation après plusieurs heures.
(b) Le LLM identifie le critère pending suivant (pas de double pose) en
    croisant les réponses persistées (via ``get_project_esg_assessment``)
    avec la liste des critères obligatoires du référentiel.
(c) La mémoire contextuelle F12 retourne les widgets passés avec leurs
    réponses sérialisées, scopés au tenant courant (RLS défense en
    profondeur applicative + BDD).

Le test couvre l'intégration logique des 2 tools (``recall_history`` +
``get_project_esg_assessment``) sans dépendre du LLM réel : on simule la
trace de la conversation passée via ``search_history`` mocké, puis on
vérifie que le tool ESG-projet retourne le bon état pour le LLM.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.graph.tools.memory_tools import _recall_history_impl
from app.graph.tools.project_esg_tools import (
    create_project_esg_assessment,
    get_project_esg_assessment,
    list_project_esg_assessments,
    save_project_esg_criterion,
)
from app.models.indicator import Criterion
from app.models.referential import Referential
from app.models.source import Source
from app.modules.memory.service import MessageRecallResult


def _config(db_session, pme_user, conversation_id=None):
    return {
        "configurable": {
            "db": db_session,
            "user_id": str(pme_user.id),
            "account_id": str(pme_user.account_id),
            "conversation_id": str(conversation_id or uuid.uuid4()),
        }
    }


async def _ifc_ref(db_session) -> Referential:
    return (
        await db_session.execute(
            select(Referential).where(Referential.code == "ifc_ps"),
        )
    ).scalar_one()


@pytest.mark.asyncio
class TestProjectEsgChatResumeViaF12:
    """T094 — 3 cas : (a) reprise via recall_history, (b) identification
    du critère pending suivant, (c) widgets passés retournés par F12."""

    async def test_recall_history_returns_past_widgets_for_account(
        self, db_session, pme_user, project, monkeypatch,
    ):
        """(c) F12 retourne les widgets passés (avec réponses sérialisées)
        scopés à l'account courant. RLS = account_id propagé au service.
        """
        # Crée une évaluation draft + 1 réponse (simule conversation passée)
        ref = await _ifc_ref(db_session)
        cfg = _config(db_session, pme_user)

        created = json.loads(
            await create_project_esg_assessment.ainvoke(
                {"project_id": project.id, "referential_id": ref.id},
                config=cfg,
            )
        )
        assessment_id = uuid.UUID(created["assessment"]["id"])
        crit = (
            await db_session.execute(
                select(Criterion).where(
                    Criterion.referential_id == ref.id,
                    Criterion.is_required.is_(True),
                ).limit(1)
            )
        ).scalar_one()
        src = (
            await db_session.execute(select(Source).limit(1))
        ).scalar_one()
        await save_project_esg_criterion.ainvoke(
            {
                "assessment_id": assessment_id,
                "criterion_id": crit.id,
                "response_type": "qcu",
                "response_value": {"choice": "yes"},
                "source_id": src.id,
                "unsourced": False,
            },
            config=cfg,
        )

        # F12 : mock search_history pour simuler la mémoire passée
        # (le pgvector réel est testé dans test_recall_history_tool.py).
        past_conv = uuid.uuid4()
        past_msg = uuid.uuid4()
        fake_past_results = [
            MessageRecallResult(
                message_id=past_msg,
                conversation_id=past_conv,
                conversation_title="Évaluation IFC PS — projet agroforesterie",
                role="assistant",
                chunk_text=(
                    f"Tu avais répondu 'oui' au critère {crit.code} "
                    f"avec la source {src.title}. Reprenons au critère suivant."
                ),
                created_at=datetime.now(timezone.utc) - timedelta(hours=2),
                similarity=0.78,
            ),
        ]
        fake_search = AsyncMock(return_value=fake_past_results)
        monkeypatch.setattr(
            "app.graph.tools.memory_tools.search_history", fake_search,
        )

        new_conv_id = uuid.uuid4()
        recall_config = {
            "configurable": {
                "account_id": str(pme_user.account_id),
                "conversation_id": str(new_conv_id),
                "user_id": str(pme_user.id),
            }
        }
        recalled = await _recall_history_impl(
            query="reprise évaluation IFC PS",
            config=recall_config,
        )
        assert isinstance(recalled, list)
        assert len(recalled) == 1
        assert recalled[0]["conversation_id"] == str(past_conv)
        assert "critère" in recalled[0]["chunk_text"].lower()

        # Le service a bien été appelé avec l'account_id du tenant (RLS).
        fake_search.assert_awaited_once()
        call_kwargs = fake_search.call_args.kwargs
        assert call_kwargs.get("account_id") == pme_user.account_id

    async def test_get_assessment_returns_persisted_responses_after_resume(
        self, db_session, pme_user, project,
    ):
        """(a) Après reprise, ``get_project_esg_assessment`` retourne les
        N réponses déjà persistées (équivalent ``recall_history`` côté DB).
        """
        ref = await _ifc_ref(db_session)
        cfg = _config(db_session, pme_user)
        src = (
            await db_session.execute(select(Source).limit(1))
        ).scalar_one()

        created = json.loads(
            await create_project_esg_assessment.ainvoke(
                {"project_id": project.id, "referential_id": ref.id},
                config=cfg,
            )
        )
        assessment_id = uuid.UUID(created["assessment"]["id"])

        # Pose 3 réponses (simule un draft mi-parcours)
        criteria_required = (
            await db_session.execute(
                select(Criterion).where(
                    Criterion.referential_id == ref.id,
                    Criterion.is_required.is_(True),
                ).limit(3)
            )
        ).scalars().all()
        for crit in criteria_required:
            await save_project_esg_criterion.ainvoke(
                {
                    "assessment_id": assessment_id,
                    "criterion_id": crit.id,
                    "response_type": "qcu",
                    "response_value": {"choice": "yes"},
                    "source_id": src.id,
                    "unsourced": False,
                },
                config=cfg,
            )

        # Simule reprise dans une nouvelle conversation : on relit l'état
        out = json.loads(
            await get_project_esg_assessment.ainvoke(
                {"assessment_id": assessment_id}, config=cfg,
            )
        )
        assert out["ok"] is True
        assert out["responses_count"] == 3
        # Les 3 critères répondus sont retournés avec leur normalized_score
        returned_crit_ids = {r["criterion_id"] for r in out["responses"]}
        assert returned_crit_ids == {str(c.id) for c in criteria_required}

    async def test_llm_identifies_next_pending_criterion_no_double_pose(
        self, db_session, pme_user, project,
    ):
        """(b) En croisant ``get_project_esg_assessment`` (réponses déjà
        posées) avec la liste des critères obligatoires du référentiel,
        on identifie sans ambiguïté les critères pending suivants.
        Aucune double-pose possible : un critère répondu est exclu du
        set pending.
        """
        ref = await _ifc_ref(db_session)
        cfg = _config(db_session, pme_user)
        src = (
            await db_session.execute(select(Source).limit(1))
        ).scalar_one()

        created = json.loads(
            await create_project_esg_assessment.ainvoke(
                {"project_id": project.id, "referential_id": ref.id},
                config=cfg,
            )
        )
        assessment_id = uuid.UUID(created["assessment"]["id"])

        # Pose 2 réponses (sur N obligatoires)
        required = (
            await db_session.execute(
                select(Criterion).where(
                    Criterion.referential_id == ref.id,
                    Criterion.is_required.is_(True),
                ).order_by(Criterion.code)
            )
        ).scalars().all()
        assert len(required) >= 3, (
            "Le seed doit fournir au moins 3 critères obligatoires IFC PS "
            "pour ce test."
        )
        for crit in required[:2]:
            await save_project_esg_criterion.ainvoke(
                {
                    "assessment_id": assessment_id,
                    "criterion_id": crit.id,
                    "response_type": "qcu",
                    "response_value": {"choice": "yes"},
                    "source_id": src.id,
                    "unsourced": False,
                },
                config=cfg,
            )

        # Reprise : LLM appelle list_project_esg_assessments + get_*
        listed = json.loads(
            await list_project_esg_assessments.ainvoke(
                {"project_id": project.id, "state": "draft"},
                config=cfg,
            )
        )
        assert listed["ok"] is True
        assert any(
            a["id"] == str(assessment_id) for a in listed["items"]
        ), "Le draft doit être retrouvable via list_project_esg_assessments."

        state = json.loads(
            await get_project_esg_assessment.ainvoke(
                {"assessment_id": assessment_id}, config=cfg,
            )
        )
        assert state["ok"] is True
        already_answered = {
            uuid.UUID(r["criterion_id"]) for r in state["responses"]
        }
        # Les critères restants = obligatoires - déjà répondus
        pending = [c for c in required if c.id not in already_answered]
        assert len(pending) == len(required) - 2
        # Le LLM peut donc poser le critère suivant sans double-pose
        next_to_ask = pending[0]
        assert next_to_ask.id not in already_answered
