"""Helpers partagés pour tous les tools LangChain des nœuds LangGraph."""

import json
import logging
import time
import uuid
from collections.abc import Callable
from functools import wraps
from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _coerce_uuid(value: Any) -> uuid.UUID | None:
    """Coercer une valeur quelconque en UUID (str ou UUID), None si invalide.

    Mutualisé pour les helpers de résolution multi-tenant (account_id) et
    aligné sur le pattern F18 (cf. ``app/graph/tools/interactive_tools.py``).
    """
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


async def _resolve_account_id_for_log(
    db: AsyncSession,
    config: RunnableConfig | None,
    conversation_id: uuid.UUID | None,
) -> uuid.UUID | None:
    """Résoudre ``account_id`` pour journaliser dans ``tool_call_logs`` (F02).

    Priorité (miroir du fix F18 sur ``interactive_questions``) :

    1. ``config['configurable']['account_id']`` — propagé par
       ``stream_graph_events`` côté API (cf. ``app/api/chat.py``).
    2. ``SELECT account_id FROM conversations WHERE id = :conversation_id``
       — filet de sécurité quand le config ne le contient pas (tests, anciens
       chemins d'appel).

    Retourne ``None`` si aucune des deux sources ne fournit un UUID. L'appelant
    DOIT alors skipper l'INSERT (le log est observabilité, jamais bloquant).
    """
    configurable = (config or {}).get("configurable", {}) or {}
    account_id = _coerce_uuid(configurable.get("account_id"))
    if account_id is not None:
        return account_id

    if conversation_id is None:
        return None

    # F02 : la table ``conversations`` porte aussi ``account_id`` (mig 019).
    try:
        from app.models.conversation import Conversation

        result = await db.execute(
            select(Conversation.account_id).where(
                Conversation.id == conversation_id,
            ),
        )
        row = result.scalar_one_or_none()
        return _coerce_uuid(row) if row is not None else None
    except Exception:  # pragma: no cover — defense en profondeur
        logger.debug(
            "Echec résolution account_id depuis la conversation",
            exc_info=True,
        )
        return None


# ─── F10 — Pattern de confirmation des actions destructives (Module 1.1.3) ──
#
# Tout tool de mutation destructif (`delete_*`, `revoke_*`, `cancel_*`) DOIT
# accepter un paramètre `confirm: bool = False`. Si `confirm=False`, il appelle
# `requires_destructive_confirmation(...)` ci-dessous, qui retourne le marker
# JSON sérialisé. Le LLM voit ce retour et invoque `ask_yes_no(destructive=True)`.
# Quand l'utilisateur confirme, le LLM rappelle le tool destructif initial avec
# `confirm=True` et la mutation s'exécute, tracée dans `audit_log` (F03).
#
# Réf : ``specs/031-widgets-bottom-sheet-complets/contracts/destructive_pattern.md``.

DESTRUCTIVE_ACTIONS: frozenset[str] = frozenset({
    "delete_project",
    "delete_application",
    "delete_assessment",
    "delete_esg_assessment",
    "delete_carbon_assessment",
    "revoke_attestation",
    "cancel_application",
    "cancel_assessment",
})


