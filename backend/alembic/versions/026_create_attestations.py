"""F08 — Création de la table ``attestations`` (Attestation Vérifiable Ed25519).

Revision ID: 026_create_attestations
Revises: 025_create_projects
Create Date: 2026-05-07

Cette migration crée :

1. La table ``attestations`` (21 colonnes, 6 contraintes CHECK, 5 indexes).
2. Les contraintes CHECK avec regex (uniquement PostgreSQL, opérateur ``~``).
3. RLS PostgreSQL héritée F02 : ENABLE+FORCE + 2 policies
   (``pme_access_own_account``, ``admin_full_access``).
4. Sur SQLite (tests CI), les CHECK regex et les RLS sont skippés.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


logger = logging.getLogger(__name__)


# revision identifiers, used by Alembic.
revision: str = "026_create_attestations"
down_revision: Union[str, None] = "025_create_projects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # ============================================================
    # CREATE TABLE attestations
    # ============================================================
    op.create_table(
        "attestations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
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
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("attestation_type", sa.String(32), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "referential_snapshot",
            postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON(),
            nullable=False,
            server_default="[]" if is_postgres else None,
        ),
        sa.Column("pdf_path", sa.String(500), nullable=False),
        sa.Column("pdf_hash_sha256", sa.CHAR(64), nullable=False),
        sa.Column("signature_ed25519", sa.String(255), nullable=False),
        sa.Column(
            "public_key_id",
            sa.String(50),
            nullable=False,
            server_default="v1",
        ),
        sa.Column("qr_code_path", sa.String(500), nullable=False),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(500), nullable=True),
        sa.Column(
            "revoked_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("verification_url", sa.String(500), nullable=False),
        sa.Column("display_id", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # CHECK portables (compat SQLite + PostgreSQL).
        sa.CheckConstraint(
            "attestation_type IN ('credit_score', 'esg_assessment', 'combined')",
            name="attestation_type_chk",
        ),
        sa.CheckConstraint(
            "valid_until > valid_from",
            name="valid_until_after_from_chk",
        ),
        sa.CheckConstraint(
            "(revoked_at IS NULL AND revoked_reason IS NULL AND revoked_by_user_id IS NULL) "
            "OR (revoked_at IS NOT NULL AND revoked_reason IS NOT NULL AND revoked_by_user_id IS NOT NULL)",
            name="revoked_consistency_chk",
        ),
        sa.UniqueConstraint("display_id", name="uq_attestations_display_id"),
    )

    # ============================================================
    # Indexes
    # ============================================================
    op.create_index(
        "idx_attestations_account_valid_until",
        "attestations",
        ["account_id", "valid_until"],
    )
    op.create_index(
        "idx_attestations_user_id",
        "attestations",
        ["user_id"],
    )

    if is_postgres:
        # CHECK regex (PostgreSQL uniquement).
        op.execute(
            "ALTER TABLE attestations ADD CONSTRAINT pdf_hash_sha256_format_chk "
            "CHECK (pdf_hash_sha256 ~ '^[0-9a-f]{64}$')"
        )
        op.execute(
            "ALTER TABLE attestations ADD CONSTRAINT display_id_format_chk "
            "CHECK (display_id ~ '^ATT-[0-9]{4}-[0-9]{5}$')"
        )
        op.execute(
            "ALTER TABLE attestations ADD CONSTRAINT public_key_id_format_chk "
            "CHECK (public_key_id ~ '^v[0-9]+$')"
        )

        # Index partiel sur revoked_at (uniquement les attestations révoquées).
        op.create_index(
            "idx_attestations_revoked_at",
            "attestations",
            ["revoked_at"],
            postgresql_where=sa.text("revoked_at IS NOT NULL"),
        )
        # Index sur l'année de valid_from (compteur display_id).
        # ``date_trunc('year', ...)`` est IMMUTABLE pour ``timestamptz`` au timezone UTC,
        # mais pour la portabilité on préfère un index simple sur ``valid_from``,
        # le COUNT(*) avec WHERE EXTRACT n'est pas critique en perf (volumétrie ~1k/mois).
        op.create_index(
            "idx_attestations_account_valid_from",
            "attestations",
            ["account_id", "valid_from"],
        )

        # ============================================================
        # RLS PostgreSQL (héritée F02)
        # ============================================================
        op.execute("ALTER TABLE attestations ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE attestations FORCE ROW LEVEL SECURITY")
        op.execute(
            """
            CREATE POLICY pme_access_own_account ON attestations
            FOR ALL
            USING (account_id = current_setting('app.current_account_id', true)::uuid)
            """
        )
        op.execute(
            """
            CREATE POLICY admin_full_access ON attestations
            FOR ALL
            USING (current_setting('app.is_admin', true) = 'true'
                   OR current_setting('app.current_role', true) = 'ADMIN')
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP POLICY IF EXISTS admin_full_access ON attestations")
        op.execute("DROP POLICY IF EXISTS pme_access_own_account ON attestations")
        op.drop_index(
            "idx_attestations_account_valid_from", table_name="attestations",
        )
        op.drop_index(
            "idx_attestations_revoked_at",
            table_name="attestations",
            postgresql_where=sa.text("revoked_at IS NOT NULL"),
        )

    op.drop_index("idx_attestations_user_id", table_name="attestations")
    op.drop_index("idx_attestations_account_valid_until", table_name="attestations")
    op.drop_table("attestations")
