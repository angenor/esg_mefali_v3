"""Tests F12 du chargeur de contexte mémoire (`_load_context_memory`)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.api.chat import _load_context_memory, format_relative_time


# ─── format_relative_time ────────────────────────────────────────────


def test_format_relative_time_just_now() -> None:
    now = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)
    assert format_relative_time(now - timedelta(seconds=30), now=now) == "à l'instant"


def test_format_relative_time_minutes() -> None:
    now = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)
    assert (
        format_relative_time(now - timedelta(minutes=5), now=now) == "il y a 5 minutes"
    )


def test_format_relative_time_hours() -> None:
    now = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)
    assert (
        format_relative_time(now - timedelta(hours=3), now=now) == "il y a 3 heures"
    )


def test_format_relative_time_yesterday() -> None:
    now = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)
    # 30 heures = entre 24h et 48h → "hier"
    assert format_relative_time(now - timedelta(hours=30), now=now) == "hier"


def test_format_relative_time_days() -> None:
    now = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)
    assert format_relative_time(now - timedelta(days=5), now=now) == "il y a 5 jours"


def test_format_relative_time_absolute_date() -> None:
    now = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)
    # 35 jours en arrière → format DD/MM/YYYY
    past = now - timedelta(days=35)
    expected_date = past.strftime("%d/%m/%Y")
    assert format_relative_time(past, now=now) == f"le {expected_date}"


# ─── _load_context_memory ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_load_context_memory_loads_15_messages(db_session) -> None:
    """Avec 17 messages en base, on charge les 15 derniers (du 3e au 17e)."""
    from tests.conftest import make_account, make_pme_user
    from app.models.conversation import Conversation
    from app.models.message import Message

    account = await make_account(db_session, name="Ctx15")
    user = await make_pme_user(db_session, account=account)
    conv = Conversation(
        user_id=user.id, account_id=account.id, title="C",
    )
    db_session.add(conv)
    await db_session.flush()

    base = datetime.now(timezone.utc) - timedelta(hours=2)
    for i in range(17):
        msg = Message(
            conversation_id=conv.id,
            account_id=account.id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"msg-{i}",
        )
        msg.created_at = base + timedelta(minutes=i)
        db_session.add(msg)
    await db_session.flush()
    await db_session.commit()

    ctx = await _load_context_memory(db_session, user.id, conversation_id=conv.id)
    # ctx contient potentiellement des résumés en tête (aucun ici), puis 15 messages.
    raw = [line for line in ctx if line.startswith("[")]
    assert len(raw) == 15
    # Vérifier que les messages 0 et 1 ne sont PAS dans le contexte (hors fenêtre)
    assert not any("msg-0" in line and "msg-10" not in line for line in raw)
    # Le dernier message en contexte doit être msg-16 (le plus récent)
    assert "msg-16" in raw[-1]


@pytest.mark.asyncio
async def test_load_context_memory_under_15_no_padding(db_session) -> None:
    """Avec 5 messages en base, on charge les 5 (pas de padding)."""
    from tests.conftest import make_account, make_pme_user
    from app.models.conversation import Conversation
    from app.models.message import Message

    account = await make_account(db_session, name="Ctx5")
    user = await make_pme_user(db_session, account=account)
    conv = Conversation(
        user_id=user.id, account_id=account.id, title="C5",
    )
    db_session.add(conv)
    await db_session.flush()

    base = datetime.now(timezone.utc) - timedelta(minutes=30)
    for i in range(5):
        msg = Message(
            conversation_id=conv.id,
            account_id=account.id,
            role="user",
            content=f"only-{i}",
        )
        msg.created_at = base + timedelta(minutes=i)
        db_session.add(msg)
    await db_session.flush()
    await db_session.commit()

    ctx = await _load_context_memory(db_session, user.id, conversation_id=conv.id)
    raw = [line for line in ctx if line.startswith("[")]
    assert len(raw) == 5


@pytest.mark.asyncio
async def test_load_context_memory_summaries_first(db_session) -> None:
    """Les résumés viennent en tête, les messages bruts en queue."""
    from tests.conftest import make_account, make_pme_user
    from app.models.conversation import Conversation
    from app.models.message import Message

    account = await make_account(db_session, name="CtxSum")
    user = await make_pme_user(db_session, account=account)

    # 2 conversations anciennes avec résumé
    for i in range(2):
        c = Conversation(
            user_id=user.id,
            account_id=account.id,
            title=f"old-{i}",
            summary=f"Résumé conversation {i}",
        )
        db_session.add(c)
    await db_session.flush()

    # 1 conversation courante avec quelques messages
    current = Conversation(
        user_id=user.id, account_id=account.id, title="current",
    )
    db_session.add(current)
    await db_session.flush()

    base = datetime.now(timezone.utc) - timedelta(minutes=10)
    for i in range(3):
        msg = Message(
            conversation_id=current.id,
            account_id=account.id,
            role="user",
            content=f"current-{i}",
        )
        msg.created_at = base + timedelta(minutes=i)
        db_session.add(msg)
    await db_session.flush()
    await db_session.commit()

    ctx = await _load_context_memory(db_session, user.id, conversation_id=current.id)
    # Les premiers éléments ne doivent PAS commencer par "[" (résumés)
    assert ctx
    # Au moins 2 résumés en tête
    summary_count = sum(1 for line in ctx if not line.startswith("["))
    assert summary_count >= 2
    # Les messages en queue doivent commencer par "["
    raw_count = sum(1 for line in ctx if line.startswith("["))
    assert raw_count == 3


@pytest.mark.asyncio
async def test_load_context_memory_no_conversation_returns_summaries_only(
    db_session,
) -> None:
    """Sans conversation_id, on récupère uniquement les résumés (legacy)."""
    from tests.conftest import make_account, make_pme_user
    from app.models.conversation import Conversation

    account = await make_account(db_session, name="CtxLegacy")
    user = await make_pme_user(db_session, account=account)
    c = Conversation(
        user_id=user.id,
        account_id=account.id,
        title="x",
        summary="Résumé seul",
    )
    db_session.add(c)
    await db_session.flush()
    await db_session.commit()

    ctx = await _load_context_memory(db_session, user.id, conversation_id=None)
    assert ctx == ["Résumé seul"]
