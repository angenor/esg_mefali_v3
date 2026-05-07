"""Hooks SQLAlchemy F12 : indexation asynchrone des messages après insertion.

À chaque insertion d'une ligne ``messages``, le hook ``after_insert`` détecte
la présence d'un event loop asyncio. Si présent, il dispatch
``asyncio.create_task(embed_message(...))`` pour embedder le message en
arrière-plan (best-effort, non bloquant). La référence à la tâche est conservée
dans un set au niveau module pour éviter le garbage collection précoce.

Si aucun loop n'est actif (tests sync, scripts batch), le hook fait un no-op
silencieux — l'indexation peut être complétée plus tard via un mécanisme de
rattrapage (F19).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import event

from app.models.message import Message
from app.modules.memory.service import embed_message

logger = logging.getLogger(__name__)


# Set au niveau module pour conserver les références aux tâches asynchrones
# en cours (évite leur GC précoce → RuntimeWarning "coroutine was never awaited").
_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()


@event.listens_for(Message, "after_insert")
def _on_message_after_insert(mapper: Any, connection: Any, target: Message) -> None:
    """Hook synchrone SQLAlchemy : dispatcher l'embedding asynchrone.

    Le hook est appelé sous transaction SQLAlchemy mais n'a pas accès à la
    session ORM (uniquement à la connexion). On capture les attributs
    nécessaires immédiatement, puis on lance la coroutine via
    ``asyncio.create_task`` — qui ne s'exécute que si un event loop tourne
    déjà (cas des routes FastAPI).
    """
    try:
        message_id = target.id
        account_id = target.account_id
        conversation_id = target.conversation_id
        role = target.role
        content = target.content
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("Lecture des attributs Message a échoué : %s", exc)
        return

    if account_id is None:
        # Sans account_id, pas d'embedding (RLS impossible) — message
        # legacy ou cas limite. On n'indexe pas.
        logger.debug(
            "Message %s sans account_id — pas d'embedding F12", message_id
        )
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Aucun event loop actif (tests sync, scripts batch). No-op silencieux.
        logger.debug(
            "Hook after_insert sans event loop — embedding différé pour %s",
            message_id,
        )
        return

    coro = embed_message(
        message_id=message_id,
        account_id=account_id,
        conversation_id=conversation_id,
        role=role or "user",
        content=content or "",
    )
    task = loop.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


def is_hook_registered() -> bool:
    """Vérifier que le hook est bien enregistré (utile pour les tests)."""
    return event.contains(Message, "after_insert", _on_message_after_insert)
