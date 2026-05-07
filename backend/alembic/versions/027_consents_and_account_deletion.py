"""F05 — Consentements RGPD + suppression de compte (J+30 + purge effective).

Revision ID: 027_consents_and_account_deletion
Revises: 026_create_attestations
Create Date: 2026-05-07

Cette migration crée :

1. Deux ENUMs PostgreSQL : ``consent_type_enum`` (7 valeurs) et
   ``legal_basis_enum`` (4 valeurs).
2. La table ``consents`` (10 colonnes + 1 CHECK + 2 indexes partiels).
3. Trois colonnes ajoutées sur ``accounts`` (deletion_scheduled_at,
   deleted_at, purge_in_progress) avec 2 indexes partiels.
4. Une fonction PL/pgSQL ``audit_log_anonymize`` qui contourne le trigger
   ``audit_log_no_update`` (F03) le temps de la purge — utilisée
   exclusivement par ``app.modules.me.purge``. La fonction écarte le trigger
   en mode session local, anonymise les rows, restaure le trigger.
5. Les colonnes ``audit_log.user_id`` et ``audit_log.account_id`` deviennent
   NULLABLE pour permettre l'anonymisation (RGPD Art. 17).

Sur SQLite (tests CI), les ENUMs et la fonction PL/pgSQL sont skippés ; les
colonnes deviennent VARCHAR.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "027_consents_and_deletion"
down_revision: Union[str, None] = "026_create_attestations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CONSENT_TYPE_VALUES = (
    "profile_analysis",
    "document_analysis_ai",
    "mobile_money_analysis",
    "photos_ia_analysis",
    "public_data_analysis",
    "credit_certificate_generation",
    "product_communications",
)

LEGAL_BASIS_VALUES = (
    "consent",
    "contract",
    "legal_obligation",
    "legitimate_interest",
)


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # --- 1. ENUMs PostgreSQL (idempotents) ---
    if is_postgres:
        consent_type_values_sql = ",".join(f"'{v}'" for v in CONSENT_TYPE_VALUES)
        legal_basis_values_sql = ",".join(f"'{v}'" for v in LEGAL_BASIS_VALUES)
        op.execute(
            f"DO $$ BEGIN CREATE TYPE consent_type_enum AS ENUM "
            f"({consent_type_values_sql}); "
            f"EXCEPTION WHEN duplicate_object THEN NULL; END $$"
        )
        op.execute(
            f"DO $$ BEGIN CREATE TYPE legal_basis_enum AS ENUM "
            f"({legal_basis_values_sql}); "
            f"EXCEPTION WHEN duplicate_object THEN NULL; END $$"
        )

    # --- 2. Table consents ---
    op.create_table(
        "consents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "consent_type",
            postgresql.ENUM(name="consent_type_enum", create_type=False)
            if is_postgres
            else sa.String(length=64),
            nullable=False,
        ),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "legal_basis",
            postgresql.ENUM(name="legal_basis_enum", create_type=False)
            if is_postgres
            else sa.String(length=32),
            nullable=False,
        ),
        sa.Column("version", sa.String(length=16), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB() if is_postgres else sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb") if is_postgres else sa.text("'{}'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= granted_at",
            name="chk_consents_revoked_after_granted",
        ),
    )

    # --- 3. Indexes partiels sur consents ---
    if is_postgres:
        op.execute(
            "CREATE INDEX idx_consents_active "
            "ON consents (account_id, consent_type) "
            "WHERE revoked_at IS NULL AND granted = true"
        )
        op.execute(
            "CREATE UNIQUE INDEX uq_consents_one_active "
            "ON consents (account_id, consent_type) "
            "WHERE revoked_at IS NULL AND granted = true"
        )
    else:  # SQLite
        op.create_index(
            "idx_consents_active",
            "consents",
            ["account_id", "consent_type"],
            sqlite_where=sa.text("revoked_at IS NULL AND granted = 1"),
        )
        op.create_index(
            "uq_consents_one_active",
            "consents",
            ["account_id", "consent_type"],
            unique=True,
            sqlite_where=sa.text("revoked_at IS NULL AND granted = 1"),
        )

    # --- 4. Trigger updated_at sur consents (PG only — SQLite gère via Python) ---
    if is_postgres:
        op.execute(
            """
            CREATE OR REPLACE FUNCTION update_consents_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = now();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_consents_updated_at
                BEFORE UPDATE ON consents
                FOR EACH ROW EXECUTE FUNCTION update_consents_updated_at();
            """
        )

    # --- 5. Colonnes accounts.deletion_scheduled_at / deleted_at / purge_in_progress ---
    op.add_column(
        "accounts",
        sa.Column(
            "deletion_scheduled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "purge_in_progress",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # --- 6. Indexes partiels sur accounts ---
    if is_postgres:
        op.execute(
            "CREATE INDEX idx_accounts_deletion_scheduled "
            "ON accounts (deletion_scheduled_at) "
            "WHERE deletion_scheduled_at IS NOT NULL"
        )
        op.execute(
            "CREATE INDEX idx_accounts_deleted "
            "ON accounts (deleted_at) "
            "WHERE deleted_at IS NOT NULL"
        )
    else:
        op.create_index(
            "idx_accounts_deletion_scheduled",
            "accounts",
            ["deletion_scheduled_at"],
            sqlite_where=sa.text("deletion_scheduled_at IS NOT NULL"),
        )
        op.create_index(
            "idx_accounts_deleted",
            "accounts",
            ["deleted_at"],
            sqlite_where=sa.text("deleted_at IS NOT NULL"),
        )

    # --- 7. audit_log : user_id et account_id deviennent NULLABLE pour anonymisation ---
    # F03 a créé ces colonnes NOT NULL. F05 les rend NULL pour permettre la purge
    # RGPD (Art. 17 — droit à l'effacement) tout en conservant l'historique
    # anonymisé (entity_type, action, timestamp, payload filtré).
    op.alter_column("audit_log", "user_id", nullable=True)
    op.alter_column("audit_log", "account_id", nullable=True)

    # --- 8. Fonction PL/pgSQL pour anonymisation audit_log (PG only) ---
    # Le trigger F03 ``audit_log_no_update`` interdit tout UPDATE sur audit_log.
    # Pour l'anonymisation RGPD, on définit une fonction qui désactive
    # temporairement le trigger en session, anonymise, puis réactive.
    if is_postgres:
        op.execute(
            """
            CREATE OR REPLACE FUNCTION audit_log_anonymize(
                p_account_id UUID,
                p_pii_fields TEXT[]
            ) RETURNS INTEGER AS $$
            DECLARE
                affected_rows INTEGER;
            BEGIN
                -- Désactiver temporairement le trigger ``audit_log_no_update``
                -- pour cette session SEULEMENT (effet local à la transaction).
                ALTER TABLE audit_log DISABLE TRIGGER audit_log_no_update;

                UPDATE audit_log
                SET user_id = NULL,
                    account_id = NULL,
                    new_value = COALESCE(
                        (SELECT jsonb_object_agg(k, v)
                         FROM jsonb_each(new_value)
                         WHERE NOT (k = ANY(p_pii_fields))),
                        new_value
                    ),
                    old_value = COALESCE(
                        (SELECT jsonb_object_agg(k, v)
                         FROM jsonb_each(old_value)
                         WHERE NOT (k = ANY(p_pii_fields))),
                        old_value
                    ),
                    actor_metadata = COALESCE(
                        (SELECT jsonb_object_agg(k, v)
                         FROM jsonb_each(actor_metadata)
                         WHERE NOT (k = ANY(p_pii_fields))),
                        actor_metadata
                    )
                WHERE account_id = p_account_id;

                GET DIAGNOSTICS affected_rows = ROW_COUNT;

                ALTER TABLE audit_log ENABLE TRIGGER audit_log_no_update;
                RETURN affected_rows;
            END;
            $$ LANGUAGE plpgsql SECURITY DEFINER;
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # --- 1. Drop fonction anonymisation ---
    if is_postgres:
        op.execute("DROP FUNCTION IF EXISTS audit_log_anonymize(UUID, TEXT[])")

    # --- 2. Restore audit_log NOT NULL ---
    # NB : si des rows anonymisées existent, ce ALTER échouera. Stratégie
    # pragmatique pour l'environnement de dev/CI : on ignore les rows nulles
    # en les supprimant. En prod, ne jamais downgrade après une purge.
    if is_postgres:
        op.execute(
            "DELETE FROM audit_log WHERE user_id IS NULL OR account_id IS NULL"
        )
    op.alter_column("audit_log", "user_id", nullable=False)
    op.alter_column("audit_log", "account_id", nullable=False)

    # --- 3. Drop indexes accounts ---
    if is_postgres:
        op.execute("DROP INDEX IF EXISTS idx_accounts_deleted")
        op.execute("DROP INDEX IF EXISTS idx_accounts_deletion_scheduled")
    else:
        op.drop_index("idx_accounts_deleted", table_name="accounts")
        op.drop_index("idx_accounts_deletion_scheduled", table_name="accounts")

    # --- 4. Drop colonnes accounts ---
    op.drop_column("accounts", "purge_in_progress")
    op.drop_column("accounts", "deleted_at")
    op.drop_column("accounts", "deletion_scheduled_at")

    # --- 5. Drop trigger updated_at consents ---
    if is_postgres:
        op.execute("DROP TRIGGER IF EXISTS trg_consents_updated_at ON consents")
        op.execute("DROP FUNCTION IF EXISTS update_consents_updated_at()")

    # --- 6. Drop indexes consents ---
    if is_postgres:
        op.execute("DROP INDEX IF EXISTS uq_consents_one_active")
        op.execute("DROP INDEX IF EXISTS idx_consents_active")
    else:
        op.drop_index("uq_consents_one_active", table_name="consents")
        op.drop_index("idx_consents_active", table_name="consents")

    # --- 7. Drop table consents ---
    op.drop_table("consents")

    # --- 8. Drop ENUMs ---
    if is_postgres:
        op.execute("DROP TYPE IF EXISTS legal_basis_enum")
        op.execute("DROP TYPE IF EXISTS consent_type_enum")
