"""Service mémoire F12 : masquage, chunking, embedding, recherche, purge.

Ce module rassemble les fonctions de bas niveau utilisées par :
- Le hook SQLAlchemy ``after_insert`` (cf. ``hooks.py``) — embed asynchrone
  d'un message dès son insertion.
- Le tool LangChain ``recall_history`` (cf. ``app/graph/tools/memory_tools.py``)
  — recherche sémantique pgvector + filtre RLS.
- La purge cascade RGPD (F05) — suppression des chunks et checkpoints.

Voir ``specs/023-memoire-contextuelle-pgvector/contracts/memory_service.md``.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.rls_session import set_rls_context
from app.models.conversation import Conversation
from app.models.message_chunk import MessageChunk

logger = logging.getLogger(__name__)


# ─── Constantes & regex de masquage ──────────────────────────────────

# Marqueurs utilisés pour remplacer les motifs sensibles. Ordre d'application
# fixe (cf. research.md R3) :
#   1. tokens (Bearer, API keys, sk-, sk_live_) → [TOKEN]
#   2. emails → [EMAIL]
#   3. IBAN → [BANK]
#   4. cartes bancaires (Luhn) → [CARD]
TOKEN_MARKER = "[TOKEN]"
EMAIL_MARKER = "[EMAIL]"
BANK_MARKER = "[BANK]"
CARD_MARKER = "[CARD]"
REDACTED_PLACEHOLDER = "[redacted]"

# Tokens d'authentification courants. On capture explicitement les préfixes
# « Bearer », « api_key= », « api-key », clés OpenAI/Anthropic (sk-…).
_TOKEN_RE = re.compile(
    r"(?i)(?:Bearer\s+|api[_-]?key[=:\s]+|sk-|sk_live_)[A-Za-z0-9_\-\.]{20,}",
)
# Cas particulier : "Authorization: Bearer xxx" → on capture aussi le préfixe.
_AUTH_HEADER_RE = re.compile(
    r"(?i)Authorization\s*:\s*Bearer\s+[A-Za-z0-9_\-\.]{20,}",
)

# Email RFC 5322 simplifié (suffisant pour les cas conversationnels MVP).
_EMAIL_RE = re.compile(r"\b[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+\b")

# IBAN : 2 lettres pays + 2 chiffres clé + 11..30 caractères alphanum (FR a 27).
# Tolère les espaces internes (groupes de 4 caractères, format imprimé).
_IBAN_RE = re.compile(
    r"\b[A-Z]{2}\d{2}(?:[ \t]?[A-Z0-9]{1,4}){3,7}\b"
)

# Carte bancaire : 13 à 19 chiffres avec espaces optionnels. Validation Luhn
# obligatoire pour réduire les faux positifs (numéros de téléphone, comptes…).
_CARD_RE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")


def _is_luhn_valid(digits: str) -> bool:
    """Vérifier qu'un numéro de carte respecte l'algorithme de Luhn.

    >>> _is_luhn_valid("4111111111111111")
    True
    >>> _is_luhn_valid("1234567890123456")
    False
    """
    digits = re.sub(r"\D", "", digits)
    if not (13 <= len(digits) <= 19):
        return False

    total = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _mask_cards(text_value: str) -> str:
    """Masquer uniquement les séquences de chiffres validant Luhn."""

    def repl(match: re.Match[str]) -> str:
        digits_only = re.sub(r"\D", "", match.group(0))
        if _is_luhn_valid(digits_only):
            return CARD_MARKER
        return match.group(0)

    return _CARD_RE.sub(repl, text_value)


def mask_secrets(text_value: str) -> str:
    """Masquer les motifs sensibles d'un texte avant indexation.

    Ordre : tokens → emails → IBAN → cartes (Luhn).

    Garanties :
    - **Idempotent** : ``mask_secrets(mask_secrets(x)) == mask_secrets(x)``.
    - **Préserve la structure** : le texte autour des motifs reste intact.
    - **Pas de modification si vide** : ``mask_secrets("") == ""``.

    Args:
        text_value: Texte original (peut être vide).

    Returns:
        Texte avec motifs sensibles remplacés par des marqueurs génériques.
    """
    if not text_value:
        return text_value

    out = text_value
    # 1. Tokens (incluant l'en-tête HTTP "Authorization: Bearer …")
    out = _AUTH_HEADER_RE.sub(TOKEN_MARKER, out)
    out = _TOKEN_RE.sub(TOKEN_MARKER, out)
    # 2. Emails
    out = _EMAIL_RE.sub(EMAIL_MARKER, out)
    # 3. IBAN
    out = _IBAN_RE.sub(BANK_MARKER, out)
    # 4. Cartes (Luhn)
    out = _mask_cards(out)
    return out


# ─── Chunking ─────────────────────────────────────────────────────────


def _split_paragraph_into_chunks(
    paragraph: str, max_chars: int, overlap: int
) -> list[str]:
    """Découper un paragraphe trop long en chunks avec overlap.

    Stratégie de découpe en cascade :
    1. Frontière de phrase (``. ! ?``).
    2. Frontière de mot (espace).
    3. Découpe brutale (cas extrême : un mot > max_chars).
    """
    if len(paragraph) <= max_chars:
        return [paragraph]

    chunks: list[str] = []
    start = 0
    text_len = len(paragraph)

    while start < text_len:
        end = min(start + max_chars, text_len)

        if end < text_len:
            # Chercher une frontière de phrase puis de mot dans la zone d'overlap
            window_start = max(start + max_chars // 2, end - overlap * 2)
            window = paragraph[window_start:end]

            sentence_match = re.search(r"[.!?]\s", window[::-1])
            if sentence_match:
                # Position depuis la fin de la fenêtre
                offset_from_end = sentence_match.start()
                end = end - offset_from_end
            else:
                # Fallback : dernier espace dans la fenêtre
                space_idx = window.rfind(" ")
                if space_idx > 0:
                    end = window_start + space_idx + 1

        chunk = paragraph[start:end]
        chunks.append(chunk)

        if end >= text_len:
            break

        # Avancer avec overlap
        start = max(end - overlap, start + 1)

    return chunks


def chunk_text(
    text_value: str, max_chars: int = 6000, overlap: int = 200
) -> list[str]:
    """Découper un texte en chunks selon la stratégie F12.

    - Si ``len(text) <= max_chars`` → un seul chunk identique.
    - Sinon → découpe par paragraphes (``\\n\\n``), puis par phrases, puis par mots.
      Recouvrement de ``overlap`` caractères entre chunks consécutifs.
    - Texte vide → ``["[redacted]"]`` (invariant data-model).

    Args:
        text_value: Texte à découper.
        max_chars: Longueur cible maximale par chunk (défaut 6000).
        overlap: Chevauchement en caractères entre chunks consécutifs (défaut 200).

    Returns:
        Liste de chunks (au moins un élément).
    """
    if not text_value:
        return [REDACTED_PLACEHOLDER]

    if len(text_value) <= max_chars:
        return [text_value]

    # Découpe par paragraphes (séparateur double saut de ligne).
    paragraphs = re.split(r"\n\s*\n", text_value)
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        # Si le paragraphe lui-même dépasse max_chars : découpe en sous-chunks.
        if len(para) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            sub_chunks = _split_paragraph_into_chunks(para, max_chars, overlap)
            chunks.extend(sub_chunks)
            continue

        # Tenter d'ajouter le paragraphe au chunk courant.
        candidate = (current + "\n\n" + para) if current else para
        if len(candidate) > max_chars:
            if current:
                chunks.append(current)
            current = para
        else:
            current = candidate

    if current:
        chunks.append(current)

    if not chunks:
        return [text_value]

    # Appliquer un overlap simple : préfixer chaque chunk (sauf le premier)
    # avec les ``overlap`` derniers caractères du précédent.
    if overlap > 0 and len(chunks) > 1:
        new_chunks = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-overlap:] if len(chunks[i - 1]) >= overlap else chunks[i - 1]
            new_chunks.append(tail + chunks[i])
        chunks = new_chunks

    return chunks


# ─── Embedding ────────────────────────────────────────────────────────


def _embeddings_model() -> Any:
    """Construire le client OpenAIEmbeddings (text-embedding-3-small).

    Isolé en helper pour faciliter le mocking dans les tests
    (``monkeypatch.setattr("app.modules.memory.service._embeddings_model", ...)``).
    """
    from langchain_openai import OpenAIEmbeddings

    from app.core.config import settings

    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=settings.openai_api_key or settings.openrouter_api_key,
        timeout=10.0,
    )


async def embed_message(
    message_id: uuid.UUID,
    account_id: uuid.UUID,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    session: AsyncSession | None = None,
) -> None:
    """Pipeline d'indexation d'un message : masquage → chunking → embedding → INSERT.

    Cette coroutine est appelée via ``asyncio.create_task`` depuis le hook
    SQLAlchemy ``after_insert``. Par défaut, elle ouvre une session DB
    indépendante (la session du hook peut être committée/fermée entre
    temps). Pour les tests, ``session`` peut être passée pour réutiliser
    la session de test.

    Tolère tout échec : l'exception ne remonte JAMAIS au caller (best-effort).
    En cas d'échec de l'embedding API (timeout, rate limit, panne), les
    chunks sont insérés avec ``embedding=NULL`` pour rattrapage F19.

    Args:
        message_id: UUID du message d'origine.
        account_id: UUID du tenant propriétaire (RLS).
        conversation_id: UUID de la conversation.
        role: ``user``, ``assistant`` ou ``system``.
        content: Contenu original du message (avant masquage).
        session: Session DB optionnelle (sinon ouvre via async_session_factory).
    """
    started = time.monotonic()
    try:
        masked = mask_secrets(content or "")
        chunks = chunk_text(masked) if masked.strip() else [REDACTED_PLACEHOLDER]
        if not chunks:
            chunks = [REDACTED_PLACEHOLDER]

        # Embedding (best-effort)
        embedding_status = "success"
        embeddings: list[Any] = []
        try:
            model = _embeddings_model()
            embeddings = await model.aembed_documents(chunks)
            if not isinstance(embeddings, list) or len(embeddings) != len(chunks):
                logger.warning(
                    "Embedding service a retourné un format invalide (chunks=%d, embeds=%s)",
                    len(chunks),
                    type(embeddings).__name__,
                )
                embeddings = [None] * len(chunks)
                embedding_status = "failed"
        except Exception as exc:  # noqa: BLE001 — best-effort, log & fallback
            logger.warning(
                "Embedding API a échoué pour message %s : %s — chunks insérés sans embedding",
                message_id,
                exc,
            )
            embeddings = [None] * len(chunks)
            embedding_status = "failed"

        # Insertion (avec RLS) — réutilise session de test ou en ouvre une.
        if session is not None:
            sess = session
            own_session = False
        else:
            sess = async_session_factory()
            await sess.__aenter__()  # type: ignore[attr-defined]
            own_session = True

        try:
            try:
                await set_rls_context(sess, account_id, role="PME", user_id=None)
            except Exception:  # pragma: no cover - SQLite tests no RLS
                pass

            for idx, (chunk, emb) in enumerate(zip(chunks, embeddings, strict=False)):
                row = MessageChunk(
                    account_id=account_id,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    chunk_index=idx,
                    role=role,
                    chunk_text=chunk if chunk else REDACTED_PLACEHOLDER,
                    embedding=emb,
                )
                sess.add(row)
            if own_session:
                await sess.commit()
            else:
                await sess.flush()
        finally:
            if own_session:
                await sess.__aexit__(None, None, None)  # type: ignore[attr-defined]

        duration_ms = int((time.monotonic() - started) * 1000)
        # Log structuré (FR-029, SC-007)
        logger.info(
            "message_embedded",
            extra={
                "event": "message_embedded",
                "message_id": str(message_id),
                "account_id": str(account_id),
                "conversation_id": str(conversation_id),
                "role": role,
                "chunk_count": len(chunks),
                "embedding_status": embedding_status,
                "duration_ms": duration_ms,
            },
        )
    except Exception as exc:  # noqa: BLE001 — best-effort, ne JAMAIS remonter
        logger.exception(
            "embed_message a échoué pour message %s : %s — message non indexé",
            message_id,
            exc,
        )


# ─── Recherche sémantique ────────────────────────────────────────────


@dataclass(frozen=True)
class MessageRecallResult:
    """Résultat d'une recherche sémantique dans l'historique."""

    message_id: uuid.UUID
    conversation_id: uuid.UUID
    conversation_title: str
    role: str
    chunk_text: str
    created_at: datetime
    similarity: float


async def search_history(
    query: str,
    account_id: uuid.UUID,
    *,
    since: datetime | None = None,
    include_current_conversation: bool = False,
    current_conversation_id: uuid.UUID | None = None,
    max_results: int = 5,
    threshold: float = 0.6,
    session: AsyncSession | None = None,
) -> list[MessageRecallResult]:
    """Rechercher dans l'historique conversationnel par similarité sémantique.

    Args:
        query: Requête textuelle libre.
        account_id: UUID du tenant courant (filtre applicatif + RLS).
        since: Date ISO 8601 optionnelle (limite inférieure).
        include_current_conversation: Si ``False`` (défaut), exclut la
            conversation courante (les 15 derniers messages y sont déjà).
        current_conversation_id: UUID de la conversation en cours (utilisé
            uniquement si ``include_current_conversation=False``).
        max_results: Nombre max de résultats (1..10).
        threshold: Seuil de similarité cosinus (défaut 0.6).
        session: Session DB optionnelle (sinon on en ouvre une nouvelle).

    Returns:
        Liste de ``MessageRecallResult`` triée par similarité décroissante,
        ou ``[]`` si embedding API en panne ou aucun résultat pertinent.
    """
    # Embedding de la query (peut échouer)
    try:
        model = _embeddings_model()
        query_embedding = await model.aembed_query(query)
    except Exception as exc:  # noqa: BLE001 — fallback silencieux
        logger.warning("Embedding query échoué : %s — recall_history retourne []", exc)
        return []

    if not query_embedding or len(query_embedding) != 1536:
        logger.warning("Query embedding invalide (len=%s)", len(query_embedding) if query_embedding else 0)
        return []

    own_session = session is None
    sess = session or async_session_factory()

    try:
        # Si on a ouvert la session nous-même, contexte RLS PME pour cohérence.
        if own_session:
            await sess.__aenter__()  # type: ignore[attr-defined]
            await set_rls_context(sess, account_id, role="PME", user_id=None)

        params: dict[str, Any] = {
            "query_embedding": str(query_embedding),
            "account_id": str(account_id),
            "threshold": threshold,
            "max_results": max_results,
        }

        sql = """
        SELECT
            mc.message_id,
            mc.conversation_id,
            COALESCE(c.title, '') AS conversation_title,
            mc.role,
            mc.chunk_text,
            mc.created_at,
            1 - (mc.embedding <=> CAST(:query_embedding AS vector)) AS similarity
        FROM message_chunks mc
        JOIN conversations c ON c.id = mc.conversation_id
        WHERE mc.account_id = CAST(:account_id AS uuid)
          AND mc.embedding IS NOT NULL
        """
        if since is not None:
            params["since"] = since
            sql += " AND mc.created_at >= :since"
        if not include_current_conversation and current_conversation_id is not None:
            params["current_conversation_id"] = str(current_conversation_id)
            sql += " AND mc.conversation_id <> CAST(:current_conversation_id AS uuid)"
        sql += """
          AND (1 - (mc.embedding <=> CAST(:query_embedding AS vector))) > :threshold
        ORDER BY mc.embedding <=> CAST(:query_embedding AS vector) ASC
        LIMIT :max_results
        """

        result = await sess.execute(text(sql), params)
        rows = result.all()

        return [
            MessageRecallResult(
                message_id=row[0] if isinstance(row[0], uuid.UUID) else uuid.UUID(str(row[0])),
                conversation_id=(
                    row[1] if isinstance(row[1], uuid.UUID) else uuid.UUID(str(row[1]))
                ),
                conversation_title=row[2] or "",
                role=row[3],
                chunk_text=row[4],
                created_at=row[5],
                similarity=float(row[6]) if row[6] is not None else 0.0,
            )
            for row in rows
        ]
    except Exception as exc:  # noqa: BLE001 — fallback silencieux
        logger.warning("search_history SQL échoué : %s", exc)
        return []
    finally:
        if own_session:
            try:
                await sess.__aexit__(None, None, None)  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover
                pass


# ─── Purge cascade RGPD ───────────────────────────────────────────────


async def purge_account_chunks(account_id: uuid.UUID) -> None:
    """Suppression cascade complète des conversations d'un account (F05/RGPD).

    1. Supprime les ``message_chunks`` du compte (filtre par account_id).
    2. Supprime les checkpoints LangGraph (3 tables : ``checkpoints``,
       ``checkpoint_writes``, ``checkpoint_blobs``) filtrés par ``thread_id``
       (= ``conversation_id::text``) appartenant à un utilisateur de cet account.

    Atomique : tout dans une seule transaction. Idempotent : appel répété
    ne fait rien la 2ᵉ fois.

    Args:
        account_id: UUID du compte à purger.
    """
    async with async_session_factory() as session:
        try:
            # Contexte ADMIN pour bypass des policies PME (purge légitime).
            await set_rls_context(
                session,
                account_id,
                role="ADMIN",
                user_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            )

            # 1. Récupérer thread_ids LangGraph (uniquement PostgreSQL — sur
            # SQLite test, les tables checkpoint_* peuvent ne pas exister).
            thread_ids: list[str] = []
            dialect = session.bind.dialect.name if session.bind is not None else ""
            try:
                result = await session.execute(
                    select(Conversation.id).where(Conversation.account_id == account_id)
                )
                thread_ids = [str(row[0]) for row in result.all()]
            except Exception as exc:  # noqa: BLE001
                logger.warning("Lecture conversations pour purge échouée : %s", exc)

            # 2. Supprimer message_chunks
            await session.execute(
                delete(MessageChunk).where(MessageChunk.account_id == account_id)
            )

            # 3. Supprimer checkpoints LangGraph (PostgreSQL uniquement)
            if dialect == "postgresql" and thread_ids:
                for table_name in ("checkpoint_blobs", "checkpoint_writes", "checkpoints"):
                    try:
                        await session.execute(
                            text(
                                f"DELETE FROM {table_name} "
                                f"WHERE thread_id = ANY(:ids)"
                            ),
                            {"ids": thread_ids},
                        )
                    except Exception as exc:  # noqa: BLE001
                        # Les tables checkpoint_* peuvent ne pas exister si le
                        # backend n'a pas encore initialisé AsyncPostgresSaver.
                        logger.debug(
                            "DELETE FROM %s ignoré (table absente ou erreur) : %s",
                            table_name,
                            exc,
                        )

            await session.commit()
            logger.info(
                "purge_account_chunks terminé pour account_id=%s (threads=%d)",
                account_id,
                len(thread_ids),
            )
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            logger.exception("purge_account_chunks a échoué : %s", exc)
            raise