def requires_destructive_confirmation(action_name: str) -> str:
    """Retourne le marker JSON destiné au LLM pour déclencher ask_yes_no.

    Le LLM, en voyant ce retour, doit invoquer immédiatement
    ``ask_yes_no(destructive=True)`` pour solliciter une confirmation
    utilisateur explicite.

    Raises:
        ValueError: Si ``action_name`` n'est pas dans ``DESTRUCTIVE_ACTIONS``
            (garde-fou contre les fausses utilisations du pattern).
    """
    if action_name not in DESTRUCTIVE_ACTIONS:
        raise ValueError(
            f"'{action_name}' n'est pas dans la liste DESTRUCTIVE_ACTIONS. "
            "Ajoutez-la à app.graph.tools.common.DESTRUCTIVE_ACTIONS si elle "
            "constitue effectivement une mutation destructive irréversible."
        )

    return json.dumps(
        {
            "requires_confirmation": True,
            "message": (
                f"Action destructive '{action_name}' nécessite une confirmation "
                "utilisateur. Invoque immédiatement "
                "ask_yes_no(destructive=True, question='...') puis re-appelle "
                "ce tool avec confirm=True si l'utilisateur confirme."
            ),
            "destructive_action": action_name,
        },
        ensure_ascii=False,
    )


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
    validation_error: list[dict] | None = None,
    account_id: uuid.UUID | None = None,
    config: RunnableConfig | None = None,
) -> None:
    """Journaliser un appel de tool dans la table tool_call_logs.

    Appelé après chaque exécution de tool (succès, erreur, retry).
    `tools_offered` (story 10.2) journalise la liste des tools exposes
    au LLM lors du tour ayant declenche cet appel.
    `validation_error` (F22) reçoit ``e.errors()`` quand l'exception capturée
    est une ``pydantic.ValidationError``. Null sinon (succès ou runtime
    exception non-Pydantic).

    F22 — Coercition defensive : ``conversation_id`` peut arriver comme str
    (RunnableConfig['configurable']['conversation_id']) ; on le convertit en
    UUID pour eviter les erreurs SQLAlchemy ``'str' has no attribute 'hex'``.
    Idem pour ``user_id`` (deja gere par get_db_and_user mais defense en
    profondeur).

    Bug fix 2026-05-09 — F02 multi-tenant : ``tool_call_logs.account_id`` est
    NOT NULL en BDD (mig 019). Si ``account_id`` n'est pas explicite, le helper
    le résout via ``config['configurable']['account_id']`` puis fallback BDD
    sur ``conversations.account_id``. Si toujours non résolvable, l'INSERT est
    SKIPPÉ avec un warning : le log est purement observabilité et ne doit
    JAMAIS faire échouer le graph (sinon cascade sur tous les tools suivants).
    """
    from app.models.tool_call_log import ToolCallLog

    if isinstance(conversation_id, str):
        try:
            conversation_id = uuid.UUID(conversation_id)
        except (ValueError, TypeError):
            conversation_id = None
    if isinstance(user_id, str):
        try:
            user_id = uuid.UUID(user_id)
        except (ValueError, TypeError):
            return  # user_id invalide, on ne peut pas journaliser

    # F02 — Résoudre account_id (kwarg → config → fallback BDD conversation).
    if account_id is None and config is not None:
        account_id = _coerce_uuid(
            (config.get("configurable", {}) or {}).get("account_id")
        )
    if account_id is None:
        account_id = await _resolve_account_id_for_log(
            db, config, conversation_id,
        )

    if account_id is None:
        # SKIP : tool_call_logs.account_id est NOT NULL en BDD (F02 mig 019).
        # Lever une exception ferait échouer la transaction et casserait
        # tous les tool calls suivants. Le log étant observabilité pure, on
        # log un warning et on retourne sans rien insérer.
        logger.warning(
            "log_tool_call: account_id non résolvable pour tool=%s "
            "(conversation_id=%s) — INSERT skippé pour préserver la transaction",
            tool_name,
            conversation_id,
        )
        return

    # F22 — UUID/datetime dans tool_args ne sont pas JSON-serialisables ;
    # les coercer en str pour eviter les erreurs de serialisation JSON SQLite.
    tool_args = _coerce_jsonable(tool_args)
    tool_result = _coerce_jsonable(tool_result) if tool_result is not None else None

    log_entry = ToolCallLog(
        user_id=user_id,
        account_id=account_id,
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
        validation_error=validation_error,
    )
    db.add(log_entry)
    await db.flush()


def _coerce_jsonable(payload: Any) -> Any:
    """Convertit récursivement les objets non-JSON (UUID, datetime) en str.

    Utilise ``json.dumps(..., default=str)`` puis ``json.loads`` pour produire
    une structure pure dict/list/str/int/float/bool/None. Robuste aux structures
    imbriquées (typique des kwargs de tools : ``{"project_id": UUID(...), ...}``).
    """
    if payload is None:
        return None
    try:
        return json.loads(json.dumps(payload, default=str, ensure_ascii=False))
    except (TypeError, ValueError):
        # Cas extreme : payload non-serialisable meme avec default=str.
        return {"_unserializable": str(payload)[:500]}


def _tools_offered_from_config(config: RunnableConfig | None) -> list[str] | None:
    """Lire `tools_offered` depuis le RunnableConfig (story 10.2)."""
    if not config:
        return None
    configurable = config.get("configurable", {}) or {}
    value = configurable.get("tools_offered")
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    return None


