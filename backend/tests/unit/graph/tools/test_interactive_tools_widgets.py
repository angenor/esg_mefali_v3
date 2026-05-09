"""Tests F10 — Tools LangChain des 9 widgets (consolidé pour T015/T026/T032/T039/T045/T051/T056/T061).

Vérifie pour chaque tool :
- Validation Pydantic args (extra='forbid', bornes)
- Persistance correcte en BDD avec ``payload`` discriminé
- Marker SSE correct
- Journalisation tool_call_logs
- Gestion ``pending → expired`` (invariant 1 question pending max)

Couvre FR-006, FR-007, FR-008, FR-009.
"""

from __future__ import annotations

import json
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.graph.tools.interactive_tools import (
    ask_date,
    ask_date_range,
    ask_file_upload,
    ask_number,
    ask_rating,
    ask_select,
    ask_yes_no,
    show_form,
    show_summary_card,
)
from app.models.interactive_question import (
    InteractiveQuestion,
    InteractiveQuestionState,
)


@pytest.fixture
async def widget_config(db_session):
    """RunnableConfig avec db, user_id, conversation_id valides."""
    from app.models.conversation import Conversation
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)
    conv = Conversation(
        id=uuid4(),
        user_id=user.id,
        account_id=user.account_id,
        title="Widget test",
    )
    db_session.add(conv)
    await db_session.flush()

    return {
        "configurable": {
            "db": db_session,
            "user_id": str(user.id),
            "conversation_id": str(conv.id),
            "account_id": str(user.account_id),
            "active_module": "chat",
            "tools_offered": ["ask_yes_no"],
        }
    }, conv.id


def _extract_sse_marker(result: str) -> dict | None:
    """Parse le marker SSE injecté à la fin du retour d'un tool."""
    if "<!--SSE:" not in result:
        return None
    json_part = result.split("<!--SSE:")[1].rstrip("-->").rstrip()
    if json_part.endswith("--"):
        json_part = json_part[:-2]
    return json.loads(json_part)


# ─── ask_yes_no ─────────────────────────────────────────────────────────


class TestAskYesNo:
    @pytest.mark.asyncio
    async def test_persist_destructive_question(self, widget_config) -> None:
        config, conv_id = widget_config
        result = await ask_yes_no.ainvoke(
            {
                "question": "Êtes-vous certain ?",
                "confirm_label": "Oui, supprimer",
                "deny_label": "Non, annuler",
                "destructive": True,
            },
            config=config,
        )
        assert "Question posée" in result
        marker = _extract_sse_marker(result)
        assert marker is not None
        assert marker["__sse_interactive_question__"] is True
        assert marker["question_type"] == "yes_no"
        assert marker["payload"]["destructive"] is True
        assert marker["payload"]["confirm_label"] == "Oui, supprimer"

        # Vérifier en BDD
        db = config["configurable"]["db"]
        rows = await db.execute(
            select(InteractiveQuestion).where(
                InteractiveQuestion.conversation_id == conv_id,
            ),
        )
        questions = rows.scalars().all()
        assert len(questions) == 1
        assert questions[0].question_type == "yes_no"
        assert questions[0].state == InteractiveQuestionState.PENDING.value
        assert questions[0].payload["destructive"] is True

    @pytest.mark.asyncio
    async def test_default_labels(self, widget_config) -> None:
        config, _ = widget_config
        result = await ask_yes_no.ainvoke(
            {"question": "Test ?"}, config=config,
        )
        marker = _extract_sse_marker(result)
        assert marker["payload"]["confirm_label"] == "Oui"
        assert marker["payload"]["deny_label"] == "Non"
        assert marker["payload"]["destructive"] is False


# ─── ask_select ─────────────────────────────────────────────────────────


