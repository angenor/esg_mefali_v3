"""F19 — Tests unitaires du bus SSE in-memory."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.services.notifications.sse_bus import SSEBus


pytestmark = pytest.mark.unit


async def test_notify_user_no_subscriber_returns_zero():
    """Si user pas connecté, notify_user retourne 0 sans erreur."""
    bus = SSEBus()
    delivered = await bus.notify_user(
        uuid.uuid4(), "reminder_due", {"id": "r1"}
    )
    assert delivered == 0


async def test_notify_user_with_subscriber_delivers():
    """Un subscriber reçoit l'évènement."""
    bus = SSEBus()
    account_id = str(uuid.uuid4())

    # Démarre le subscriber dans une task séparée.
    received: list[dict] = []

    async def consume():
        async for event in bus.subscribe(account_id):
            received.append(event)
            return  # consume just one then exit

    task = asyncio.create_task(consume())
    # Attendre que le subscriber s'inscrive.
    await asyncio.sleep(0.01)

    delivered = await bus.notify_user(
        account_id, "reminder_due", {"id": "r1", "type": "fund_deadline"}
    )
    assert delivered == 1

    await asyncio.wait_for(task, timeout=1.0)
    assert len(received) == 1
    assert received[0]["type"] == "reminder_due"
    assert received[0]["data"]["id"] == "r1"


async def test_notify_two_users_only_target_receives():
    """2 users connectés → seul le ciblé reçoit."""
    bus = SSEBus()
    a = str(uuid.uuid4())
    b = str(uuid.uuid4())
    received_a: list[dict] = []
    received_b: list[dict] = []

    async def consume(target_id, sink):
        async for event in bus.subscribe(target_id):
            sink.append(event)
            return

    task_a = asyncio.create_task(consume(a, received_a))
    task_b = asyncio.create_task(consume(b, received_b))
    await asyncio.sleep(0.01)

    await bus.notify_user(a, "reminder_due", {"id": "r-a"})

    await asyncio.wait_for(task_a, timeout=1.0)
    # b ne doit pas avoir reçu — on cancel après un petit délai.
    await asyncio.sleep(0.05)
    task_b.cancel()
    try:
        await task_b
    except asyncio.CancelledError:
        pass

    assert len(received_a) == 1
    assert received_a[0]["data"]["id"] == "r-a"
    assert received_b == []


async def test_has_subscribers():
    """has_subscribers reflète l'état des connexions."""
    bus = SSEBus()
    account_id = str(uuid.uuid4())
    assert bus.has_subscribers(account_id) is False

    received: list[dict] = []

    async def consume():
        async for event in bus.subscribe(account_id):
            received.append(event)
            return

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.01)
    assert bus.has_subscribers(account_id) is True

    await bus.notify_user(account_id, "ping", {})
    await asyncio.wait_for(task, timeout=1.0)
    # Après désabonnement
    await asyncio.sleep(0.01)
    assert bus.has_subscribers(account_id) is False


async def test_event_serializable_json():
    """Les payloads doivent être JSON-serializable (dict simple)."""
    bus = SSEBus()
    payload = {
        "id": "uuid-123",
        "type": "fund_deadline",
        "metadata": {"action_url": "/financing/abc"},
    }
    received: list[dict] = []

    async def consume():
        async for event in bus.subscribe("acct-1"):
            received.append(event)
            return

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.01)
    await bus.notify_user("acct-1", "reminder_due", payload)
    await asyncio.wait_for(task, timeout=1.0)
    import json

    json.dumps(received[0])  # ne lève pas
