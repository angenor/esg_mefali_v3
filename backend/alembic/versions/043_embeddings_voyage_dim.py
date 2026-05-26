"""F25 — Migration des embeddings de 1536d (OpenAI) vers 1024d (Voyage AI).

Revision ID: 043_embeddings_voyage_dim
Revises: 042_extension_url_patterns
Create Date: 2026-05-08

Cette migration ajuste les **3 tables vectorielles** existantes pour passer
de ``vector(1536)`` (text-embedding-3-small) a ``vector(1024)`` (voyage-3.5) :

- ``message_chunks.embedding`` : vector(1536) → vector(1024) ; recree
  l'index HNSW + l'index partiel ``pending_embedding``.
- ``document_chunks.embedding`` : vector(1536) → vector(1024) ; recree
  l'index HNSW.
- ``financing_chunks.embedding`` : ``TEXT`` → ``vector(1024)`` (corrige
  opportunement le bug schema mig. 008 ou la colonne avait ete creee en
  ``TEXT`` au lieu de ``vector``) ; cree un nouvel index HNSW
  (``ix_financing_chunks_embedding_hnsw``) qui n'existait pas en prod.

Procedure pour chaque table :
1. DROP des index HNSW existants.
2. ``UPDATE ... SET embedding = NULL`` (FR-009 : vide les valeurs avant
   ALTER pour eviter une erreur de cast et marquer toutes les lignes
   pour ré-embedding lazy).
3. ``ALTER COLUMN embedding TYPE vector(1024)`` (avec ``USING NULL`` pour
   la conversion forcée TEXT → vector côté financing_chunks).
4. CREATE des index HNSW + index partiels.

Idempotence : chaque ALTER est protégé par une lecture de
``pg_attribute.atttypmod`` (skip si déjà en dim cible).

RLS F02 et triggers audit F03 : préservés automatiquement par
``ALTER COLUMN ... TYPE`` (PostgreSQL conserve les policies sur les
modifications de type colonne). Aucune intervention nécessaire.

Round-trip up/down/up validé en < 30 s (SC-004).

Skip total sur SQLite (les colonnes restent ``TEXT`` côté tests in-memory).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence, Union

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection


# revision identifiers, used by Alembic.
revision: str = "043_embeddings_voyage_dim"
down_revision: Union[str, None] = "042_extension_url_patterns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_vector_dim(
    bind: "Connection", table: str, column: str = "embedding"
) -> int | None:
    """Retourne la dimension actuelle d'une colonne pgvector, ou None.

    ``pg_attribute.atttypmod`` pour ``vector(N)`` retourne N. Pour les
    autres types (TEXT, etc.), retourne -1 ou une valeur non-positive.
    """
    result = bind.execute(
        sa.text(
            """
            SELECT a.atttypmod
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            WHERE c.relname = :table
              AND a.attname = :col
              AND NOT a.attisdropped
            """
        ),
        {"table": table, "col": column},
    ).scalar()
    if result is None or result <= 0:
        return None
    return int(result)


def _is_text_column(
    bind: "Connection", table: str, column: str = "embedding"
) -> bool:
    """True si la colonne est de type TEXT (pas vector)."""
    result = bind.execute(
        sa.text(
            """
            SELECT format_type(a.atttypid, a.atttypmod)
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            WHERE c.relname = :table
              AND a.attname = :col
              AND NOT a.attisdropped
            """
        ),
        {"table": table, "col": column},
    ).scalar()
    return result == "text"


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if not is_postgres:
        # SQLite : les colonnes sont declarees TEXT cote modele
        # (Vector is None branch). Aucune migration de schema necessaire.
        return

    # ─────────────────────────────────────────────────────────────
    # 1. message_chunks : vector(1536) → vector(1024)
    # ─────────────────────────────────────────────────────────────
    current_dim = _get_vector_dim(bind, "message_chunks")
    if current_dim != 1024:
        op.execute("DROP INDEX IF EXISTS ix_message_chunks_embedding_hnsw")
        op.execute("DROP INDEX IF EXISTS idx_message_chunks_pending_embedding")
        op.execute("UPDATE message_chunks SET embedding = NULL")
        op.execute(
            "ALTER TABLE message_chunks "
            "ALTER COLUMN embedding TYPE vector(1024) USING NULL"
        )
        op.execute(
            """
            CREATE INDEX ix_message_chunks_embedding_hnsw
            ON message_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
            """
        )
        op.execute(
            """
            CREATE INDEX idx_message_chunks_pending_embedding
            ON message_chunks (created_at)
            WHERE embedding IS NULL
            """
        )

    # ─────────────────────────────────────────────────────────────
    # 2. document_chunks : vector(1536) → vector(1024)
    # ─────────────────────────────────────────────────────────────
    current_dim = _get_vector_dim(bind, "document_chunks")
    if current_dim != 1024:
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
        op.execute("UPDATE document_chunks SET embedding = NULL")
        op.execute(
            "ALTER TABLE document_chunks "
            "ALTER COLUMN embedding TYPE vector(1024) USING NULL"
        )
        op.execute(
            """
            CREATE INDEX ix_document_chunks_embedding_hnsw
            ON document_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
            """
        )

    # ─────────────────────────────────────────────────────────────
    # 3. financing_chunks : TEXT (bug mig. 008) → vector(1024)
    #    Aucun index HNSW preexistant — on en cree un nouveau.
    # ─────────────────────────────────────────────────────────────
    current_dim = _get_vector_dim(bind, "financing_chunks")
    if current_dim != 1024:
        op.execute("DROP INDEX IF EXISTS ix_financing_chunks_embedding_hnsw")
        op.execute("UPDATE financing_chunks SET embedding = NULL")
        op.execute(
            "ALTER TABLE financing_chunks "
            "ALTER COLUMN embedding TYPE vector(1024) USING NULL"
        )
        op.execute(
            """
            CREATE INDEX ix_financing_chunks_embedding_hnsw
            ON financing_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if not is_postgres:
        return

    # ─────────────────────────────────────────────────────────────
    # 3. financing_chunks : vector(1024) → TEXT (etat anterieur bug)
    # ─────────────────────────────────────────────────────────────
    current_dim = _get_vector_dim(bind, "financing_chunks")
    if current_dim == 1024:
        op.execute("DROP INDEX IF EXISTS ix_financing_chunks_embedding_hnsw")
        op.execute("UPDATE financing_chunks SET embedding = NULL")
        op.execute(
            "ALTER TABLE financing_chunks "
            "ALTER COLUMN embedding TYPE text USING NULL"
        )
        # Pas de recreation d'index HNSW : il n'existait pas avant 043.

    # ─────────────────────────────────────────────────────────────
    # 2. document_chunks : vector(1024) → vector(1536)
    # ─────────────────────────────────────────────────────────────
    current_dim = _get_vector_dim(bind, "document_chunks")
    if current_dim == 1024:
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
        op.execute("UPDATE document_chunks SET embedding = NULL")
        op.execute(
            "ALTER TABLE document_chunks "
            "ALTER COLUMN embedding TYPE vector(1536) USING NULL"
        )
        op.execute(
            """
            CREATE INDEX ix_document_chunks_embedding_hnsw
            ON document_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
            """
        )

    # ─────────────────────────────────────────────────────────────
    # 1. message_chunks : vector(1024) → vector(1536)
    # ─────────────────────────────────────────────────────────────
    current_dim = _get_vector_dim(bind, "message_chunks")
    if current_dim == 1024:
        op.execute("DROP INDEX IF EXISTS ix_message_chunks_embedding_hnsw")
        op.execute("DROP INDEX IF EXISTS idx_message_chunks_pending_embedding")
        op.execute("UPDATE message_chunks SET embedding = NULL")
        op.execute(
            "ALTER TABLE message_chunks "
            "ALTER COLUMN embedding TYPE vector(1536) USING NULL"
        )
        op.execute(
            """
            CREATE INDEX ix_message_chunks_embedding_hnsw
            ON message_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
            """
        )
        op.execute(
            """
            CREATE INDEX idx_message_chunks_pending_embedding
            ON message_chunks (created_at)
            WHERE embedding IS NULL
            """
        )
