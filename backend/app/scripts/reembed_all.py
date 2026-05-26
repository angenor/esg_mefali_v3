"""F25 — Script CLI admin : ré-embedding batch des chunks ``embedding IS NULL``.

Usage::

    python -m app.scripts.reembed_all [OPTIONS]

Options:
    --table {messages,documents,financing,all}   Table cible (defaut: all)
    --limit N                                    Limite par table (defaut: aucune)
    --batch-size B                               Taille batch SDK (defaut: 72)
    --dry-run                                    Simule sans ecrire en BDD

Comportement :
- Pour chaque table cible, ``SELECT id, <text_column> WHERE embedding IS NULL``
  ORDER BY ``created_at`` LIMIT N.
- Mapping ``<text_column>`` :
    * ``message_chunks``   → ``chunk_text``
    * ``document_chunks``  → ``content``
    * ``financing_chunks`` → ``content``
- Batche les contenus (par ``batch_size``), appelle ``aembed_documents(batch)``,
  persiste via ``UPDATE ... SET embedding = :v WHERE id = :id``.
- Si ``get_embeddings_client()`` retourne ``None`` → exit 1 + message clair.
- Logs : compteur par table + total + estimation cout Voyage.
- ``--dry-run`` : tout sauf le ``UPDATE`` final + log ``[DRY-RUN]`` prefixe.

Codes de sortie :
    0 — Tout traite (meme partiellement avec quelques echecs Voyage).
    1 — Erreur fatale : cle Voyage absente, BDD indisponible, table inconnue.
    2 — Argument invalide (gere par argparse).

⚠️  PRIVILEGE & RLS — A LIRE AVANT D'EXECUTER
─────────────────────────────────────────────
Ce script ouvre une session SQLAlchemy via ``async_session_factory()`` SANS
appeler ``set_rls_context()``. Les policies PostgreSQL Row-Level Security
F02 (``pme_access_own_account`` filtrant par ``account_id``) sont DONC
INACTIVES dans cette session : le script lit et met a jour les chunks de
TOUS les tenants (toutes accounts confondues).

C'est intentionnel — un backfill batch admin doit traiter l'ensemble du
corpus, pas seulement le tenant courant. Mais cela cree un privilege
elev eet un risque cross-tenant si le script est execute dans un contexte
inattendu :

- A executer UNIQUEMENT par un operateur admin authentifie sur l'host de
  prod / staging avec acces direct a la base.
- Ne JAMAIS exposer ce script via une interface web/API.
- Ne JAMAIS lancer en presence d'une connexion BDD compromise.
- Logguer l'execution (qui / quand / quoi) cote ops si possible.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


# Mapping table → colonne texte source pour le ré-embedding.
TABLE_CONFIG: dict[str, dict[str, str]] = {
    "messages": {
        "table_name": "message_chunks",
        "text_column": "chunk_text",
    },
    "documents": {
        "table_name": "document_chunks",
        "text_column": "content",
    },
    "financing": {
        "table_name": "financing_chunks",
        "text_column": "content",
    },
}


def _build_parser() -> argparse.ArgumentParser:
    """Construire le parser CLI."""
    parser = argparse.ArgumentParser(
        prog="reembed_all",
        description=(
            "Re-embedding batch des chunks `embedding IS NULL` "
            "(F25 Voyage AI, voyage-3.5, 1024 dims)."
        ),
    )
    parser.add_argument(
        "--table",
        choices=("messages", "documents", "financing", "all"),
        default="all",
        help="Table cible (defaut: all = les 3 tables).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite le nombre de lignes traitees par table (defaut: aucune).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=72,
        help="Taille du batch envoye au SDK Voyage (defaut: 72).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simule sans ecrire en BDD (aperçu seulement).",
    )
    return parser


# Whitelist des couples (table, colonne) autorises — defense en profondeur
# contre une SQL injection via interpolation d'identifiants.
_ALLOWED_TABLES_COLUMNS: dict[str, set[str]] = {
    "message_chunks": {"chunk_text"},
    "document_chunks": {"content"},
    "financing_chunks": {"content"},
}


def _validate_identifiers(table_name: str, text_column: str) -> None:
    """Garde-fou contre l'injection : seuls les identifiants whitelistes passent."""
    if table_name not in _ALLOWED_TABLES_COLUMNS:
        raise ValueError(
            f"Table non autorisee : {table_name!r}. "
            f"Tables permises : {sorted(_ALLOWED_TABLES_COLUMNS)}"
        )
    if text_column not in _ALLOWED_TABLES_COLUMNS[table_name]:
        raise ValueError(
            f"Colonne non autorisee : {table_name!r}.{text_column!r}. "
            f"Colonnes permises : {sorted(_ALLOWED_TABLES_COLUMNS[table_name])}"
        )


async def _select_pending(
    session: AsyncSession,
    table_name: str,
    text_column: str,
    limit: int | None = None,
) -> list[tuple[Any, str]]:
    """Recupere les lignes (id, texte) avec ``embedding IS NULL``.

    Returns:
        Liste de tuples ``(id, texte)`` triee par ``created_at``.

    Raises:
        ValueError: Si ``table_name`` ou ``text_column`` n'est pas dans la
            whitelist (defense en profondeur contre l'injection SQL).
    """
    _validate_identifiers(table_name, text_column)
    # Identifiants valides (whitelist) — l'interpolation est sure.
    sql = (
        f"SELECT id, {text_column} FROM {table_name} "
        f"WHERE embedding IS NULL "
        f"ORDER BY created_at"
    )
    if limit is not None:
        sql += " LIMIT :limit"
        result = await session.execute(text(sql), {"limit": int(limit)})
    else:
        result = await session.execute(text(sql))
    return [(row[0], row[1]) for row in result.fetchall()]


