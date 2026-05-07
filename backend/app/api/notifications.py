"""F19 — Endpoint SSE pour les notifications de rappels.

``GET /api/notifications/sse`` : flux Server-Sent Events filtré par
``account_id`` de l'utilisateur authentifié. Reçoit en temps réel les
évènements ``reminder_due`` poussés par le cron dispatcher.

Format d'évènement (RFC EventSource) :

```
event: reminder_due
data: {"id": "uuid", "type": "fund_deadline", ...}

```

Heartbeat : un keepalive ``: ping`` est envoyé toutes les 30 s pour éviter
les déconnexions intermédiaires.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.models.user import User
from app.services.notifications.sse_bus import bus

logger = logging.getLogger(__name__)

router = APIRouter()

# Intervalle (s) entre 2 keepalives pour maintenir la connexion ouverte.
_KEEPALIVE_INTERVAL_S = 30.0


def _format_sse(event_type: str, data: dict[str, Any]) -> str:
    """Formate un évènement au format text/event-stream."""
    payload = json.dumps(data, default=str, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"


async def _stream_events(account_id: str) -> AsyncGenerator[bytes, None]:
    """Générateur principal : multiplexe le bus SSE et un heartbeat."""
    # Hello frame initial pour confirmer la connexion.
    yield _format_sse(
        "connected", {"account_id": account_id, "stream": "notifications"}
    ).encode("utf-8")

    # On boucle entre la queue du bus et un timeout de keepalive.
    iterator = bus.subscribe(account_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(
                    iterator.__anext__(), timeout=_KEEPALIVE_INTERVAL_S
                )
                yield _format_sse(event["type"], event["data"]).encode("utf-8")
            except asyncio.TimeoutError:
                # Heartbeat (commentaire SSE — non parsé par le client).
                yield b": keepalive\n\n"
            except StopAsyncIteration:
                break
    except asyncio.CancelledError:
        logger.info("notifications.sse | client disconnected account_id=%s", account_id)
        raise
    finally:
        # Nettoyage de l'itérateur (ferme la queue côté bus).
        await iterator.aclose()


@router.get("/sse")
async def stream_notifications(
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Endpoint SSE — flux des notifications pour l'utilisateur connecté.

    Filtré par ``current_user.account_id``. Si l'utilisateur n'a pas
    d'account, on tombe sur ``current_user.id`` (legacy single-tenant).
    """
    account_id = (
        str(current_user.account_id)
        if current_user.account_id is not None
        else str(current_user.id)
    )
    return StreamingResponse(
        _stream_events(account_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx : désactive le buffering proxy
        },
    )
