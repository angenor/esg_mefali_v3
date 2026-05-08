"""F18 — Alternative Credit Data (Mobile Money + Photos IA + Données publiques).

Revision ID: 037_alternative_credit_data
Revises: 036_offer_matches_and_alerts
Create Date: 2026-05-08

Cette migration crée les 6 nouvelles tables F18 et étend l'enum
``credit_category_enum`` avec 3 valeurs :

1. ``mobile_money_imports`` : trace chaque upload CSV/Excel avec compteurs.
2. ``mobile_money_transactions`` : transactions normalisées (counterparty SHA-256).
3. ``mobile_money_analyses`` : KPIs agrégés courants par PME.
4. ``credit_photos`` : photos téléversées + analyse IA structurée (JSONB).
5. ``public_data_sources`` : sources publiques déclarées par la PME.
6. ``credit_methodology_factors`` : catalogue admin (lecture publique).

Toutes les tables tenant ont ``account_id`` FK + RLS PostgreSQL ENABLE+FORCE
+ 2 policies (``pme_access_own_account``, ``admin_full_access``).

``credit_methodology_factors`` est un catalogue (sans account_id) — exempté
RLS et exempté Auditable (admin only).

Sur SQLite (tests CI), RLS et ALTER TYPE sont skippés.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "037_alternative_credit_data"
down_revision: Union[str, None] = "036_offer_matches_and_alerts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TENANT_TABLES = (
    "mobile_money_imports",
    "mobile_money_transactions",
    "mobile_money_analyses",
    "credit_photos",
    "public_data_sources",
)


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    jsonb_type = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")
    uuid_pk_default = sa.text("gen_random_uuid()") if is_postgres else None

    # --- 1. mobile_money_imports ---
    op.create_table(
        "mobile_money_imports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=uuid_pk_default,
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("imported_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="pending"
        ),
        sa.Column("error_summary", jsonb_type, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provider IN ('wave','orange_money','mtn_momo','moov_money')",
            name="mm_imports_provider_chk",
        ),
        sa.CheckConstraint(
            "status IN ('pending','completed','failed')",
            name="mm_imports_status_chk",
        ),
    )
    op.create_index(
        "idx_mm_imports_account_created",
        "mobile_money_imports",
        ["account_id", "created_at"],
    )

    # --- 2. mobile_money_transactions ---
    op.create_table(
        "mobile_money_transactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=uuid_pk_default,
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "import_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mobile_money_imports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("counterparty_hash", sa.String(length=64), nullable=False),
        sa.Column("balance_amount", sa.Numeric(20, 2), nullable=True),
        sa.Column("balance_currency", sa.String(length=3), nullable=True),
        sa.Column(
            "unused", sa.Boolean(), nullable=False,
            server_default=sa.false() if is_postgres else sa.text("0"),
        ),
        sa.Column("purge_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "account_id",
            "transaction_date",
            "amount",
            "counterparty_hash",
            "direction",
            name="uq_mm_transaction_dedup",
        ),
        sa.CheckConstraint(
            "direction IN ('incoming','outgoing')", name="mm_tx_direction_chk"
        ),
        sa.CheckConstraint("amount >= 0", name="mm_tx_amount_chk"),
        sa.CheckConstraint(
            "currency IN ('XOF','EUR','USD','GBP','JPY')",
            name="mm_tx_currency_chk",
        ),
        sa.CheckConstraint(
            "balance_currency IS NULL OR balance_currency IN ('XOF','EUR','USD','GBP','JPY')",
            name="mm_tx_balance_currency_chk",
        ),
    )
    op.create_index(
        "idx_mm_tx_account_date",
        "mobile_money_transactions",
        ["account_id", "transaction_date"],
    )

    # --- 3. mobile_money_analyses ---
    op.create_table(
        "mobile_money_analyses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=uuid_pk_default,
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("methodology_version", sa.String(length=20), nullable=False),
        sa.Column("kpis", jsonb_type, nullable=False),
        sa.Column("consent_active", sa.Boolean(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "account_id", "methodology_version", name="uq_mm_analysis_account_version"
        ),
    )
    op.create_index(
        "idx_mm_analyses_account_computed",
        "mobile_money_analyses",
        ["account_id", "computed_at"],
    )

    # --- 4. credit_photos ---
    op.create_table(
        "credit_photos",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=uuid_pk_default,
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("analysis_result", jsonb_type, nullable=True),
        sa.Column(
            "quality_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("methodology_version", sa.String(length=20), nullable=True),
        sa.Column(
            "unused", sa.Boolean(), nullable=False,
            server_default=sa.false() if is_postgres else sa.text("0"),
        ),
        sa.Column("purge_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "account_id", "content_hash", name="uq_credit_photo_dedup"
        ),
        sa.CheckConstraint(
            "quality_status IN ('pending','ok','low_quality','failed')",
            name="credit_photos_quality_chk",
        ),
    )
    op.create_index(
        "idx_credit_photos_account_created",
        "credit_photos",
        ["account_id", "created_at"],
    )

    # --- 5. public_data_sources ---
    op.create_table(
        "public_data_sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=uuid_pk_default,
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column("declared_rating", sa.Numeric(3, 1), nullable=True),
        sa.Column("declared_reviews_count", sa.Integer(), nullable=True),
        sa.Column("program_label", sa.String(length=100), nullable=True),
        sa.Column("evidence_path", sa.String(length=500), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="declared",
        ),
        sa.Column("sentiment_score", sa.Numeric(3, 2), nullable=True),
        sa.Column("green_signals", jsonb_type, nullable=True),
        sa.Column(
            "unused", sa.Boolean(), nullable=False,
            server_default=sa.false() if is_postgres else sa.text("0"),
        ),
        sa.Column("purge_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_type IN ('google_my_business','facebook_page','google_reviews',"
            "'trustpilot','green_program','other')",
            name="public_data_source_type_chk",
        ),
        sa.CheckConstraint(
            "status IN ('declared','evidence_attached','pending_review')",
            name="public_data_status_chk",
        ),
        sa.CheckConstraint(
            "declared_rating IS NULL OR (declared_rating >= 0 AND declared_rating <= 5)",
            name="public_data_rating_chk",
        ),
        sa.CheckConstraint(
            "declared_reviews_count IS NULL OR declared_reviews_count >= 0",
            name="public_data_reviews_chk",
        ),
    )
    op.create_index(
        "idx_public_data_account_type",
        "public_data_sources",
        ["account_id", "source_type"],
    )

    # --- 6. credit_methodology_factors (catalogue, exempt account_id) ---
    op.create_table(
        "credit_methodology_factors",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=uuid_pk_default,
            nullable=False,
        ),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("weight", sa.Numeric(4, 3), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "publication_status",
            sa.String(length=20),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "version", "name", name="uq_credit_methodology_factor"
        ),
        sa.CheckConstraint(
            "weight >= 0 AND weight <= 1",
            name="credit_methodology_weight_chk",
        ),
        sa.CheckConstraint(
            "publication_status IN ('draft','published')",
            name="credit_methodology_publication_chk",
        ),
    )
    op.create_index(
        "idx_credit_methodology_version",
        "credit_methodology_factors",
        ["version", "publication_status"],
    )

    # --- 7. RLS PostgreSQL ---
    if is_postgres:
        for table in _TENANT_TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY {table}_pme_access_own_account "
                f"ON {table} FOR ALL "
                "USING ("
                "  account_id = NULLIF(current_setting('app.current_account_id', true), '')::uuid"
                ") "
                "WITH CHECK ("
                "  account_id = NULLIF(current_setting('app.current_account_id', true), '')::uuid"
                ")"
            )
            op.execute(
                f"CREATE POLICY {table}_admin_full_access "
                f"ON {table} FOR ALL "
                "USING (current_setting('app.current_role', true) = 'ADMIN') "
                "WITH CHECK (current_setting('app.current_role', true) = 'ADMIN')"
            )

    # --- 8. ALTER TYPE credit_category_enum ADD VALUE × 3 ---
    if is_postgres:
        with op.get_context().autocommit_block():
            for value in ("mobile_money_flux", "photos_ia", "public_data"):
                op.execute(
                    f"ALTER TYPE credit_category_enum ADD VALUE IF NOT EXISTS '{value}'"
                )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        for table in _TENANT_TABLES:
            op.execute(
                f"DROP POLICY IF EXISTS {table}_pme_access_own_account ON {table}"
            )
            op.execute(
                f"DROP POLICY IF EXISTS {table}_admin_full_access ON {table}"
            )

    op.drop_index(
        "idx_credit_methodology_version", table_name="credit_methodology_factors"
    )
    op.drop_table("credit_methodology_factors")

    op.drop_index("idx_public_data_account_type", table_name="public_data_sources")
    op.drop_table("public_data_sources")

    op.drop_index("idx_credit_photos_account_created", table_name="credit_photos")
    op.drop_table("credit_photos")

    op.drop_index(
        "idx_mm_analyses_account_computed", table_name="mobile_money_analyses"
    )
    op.drop_table("mobile_money_analyses")

    op.drop_index(
        "idx_mm_tx_account_date", table_name="mobile_money_transactions"
    )
    op.drop_table("mobile_money_transactions")

    op.drop_index(
        "idx_mm_imports_account_created", table_name="mobile_money_imports"
    )
    op.drop_table("mobile_money_imports")

    # Note : ALTER TYPE ... DROP VALUE n'est pas supporté en PostgreSQL <16
    # → les valeurs `mobile_money_flux`, `photos_ia`, `public_data` restent
    # dans l'enum. Acceptable (downgrade rare).
