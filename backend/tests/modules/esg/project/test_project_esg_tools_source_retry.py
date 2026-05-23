"""T093 [US4] — Sourçage F01 obligatoire dans les tools ESG-projet.

Valide le contrat FR-023 / Constitution V (Sécurité — sourçage F01) pour
le tool ``save_project_esg_criterion`` (F047) :

(a) Première réponse sans ``source_id`` ET sans ``unsourced=true`` est
    rejetée par le validator XOR Pydantic ; le tool retourne ``ok=false``
    avec un message d'erreur exploitable par le validator
    ``source_required.py`` pour déclencher un retry LLM.
(b) Sur réponse finale sans citation, le validator ``source_required``
    bascule en fallback texte explicite (jamais d'évaluation silencieuse).
(c) ``unsourced=true`` est accepté uniquement quand l'utilisateur a
    explicitement choisi cette option (le tool n'a pas besoin de
    distinguer la provenance ; c'est le flag_unsourced upstream qui
    enregistre la justification, et le validator côté LLM se charge de
    s'assurer que cette pose est explicite).

Référence : ``app/graph/validators/source_required.py``, FR-023,
Constitution V principe 1 (« Sourçage obligatoire »).
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from app.graph.tools.project_esg_tools import (
    create_project_esg_assessment,
    save_project_esg_criterion,
)
from app.graph.validators.source_required import (
    FALLBACK_TEXT,
    validate_response,
)
from app.models.indicator import Criterion
from app.models.referential import Referential
from app.models.source import Source


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


async def _first_required_criterion(db_session, ref_id) -> Criterion:
    return (
        await db_session.execute(
            select(Criterion).where(
                Criterion.referential_id == ref_id,
                Criterion.is_required.is_(True),
            ).limit(1)
        )
    ).scalar_one()


@pytest.mark.asyncio
class TestProjectEsgSourcingRetry:
    """T093 — 3 cas : (a) refus initial XOR, (b) fallback validator,
    (c) unsourced=true explicite accepté."""

    async def test_save_without_source_and_without_unsourced_rejected(
        self, db_session, pme_user, project,
    ):
        """(a) source_id=None ET unsourced=False → XOR violé → tool retourne
        ok=false. Le LLM doit corriger au prochain tour (retry source_required).
        """
        ref = await _ifc_ref(db_session)
        cfg = _config(db_session, pme_user)

        created = json.loads(
            await create_project_esg_assessment.ainvoke(
                {"project_id": project.id, "referential_id": ref.id},
                config=cfg,
            )
        )
        assessment_id = uuid.UUID(created["assessment"]["id"])
        crit = await _first_required_criterion(db_session, ref.id)

        out = json.loads(
            await save_project_esg_criterion.ainvoke(
                {
                    "assessment_id": assessment_id,
                    "criterion_id": crit.id,
                    "response_type": "qcu",
                    "response_value": {"choice": "yes"},
                    # Volontairement aucun source_id ni unsourced
                },
                config=cfg,
            )
        )
        assert out["ok"] is False
        # Le message d'erreur doit être interprétable par le validator
        # source_required pour déclencher la stratégie retry → fallback.
        assert (
            "source_id" in out["error"].lower()
            or "exclusi" in out["error"].lower()
            or "xor" in out["error"].lower()
        )

    async def test_validator_retry_then_fallback_when_no_citation(self):
        """(b) Si le LLM produit malgré tout un texte avec un chiffre non
        cité, le validator source_required demande un retry (1er passage)
        puis bascule en fallback texte (retry épuisé).

        Indépendant de la BDD : valide le contrat
        Constitution V « retry 1x sinon fallback ».
        """
        text = "Score IFC PS attendu : 75/100 selon l'évaluation."

        first_pass = validate_response(text, tool_calls=[], retry_count=0)
        assert first_pass.passed is False
        assert first_pass.requires_retry is True

        # Tentative finale après retry : fallback texte appliqué.
        final_pass = validate_response(text, tool_calls=[], retry_count=1)
        assert final_pass.passed is False
        assert final_pass.requires_retry is False
        assert final_pass.substituted_text is not None
        assert FALLBACK_TEXT in final_pass.substituted_text
        assert final_pass.incident_logged is True

    async def test_save_with_unsourced_true_explicit_accepted(
        self, db_session, pme_user, project,
    ):
        """(c) ``unsourced=true`` (sans source_id) est accepté côté tool —
        le validator source_required côté LLM s'assure que cette pose est
        précédée d'un appel ``flag_unsourced`` (granularité paragraphe).
        Aucune évaluation silencieuse : l'option doit être un choix explicite.
        """
        ref = await _ifc_ref(db_session)
        cfg = _config(db_session, pme_user)

        created = json.loads(
            await create_project_esg_assessment.ainvoke(
                {"project_id": project.id, "referential_id": ref.id},
                config=cfg,
            )
        )
        assessment_id = uuid.UUID(created["assessment"]["id"])
        crit = await _first_required_criterion(db_session, ref.id)

        out = json.loads(
            await save_project_esg_criterion.ainvoke(
                {
                    "assessment_id": assessment_id,
                    "criterion_id": crit.id,
                    "response_type": "qcu_justification",
                    "response_value": {"choice": "yes", "justification": "pas de donnée publique disponible"},
                    "source_id": None,
                    "unsourced": True,
                },
                config=cfg,
            )
        )
        assert out["ok"] is True
        assert out["response"]["unsourced"] is True

        # Côté validator LLM : un texte de réponse qui ne contient aucun
        # chiffre numérique passe sans citation requise. Le validator est
        # déclenché chiffre par chiffre, pas par flag binaire.
        text_no_number = "Le critère est répondu sans donnée chiffrée."
        result = validate_response(text_no_number, tool_calls=[])
        assert result.passed is True

    async def test_save_with_source_id_only_accepted(
        self, db_session, pme_user, project,
    ):
        """Validation positive : ``source_id`` seul est accepté."""
        ref = await _ifc_ref(db_session)
        cfg = _config(db_session, pme_user)

        created = json.loads(
            await create_project_esg_assessment.ainvoke(
                {"project_id": project.id, "referential_id": ref.id},
                config=cfg,
            )
        )
        assessment_id = uuid.UUID(created["assessment"]["id"])
        crit = await _first_required_criterion(db_session, ref.id)
        src = (
            await db_session.execute(select(Source).limit(1))
        ).scalar_one()

        out = json.loads(
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
        )
        assert out["ok"] is True
        assert out["response"]["unsourced"] is False
