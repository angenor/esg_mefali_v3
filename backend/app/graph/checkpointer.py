"""Configuration du checkpointer PostgreSQL pour LangGraph (F12).

``AsyncPostgresSaver`` persiste les états de conversation LangGraph dans
PostgreSQL, contrairement à ``MemorySaver`` (RAM volatile). Au premier
démarrage, il crée automatiquement les tables ``checkpoints``,
``checkpoint_writes`` et ``checkpoint_blobs``.

L'objet retourné par ``AsyncPostgresSaver.from_conn_string()`` est un
async context manager (depuis langgraph 0.2.x). Il faut donc ``__aenter__``
puis ``__aexit__`` proprement pour libérer la connexion psycopg.

Voir ``specs/023-memoire-contextuelle-pgvector/research.md`` (R1).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_checkpointer_connection_string() -> str:
    """Retourner l'URL de connexion pour le checkpointer.

    Le checkpointer utilise psycopg (pas asyncpg), donc on convertit
    ``postgresql+asyncpg://`` en ``postgresql://``.
    """
    db_url = settings.database_url
    return db_url.replace("postgresql+asyncpg://", "postgresql://")


@asynccontextmanager
async def create_checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    """Initialiser un ``AsyncPostgresSaver`` dans un async context manager.

    Usage typique (dans le lifespan FastAPI) ::

        async with create_checkpointer() as cp:
            app.state.checkpointer = cp
            yield  # serveur tourne
        # nettoyage automatique au sortir du with

    À l'entrée, ``setup()`` est appelé pour s'assurer que les tables
    LangGraph existent. Au sortir, le context manager interne
    libère la connexion psycopg.

    Yields:
        Une instance ``AsyncPostgresSaver`` opérationnelle.
    """
    conn_string = get_checkpointer_connection_string()
    saver_ctx: Any = AsyncPostgresSaver.from_conn_string(conn_string)

    if hasattr(saver_ctx, "__aenter__"):
        saver = await saver_ctx.__aenter__()
    else:  # pragma: no cover - branche legacy si l'API change
        saver = saver_ctx
        saver_ctx = None

    try:
        await saver.setup()
        logger.info("AsyncPostgresSaver setup completed.")
        yield saver
    finally:
        if saver_ctx is not None and hasattr(saver_ctx, "__aexit__"):
            try:
                await saver_ctx.__aexit__(None, None, None)
            except Exception as exc:  # pragma: no cover
                logger.warning("Erreur fermeture AsyncPostgresSaver : %s", exc)
