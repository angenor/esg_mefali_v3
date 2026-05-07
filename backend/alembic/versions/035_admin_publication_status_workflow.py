"""F09 — Publication status workflow + 4-yeux triggers + password reset.

Revision ID: 035_admin_publication_status_workflow
Revises: 033_create_skills
Create Date: 2026-05-07

Cette migration finalise l'infrastructure F09 (back-office admin) :

1. Ajoute ``publication_status VARCHAR(20)`` sur les tables catalogue qui ne
   l'ont pas encore (``simulation_factors``).
2. Aligne la colonne ``status`` de ``skills`` sur le workflow draft/published
   (déjà compatible).
3. Crée la table ``password_reset_tokens`` (FR-016) avec lien vers ``users``.
4. Crée 2 fonctions PL/pgSQL + triggers PostgreSQL (skip SQLite) :
   - ``before_publish_check_sources_verified()`` : empêche la publication
     d'une entité catalogue dont des sources liées ne sont pas ``verified``.
   - ``before_verify_source_check_different_admin()`` : applique la règle
     4-yeux côté BDD (``verified_by`` ≠ ``captured_by`` au passage à
     ``verified``). Une CHECK constraint statique existe déjà côté Source
     (``sources_four_eyes_chk``), le trigger ajoute un message clair
     P0001 exploitable par le router admin.

Compatibilité SQLite (tests) : les triggers sont conditionnels au dialecte.
La colonne ``publication_status`` est ajoutée via ``ADD COLUMN IF NOT
EXISTS`` lorsque PostgreSQL est utilisé.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "035_admin_publication_status_workflow"
down_revision: Union[str, None] = "033_create_skills"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables catalogue qui doivent porter ``publication_status`` (10 tables).
PUBLICATION_TABLES_WITH_STATUS = (
    "funds",
    "intermediaries",
    "offers",
    "referentials",
    "indicators",
    "criteria",
    "emission_factors",
    "simulation_factors",
    "required_documents",
)


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # 1. Ajouter publication_status sur simulation_factors (manquant).
    if is_pg:
        bind.execute(
            sa.text(
                "ALTER TABLE simulation_factors "
                "ADD COLUMN IF NOT EXISTS publication_status VARCHAR(20) "
                "NOT NULL DEFAULT 'draft' "
                "CHECK (publication_status IN ('draft','published'))"
            )
        )
        bind.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_simulation_factors_publication_status "
                "ON simulation_factors (publication_status)"
            )
        )
    else:
        # SQLite : ADD COLUMN sans IF NOT EXISTS.
        with op.batch_alter_table("simulation_factors") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "publication_status",
                    sa.String(length=20),
                    nullable=False,
                    server_default="draft",
                )
            )
        op.create_index(
            "ix_simulation_factors_publication_status",
            "simulation_factors",
            ["publication_status"],
        )

    # 2. Index publication_status sur les tables qui en ont déjà la colonne.
    if is_pg:
        for tbl in PUBLICATION_TABLES_WITH_STATUS:
            bind.execute(
                sa.text(
                    f"CREATE INDEX IF NOT EXISTS ix_{tbl}_publication_status "
                    f"ON {tbl} (publication_status)"
                )
            )

    # 3. Table password_reset_tokens.
    op.create_table(
        "password_reset_tokens",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True) if is_pg else sa.String(36),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True) if is_pg else sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("token_hash", sa.String(length=128), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Index user_id : déjà créé automatiquement par index=True sur la colonne.
    if is_pg:
        bind.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_id "
                "ON password_reset_tokens (user_id)"
            )
        )
    else:
        op.create_index(
            "ix_password_reset_tokens_user_id",
            "password_reset_tokens",
            ["user_id"],
        )

    # 4. Triggers PostgreSQL only.
    if not is_pg:
        return

    # 4a. Fonction publish gating : vérifie que toutes les sources liées sont
    # verified avant le passage en published.
    bind.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION before_publish_check_sources_verified()
            RETURNS TRIGGER AS $$
            DECLARE
                pending_count INTEGER;
            BEGIN
                IF (TG_OP = 'UPDATE'
                    AND NEW.publication_status = 'published'
                    AND (OLD.publication_status IS NULL OR OLD.publication_status = 'draft')) THEN
                    -- Vérifie sources_attachments (table de liaison polymorphe).
                    -- Si la table de liaison n'existe pas, no-op (compat MVP).
                    IF EXISTS (SELECT 1 FROM information_schema.tables
                               WHERE table_name = 'source_attachments') THEN
                        SELECT COUNT(*) INTO pending_count
                        FROM source_attachments sa
                        JOIN sources s ON s.id = sa.source_id
                        WHERE sa.entity_type = TG_TABLE_NAME
                          AND sa.entity_id = NEW.id
                          AND s.verification_status != 'verified';
                        IF pending_count > 0 THEN
                            RAISE EXCEPTION
                                'Cannot publish: % source(s) not verified for entity %',
                                pending_count, NEW.id
                                USING ERRCODE = 'P0001';
                        END IF;
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )

    # 4b. Fonction 4-yeux : empêche un admin de valider sa propre source.
    bind.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION before_verify_source_check_different_admin()
            RETURNS TRIGGER AS $$
            BEGIN
                IF (TG_OP = 'UPDATE'
                    AND NEW.verification_status = 'verified'
                    AND (OLD.verification_status IS NULL
                         OR OLD.verification_status != 'verified')) THEN
                    IF NEW.verified_by IS NULL THEN
                        RAISE EXCEPTION
                            'Cannot verify source: verified_by is required'
                            USING ERRCODE = 'P0001';
                    END IF;
                    IF NEW.verified_by = NEW.captured_by THEN
                        RAISE EXCEPTION
                            'Cannot verify source: 4-eyes rule violation '
                            '(verified_by must differ from captured_by)'
                            USING ERRCODE = 'P0001';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )

    # 4c. Triggers BEFORE UPDATE sur les 9 tables avec publication_status.
    for tbl in PUBLICATION_TABLES_WITH_STATUS:
        bind.execute(
            sa.text(
                f"DROP TRIGGER IF EXISTS trg_before_publish_{tbl} ON {tbl}"
            )
        )
        bind.execute(
            sa.text(
                f"""
                CREATE TRIGGER trg_before_publish_{tbl}
                BEFORE UPDATE ON {tbl}
                FOR EACH ROW
                EXECUTE FUNCTION before_publish_check_sources_verified();
                """
            )
        )

    # 4d. Trigger BEFORE UPDATE sur sources pour 4-yeux.
    bind.execute(
        sa.text("DROP TRIGGER IF EXISTS trg_before_verify_source ON sources")
    )
    bind.execute(
        sa.text(
            """
            CREATE TRIGGER trg_before_verify_source
            BEFORE UPDATE ON sources
            FOR EACH ROW
            EXECUTE FUNCTION before_verify_source_check_different_admin();
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        # Drop triggers + functions.
        for tbl in PUBLICATION_TABLES_WITH_STATUS:
            bind.execute(
                sa.text(f"DROP TRIGGER IF EXISTS trg_before_publish_{tbl} ON {tbl}")
            )
        bind.execute(
            sa.text("DROP TRIGGER IF EXISTS trg_before_verify_source ON sources")
        )
        bind.execute(
            sa.text("DROP FUNCTION IF EXISTS before_publish_check_sources_verified()")
        )
        bind.execute(
            sa.text(
                "DROP FUNCTION IF EXISTS before_verify_source_check_different_admin()"
            )
        )

        # Drop indexes.
        for tbl in PUBLICATION_TABLES_WITH_STATUS:
            bind.execute(
                sa.text(f"DROP INDEX IF EXISTS ix_{tbl}_publication_status")
            )

    # Drop password_reset_tokens.
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")

    # Drop publication_status from simulation_factors.
    if is_pg:
        bind.execute(
            sa.text("DROP INDEX IF EXISTS ix_simulation_factors_publication_status")
        )
        bind.execute(
            sa.text("ALTER TABLE simulation_factors DROP COLUMN IF EXISTS publication_status")
        )
    else:
        op.drop_index(
            "ix_simulation_factors_publication_status",
            table_name="simulation_factors",
        )
        with op.batch_alter_table("simulation_factors") as batch_op:
            batch_op.drop_column("publication_status")
