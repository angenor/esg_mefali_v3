"""Tool LangChain F12 : recall_history.

Recherche sémantique dans l'historique conversationnel d'un account, via
embedding pgvector + index HNSW. Filtre RLS strict par ``account_id``
(défense en profondeur applicative + base de données).

Voir ``specs/023-memoire-contextuelle-pgvector/contracts/memory_tools.md``.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.modules.memory.service import MessageRecallResult, search_history

logger = logging.getLogger(__name__)


# Taille max de chunk_text retournée au LLM (évite de saturer le contexte
# si un chunk dépasse 6 000 caractères, par sécurité défensive).
_CHUNK_TEXT_MAX_LEN = 1500


class RecallHistoryArgs(BaseModel):
    """Paramètres validés du tool recall_history."""

    query: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="Requête textuelle libre décrivant ce que l'on cherche dans l'historique.",
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Nombre maximum de résultats à retourner (1 à 10, défaut 5).",
    )
    since: datetime | None = Field(
        default=None,
        description=(
            "Date ISO 8601 optionnelle (UTC). Limite les résultats aux chunks "
            "créés à cette date ou après."
        ),
    )
    include_current_conversation: bool = Field(
        default=False,
        description=(
            "Si False (défaut), exclut la conversation courante du résultat "
            "(les 15 derniers messages y sont déjà). Si True, inclut la conversation "
            "courante (utile pour chercher au-delà de la fenêtre des 15 derniers "
            "messages dans la même conversation)."
        ),
    )


def _format_relative_time(dt: datetime, now: datetime | None = None) -> str:
    """Formater un horodatage en français court.

    Format (clarification Q4) :
    - âge < 1 minute → « à l'instant »
    - âge < 60 minutes → « il y a N minutes »
    - âge < 24 heures → « il y a N heures »
    - âge < 48 heures → « hier »
    - âge ≤ 30 jours → « il y a N jours »
    - âge > 30 jours → « le DD/MM/YYYY »
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    delta = now - dt
    seconds = int(delta.total_seconds())

    if seconds < 60:
        return "à l'instant"
    if seconds < 3600:
        minutes = seconds // 60
        suffix = "s" if minutes > 1 else ""
        return f"il y a {minutes} minute{suffix}"
    if seconds < 86400:
        hours = seconds // 3600
        suffix = "s" if hours > 1 else ""
        return f"il y a {hours} heure{suffix}"
    if seconds < 172800:  # 48h
        return "hier"

    days = delta.days
    if days <= 30:
        return f"il y a {days} jours"
    return f"le {dt.strftime('%d/%m/%Y')}"


def _serialize_result(result: MessageRecallResult, now: datetime) -> dict:
    """Sérialiser un résultat de recall pour injection dans le contexte LLM."""
    chunk = result.chunk_text or ""
    if len(chunk) > _CHUNK_TEXT_MAX_LEN:
        chunk = chunk[: _CHUNK_TEXT_MAX_LEN - 3] + "..."

    return {
        "message_id": str(result.message_id),
        "conversation_id": str(result.conversation_id),
        "conversation_title": result.conversation_title,
        "role": result.role,
        "chunk_text": chunk,
        "created_at": result.created_at.isoformat() if result.created_at else "",
        "relative_time": _format_relative_time(result.created_at, now=now)
        if result.created_at
        else "",
        "similarity": round(result.similarity, 3),
    }


