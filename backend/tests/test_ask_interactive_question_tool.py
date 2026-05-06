"""Tests unitaires du tool ask_interactive_question (feature 018)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.graph.tools.interactive_tools import ask_interactive_question
from app.models.conversation import Conversation
from app.models.interactive_question import (
    InteractiveQuestion,
    InteractiveQuestionState,
)
from app.models.user import User


pytestmark = pytest.mark.asyncio


async def _make_user_and_conversation(db_session) -> tuple[User, Conversation]:
    from app.models.account import Account

    account = Account(name="Test Co")
    db_session.add(account)
    await db_session.flush()
    user = User(
        email=f"u-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password="x",
        full_name="Test User",
        company_name="Test Co",
        is_active=True,
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()
    conv = Conversation(user_id=user.id, title="t")
    db_session.add(conv)
    await db_session.flush()
    return user, conv


def _config_for(db_session, user_id: uuid.UUID, conv_id: uuid.UUID) -> dict:
    return {
        "configurable": {
            "db": db_session,
            "user_id": user_id,
            "conversation_id": conv_id,
            "active_module": "profiling",
        }
    }


def _extract_sse_payload(result: str) -> dict | None:
    marker = "<!--SSE:"
    if marker not in result:
        return None
    start = result.index(marker) + len(marker)
    end = result.index("-->", start)
    return json.loads(result[start:end])


async def test_ask_qcu_creates_pending_question(db_session):
    user, conv = await _make_user_and_conversation(db_session)

    result = await ask_interactive_question.ainvoke(
        {
            "question_type": "qcu",
            "prompt": "Quel est ton secteur ?",
            "options": [
                {"id": "agri", "label": "Agriculture", "emoji": "🌾"},
                {"id": "energy", "label": "Energie", "emoji": "⚡"},
                {"id": "recycle", "label": "Recyclage", "emoji": "♻️"},
            ],
        },
        config=_config_for(db_session, user.id, conv.id),
    )

    payload = _extract_sse_payload(result)
    assert payload is not None
    assert payload["type"] == "interactive_question"
    assert payload["question_type"] == "qcu"
    assert len(payload["options"]) == 3

    rows = (await db_session.execute(select(InteractiveQuestion))).scalars().all()
    assert len(rows) == 1
    assert rows[0].state == InteractiveQuestionState.PENDING.value
    assert rows[0].max_selections == 1
    assert rows[0].module == "profiling"


async def test_ask_expires_previous_pending(db_session):
    user, conv = await _make_user_and_conversation(db_session)

    config = _config_for(db_session, user.id, conv.id)
    await ask_interactive_question.ainvoke(
        {
            "question_type": "qcu",
            "prompt": "Q1",
            "options": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
            ],
        },
        config=config,
    )
    await ask_interactive_question.ainvoke(
        {
            "question_type": "qcu",
            "prompt": "Q2",
            "options": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
            ],
        },
        config=config,
    )

    rows = (
        await db_session.execute(
            select(InteractiveQuestion).order_by(InteractiveQuestion.created_at.asc())
        )
    ).scalars().all()
    assert len(rows) == 2
    assert rows[0].state == InteractiveQuestionState.EXPIRED.value
    assert rows[1].state == InteractiveQuestionState.PENDING.value


async def test_ask_qcm_with_min_max(db_session):
    user, conv = await _make_user_and_conversation(db_session)

    result = await ask_interactive_question.ainvoke(
        {
            "question_type": "qcm",
            "prompt": "Quelles sources d'energie ?",
            "options": [
                {"id": "solar", "label": "Solaire"},
                {"id": "wind", "label": "Eolien"},
                {"id": "diesel", "label": "Diesel"},
                {"id": "grid", "label": "Reseau"},
            ],
            "min_selections": 1,
            "max_selections": 3,
        },
        config=_config_for(db_session, user.id, conv.id),
    )

    payload = _extract_sse_payload(result)
    assert payload["question_type"] == "qcm"
    assert payload["max_selections"] == 3


async def test_ask_qcu_justification_valid(db_session):
    user, conv = await _make_user_and_conversation(db_session)

    result = await ask_interactive_question.ainvoke(
        {
            "question_type": "qcu_justification",
            "prompt": "As-tu une politique dechets ?",
            "options": [
                {"id": "yes", "label": "Oui"},
                {"id": "no", "label": "Non"},
            ],
            "requires_justification": True,
            "justification_prompt": "Raconte-nous !",
        },
        config=_config_for(db_session, user.id, conv.id),
    )

    payload = _extract_sse_payload(result)
    assert payload["requires_justification"] is True
    assert payload["justification_prompt"] == "Raconte-nous !"


async def test_ask_rejects_duplicate_option_ids(db_session):
    user, conv = await _make_user_and_conversation(db_session)

    result = await ask_interactive_question.ainvoke(
        {
            "question_type": "qcm",
            "prompt": "Test",
            "options": [
                {"id": "a", "label": "A"},
                {"id": "a", "label": "B"},
            ],
            "max_selections": 2,
        },
        config=_config_for(db_session, user.id, conv.id),
    )
    assert "Erreur" in result
    assert _extract_sse_payload(result) is None


async def test_ask_rejects_inconsistent_justification(db_session):
    user, conv = await _make_user_and_conversation(db_session)

    result = await ask_interactive_question.ainvoke(
        {
            "question_type": "qcu",
            "prompt": "Test",
            "options": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
            ],
            "requires_justification": True,
        },
        config=_config_for(db_session, user.id, conv.id),
    )
    assert "Erreur" in result


async def test_ask_missing_config_returns_error():
    result = await ask_interactive_question.ainvoke(
        {
            "question_type": "qcu",
            "prompt": "Test",
            "options": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
            ],
        },
        config={"configurable": {}},
    )
    assert "Erreur" in result