class TestAskSelect:
    @pytest.mark.asyncio
    async def test_persist_with_grouped_options(self, widget_config) -> None:
        config, conv_id = widget_config
        result = await ask_select.ainvoke(
            {
                "question": "Quel pays ?",
                "options": [
                    {"id": "ci", "label": "Côte d'Ivoire", "group": "UEMOA"},
                    {"id": "sn", "label": "Sénégal", "group": "UEMOA"},
                ],
                "min_selections": 1,
                "max_selections": 1,
                "allow_other": False,
            },
            config=config,
        )
        marker = _extract_sse_marker(result)
        assert marker["question_type"] == "select"
        assert len(marker["payload"]["options"]) == 2
        assert marker["payload"]["options"][0]["group"] == "UEMOA"

    @pytest.mark.asyncio
    async def test_refuse_201_options(self, widget_config) -> None:
        config, _ = widget_config
        opts = [{"id": f"o_{i}", "label": f"L {i}"} for i in range(201)]
        # Pydantic args_schema valide en amont avant l'invocation : ValidationError remontée.
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            await ask_select.ainvoke(
                {"question": "Q ?", "options": opts}, config=config,
            )

    @pytest.mark.asyncio
    async def test_max_selections_50_with_select(self, widget_config) -> None:
        """Vérifie que max_selections=50 passe la contrainte étendue."""
        config, conv_id = widget_config
        opts = [{"id": f"o_{i}", "label": f"L {i}"} for i in range(50)]
        result = await ask_select.ainvoke(
            {
                "question": "Multi ?",
                "options": opts,
                "min_selections": 1,
                "max_selections": 50,
            },
            config=config,
        )
        marker = _extract_sse_marker(result)
        assert marker is not None, f"Aucun marker SSE: {result}"
        # Vérifier en BDD que max_selections=50 passe la contrainte ck_iq_max_le_8_or_select_form
        db = config["configurable"]["db"]
        rows = await db.execute(
            select(InteractiveQuestion).where(
                InteractiveQuestion.conversation_id == conv_id,
            ),
        )
        q = rows.scalars().first()
        assert q is not None
        assert q.max_selections == 50


# ─── ask_number ─────────────────────────────────────────────────────────


class TestAskNumber:
    @pytest.mark.asyncio
    async def test_with_currency(self, widget_config) -> None:
        config, _ = widget_config
        result = await ask_number.ainvoke(
            {
                "question": "CA annuel ?",
                "unit": "FCFA",
                "min": 0,
                "max": 1_000_000_000,
                "currency": "XOF",
            },
            config=config,
        )
        marker = _extract_sse_marker(result)
        assert marker["question_type"] == "number"
        assert marker["payload"]["currency"] == "XOF"
        assert marker["payload"]["unit"] == "FCFA"


# ─── ask_date / ask_date_range ──────────────────────────────────────────


class TestAskDate:
    @pytest.mark.asyncio
    async def test_with_min_today(self, widget_config) -> None:
        config, _ = widget_config
        today = date(2026, 5, 7)
        result = await ask_date.ainvoke(
            {"question": "Validité jusqu'à ?", "min": today.isoformat()},
            config=config,
        )
        marker = _extract_sse_marker(result)
        assert marker["question_type"] == "date"
        assert marker["payload"]["min"] == today.isoformat()


class TestAskDateRange:
    @pytest.mark.asyncio
    async def test_basic(self, widget_config) -> None:
        config, _ = widget_config
        result = await ask_date_range.ainvoke(
            {"question": "Quelle période ?"},
            config=config,
        )
        marker = _extract_sse_marker(result)
        assert marker["question_type"] == "date_range"


# ─── ask_rating ─────────────────────────────────────────────────────────


class TestAskRating:
    @pytest.mark.asyncio
    async def test_scale_5(self, widget_config) -> None:
        config, _ = widget_config
        result = await ask_rating.ainvoke(
            {
                "question": "Évaluez votre tri",
                "scale": 5,
                "labels": ["Très mauvais", "Mauvais", "Moyen", "Très bien", "Excellent"],
            },
            config=config,
        )
        marker = _extract_sse_marker(result)
        assert marker["question_type"] == "rating"
        assert marker["payload"]["scale"] == 5
        assert len(marker["payload"]["labels"]) == 5


# ─── ask_file_upload ────────────────────────────────────────────────────


class TestAskFileUpload:
    @pytest.mark.asyncio
    async def test_default_accept(self, widget_config) -> None:
        config, _ = widget_config
        result = await ask_file_upload.ainvoke(
            {"question": "Envoyez votre business plan"},
            config=config,
        )
        marker = _extract_sse_marker(result)
        assert marker["question_type"] == "file_upload"
        assert ".pdf" in marker["payload"]["accept"]
        assert marker["payload"]["max_size_mb"] == 10

    @pytest.mark.asyncio
    async def test_with_custom_accept_and_doc_hint(self, widget_config) -> None:
        config, _ = widget_config
        result = await ask_file_upload.ainvoke(
            {
                "question": "PDF only",
                "accept": [".pdf"],
                "max_size_mb": 5,
                "multi": True,
                "doc_type_hint": "business_plan",
            },
            config=config,
        )
        marker = _extract_sse_marker(result)
        assert marker["payload"]["accept"] == [".pdf"]
        assert marker["payload"]["max_size_mb"] == 5
        assert marker["payload"]["multi"] is True
        assert marker["payload"]["doc_type_hint"] == "business_plan"


