"""F03 — Audit log append-only.

Revision ID: 021_audit_log
Revises: 020_sources
Create Date: 2026-05-06

Cette migration introduit :
- Deux ENUMs PostgreSQL : ``audit_action`` et ``audit_source``.
- Une table ``audit_log`` strictement append-only avec FK NOT NULL vers
  ``users`` et ``accounts``, et 4 index ciblés.
- Deux fonctions PL/pgSQL ``raise_audit_log_no_update`` /
  ``raise_audit_log_no_delete`` et 2 triggers ``BEFORE UPDATE/DELETE`` qui
  ``RAISE EXCEPTION`` (défense en profondeur trigger).
- Un bloc DO best-effort qui ``REVOKE UPDATE, DELETE`` sur ``audit_log``
  pour le rôle applicatif (no-op si superuser/owner — un NOTICE est émis).
- ``ENABLE`` + ``FORCE`` Row-Level Security avec 4 policies cohérentes
  avec F02 : ``pme_access_own_account`` (SELECT), ``pme_insert_own_account``
  (INSERT), ``admin_full_access`` (SELECT), ``admin_insert_anywhere`` (INSERT).
  Aucune policy UPDATE/DELETE n'est créée (cohérent avec triggers/REVOKE).

Downgrade : drop policies, RLS, triggers, fonctions, indexes, table, ENUMs
en ordre inverse.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "021_audit_log"
down_revision: Union[str, None] = "020_sources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # --- 1. ENUMs PostgreSQL (idempotents) ---
    if is_postgres:
        op.execute(
            "DO $$ BEGIN CREATE TYPE audit_action AS ENUM "
            "('create','update','delete','view_admin'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
        )
        op.execute(
            "DO $$ BEGIN CREATE TYPE audit_source AS ENUM "
            "('manual','llm','import','admin'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
        )

    # --- 2. Table audit_log ---
    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column(
            "entity_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "action",
            postgresql.ENUM(
                name="audit_action", create_type=False
            ) if is_postgres else sa.String(length=32),
            nullable=False,
        ),
        sa.Column("field", sa.String(length=128), nullable=True),
        sa.Column(
            "old_value",
            postgresql.JSONB() if is_postgres else sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "new_value",
            postgresql.JSONB() if is_postgres else sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "source_of_change",
            postgresql.ENUM(
                name="audit_source", create_type=False
            ) if is_postgres else sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "actor_metadata",
            postgresql.JSONB() if is_postgres else sa.JSON(),
            nullable=True,
        ),
    )

    # --- 3. Index ciblés (FR-004) ---
    if is_postgres:
        op.execute(
            "CREATE INDEX idx_audit_log_account_timestamp "
            "ON audit_log (account_id, timestamp DESC)"
        )
        op.execute(
            "CREATE INDEX idx_audit_log_user_timestamp "
            "ON audit_log (user_id, timestamp DESC)"
        )
        op.execute(
            "CREATE INDEX idx_audit_log_source_timestamp "
            "ON audit_log (source_of_change, timestamp DESC)"
        )
    else:  # SQLite (tests) : pas de DESC support reliable, indexes simples.
        op.create_index(
            "idx_audit_log_account_timestamp",
            "audit_log",
            ["account_id", "timestamp"],
        )
        op.create_index(
            "idx_audit_log_user_timestamp",
            "audit_log",
            ["user_id", "timestamp"],
        )
        op.create_index(
            "idx_audit_log_source_timestamp",
            "audit_log",
            ["source_of_change", "timestamp"],
        )
    op.create_index(
        "idx_audit_log_account_entity",
        "audit_log",
        ["account_id", "entity_type", "entity_id"],
    )

    # --- 4. Triggers append-only (PG uniquement) ---
    if is_postgres:
        op.execute(
            """
            CREATE OR REPLACE FUNCTION raise_audit_log_no_update()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'audit_log is append-only ; UPDATE is forbidden';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE OR REPLACE FUNCTION raise_audit_log_no_delete()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'audit_log is append-only ; DELETE is forbidden';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER audit_log_no_update
                BEFORE UPDATE ON audit_log
                FOR EACH ROW EXECUTE FUNCTION raise_audit_log_no_update();
            """
        )
        op.execute(
            """
            CREATE TRIGGER audit_log_no_delete
                BEFORE DELETE ON audit_log
                FOR EACH ROW EXECUTE FUNCTION raise_audit_log_no_delete();
            """
        )

    # --- 5. Permissions DB (best-effort, no-op si superuser) ---
    if is_postgres:
        op.execute(
            """
            DO $$
            BEGIN
                BEGIN
                    REVOKE UPDATE, DELETE ON audit_log FROM CURRENT_USER;
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE
                        'REVOKE UPDATE, DELETE failed (rôle superuser/owner) : %. Trigger remains effective.',
                        SQLERRM;
                END;
            END $$;
            """
        )

    # --- 6. RLS héritée de F02 ---
    if is_postgres:
        op.execute("ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE audit_log FORCE ROW LEVEL SECURITY")
        op.execute(
            """
            CREATE POLICY pme_access_own_account ON audit_log
            FOR SELECT
            USING (
                account_id IS NOT NULL
                AND current_setting('app.current_account_id', true) <> ''
                AND account_id = current_setting('app.current_account_id', true)::uuid
            )
            """
        )
        op.execute(
            """
            CREATE POLICY pme_insert_own_account ON audit_log
            FOR INSERT
            WITH CHECK (
                account_id IS NOT NULL
                AND current_setting('app.current_account_id', true) <> ''
                AND account_id = current_setting('app.current_account_id', true)::uuid
            )
            """
        )
        op.execute(
            """
            CREATE POLICY admin_full_access ON audit_log
            FOR SELECT
            USING (current_setting('app.current_role', true) = 'ADMIN')
            """
        )
        op.execute(
            """
            CREATE POLICY admin_insert_anywhere ON audit_log
            FOR INSERT
            WITH CHECK (current_setting('app.current_role', true) = 'ADMIN')
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        # Drop policies + RLS
        op.execute("DROP POLICY IF EXISTS admin_insert_anywhere ON audit_log")
        op.execute("DROP POLICY IF EXISTS admin_full_access ON audit_log")
        op.execute("DROP POLICY IF EXISTS pme_insert_own_account ON audit_log")
        op.execute("DROP POLICY IF EXISTS pme_access_own_account ON audit_log")
        op.execute("ALTER TABLE audit_log NO FORCE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE audit_log DISABLE ROW LEVEL SECURITY")

        # Drop triggers + fonctions
        op.execute("DROP TRIGGER IF EXISTS audit_log_no_delete ON audit_log")
        op.execute("DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log")
        op.execute("DROP FUNCTION IF EXISTS raise_audit_log_no_delete()")
        op.execute("DROP FUNCTION IF EXISTS raise_audit_log_no_update()")

    # Drop indexes (en ordre inverse)
    op.drop_index("idx_audit_log_account_entity", table_name="audit_log")
    op.drop_index("idx_audit_log_source_timestamp", table_name="audit_log")
    op.drop_index("idx_audit_log_user_timestamp", table_name="audit_log")
    op.drop_index("idx_audit_log_account_timestamp", table_name="audit_log")

    # Drop table
    op.drop_table("audit_log")

    # Drop ENUMs
    if is_postgres:
        op.execute("DROP TYPE IF EXISTS audit_source")
        op.execute("DROP TYPE IF EXISTS audit_action")