async def _persist_batch(
    session: AsyncSession,
    table_name: str,
    rows: list[tuple[Any, list[float]]],
) -> int:
    """Persister un batch de paires (id, vecteur) via UPDATE executemany.

    Returns:
        Le nombre de lignes mises a jour.

    Raises:
        ValueError: Si ``table_name`` n'est pas dans la whitelist.
    """
    if table_name not in _ALLOWED_TABLES_COLUMNS:
        raise ValueError(
            f"Table non autorisee : {table_name!r}. "
            f"Tables permises : {sorted(_ALLOWED_TABLES_COLUMNS)}"
        )
    if not rows:
        return 0

    payload = [
        {"v": str(vector), "id": str(row_id)} for row_id, vector in rows
    ]
    # `executemany` en un seul aller-retour, transaction atomique.
    await session.execute(
        text(f"UPDATE {table_name} SET embedding = :v WHERE id = :id"),
        payload,
    )
    await session.commit()
    return len(payload)


async def _process_table(
    session: AsyncSession,
    client: Any,
    table_key: str,
    batch_size: int,
    limit: int | None,
    dry_run: bool,
) -> tuple[int, int]:
    """Traiter une table : selection, embedding par batch, persistance.

    Returns:
        ``(succes, candidats)`` : nombre de lignes ré-embeddées vs scannées.
    """
    cfg = TABLE_CONFIG[table_key]
    table_name = cfg["table_name"]
    text_column = cfg["text_column"]

    candidates = await _select_pending(
        session, table_name=table_name, text_column=text_column, limit=limit
    )
    n_candidates = len(candidates)

    if n_candidates == 0:
        logger.info(
            "[%s] Aucun candidat (embedding IS NULL).", table_name
        )
        return 0, 0

    prefix = "[DRY-RUN] " if dry_run else ""
    logger.info(
        "%s[%s] %d candidat(s) a re-embedder.",
        prefix,
        table_name,
        n_candidates,
    )

    succeeded = 0
    for start in range(0, n_candidates, batch_size):
        batch = candidates[start : start + batch_size]
        ids = [row[0] for row in batch]
        texts_batch = [row[1] for row in batch]

        try:
            vectors = await client.aembed_documents(texts_batch)
        except Exception as exc:  # noqa: BLE001 — best-effort par batch
            logger.warning(
                "%s[%s] Batch %d-%d : echec API Voyage (%s) — saute.",
                prefix,
                table_name,
                start,
                start + len(batch),
                exc,
            )
            continue

        if dry_run:
            logger.info(
                "%s[%s] Batch %d-%d : %d vecteurs generes (non persistes).",
                prefix,
                table_name,
                start,
                start + len(batch),
                len(vectors),
            )
            succeeded += len(vectors)
        else:
            pairs = list(zip(ids, vectors))
            updated = await _persist_batch(
                session, table_name=table_name, rows=pairs
            )
            succeeded += updated
            logger.info(
                "[%s] Batch %d-%d : %d lignes mises a jour.",
                table_name,
                start,
                start + len(batch),
                updated,
            )

    return succeeded, n_candidates


async def main(
    table: str = "all",
    limit: int | None = None,
    batch_size: int = 72,
    dry_run: bool = False,
) -> int:
    """Point d'entree async du script.

    Returns:
        Code de sortie (0 = succes, 1 = erreur fatale).
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from app.lib.embeddings import get_embeddings_client

    client = get_embeddings_client()
    if client is None:
        msg = (
            "Aucune cle d'embedding configuree. "
            "Definir VOYAGE_API_KEY dans .env."
        )
        print(msg, file=sys.stderr)
        return 1

    # Selection des tables a traiter.
    if table == "all":
        tables_to_process = ["messages", "documents", "financing"]
    else:
        tables_to_process = [table]

    total_succeeded = 0
    total_candidates = 0

    from app.core.database import async_session_factory

    async with async_session_factory() as session:
        for table_key in tables_to_process:
            try:
                succeeded, candidates = await _process_table(
                    session,
                    client=client,
                    table_key=table_key,
                    batch_size=batch_size,
                    limit=limit,
                    dry_run=dry_run,
                )
                total_succeeded += succeeded
                total_candidates += candidates
            except Exception:  # noqa: BLE001 — log + continue autres tables
                logger.exception(
                    "Erreur fatale sur table %s — passage a la suivante.",
                    table_key,
                )

    prefix = "[DRY-RUN] " if dry_run else ""
    # Estimation cout grossiere : voyage-3.5 ~ $0.06 / M tokens, ~ 200 tokens /
    # chunk moyen → ~$0.012 / 1000 chunks.
    estimated_cost_usd = (total_succeeded * 200 * 0.06) / 1_000_000
    logger.info(
        "%sTotal: %d succes / %d candidats. Cout estime Voyage : ~$%0.4f.",
        prefix,
        total_succeeded,
        total_candidates,
        estimated_cost_usd,
    )
    return 0


def run_cli() -> int:
    """Point d'entree CLI synchrone (parse args + asyncio.run)."""
    parser = _build_parser()
    ns = parser.parse_args()
    return asyncio.run(
        main(
            table=ns.table,
            limit=ns.limit,
            batch_size=ns.batch_size,
            dry_run=ns.dry_run,
        )
    )


if __name__ == "__main__":
    sys.exit(run_cli())