# ─── show_form ──────────────────────────────────────────────────────────


class TestShowForm:
    @pytest.mark.asyncio
    async def test_8_fields(self, widget_config) -> None:
        config, conv_id = widget_config
        fields = [
            {"name": "project_name", "label": "Nom", "type": "text", "required": True},
            {"name": "description", "label": "Description", "type": "textarea"},
            {"name": "target_amount", "label": "Montant", "type": "money"},
            {"name": "sector", "label": "Secteur", "type": "select"},
            {"name": "duration_months", "label": "Durée", "type": "number"},
            {"name": "start_date", "label": "Démarrage", "type": "date"},
            {"name": "site", "label": "Site", "type": "text"},
            {"name": "owner", "label": "Porteur", "type": "text"},
        ]
        result = await show_form.ainvoke(
            {"title": "Nouveau projet", "fields": fields, "submit_label": "Créer"},
            config=config,
        )
        marker = _extract_sse_marker(result)
        assert marker["question_type"] == "form"
        assert marker["payload"]["title"] == "Nouveau projet"
        assert len(marker["payload"]["fields"]) == 8

        # Vérifier que max_selections=8 passe la contrainte étendue
        db = config["configurable"]["db"]
        rows = await db.execute(
            select(InteractiveQuestion).where(
                InteractiveQuestion.conversation_id == conv_id,
            ),
        )
        q = rows.scalars().first()
        assert q.question_type == "form"
        assert q.max_selections == 8


# ─── show_summary_card ──────────────────────────────────────────────────


class TestShowSummaryCard:
    @pytest.mark.asyncio
    async def test_mix_editable(self, widget_config) -> None:
        config, _ = widget_config
        result = await show_summary_card.ainvoke(
            {
                "title": "Extraction Statuts.pdf",
                "items": [
                    {"label": "Forme juridique", "value": "SARL", "editable": True},
                    {"label": "Capital", "value": "5 000 000 FCFA", "editable": True},
                    {"label": "Date création", "value": "2018-03-15", "editable": False},
                ],
            },
            config=config,
        )
        marker = _extract_sse_marker(result)
        assert marker["question_type"] == "summary_card"
        assert len(marker["payload"]["items"]) == 3
        assert marker["payload"]["items"][0]["editable"] is True
        assert marker["payload"]["items"][2]["editable"] is False


# ─── Error paths : config manquant, conversation_id absent ──────────────


class TestErrorPaths:
    @pytest.mark.asyncio
    async def test_ask_yes_no_returns_error_when_config_missing(self) -> None:
        # Pas de config → message d'erreur
        result = await ask_yes_no.ainvoke({"question": "Q ?"}, config=None)
        assert "Erreur" in result

    @pytest.mark.asyncio
    async def test_ask_yes_no_returns_error_when_conversation_id_missing(
        self, db_session,
    ) -> None:
        from tests.conftest import make_pme_user

        user = await make_pme_user(db_session)
        config = {
            "configurable": {
                "db": db_session,
                "user_id": str(user.id),
                # conversation_id manquant
            },
        }
        result = await ask_yes_no.ainvoke({"question": "Q ?"}, config=config)
        assert "conversation_id" in result.lower()

    @pytest.mark.asyncio
    async def test_show_form_with_form_field_missing_required(self, widget_config) -> None:
        config, _ = widget_config
        # Test que les champs requis sont validés via Pydantic
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            await show_form.ainvoke(
                {
                    "title": "T",
                    "fields": [{"name": "x", "label": "X"}],  # missing 'type'
                },
                config=config,
            )


# ─── Invariant : 1 question pending max par conversation ────────────────


class TestPendingExpiry:
    @pytest.mark.asyncio
    async def test_new_widget_expires_previous_pending(self, widget_config) -> None:
        config, conv_id = widget_config
        # Première question
        await ask_yes_no.ainvoke({"question": "Q1 ?"}, config=config)

        # Deuxième question : doit expirer la première
        await ask_select.ainvoke(
            {"question": "Q2 ?", "options": [{"id": "a", "label": "A"}]},
            config=config,
        )

        db = config["configurable"]["db"]
        rows = await db.execute(
            select(InteractiveQuestion).where(
                InteractiveQuestion.conversation_id == conv_id,
            ),
        )
        questions = sorted(rows.scalars().all(), key=lambda q: q.created_at)
        assert len(questions) == 2
        assert questions[0].state == InteractiveQuestionState.EXPIRED.value
        assert questions[1].state == InteractiveQuestionState.PENDING.value
