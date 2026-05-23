"""[bug F047 US3] — Reproduction et verrou du bug d'hallucination du rapport
ESIA-light.

Avant le fix, le LLM affirmait « le rapport ESIA-light est généré » sans
réellement appeler ``generate_project_esg_report`` :
- aucune ligne ``generate_project_esg_report`` dans ``tool_call_logs`` ;
- aucun fichier ``esia_{assessment_id}_*.pdf`` sur disque ;
- ``project_esg_assessments.score`` à 0 (les `save` étaient silencieusement
  rejetés faute de ``criterion_id`` valides).

Ce test verrouille trois garanties qui matérialisent le fix :

(A) ``create_project_esg_assessment`` retourne ``applicable_criteria`` (liste
    des critères avec leurs UUIDs valides) → le LLM n'a plus à deviner.

(B) ``get_project_esg_assessment`` retourne lui aussi
    ``applicable_criteria`` (utile à la reprise d'un draft).

(C) Quand la séquence complète create → save × N → finalize → generate est
    exécutée, un PDF est réellement écrit sur disque (``file_path`` non vide
    et fichier existant).

(D) La docstring du tool ``generate_project_esg_report`` contient une
    clause anti-hallucination explicite (verrou de spec, pas seulement
    de code).
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.graph.tools.project_esg_tools import (
    create_project_esg_assessment,
    finalize_project_esg_assessment,
    generate_project_esg_report,
    get_project_esg_assessment,
    save_project_esg_criterion,
)
from app.models.indicator import Criterion
from app.models.referential import Referential
from app.models.source import Source


def _config(db_session, pme_user):
    return {
        "configurable": {
            "db": db_session,
            "user_id": str(pme_user.id),
            "account_id": str(pme_user.account_id),
        }
    }


async def _ifc_ref(db_session) -> Referential:
    return (
        await db_session.execute(
            select(Referential).where(Referential.code == "ifc_ps"),
        )
    ).scalar_one()


@pytest.mark.asyncio
class TestApplicableCriteriaExposedToLLM:
    """(A) + (B) : le LLM doit pouvoir obtenir les `criterion_id` valides
    sans avoir à les inventer.
    """

    async def test_create_returns_applicable_criteria(
        self, db_session, pme_user, project,
    ):
        ref = await _ifc_ref(db_session)
        cfg = _config(db_session, pme_user)

        out = json.loads(
            await create_project_esg_assessment.ainvoke(
                {"project_id": project.id, "referential_id": ref.id},
                config=cfg,
            )
        )
        assert out["ok"] is True
        assert "applicable_criteria" in out, (
            "create_project_esg_assessment doit exposer applicable_criteria "
            "au LLM pour qu'il puisse passer un criterion_id valide à "
            "save_project_esg_criterion."
        )
        assert isinstance(out["applicable_criteria"], list)
        assert len(out["applicable_criteria"]) >= 1
        first = out["applicable_criteria"][0]
        for key in ("id", "code", "label", "pillar", "is_required", "weight"):
            assert key in first, f"Champ manquant dans applicable_criteria: {key}"
        # L'id doit être un UUID parseable.
        uuid.UUID(first["id"])
        assert out["applicable_criteria_count"] == len(out["applicable_criteria"])

    async def test_list_returns_available_referentials(
        self, db_session, pme_user, project,
    ):
        """[bug F047 US3 — 2026-05-23 #4] Le LLM doit pouvoir obtenir les
        ``referential_id`` UUIDs sans avoir à les inventer. Live observé :
        avant ce fix, le LLM disait « les UUIDs des référentiels ne sont
        pas accessibles depuis cette session de chat » et abandonnait.
        ``search_source`` ne convient pas (retourne ``source.id``, pas
        ``referential.id``).
        """
        from app.graph.tools.project_esg_tools import list_project_esg_assessments

        cfg = _config(db_session, pme_user)
        out = json.loads(
            await list_project_esg_assessments.ainvoke(
                {"project_id": project.id}, config=cfg,
            )
        )
        assert out["ok"] is True
        assert "available_referentials" in out, (
            "list_project_esg_assessments doit exposer available_referentials "
            "pour permettre au LLM de démarrer une évaluation depuis le chat."
        )
        refs = out["available_referentials"]
        assert isinstance(refs, list)
        assert len(refs) >= 1
        # Au moins l'un des 3 référentiels MVP doit être présent.
        codes = {r["code"] for r in refs}
        assert any(c in codes for c in ("ifc_ps", "gcf_ess", "boad_ess")), (
            f"Au moins ifc_ps/gcf_ess/boad_ess attendu, reçu : {codes}"
        )
        # Chaque entrée a id (UUID), code, label.
        for r in refs:
            for key in ("id", "code", "label"):
                assert key in r, f"Champ manquant : {key}"
            uuid.UUID(r["id"])

    async def test_get_returns_applicable_criteria(
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
        out = json.loads(
            await get_project_esg_assessment.ainvoke(
                {"assessment_id": uuid.UUID(created["assessment"]["id"])},
                config=cfg,
            )
        )
        assert out["ok"] is True
        assert "applicable_criteria" in out
        assert len(out["applicable_criteria"]) >= 1


@pytest.mark.asyncio
class TestFullReportGenerationSequence:
    """(C) La séquence complète doit aboutir à un PDF réellement écrit
    sur disque (et non hallucinée par le LLM).

    Simule l'enchaînement exact que le LLM doit reproduire après le fix :
    create_project_esg_assessment → save_project_esg_criterion × N
    → finalize_project_esg_assessment → generate_project_esg_report.
    """

    async def test_create_save_finalize_generate_pdf(
        self, db_session, pme_user, project, tmp_path, monkeypatch,
    ):
        # Forcer l'écriture du PDF dans tmp_path (isolation test).
        monkeypatch.setattr(
            "app.modules.esg.project_report.UPLOADS_DIR",
            tmp_path,
        )

        ref = await _ifc_ref(db_session)
        cfg = _config(db_session, pme_user)

        # 1. Création
        created = json.loads(
            await create_project_esg_assessment.ainvoke(
                {"project_id": project.id, "referential_id": ref.id},
                config=cfg,
            )
        )
        assert created["ok"] is True
        assessment_id = uuid.UUID(created["assessment"]["id"])
        # Le LLM dispose désormais des criterion_id valides directement
        # dans le retour du tool.
        applicable = created["applicable_criteria"]
        assert len(applicable) >= 1

        # 2. Save des critères obligatoires (en utilisant les criterion_id
        # remontés par le tool create — c'est exactement ce que le LLM doit
        # faire après le fix).
        src = (await db_session.execute(select(Source).limit(1))).scalar_one()
        required_count = 0
        for crit_dict in applicable:
            if not crit_dict["is_required"]:
                continue
            required_count += 1
            res = json.loads(
                await save_project_esg_criterion.ainvoke(
                    {
                        "assessment_id": assessment_id,
                        "criterion_id": uuid.UUID(crit_dict["id"]),
                        "response_type": "qcu",
                        "response_value": {"choice": "yes"},
                        "source_id": src.id,
                        "unsourced": False,
                    },
                    config=cfg,
                )
            )
            assert res["ok"] is True, res
        assert required_count >= 1, (
            "Le référentiel IFC PS seedé doit comporter au moins un critère "
            "is_required=True."
        )

        # 3. Finalisation
        fin = json.loads(
            await finalize_project_esg_assessment.ainvoke(
                {"assessment_id": assessment_id}, config=cfg,
            )
        )
        assert fin["ok"] is True, fin
        assert fin["assessment"]["state"] == "finalized"
        assert fin["score"] >= 0  # peut être 0 si toutes les réponses == "yes" ne couvrent que les obligatoires

        # 4. Génération du rapport — DOIT créer un fichier réel.
        gen = json.loads(
            await generate_project_esg_report.ainvoke(
                {"assessment_id": assessment_id, "include_appendix_sources": True},
                config=cfg,
            )
        )
        assert gen["ok"] is True, gen
        assert gen["file_path"], (
            "generate_project_esg_report doit retourner un file_path non vide."
        )
        pdf_path = Path(gen["file_path"])
        # Le chemin doit être sous le UPLOADS_DIR overridé (tmp_path).
        assert str(pdf_path).startswith(str(tmp_path)), (
            f"Le fichier doit être écrit sous {tmp_path}, reçu : {pdf_path}"
        )
        assert pdf_path.exists(), (
            f"Le PDF ESIA-light doit exister sur disque : {pdf_path}"
        )
        # Le filename respecte le pattern documenté.
        assert re.match(
            rf"^esia_{assessment_id}_\d{{8}}-\d{{6}}\.pdf$",
            pdf_path.name,
        ), f"Nom de fichier inattendu : {pdf_path.name}"
        # Le binaire doit commencer par le header PDF.
        assert pdf_path.read_bytes()[:4] == b"%PDF", (
            "Le fichier généré doit être un PDF valide (header %PDF)."
        )

    async def test_generate_refuses_draft(
        self, db_session, pme_user, project, tmp_path, monkeypatch,
    ):
        """``generate_project_esg_report`` doit refuser une évaluation
        ``draft`` (cohérent avec la directive FR-019). Le LLM doit alors
        appeler ``finalize_project_esg_assessment`` d'abord, et n'affirmera
        pas que le rapport est généré tant que ce tool n'a pas retourné
        ``ok=true``.
        """
        monkeypatch.setattr(
            "app.modules.esg.project_report.UPLOADS_DIR",
            tmp_path,
        )
        ref = await _ifc_ref(db_session)
        cfg = _config(db_session, pme_user)
        created = json.loads(
            await create_project_esg_assessment.ainvoke(
                {"project_id": project.id, "referential_id": ref.id},
                config=cfg,
            )
        )
        out = json.loads(
            await generate_project_esg_report.ainvoke(
                {
                    "assessment_id": uuid.UUID(created["assessment"]["id"]),
                    "include_appendix_sources": False,
                },
                config=cfg,
            )
        )
        assert out["ok"] is False
        assert "file_path" not in out, (
            "Aucun file_path ne doit être retourné sur draft — c'est ce qui "
            "doit empêcher le LLM d'affirmer faussement la génération."
        )


@pytest.mark.unit
class TestProjectEsgIntentChatGlobal:
    """[bug F047 US3 — 2026-05-23] Sur le chat flottant (current_page hors
    fiche projet), le LLM doit reconnaître « rapport ESG de mon projet
    [nom] » comme une intention F047 et NE PAS basculer sur F05 entreprise
    (Mefali 30 critères + batch_save_esg_criteria).
    """

    @pytest.mark.parametrize(
        "msg",
        [
            "génère le rapport ESG de mon projet Solarisation Boulangerie Dakar",
            "rapport ESG de mon projet",
            "genere mon rapport ESG du projet",
            "finalise l'évaluation ESG de mon projet",
            "rapport ESIA-light pour la BOAD",
            "dossier bailleur GCF pour mon projet",
            "dossier IFC",
        ],
    )
    def test_detect_project_esg_intent_extended_phrases(self, msg: str):
        from app.graph.nodes import _detect_project_esg_intent

        assert _detect_project_esg_intent(msg) is True, (
            f"« {msg} » doit déclencher l'intent F047 (cf. bugfix US3 live)."
        )

    def test_global_whitelist_exposes_project_esg_tools(self):
        """F047 tools doivent être transverses (chat flottant) — peu importe
        la page courante, le LLM doit pouvoir appeler
        ``generate_project_esg_report`` et compagnie.
        """
        from app.graph.tool_selector_config import GLOBAL_WHITELIST

        for tool_name in (
            "create_project_esg_assessment",
            "save_project_esg_criterion",
            "finalize_project_esg_assessment",
            "get_project_esg_assessment",
            "list_project_esg_assessments",
            "generate_project_esg_report",
        ):
            assert tool_name in GLOBAL_WHITELIST, (
                f"{tool_name} doit être dans GLOBAL_WHITELIST pour rester "
                "accessible depuis le chat flottant."
            )

    @pytest.mark.asyncio
    async def test_chat_node_injects_no_page_variant_on_chat_global(
        self, monkeypatch,
    ):
        """Sur ``/`` (chat_global), message « rapport ESG mon projet » →
        la directive variante ``_no_page`` doit être injectée (instruct
        LLM à utiliser ``list_projects`` AVANT toute action F047, et à
        NE PAS appeler les tools F05 entreprise).
        """
        from langchain_core.messages import HumanMessage

        captured: dict = {}

        class _FakeBoundLLM:
            async def ainvoke(self, messages):  # noqa: ANN001
                captured["messages"] = messages
                from langchain_core.messages import AIMessage

                return AIMessage(content="ok")

        class _FakeLLM:
            def bind_tools(self, _tools):  # noqa: ANN001
                return _FakeBoundLLM()

        monkeypatch.setattr("app.graph.nodes.get_llm", lambda: _FakeLLM())

        async def _bypass_skills(*, base_prompt, base_tools, **_kwargs):  # noqa: ANN001
            return base_prompt, list(base_tools), None

        monkeypatch.setattr(
            "app.graph.skill_integration.apply_skills_to_node",
            _bypass_skills,
        )

        from app.graph.nodes import chat_node

        state = {
            "messages": [
                HumanMessage(
                    content="génère le rapport ESG de mon projet Solarisation Boulangerie Dakar"
                )
            ],
            "user_id": "00000000-0000-0000-0000-000000000001",
            "user_profile": {"company_name": "TestPME"},
            "context_memory": [],
            "current_page": "/",
        }
        await chat_node(state, config={"configurable": {}})
        text = captured["messages"][0].content
        # Directive _no_page doit être présente.
        assert "REGLE TRANSVERSE" in text, (
            "La directive _no_page (chat flottant) doit être injectée quand "
            "l'utilisateur demande un rapport projet hors fiche projet."
        )
        # Doit instruire d'utiliser list_projects AVANT d'agir.
        assert "list_projects" in text, (
            "La directive doit dire au LLM d'appeler list_projects pour "
            "retrouver le projet par son nom."
        )
        # Doit interdire les tools F05 entreprise.
        assert "batch_save_esg_criteria" in text, (
            "La directive doit explicitement nommer les anti-patterns F05 "
            "à rejeter (batch_save_esg_criteria, finalize_esg_assessment, "
            "generate_esg_report)."
        )


@pytest.mark.unit
class TestSaveCriterionStrictPayloadValidation:
    """[bug F047 US3 — payload BDD 2026-05-23] Validator Pydantic strict.

    Avant le fix, le LLM passait par exemple ``response_value={"value":"B"}``
    pour un ``response_type="qcu"`` ; le tool acceptait silencieusement et
    ``normalize_response`` retournait 0.0 (ni `choice` ni `choices`
    présents). Conséquence observée live : 4 critères BOAD ESS persistés
    avec ``normalized_score=0`` chacun → score global = 0 + coverage 26.7%.

    Désormais le validator rejette explicitement ce payload, le LLM
    relit l'erreur et retry avec ``{"choice":"yes"}`` (ou la forme
    correcte selon le response_type).
    """

    def _build_args(self, response_type: str, response_value: Any):
        import uuid as _uuid
        from app.graph.tools.project_esg_tools import SaveCriterionArgs

        return SaveCriterionArgs(
            assessment_id=_uuid.uuid4(),
            criterion_id=_uuid.uuid4(),
            response_type=response_type,
            response_value=response_value,
        )

    # --- response_type=qcu ---
    def test_qcu_accepts_choice(self):
        args = self._build_args("qcu", {"choice": "yes"})
        assert args.response_value == {"choice": "yes"}

    def test_qcu_accepts_choices_list(self):
        args = self._build_args("qcu", {"choices": ["a"]})
        assert args.response_value == {"choices": ["a"]}

    def test_qcu_rejects_value_key(self):
        """Bug live observé : LLM passait {"value":"B"} pour qcu."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc:
            self._build_args("qcu", {"value": "B"})
        msg = str(exc.value)
        assert "choice" in msg
        assert "choices" in msg

    def test_qcu_rejects_empty_payload(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._build_args("qcu", {})

    def test_qcu_rejects_empty_choice_string(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._build_args("qcu", {"choice": "   "})

    # --- response_type=qcm ---
    def test_qcm_accepts_choices_list(self):
        args = self._build_args("qcm", {"choices": ["a", "b"]})
        assert args.response_value == {"choices": ["a", "b"]}

    def test_qcm_rejects_empty_choices_list(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._build_args("qcm", {"choices": []})

    # --- response_type=qcu_justification ---
    def test_qcu_justification_accepts_choice_plus_justification(self):
        args = self._build_args(
            "qcu_justification",
            {"choice": "yes", "justification": "conforme code travail UEMOA"},
        )
        assert args.response_value["justification"].startswith("conforme")

    def test_qcu_justification_rejects_missing_justification(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc:
            self._build_args("qcu_justification", {"choice": "yes"})
        assert "justification" in str(exc.value)

    # --- response_type=numeric ---
    def test_numeric_accepts_value_number(self):
        args = self._build_args("numeric", {"value": 0.7})
        assert args.response_value["value"] == 0.7

    def test_numeric_rejects_value_string(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._build_args("numeric", {"value": "0.7"})

    def test_numeric_rejects_choice_key(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._build_args("numeric", {"choice": "yes"})

    # --- response_type=money ---
    def test_money_accepts_amount_and_currency(self):
        args = self._build_args("money", {"amount": 1000, "currency": "XOF"})
        assert args.response_value == {"amount": 1000, "currency": "XOF"}

    def test_money_accepts_amount_only(self):
        args = self._build_args("money", {"amount": 500})
        assert args.response_value == {"amount": 500}

    def test_money_rejects_missing_amount(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._build_args("money", {"currency": "XOF"})

    def test_money_rejects_non_string_currency(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._build_args("money", {"amount": 100, "currency": 42})

    # --- response_type=free_text ---
    def test_free_text_accepts_text_string(self):
        args = self._build_args("free_text", {"text": "Description du critère"})
        assert args.response_value["text"].startswith("Description")

    def test_free_text_rejects_missing_text(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._build_args("free_text", {"value": "B"})

    # --- response_type invalide ---
    def test_invalid_response_type_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc:
            self._build_args("scale", {"value": 5})
        assert "response_type" in str(exc.value)


@pytest.mark.unit
class TestGenerateReportDocstringAntiHallucination:
    """(D) Le contrat docstring est verrouillé : il doit contenir une
    clause anti-hallucination explicite que le LLM lit au moment du
    tool selection.
    """

    def test_docstring_includes_anti_hallucination_clause(self):
        doc = (generate_project_esg_report.description or "")
        upper = doc.upper()
        assert "ANTI-HALLUCINATION" in upper, (
            "La docstring de generate_project_esg_report doit comporter une "
            "clause ANTI-HALLUCINATION pour empêcher le LLM d'affirmer la "
            "génération du rapport sans appeler le tool."
        )
        assert "N'AFFIRME JAMAIS" in upper or "JAMAIS" in upper, (
            "La docstring doit interdire explicitement l'affirmation du "
            "rapport généré sans tool call."
        )

    def test_docstring_mentions_pdf_format(self):
        doc = (generate_project_esg_report.description or "").upper()
        assert "PDF" in doc, (
            "La docstring doit rappeler le format PDF (vs .docx de F05)."
        )
