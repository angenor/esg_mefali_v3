"""F12 — Mémoire contextuelle : table message_chunks + RLS + index HNSW.

Revision ID: 023_create_message_chunks
Revises: 022_money_and_versioning
Create Date: 2026-05-07

Cette migration introduit :
- Table ``message_chunks`` (UUID PK, account_id FK accounts RESTRICT, conversation_id
  FK conversations CASCADE, message_id FK messages CASCADE, chunk_index INT,
  role VARCHAR(20), chunk_text TEXT, embedding VECTOR(1536) NULL,
  created_at TIMESTAMPTZ).
- 2 CHECK constraints (role IN, chunk_index ≥ 0).
- 3 indexes : composite ``(account_id, conversation_id, created_at DESC)``,
  partial ``(created_at) WHERE embedding IS NULL`` (rattrapage F19),
  HNSW ``(embedding vector_cosine_ops)`` avec ``m=16, ef_construction=64``.
- RLS PostgreSQL : ENABLE + FORCE + 2 policies (admin_full_access,
  pme_access_own_account) — F02-compatibles via ``current_setting('app.current_*')``.

Downgrade : DROP les 3 indexes, puis DROP TABLE message_chunks.

L'index HNSW et les policies RLS ne sont créés que sous PostgreSQL (skip SQLite
pour les tests unitaires).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = "023_create_message_chunks"
down_revision: Union[str, None] = "022_money_and_versioning"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # ── Table principale ────────────────────────────────────────────────
    op.create_table(
        "message_chunks",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chunk_index",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column(
            "embedding",
            pgvector.sqlalchemy.Vector(1536) if is_postgres else sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="message_chunks_role_chk",
        ),
        sa.CheckConstraint(
            "chunk_index >= 0",
            name="message_chunks_chunk_index_chk",
        ),
    )

    # ── Index composite (cascade par account, rattrapage F19) ────────
    op.create_index(
        "idx_message_chunks_account_conv_created",
        "message_chunks",
        ["account_id", "conversation_id", sa.text("created_at DESC")],
        unique=False,
    )

    if is_postgres:
        # ── Index partiel : chunks en attente d'embedding (rattrapage F19) ─
        op.execute(
            """
            CREATE INDEX idx_message_chunks_pending_embedding
            ON message_chunks (created_at)
            WHERE embedding IS NULL
            """
        )

        # ── Index HNSW pour la recherche cosine ─────────────────────────
        op.execute(
            """
            CREATE INDEX ix_message_chunks_embedding_hnsw
            ON message_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
            """
        )

        # ── RLS PostgreSQL ─────────────────────────────────────────────
        op.execute("ALTER TABLE message_chunks ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE message_chunks FORCE ROW LEVEL SECURITY")
        op.execute(
            """
            CREATE POLICY admin_full_access ON message_chunks
            FOR ALL
            USING (current_setting('app.current_role', true) = 'ADMIN')
            WITH CHECK (current_setting('app.current_role', true) = 'ADMIN')
            """
        )
        op.execute(
            """
            CREATE POLICY pme_access_own_account ON message_chunks
            FOR ALL
            USING (
                current_setting('app.current_role', true) = 'PME'
                AND current_setting('app.current_account_id', true) <> ''
                AND account_id = current_setting('app.current_account_id', true)::uuid
            )
            WITH CHECK (
                current_setting('app.current_role', true) = 'PME'
                AND current_setting('app.current_account_id', true) <> ''
                AND account_id = current_setting('app.current_account_id', true)::uuid
            )
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP POLICY IF EXISTS pme_access_own_account ON message_chunks")
        op.execute("DROP POLICY IF EXISTS admin_full_access ON message_chunks")
        op.execute("ALTER TABLE message_chunks NO FORCE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE message_chunks DISABLE ROW LEVEL SECURITY")
        op.execute("DROP INDEX IF EXISTS ix_message_chunks_embedding_hnsw")
        op.execute("DROP INDEX IF EXISTS idx_message_chunks_pending_embedding")

    op.drop_index(
        "idx_message_chunks_account_conv_created",
        table_name="message_chunks",
    )
    op.drop_table("message_chunks")
