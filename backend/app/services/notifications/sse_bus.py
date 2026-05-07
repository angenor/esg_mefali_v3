"""F19 — Bus SSE in-memory pour les notifications de rappels.

Pub/sub minimal par ``account_id`` : chaque utilisateur connecté reçoit ses
rappels via une ``asyncio.Queue`` dédiée. Le bus est un singleton module
(``bus``) accessible depuis le scheduler et l'endpoint SSE.

Limitation MVP : in-memory single-process. Si on scale à plusieurs replicas
FastAPI, prévoir un broker (Redis pub/sub).

Pattern :

```python
from app.services.notifications.sse_bus import bus

# Côté scheduler (publisher)
await bus.notify_user(account_id, "reminder_due", payload)

# Côté endpoint SSE (consumer)
async for event in bus.subscribe(account_id):
    yield f"event: {event['type']}\\ndata: {json.dumps(event['data'])}\\n\\n"
```
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any

logger = logging.getLogger(__name__)

# Taille maximale d'une queue avant drop (back-pressure best-effort).
_QUEUE_MAXSIZE = 100


class SSEBus:
    """Bus pub/sub in-memory pour les évènements SSE par account_id.

    Thread-safety : protégé par ``asyncio.Lock`` sur les mutations du dict
    de connexions. Les ``put_nowait`` sont par-queue donc safe sans lock.
    """

    def __init__(self) -> None:
        self._connections: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(
        self, account_id: str | uuid.UUID
    ) -> AsyncIterator[dict[str, Any]]:
        """S'abonner aux évènements SSE pour ``account_id``.

        Retourne un async generator qui yield chaque event dispatché. Quand
        le consumer s'arrête (déconnexion), la queue est nettoyée
        automatiquement.
        """
        key = str(account_id)
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)

        async with self._lock:
            self._connections.setdefault(key, []).append(queue)

        logger.info(
            "sse_bus.subscribe | account_id=%s subscribers=%d",
            key,
            len(self._connections[key]),
        )

        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            await self._unsubscribe(key, queue)

    async def _unsubscribe(
        self, key: str, queue: asyncio.Queue[dict[str, Any]]
    ) -> None:
        """Retire la queue du registre."""
        async with self._lock:
            queues = self._connections.get(key, [])
            with suppress(ValueError):
                queues.remove(queue)
            if not queues and key in self._connections:
                del self._connections[key]
        logger.info("sse_bus.unsubscribe | account_id=%s", key)

    async def notify_user(
        self,
        account_id: str | uuid.UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> int:
        """Push un évènement à tous les subscribers de ``account_id``.

        Retourne le nombre de queues notifiées (0 si user pas connecté).
        Les queues pleines (back-pressure) drop graceful avec un warning.
        """
        key = str(account_id)
        event = {"type": event_type, "data": payload}

        async with self._lock:
            queues = list(self._connections.get(key, []))

        delivered = 0
        for queue in queues:
            try:
                queue.put_nowait(event)
                delivered += 1
            except asyncio.QueueFull:
                logger.warning(
                    "sse_bus.notify_user | queue full account_id=%s event_type=%s",
                    key,
                    event_type,
                )

        if delivered == 0:
            logger.debug(
                "sse_bus.notify_user | no subscribers account_id=%s event_type=%s",
                key,
                event_type,
            )

        return delivered

    def has_subscribers(self, account_id: str | uuid.UUID) -> bool:
        """Indique si au moins un subscriber est connecté pour ``account_id``."""
        return bool(self._connections.get(str(account_id), []))


# Singleton module global.
bus = SSEBus()
