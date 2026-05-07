"""Tests F12 d'observabilité (FR-028, FR-029, SC-007, SC-010).

Vérifie que les logs structurés ``recall_history_invoked`` et
``message_embedded`` sont émis avec les champs attendus.
"""

from __future__ import annotations

import logging
import uuid
from unittest.mock import AsyncMock

import pytest

from app.graph.tools.memory_tools import _recall_history_impl


@pytest.mark.asyncio
async def test_recall_history_emits_observability_log(monkeypatch, caplog) -> None:
    """Chaque invocation de recall_history doit émettre un log structuré INFO."""
    fake_search = AsyncMock(return_value=[])
    monkeypatch.setattr("app.graph.tools.memory_tools.search_history", fake_search)

    config = {
        "configurable": {
            "account_id": uuid.uuid4(),
            "conversation_id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
        }
    }
    with caplog.at_level(logging.INFO, logger="app.graph.tools.memory_tools"):
        await _recall_history_impl(query="test obs", config=config)

    invoked_records = [
        r
        for r in caplog.records
        if getattr(r, "event", None) == "recall_history_invoked"
        or "recall_history_invoked" in r.message
    ]
    assert invoked_records, "Aucun log structuré recall_history_invoked"
    record = invoked_records[0]
    # Les champs structurés doivent être présents (via extra=...)
    assert hasattr(record, "account_id")
    assert hasattr(record, "max_results")
    assert hasattr(record, "results_count")
    assert hasattr(record, "duration_ms")


@pytest.mark.asyncio
async def test_embed_message_emits_message_embedded_log(monkeypatch, caplog, db_session) -> None:
    """embed_message doit émettre un log message_embedded avec les bons champs."""
    from tests.conftest import make_account, make_pme_user
    from types import SimpleNamespace

    from app.models.conversation import Conversation
    from app.models.message import Message
    from app.modules.memory.service import embed_message

    account = await make_account(db_session, name="Obs")
    user = await make_pme_user(db_session, account=account)
    conv = Conversation(user_id=user.id, account_id=account.id, title="obs conv")
    db_session.add(conv)
    await db_session.flush()
    msg = Message(
        conversation_id=conv.id,
        account_id=account.id,
        role="user",
        content="texte d'observation",
    )
    db_session.add(msg)
    await db_session.flush()
    await db_session.commit()

    fake_embed = AsyncMock(return_value=[[0.5] * 1536])
    monkeypatch.setattr(
        "app.modules.memory.service._embeddings_model",
        lambda: SimpleNamespace(aembed_documents=fake_embed),
    )

    with caplog.at_level(logging.INFO, logger="app.modules.memory.service"):
        await embed_message(
            message_id=msg.id,
            account_id=account.id,
            conversation_id=conv.id,
            role="user",
            content=msg.content,
            session=db_session,
        )

    embedded = [
        r
        for r in caplog.records
        if getattr(r, "event", None) == "message_embedded"
        or "message_embedded" in r.message
    ]
    assert embedded, "Aucun log structuré message_embedded"
    record = embedded[0]
    assert hasattr(record, "message_id")
    assert hasattr(record, "embedding_status")
    assert hasattr(record, "chunk_count")
    assert hasattr(record, "duration_ms")
