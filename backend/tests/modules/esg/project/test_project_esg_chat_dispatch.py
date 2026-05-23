"""[bug F047 US4] — Le LLM doit appeler `create_project_esg_assessment` (et
non se contenter de `ask_interactive_question`) quand l'utilisateur demande
une évaluation ESG-projet depuis la fiche projet (`/profile/projects/{id}`).

Symptôme reproduit en prod : sur cette URL, message "Évalue mon projet
contre IFC PS" → le LLM appelait `ask_interactive_question` mais jamais
`create_project_esg_assessment`. Aucun draft n'était créé en BDD.

Ce test verrouille deux garanties qui matérialisent le fix :

(A) La procédure du skill F23 `skill_project_esg_assessment` est rédigée
    en mode impératif explicite (« TU DOIS », « AVANT toute autre action »)
    pour que le LLM sache quels tools appeler dans quel ordre.

(B) Le prompt système de `chat_node`, quand `current_page` matche la fiche
    projet (avec ou sans `/esg`) ET que le dernier message exprime une
    intention ESG-projet (IFC PS / GCF ESS / BOAD ESS / etc.), contient
    une section page-contextuelle dirigeant le LLM vers
    `create_project_esg_assessment` AVANT toute interaction widget.

Le test ne dépend pas du LLM réel : il vérifie la composition du prompt
et la procédure publiée (sources de vérité côté instructions).
"""

from __future__ import annotations

import re

import pytest
from langchain_core.messages import HumanMessage

from app.graph.nodes import (
    _detect_financing_request,
    _detect_project_esg_intent,
    _extract_project_id_from_page,
    _is_project_page,
)
from app.modules.skills.seed import _build_seeds


@pytest.mark.unit
class TestSkillF23ProcedureIsImperative:
    """(A) La procédure publiée doit dicter l'ordre des tools sans ambiguïté."""

    def _skill_seed(self) -> dict:
        import uuid

        for seed in _build_seeds(uuid.uuid4()):
            if seed["name"] == "skill_project_esg_assessment":
                return seed
        raise AssertionError("skill_project_esg_assessment introuvable dans _build_seeds")

    def test_procedure_orders_create_before_ask_widget(self):
        proc = self._skill_seed()["procedure"]
        idx_create = proc.find("create_project_esg_assessment")
        idx_ask = proc.find("ask_interactive_question")
        assert idx_create != -1, (
            "La procédure doit explicitement nommer create_project_esg_assessment."
        )
        assert idx_ask != -1, (
            "La procédure doit aussi nommer ask_interactive_question (étape 3)."
        )
        assert idx_create < idx_ask, (
            "create_project_esg_assessment DOIT apparaître AVANT "
            "ask_interactive_question dans la procédure (ordre du workflow)."
        )

    def test_procedure_contains_imperative_marker(self):
        """La procédure doit contenir une instruction impérative explicite."""
        proc = self._skill_seed()["procedure"].upper()
        # "TU DOIS", "AVANT", "OBLIGATOIRE" ou une formulation impérative
        # équivalente doit apparaître pour ancrer la directive côté LLM.
        markers = ("TU DOIS", "AVANT TOUTE AUTRE", "OBLIGATOIRE", "RÈGLE ABSOLUE", "REGLE ABSOLUE")
        assert any(m in proc for m in markers), (
            "La procédure doit contenir au moins un marqueur impératif "
            f"parmi {markers}, sinon le LLM ignore les étapes 2-4."
        )


@pytest.mark.unit
class TestProjectEsgIntentDetection:
    """(B-1) Détection de l'intention ESG-projet (helper pur, déterministe)."""

    @pytest.mark.parametrize(
        "message,expected",
        [
            ("Évalue mon projet contre IFC PS", True),
            ("évaluer mon projet contre GCF ESS", True),
            ("Lance l'évaluation BOAD ESS de mon projet", True),
            ("Je veux scorer mon projet pour les Performance Standards", True),
            ("Préparer mon ESIA-light pour la BOAD", True),
            ("Quel est mon CA annuel ?", False),
            ("Bonjour", False),
            ("", False),
        ],
    )
    def test_detect_project_esg_intent(self, message: str, expected: bool):
        assert _detect_project_esg_intent(message) is expected


@pytest.mark.unit
class TestFinancingRouterExclusion:
    """`_detect_financing_request` doit IGNORER les mots-clés bailleurs
    (IFC PS, GCF ESS, BOAD ESS) qui désignent en fait des référentiels
    ESG-projet F047. Sans cette exclusion, le pattern ``\\bIFC\\b`` match
    "IFC PS" et envoie vers `financing_node` qui n'a pas les tools F047.
    """

    @pytest.mark.parametrize(
        "msg,routes_to_financing",
        [
            # Demandes ESG-projet — doivent rester sur chat_node (False).
            ("Évalue mon projet contre IFC PS", False),
            ("évaluer mon projet contre GCF ESS", False),
            ("Score mon projet selon BOAD ESS", False),
            ("Je veux faire l'ESIA-light", False),
            ("Performance Standards IFC pour mon projet", False),
            # Demandes financement classiques — doivent router financing (True).
            ("Je cherche un fonds vert GCF", True),
            ("Quels fonds climat sont éligibles ?", True),
            ("Comment accéder au financement BOAD ?", True),
            ("Je veux postuler à un fonds vert", True),
        ],
    )
    def test_financing_excludes_project_esg_keywords(
        self, msg: str, routes_to_financing: bool
    ):
        assert _detect_financing_request(msg) is routes_to_financing