async def _recall_history_impl(
    query: str,
    max_results: int = 5,
    since: datetime | None = None,
    include_current_conversation: bool = False,
    config: RunnableConfig | None = None,
) -> list[dict]:
    """Implémentation interne testable (sans décorateur @tool).

    Cette fonction est appelée par le tool LangChain ``recall_history`` et
    aussi directement par les tests (qui contournent le wrapping LangChain).
    """
    started = time.monotonic()

    # Validation params (équivalent Pydantic)
    if not isinstance(query, str) or len(query.strip()) < 2 or len(query) > 500:
        logger.debug("recall_history : query invalide (len=%s)", len(query) if isinstance(query, str) else "NA")
        return []

    if config is None:
        logger.warning("recall_history sans contexte d'exécution — retour []")
        return []

    configurable = config.get("configurable", {}) or {}
    account_id_raw = configurable.get("account_id")
    current_conv_raw = configurable.get("conversation_id")

    if not account_id_raw:
        logger.warning("recall_history : account_id manquant — retour []")
        return []

    try:
        account_id = (
            account_id_raw
            if isinstance(account_id_raw, uuid.UUID)
            else uuid.UUID(str(account_id_raw))
        )
    except (ValueError, TypeError):
        logger.warning("recall_history : account_id invalide '%s'", account_id_raw)
        return []

    current_conversation_id: uuid.UUID | None = None
    if current_conv_raw:
        try:
            current_conversation_id = (
                current_conv_raw
                if isinstance(current_conv_raw, uuid.UUID)
                else uuid.UUID(str(current_conv_raw))
            )
        except (ValueError, TypeError):
            logger.debug(
                "recall_history : conversation_id invalide '%s' — ignoré",
                current_conv_raw,
            )

    # Hard cap server-side (défense en profondeur)
    capped_max = max(1, min(int(max_results), 10))

    results = await search_history(
        query=query,
        account_id=account_id,
        since=since,
        include_current_conversation=include_current_conversation,
        current_conversation_id=current_conversation_id,
        max_results=capped_max,
    )

    now = datetime.now(timezone.utc)
    serialized = [_serialize_result(r, now) for r in results]

    duration_ms = int((time.monotonic() - started) * 1000)
    # Log structuré (FR-028, SC-010)
    logger.info(
        "recall_history_invoked",
        extra={
            "event": "recall_history_invoked",
            "account_id": str(account_id),
            "conversation_id": str(current_conversation_id) if current_conversation_id else None,
            "user_id": str(configurable.get("user_id") or ""),
            "max_results": capped_max,
            "results_count": len(serialized),
            "duration_ms": duration_ms,
        },
    )

    return serialized


@tool
async def recall_history(
    query: str,
    max_results: int = 5,
    since: datetime | None = None,
    include_current_conversation: bool = False,
    config: RunnableConfig | None = None,  # type: ignore[assignment]
) -> list[dict]:
    """Recupere des messages anciens de l'historique conversationnel semantiquement proches.

    Use when:
    - l'utilisateur fait reference a un echange passe ("tu te souviens", "la derniere fois").
    - le contexte recent (15 derniers messages + 3 resumes) est insuffisant.
    - l'utilisateur cite un projet/fonds/montant qu'il a partage dans le passe.
    Don't use when:
    - l'information est dans les 15 derniers messages (deja dans le contexte).
    - l'information est dans le profil/projets/scores recents (utiliser `get_company_profile_chat`).
    - requete generale sans reference au passe.
    Exemple: "Tu te souviens du fonds pour mes panneaux ?" -> recall_history(query="fonds panneaux solaires", max_results=3).
    Anti: "Mon score ESG actuel ?" -> NE PAS appeler (utiliser `get_esg_assessment_chat`).

    Args:
        query: Requête textuelle libre (2..500 caractères).
        max_results: Nombre max de résultats (1..10, défaut 5).
        since: Date ISO 8601 optionnelle (limite temporelle inférieure).
        include_current_conversation: Si False (défaut), exclut la conversation
            courante. Si True, inclut la conversation courante.

    Returns:
        Liste de dictionnaires avec ``message_id``, ``conversation_id``,
        ``conversation_title``, ``role``, ``chunk_text``, ``created_at``,
        ``relative_time``, ``similarity``. Liste vide si aucun résultat
        pertinent (similarité ≤ 0.6) ou si embedding API en panne.
    """
    return await _recall_history_impl(
        query=query,
        max_results=max_results,
        since=since,
        include_current_conversation=include_current_conversation,
        config=config,
    )


# Liste des tools mémoire à injecter dans les noeuds LangGraph.
MEMORY_TOOLS: list = [recall_history]