def _validation_error_payload(exc: Exception) -> list[dict] | None:
    """Sérialise ``ValidationError.errors()`` pour journalisation JSONB.

    Retourne ``None`` si l'exception n'est pas une ``ValidationError`` ou si
    la sérialisation échoue (cas dégénéré — on garde la robustesse du log).
    """
    if not isinstance(exc, ValidationError):
        return None
    try:
        # Pydantic v2 expose .errors() qui retourne une list[dict] sérialisable.
        # On retire la clé 'ctx' qui peut contenir des objets non-JSON-friendly.
        raw = exc.errors()
        cleaned: list[dict] = []
        for err in raw:
            entry = {k: v for k, v in err.items() if k != "ctx"}
            # ``input`` peut contenir des objets complexes ; tenter conversion str
            # si la sérialisation échoue.
            try:
                json.dumps(entry, default=str)
            except (TypeError, ValueError):
                entry = {k: str(v) for k, v in entry.items()}
            cleaned.append(entry)
        return cleaned
    except Exception:
        logger.debug("Impossible de sérialiser ValidationError.errors()", exc_info=True)
        return None


def with_retry(
    func: Callable | None = None,
    *,
    max_retries: int = 1,
    node_name: str = "",
    fallback_message: str | None = None,
) -> Callable:
    """Wrapper ajoutant 1 retry automatique silencieux avant de retourner l'erreur (FR-021).

    Le retry est transparent pour le LLM : en cas d'échec du premier appel,
    un second appel est tenté. Si le retry échoue aussi, l'erreur est retournée.
    La journalisation est effectuée pour chaque tentative.

    Double-syntaxe supportée (F22) :

    - Legacy (sans paramètre) : ``with_retry(func, node_name="...")`` ou
      ``@with_retry`` (équivalent ``@with_retry()``).
    - Paramétrée (F22) : ``@with_retry(max_retries=1, fallback_message="...")``.
      Si ``fallback_message`` est fourni et que toutes les tentatives échouent,
      le wrapper retourne un JSON sérialisé
      ``{"success": false, "fallback_message": "<message>"}``
      au lieu du legacy ``f"Erreur : {e}"``.

    F22 — Capture spécifique de ``pydantic.ValidationError`` : ``e.errors()`` est
    sérialisé et journalisé dans ``tool_call_logs.validation_error`` (JSONB).
    Pour les autres exceptions, ``validation_error`` reste null.
    """
    # Support de la double-syntaxe : si appelé sans func (avec ou sans paren),
    # on retourne un décorateur. Sinon, on enroule directement.
    if func is None:
        def _decorator(inner_func: Callable) -> Callable:
            return _build_with_retry_wrapper(
                inner_func,
                max_retries=max_retries,
                node_name=node_name,
                fallback_message=fallback_message,
            )

        return _decorator

    return _build_with_retry_wrapper(
        func,
        max_retries=max_retries,
        node_name=node_name,
        fallback_message=fallback_message,
    )


def _build_with_retry_wrapper(
    func: Callable,
    *,
    max_retries: int,
    node_name: str,
    fallback_message: str | None,
) -> Callable:
    """Construit le wrapper effectif (factorise la logique commune)."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        config: RunnableConfig | None = kwargs.get("config") or (
            args[-1] if args and isinstance(args[-1], dict) and "configurable" in args[-1] else None
        )

        last_exc: Exception | None = None
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
                            config=config,
                        )
                    except Exception:
                        logger.debug("Erreur lors de la journalisation du tool call", exc_info=True)

                return result

            except Exception as e:
                last_exc = e
                duration_ms = int((time.monotonic() - start) * 1000)
                v_error = _validation_error_payload(e)

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
                                validation_error=v_error,
                                config=config,
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
                            validation_error=v_error,
                            config=config,
                        )
                    except Exception:
                        logger.debug("Erreur journalisation erreur finale", exc_info=True)

        # Toutes les tentatives ont échoué — choisir le format de retour
        if fallback_message is not None:
            return json.dumps(
                {"success": False, "fallback_message": fallback_message},
                ensure_ascii=False,
            )
        return f"Erreur : {last_exc}"

    return wrapper


def _extract_tool_args(args: tuple, kwargs: dict) -> dict[str, Any]:
    """Extraire les arguments du tool pour la journalisation (sans config/db)."""
    filtered = {
        k: v for k, v in kwargs.items()
        if k not in ("config", "db", "self")
    }
    return filtered
