"""Tests F12 du hook SQLAlchemy after_insert sur Message."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.memory import hooks


def test_hook_is_registered() -> None:
    """Le listener after_insert doit être enregistré sur Message."""
    assert hooks.is_hook_registered() is True


@pytest.mark.asyncio
async def test_hook_dispatches_task_when_loop_active(monkeypatch, db_session) -> None:
    """Avec un event loop actif, le hook dispatche asyncio.create_task."""
    from tests.conftest import make_account, make_pme_user
    from app.models.conversation import Conversation
    from app.models.message import Message

    account = await make_account(db_session, name="HookTest")
    user = await make_pme_user(db_session, account=account)
    conv = Conversation(
        user_id=user.id, account_id=account.id, title="hook conv",
    )
    db_session.add(conv)
    await db_session.flush()

    captured = {"called": 0, "args": None}

    fake_embed = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.modules.memory.service.embed_message",
        fake_embed,
    )
    # Le hook importe embed_message depuis service au moment du listen ;
    # on patch aussi l'import direct dans hooks.py.
    monkeypatch.setattr("app.modules.memory.hooks.embed_message", fake_embed)

    msg = Message(
        conversation_id=conv.id,
        account_id=account.id,
        role="user",
        content="Test message du hook",
    )
    db_session.add(msg)
    await db_session.flush()
    await db_session.commit()

    # Attendre un tick pour que la tâche async soit planifiée
    await asyncio.sleep(0.05)

    # Le hook doit avoir appelé fake_embed (dispatch via create_task)
    assert fake_embed.call_count >= 1
    last_call = fake_embed.call_args
    # Les args doivent contenir l'id du message
    if last_call.kwargs:
        assert last_call.kwargs.get("message_id") == msg.id
        assert last_call.kwargs.get("account_id") == account.id


@pytest.mark.asyncio
async def test_hook_skips_when_no_account_id(monkeypatch, db_session) -> None:
    """Si account_id est NULL, pas de dispatch (legacy data)."""
    from tests.conftest import make_account, make_pme_user
    from app.models.conversation import Conversation
    from app.models.message import Message

    account = await make_account(db_session, name="NullAcc")
    user = await make_pme_user(db_session, account=account)
    conv = Conversation(
        user_id=user.id, account_id=account.id, title="conv",
    )
    db_session.add(conv)
    await db_session.flush()

    fake_embed = AsyncMock(return_value=None)
    monkeypatch.setattr("app.modules.memory.hooks.embed_message", fake_embed)

    # Crée un message sans account_id (cas legacy avant F02 backfill)
    msg = Message(
        conversation_id=conv.id,
        account_id=None,
        role="user",
        content="Sans account_id",
    )
    db_session.add(msg)
    await db_session.flush()
    await db_session.commit()

    await asyncio.sleep(0.05)
    # Le hook NE doit PAS appeler embed_message pour ce message
    # (filtrer parmi les éventuels appels de tests précédents : on regarde
    # les call_args).
    if fake_embed.call_args is not None:
        assert fake_embed.call_args.kwargs.get("message_id") != msg.id


def test_hook_no_op_without_event_loop(monkeypatch) -> None:
    """Sans event loop, le hook fait un no-op silencieux (pas d'erreur)."""
    fake_embed = AsyncMock(return_value=None)
    monkeypatch.setattr("app.modules.memory.hooks.embed_message", fake_embed)

    target_message = type(
        "FakeMessage",
        (),
        {
            "id": uuid.uuid4(),
            "account_id": uuid.uuid4(),
            "conversation_id": uuid.uuid4(),
            "role": "user",
            "content": "test",
        },
    )()

    # Appel direct du hook hors d'un event loop async
    # Hors `asyncio.run`, get_running_loop() lève RuntimeError → no-op
    hooks._on_message_after_insert(None, None, target_message)
    # Pas d'exception levée = OK
    assert fake_embed.call_count == 0