@pytest.mark.unit
class TestProjectIdExtraction:
    """(B-1bis) Le UUID du projet doit être extrait depuis l'URL active."""

    @pytest.mark.parametrize(
        "url,expected",
        [
            (
                "/profile/projects/2fd64c66-3aa4-4de7-b9eb-f47d50d03e36",
                "2fd64c66-3aa4-4de7-b9eb-f47d50d03e36",
            ),
            (
                "/profile/projects/2fd64c66-3aa4-4de7-b9eb-f47d50d03e36/esg",
                "2fd64c66-3aa4-4de7-b9eb-f47d50d03e36",
            ),
            (
                "/profile/projects/2fd64c66-3aa4-4de7-b9eb-f47d50d03e36/",
                "2fd64c66-3aa4-4de7-b9eb-f47d50d03e36",
            ),
            ("/profile/projects/not-a-uuid", None),
            ("/profile/projects", None),
            ("/profile", None),
            ("", None),
            (None, None),
        ],
    )
    def test_extract_project_id(self, url, expected):
        assert _extract_project_id_from_page(url) == expected


@pytest.mark.unit
class TestChatNodePromptOnProjectPage:
    """(B-2) Le prompt système de `chat_node` doit inclure une instruction
    page-contextuelle quand `current_page` est une fiche projet ET le
    dernier message exprime une intention ESG-projet.
    """

    @pytest.mark.asyncio
    async def test_chat_node_injects_project_esg_directive(self, monkeypatch):
        """Sur /profile/projects/{id}, message « Évalue contre IFC PS » →
        le prompt système doit contenir une directive dirigeant le LLM
        vers `create_project_esg_assessment` AVANT tout widget interactif.
        """
        captured: dict = {}

        # Mock du LLM : on capture les messages envoyés sans appel réseau.
        class _FakeBoundLLM:
            async def ainvoke(self, messages):  # noqa: ANN001
                captured["messages"] = messages
                from langchain_core.messages import AIMessage

                return AIMessage(content="ok")

        class _FakeLLM:
            def bind_tools(self, _tools):  # noqa: ANN001
                return _FakeBoundLLM()

        monkeypatch.setattr("app.graph.nodes.get_llm", lambda: _FakeLLM())
        # Bypass intégration skill (BDD non requise pour ce test).
        monkeypatch.setattr(
            "app.graph.skill_integration.apply_skills_to_node",
            _bypass_skills,
        )

        from app.graph.nodes import chat_node

        state = {
            "messages": [HumanMessage(content="Évalue mon projet contre IFC PS")],
            "user_id": "00000000-0000-0000-0000-000000000001",
            "user_profile": {"company_name": "TestPME", "sector": "agriculture"},
            "context_memory": [],
            "current_page": "/profile/projects/abc-123",
        }
        await chat_node(state, config={"configurable": {}})

        system_msg = captured["messages"][0]
        text = system_msg.content
        # 1. La directive ESG-projet doit être présente.
        assert "create_project_esg_assessment" in text, (
            "Le prompt doit nommer create_project_esg_assessment quand "
            "l'utilisateur demande une évaluation projet contre IFC PS."
        )
        # 2. La directive doit explicitement interdire / décourager
        # ask_interactive_question avant la création de l'évaluation projet.
        # L'ordre exact (interdiction d'abord ou tool d'abord) n'a pas
        # d'importance — ce qui compte est que LES DEUX cohabitent dans
        # la même directive.
        block_match = re.search(
            r"(NE JAMAIS|NE\s+DEMANDE\s+PAS|NE\s+POSE\s+AUCUNE|AVANT|"
            r"N'APPELLE\s+PAS|ANTI[- ]PATTERN).{0,200}ask_interactive_question",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        assert block_match is not None, (
            "Le prompt doit interdire ask_interactive_question (mot-clés "
            "attendus : NE JAMAIS/NE DEMANDE PAS/NE POSE AUCUNE/AVANT/"
            "N'APPELLE PAS/ANTI-PATTERN)."
        )
        # Le cas UUID est couvert par test_chat_node_injects_uuid_in_directive.

    @pytest.mark.asyncio
    async def test_chat_node_injects_uuid_in_directive(self, monkeypatch):
        """Quand current_page contient un UUID valide, la directive doit le
        citer explicitement pour empêcher le LLM de redemander le projet.
        """
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
        monkeypatch.setattr(
            "app.graph.skill_integration.apply_skills_to_node",
            _bypass_skills,
        )

        from app.graph.nodes import chat_node

        project_uuid = "2fd64c66-3aa4-4de7-b9eb-f47d50d03e36"
        state = {
            "messages": [HumanMessage(content="Évalue mon projet contre IFC PS")],
            "user_id": "00000000-0000-0000-0000-000000000001",
            "user_profile": {"company_name": "TestPME", "sector": "agriculture"},
            "context_memory": [],
            "current_page": f"/profile/projects/{project_uuid}",
        }
        await chat_node(state, config={"configurable": {}})
        text = captured["messages"][0].content
        # Le UUID doit apparaître dans la directive pour court-circuiter
        # toute question d'orientation côté LLM.
        assert project_uuid in text, (
            f"Le project_id ({project_uuid}) doit être injecté dans la "
            "directive pour empêcher le LLM de redemander l'identifiant "
            "du projet via ask_interactive_question."
        )
        # Et il doit être attaché à create_project_esg_assessment dans le texte.
        assert (
            f'create_project_esg_assessment(project_id="{project_uuid}"'
            in text
        ), (
            "Le UUID doit être passé en argument positionnel/keyword de "
            "create_project_esg_assessment dans la directive."
        )

    @pytest.mark.asyncio
    async def test_chat_node_skips_directive_when_intent_unrelated(self, monkeypatch):
        """Sur la même page, mais sans intent ESG-projet, la directive ne
        doit PAS être injectée (sinon on pollue le prompt sur des questions
        non ESG comme « Mets à jour le nom du projet »).
        """
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
        monkeypatch.setattr(
            "app.graph.skill_integration.apply_skills_to_node",
            _bypass_skills,
        )

        from app.graph.nodes import chat_node

        state = {
            "messages": [HumanMessage(content="Renomme ce projet en Solaire 2026")],
            "user_id": "00000000-0000-0000-0000-000000000001",
            "user_profile": {"company_name": "TestPME"},
            "context_memory": [],
            "current_page": "/profile/projects/abc-123",
        }
        await chat_node(state, config={"configurable": {}})
        text = captured["messages"][0].content
        # La directive ESG-projet n'est PAS pertinente ici.
        assert "EVALUATION ESG-PROJET" not in text.upper(), (
            "La directive ne doit s'activer que sur intent ESG-projet."
        )


async def _bypass_skills(*, base_prompt, base_tools, **_kwargs):  # noqa: ANN001
    """Stub `apply_skills_to_node` qui renvoie l'identité (pas de BDD)."""
    return base_prompt, list(base_tools), None


@pytest.mark.unit
class TestSaveCriterionAcceptsJsonString:
    """`SaveCriterionArgs.response_value` tolère les chaînes JSON sérialisées
    en plus du dict natif. Certains LLMs envoient `response_value="{\\"choice\\":\\"yes\\"}"`
    (string) plutôt que l'objet JSON, ce qui faisait échouer le tool avec
    « Input should be a valid dictionary ».
    """

    def test_native_dict_accepted(self):
        import uuid as _uuid
        from app.graph.tools.project_esg_tools import SaveCriterionArgs

        args = SaveCriterionArgs(
            assessment_id=_uuid.uuid4(),
            criterion_id=_uuid.uuid4(),
            response_type="qcu",
            response_value={"choice": "yes"},
        )
        assert args.response_value == {"choice": "yes"}

    def test_json_string_auto_parsed(self):
        import uuid as _uuid
        from app.graph.tools.project_esg_tools import SaveCriterionArgs

        args = SaveCriterionArgs(
            assessment_id=_uuid.uuid4(),
            criterion_id=_uuid.uuid4(),
            response_type="qcu",
            response_value='{"choice": "yes"}',
        )
        assert args.response_value == {"choice": "yes"}
        assert isinstance(args.response_value, dict)

    def test_non_json_string_rejected(self):
        import uuid as _uuid
        from pydantic import ValidationError
        from app.graph.tools.project_esg_tools import SaveCriterionArgs

        with pytest.raises(ValidationError):
            SaveCriterionArgs(
                assessment_id=_uuid.uuid4(),
                criterion_id=_uuid.uuid4(),
                response_type="qcu",
                response_value="not a json string",
            )

    def test_json_string_with_array_rejected(self):
        """response_value doit toujours être un dict, pas un array JSON."""
        import uuid as _uuid
        from pydantic import ValidationError
        from app.graph.tools.project_esg_tools import SaveCriterionArgs

        with pytest.raises(ValidationError):
            SaveCriterionArgs(
                assessment_id=_uuid.uuid4(),
                criterion_id=_uuid.uuid4(),
                response_type="qcm",
                response_value='["choice1", "choice2"]',
            )
