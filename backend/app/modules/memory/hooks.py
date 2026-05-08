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

from sqlalchemy.orm import Session

from app.models.message import Message
from app.modules.memory.service import embed_message

logger = logging.getLogger(__name__)


# Set au niveau module pour conserver les références aux tâches asynchrones
# en cours (évite leur GC précoce → RuntimeWarning "coroutine was never awaited").
_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()

# Buffer transactionnel : messages en attente d'embedding par session.
# Cle = id(session). Vide en cas de rollback, dispatch en cas de commit.
_PENDING_BY_SESSION: dict[int, list[dict[str, Any]]] = {}


def _capture_message(target: Message) -> dict[str, Any] | None:
    try:
        if target.account_id is None:
            return None
        return {
            "message_id": target.id,
            "account_id": target.account_id,
            "conversation_id": target.conversation_id,
            "role": target.role or "user",
            "content": target.content or "",
        }
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("Lecture des attributs Message a échoué : %s", exc)
        return None


@event.listens_for(Session, "after_flush")
def _on_session_after_flush(session: Session, flush_context: Any) -> None:
    """Capturer les Message inserts pour dispatch après commit.

    Au flush, on collecte les messages dans un buffer indexé par session.
    Le dispatch effectif (asyncio.create_task) a lieu dans after_commit
    pour eviter les FK violations sur message_chunks (les inserts ne sont
    visibles d'une autre session qu'apres commit).
    """
    pending = _PENDING_BY_SESSION.setdefault(id(session), [])
    for obj in session.new:
        if isinstance(obj, Message):
            payload = _capture_message(obj)
            if payload is not None:
                pending.append(payload)


@event.listens_for(Session, "after_commit")
def _on_session_after_commit(session: Session) -> None:
    """Dispatcher les embeddings une fois la transaction committée."""
    pending = _PENDING_BY_SESSION.pop(id(session), None)
    if not pending:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.debug(
            "after_commit sans event loop — %d embeddings differes", len(pending)
        )
        return

    for payload in pending:
        coro = embed_message(**payload)
        task = loop.create_task(coro)
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)


@event.listens_for(Session, "after_rollback")
def _on_session_after_rollback(session: Session) -> None:
    """Vider le buffer si la transaction est annulee."""
    _PENDING_BY_SESSION.pop(id(session), None)


def is_hook_registered() -> bool:
    """Vérifier que les hooks sont bien enregistrés (utile pour les tests)."""
    return event.contains(Session, "after_commit", _on_session_after_commit)
