"""Helpers partagés pour tous les tools LangChain des nœuds LangGraph."""

import logging
import time
import uuid
from collections.abc import Callable
from functools import wraps
from typing import Any

from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# Pattern UUID standard (8-4-4-4-12, hex insensible a la casse).
# Centralise pour eviter la duplication entre esg_tools.py et application_tools.py
# (cf. revue story 10.1 finding M3).
UUID_PATTERN = (
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def get_db_and_user(config: RunnableConfig) -> tuple[AsyncSession, uuid.UUID]:
    """Extraire la session DB et le user_id depuis le RunnableConfig.

    Chaque tool reçoit un RunnableConfig injecté par le handler SSE.
    Les valeurs sont stockées dans config["configurable"].

    Raises:
        ValueError: Si user_id ou db manquent dans la configuration.
    """
    configurable = (config or {}).get("configurable", {})

    db = configurable.get("db")
    if db is None:
        raise ValueError("Session DB manquante dans RunnableConfig['configurable']['db']")

    user_id_raw = configurable.get("user_id")
    if user_id_raw is None:
        raise ValueError("user_id manquant dans RunnableConfig['configurable']['user_id']")

    if isinstance(user_id_raw, str):
        user_id = uuid.UUID(user_id_raw)
    else:
        user_id = user_id_raw

    return db, user_id


async def log_tool_call(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    node_name: str,
    tool_name: str,
    tool_args: dict[str, Any],
    tool_result: dict[str, Any] | None = None,
    duration_ms: int | None = None,
    status: str = "success",
    error_message: str | None = None,
    retry_count: int = 0,
    tools_offered: list[str] | None = None,
    validation_status: str | None = None,
    pydantic_errors: list[dict] | None = None,
) -> None:
    """Journaliser un appel de tool dans la table tool_call_logs.

    Appelé après chaque exécution de tool (succès, erreur, retry).
    `tools_offered` (story 10.2) journalise la liste des tools exposes
    au LLM lors du tour ayant declenche cet appel.
    `validation_status` et `pydantic_errors` (story 10.4) tracent la boucle
    de correction Pydantic ; restent NULL pour les logs runtime non-Pydantic
    (couche `with_retry`).
    """
    from app.models.tool_call_log import ToolCallLog

    log_entry = ToolCallLog(
        user_id=user_id,
        conversation_id=conversation_id,
        node_name=node_name,
        tool_name=tool_name,
        tool_args=tool_args,
        tool_result=tool_result,
        duration_ms=duration_ms,
        status=status,
        error_message=error_message,
        retry_count=retry_count,
        tools_offered=tools_offered,
        validation_status=validation_status,
        pydantic_errors=pydantic_errors,
    )
    db.add(log_entry)
    await db.flush()


def _tools_offered_from_config(config: RunnableConfig | None) -> list[str] | None:
    """Lire `tools_offered` depuis le RunnableConfig (story 10.2)."""
    if not config:
        return None
    configurable = config.get("configurable", {}) or {}
    value = configurable.get("tools_offered")
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    return None


def with_retry(
    func: Callable,
    *,
    max_retries: int = 1,
    node_name: str = "",
) -> Callable:
    """Wrapper ajoutant 1 retry automatique silencieux avant de retourner l'erreur (FR-021).

    Le retry est transparent pour le LLM : en cas d'échec du premier appel,
    un second appel est tenté. Si le retry échoue aussi, l'erreur est retournée.
    La journalisation est effectuée pour chaque tentative.
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        config: RunnableConfig | None = kwargs.get("config") or (
            args[-1] if args and isinstance(args[-1], dict) and "configurable" in args[-1] else None
        )

        for attempt in range(max_retries + 1):
            start = time.monotonic()
            try:
                result = await func(*args, **kwargs)

                # Journaliser le succès
                if config:
                    try:
                        db, user_id = get_db_and_user(config)
                        configurable = config.get("configurable", {})
                        await log_tool_call(
                            db,
                            user_id=user_id,
                            conversation_id=configurable.get("conversation_id"),
                            node_name=node_name,
                            tool_name=func.__name__,
                            tool_args=_extract_tool_args(args, kwargs),
                            tool_result={"summary": str(result)[:500]},
                            duration_ms=int((time.monotonic() - start) * 1000),
                            status="retry_success" if attempt > 0 else "success",
                            retry_count=attempt,
                            tools_offered=_tools_offered_from_config(config),
                        )
                    except Exception:
                        logger.debug("Erreur lors de la journalisation du tool call", exc_info=True)

                return result

            except Exception as e:
                duration_ms = int((time.monotonic() - start) * 1000)

                if attempt < max_retries:
                    logger.warning(
                        "Tool %s échoué (tentative %d/%d), retry...",
                        func.__name__, attempt + 1, max_retries + 1,
                    )
                    # Journaliser le retry
                    if config:
                        try:
                            db, user_id = get_db_and_user(config)
                            configurable = config.get("configurable", {})
                            await log_tool_call(
                                db,
                                user_id=user_id,
                                conversation_id=configurable.get("conversation_id"),
                                node_name=node_name,
                                tool_name=func.__name__,
                                tool_args=_extract_tool_args(args, kwargs),
                                duration_ms=duration_ms,
                                status="error",
                                error_message=str(e)[:500],
                                retry_count=attempt,
                                tools_offered=_tools_offered_from_config(config),
                            )
                        except Exception:
                            logger.debug("Erreur journalisation retry", exc_info=True)
                    continue

                # Dernier essai échoué — journaliser et retourner l'erreur
                if config:
                    try:
                        db, user_id = get_db_and_user(config)
                        configurable = config.get("configurable", {})
                        await log_tool_call(
                            db,
                            user_id=user_id,
                            conversation_id=configurable.get("conversation_id"),
                            node_name=node_name,
                            tool_name=func.__name__,
                            tool_args=_extract_tool_args(args, kwargs),
                            duration_ms=duration_ms,
                            status="error",
                            error_message=str(e)[:500],
                            retry_count=attempt,
                            tools_offered=_tools_offered_from_config(config),
                        )
                    except Exception:
                        logger.debug("Erreur journalisation erreur finale", exc_info=True)

                return f"Erreur : {e}"

    return wrapper


def _extract_tool_args(args: tuple, kwargs: dict) -> dict[str, Any]:
    """Extraire les arguments du tool pour la journalisation (sans config/db)."""
    filtered = {
        k: v for k, v in kwargs.items()
        if k not in ("config", "db", "self")
    }
    return filtered
