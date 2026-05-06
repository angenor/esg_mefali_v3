"""F01 - Catalogue de sources verifiees + entites factuelles sourcees.

Revision ID: 020_sources
Revises: 019_multitenant
Create Date: 2026-05-06

Cette migration introduit :
- Table `sources` avec workflow 4-yeux (CHECK captured_by != verified_by)
  + statuts (draft / pending / verified / outdated).
- Tables factuelles (indicators, criteria, formulas, thresholds,
  referentials, referential_indicators, emission_factors, required_documents,
  simulation_factors).
- Table journal `unsourced_flags` pour les invocations flag_unsourced.
- Toutes les nouvelles tables embarquent `account_id` (F02 multi-tenant) et
  `created_by_user_id` (audit createur).
- RLS PostgreSQL active sur les tables exposant des donnees PME.

Downgrade : drop des 11 tables en ordre inverse.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "020_sources"
down_revision: Union[str, None] = "019_multitenant"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables F01 qui beneficient de RLS (en mode lecture publique pour les
# entites verifiees + acces complet admin).
F01_RLS_TABLES: tuple[str, ...] = (
    "sources",
    "indicators",
    "criteria",
    "formulas",
    "thresholds",
    "referentials",
    "referential_indicators",
    "emission_factors",
    "required_documents",
    "simulation_factors",
    "unsourced_flags",
)


def _enable_rls_public_read(table: str) -> None:
    """Active RLS avec policies admin + lecture publique des entites verified.

    PME : peuvent lire (SELECT) les entites avec verification_status='verified'
    pour `sources`, ou publication_status='published' pour les autres tables.
    Ecriture : reservee aux admins.
    """
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    # Policy ADMIN : acces complet.
    op.execute(
        f"""
        CREATE POLICY admin_full_access ON {table}
        FOR ALL
        USING (current_setting('app.current_role', true) = 'ADMIN')
        WITH CHECK (current_setting('app.current_role', true) = 'ADMIN')
        """
    )
    # Policy lecture publique : sources verified ou entites published.
    if table == "sources":
        op.execute(
            f"""
            CREATE POLICY public_read_verified ON {table}
            FOR SELECT
            USING (verification_status = 'verified')
            """
        )
    elif table in ("unsourced_flags", "referential_indicators"):
        # journal admin only / table de jointure : lecture publique simple si
        # toutes les FK pointent vers des objets publies (geree par lookup
        # applicatif). Pas de policy SELECT publique ici pour eviter une
        # complexite SQL inutile.
        pass
    elif table == "simulation_factors":
        op.execute(
            f"""
            CREATE POLICY public_read_published ON {table}
            FOR SELECT
            USING (status = 'verified')
            """
        )
    else:
        op.execute(
            f"""
            CREATE POLICY public_read_published ON {table}
            FOR SELECT
            USING (publication_status = 'published')
            """
        )


def _disable_rls(table: str) -> None:
    """Drop policies + RLS pour la downgrade."""
    op.execute(f"DROP POLICY IF EXISTS public_read_published ON {table}")
    op.execute(f"DROP POLICY IF EXISTS public_read_verified ON {table}")
    op.execute(f"DROP POLICY IF EXISTS admin_full_access ON {table}")
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # --- Table sources ---
    op.create_table(
        "sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("publisher", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("date_publi", sa.Date(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(length=200), nullable=True),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "captured_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "verified_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "verification_status",
            sa.String(length=20),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outdated_reason", sa.Text(), nullable=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "embedding",
            postgresql.JSONB() if is_postgres else sa.JSON(),
            nullable=True,
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
            "verified_by IS NULL OR verified_by != captured_by",
            name="sources_four_eyes_chk",
        ),
        sa.CheckConstraint(
            "verification_status IN ('draft','pending','verified','outdated')",
            name="sources_verification_status_chk",
        ),
        sa.CheckConstraint(
            "(verification_status IN ('verified','outdated') "
            "AND verified_by IS NOT NULL AND verified_at IS NOT NULL) "
            "OR verification_status IN ('draft','pending')",
            name="sources_verified_consistency_chk",
        ),
        sa.CheckConstraint(
            "(verification_status = 'outdated' AND outdated_reason IS NOT NULL) "
            "OR verification_status != 'outdated'",
            name="sources_outdated_reason_chk",
        ),
    )
    op.create_index("sources_url_uniq_idx", "sources", ["url"], unique=True)
    op.create_index(
        "sources_verification_status_idx", "sources", ["verification_status"],
    )
    op.create_index("sources_publisher_idx", "sources", ["publisher"])
    op.create_index("idx_sources_account_id", "sources", ["account_id"])

    # --- Table indicators ---
    op.create_table(
        "indicators",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("pillar", sa.String(length=20), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "publication_status",
            sa.String(length=20),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
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
            "pillar IN ('environment','social','governance')",
            name="indicators_pillar_chk",
        ),
        sa.CheckConstraint(
            "publication_status IN ('draft','published')",
            name="indicators_publication_status_chk",
        ),
    )
    op.create_index("indicators_code_uniq_idx", "indicators", ["code"], unique=True)
    op.create_index("idx_indicators_account_id", "indicators", ["account_id"])

    # --- Table criteria ---
    op.create_table(
        "criteria",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column(
            "expression",
            postgresql.JSONB() if is_postgres else sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "publication_status",
            sa.String(length=20),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
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
            "publication_status IN ('draft','published')",
            name="criteria_publication_status_chk",
        ),
    )
    op.create_index("criteria_code_uniq_idx", "criteria", ["code"], unique=True)
    op.create_index("idx_criteria_account_id", "criteria", ["account_id"])

    # --- Table formulas ---
    op.create_table(
        "formulas",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("expression", sa.Text(), nullable=False),
        sa.Column(
            "parameters",
            postgresql.JSONB() if is_postgres else sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "publication_status",
            sa.String(length=20),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
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
            "publication_status IN ('draft','published')",
            name="formulas_publication_status_chk",
        ),
    )
    op.create_index("formulas_code_uniq_idx", "formulas", ["code"], unique=True)
    op.create_index("idx_formulas_account_id", "formulas", ["account_id"])

    # --- Table thresholds ---
    op.create_table(
        "thresholds",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("value", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("scope", sa.String(length=100), nullable=False),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "publication_status",
            sa.String(length=20),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
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
            "publication_status IN ('draft','published')",
            name="thresholds_publication_status_chk",
        ),
    )
    op.create_index("thresholds_code_uniq_idx", "thresholds", ["code"], unique=True)
    op.create_index("idx_thresholds_account_id", "thresholds", ["account_id"])

    # --- Table referentials ---
    op.create_table(
        "referentials",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
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
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
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
            "publication_status IN ('draft','published')",
            name="referentials_publication_status_chk",
        ),
    )
    op.create_index(
        "referentials_code_uniq_idx", "referentials", ["code"], unique=True,
    )
    op.create_index("idx_referentials_account_id", "referentials", ["account_id"])

    # --- Table referential_indicators (jointure N-N) ---
    op.create_table(
        "referential_indicators",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column(
            "referential_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("referentials.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "indicator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("indicators.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "weight",
            sa.Numeric(precision=4, scale=2),
            server_default="1.00",
            nullable=False,
        ),
        sa.Column("threshold", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
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
        sa.UniqueConstraint(
            "referential_id", "indicator_id", name="referential_indicators_uniq",
        ),
    )

    # --- Table emission_factors ---
    op.create_table(
        "emission_factors",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("country", sa.String(length=50), nullable=False),
        sa.Column("value", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "publication_status",
            sa.String(length=20),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
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
            "publication_status IN ('draft','published')",
            name="emission_factors_publication_status_chk",
        ),
    )
    op.create_index(
        "emission_factors_code_uniq_idx", "emission_factors", ["code"], unique=True,
    )
    op.create_index(
        "emission_factors_category_country_idx",
        "emission_factors",
        ["category", "country"],
    )
    op.create_index(
        "idx_emission_factors_account_id", "emission_factors", ["account_id"],
    )

    # --- Table required_documents ---
    op.create_table(
        "required_documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "fund_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("funds.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "intermediary_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intermediaries.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "publication_status",
            sa.String(length=20),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
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
            "(fund_id IS NOT NULL AND intermediary_id IS NULL) "
            "OR (fund_id IS NULL AND intermediary_id IS NOT NULL)",
            name="required_documents_owner_chk",
        ),
        sa.CheckConstraint(
            "publication_status IN ('draft','published')",
            name="required_documents_publication_status_chk",
        ),
    )
    op.create_index(
        "idx_required_documents_account_id", "required_documents", ["account_id"],
    )

    # --- Table simulation_factors ---
    op.create_table(
        "simulation_factors",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("value", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("scope", sa.String(length=100), nullable=False),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
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
            "(status = 'verified' AND source_id IS NOT NULL) "
            "OR (status = 'pending' AND source_id IS NULL)",
            name="simulation_factors_source_required_chk",
        ),
        sa.CheckConstraint(
            "status IN ('verified','pending')",
            name="simulation_factors_status_chk",
        ),
    )
    op.create_index(
        "simulation_factors_code_uniq_idx",
        "simulation_factors",
        ["code"],
        unique=True,
    )
    op.create_index(
        "idx_simulation_factors_account_id", "simulation_factors", ["account_id"],
    )

    # --- Table unsourced_flags (journal) ---
    op.create_table(
        "unsourced_flags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "unsourced_flags_created_at_idx", "unsourced_flags", ["created_at"],
    )
    op.create_index(
        "idx_unsourced_flags_account_id", "unsourced_flags", ["account_id"],
    )

    # --- Index full-text PostgreSQL sur sources (recherche FR) ---
    if is_postgres:
        op.execute(
            "CREATE INDEX sources_title_publisher_fts_idx ON sources "
            "USING GIN (to_tsvector('french', "
            "title || ' ' || publisher || ' ' || COALESCE(section, '')))"
        )

    # --- Activation RLS sur les tables F01 ---
    if is_postgres:
        for table in F01_RLS_TABLES:
            _enable_rls_public_read(table)


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # --- Desactiver RLS ---
    if is_postgres:
        for table in F01_RLS_TABLES:
            _disable_rls(table)

    # --- Drop FTS index ---
    if is_postgres:
        op.execute("DROP INDEX IF EXISTS sources_title_publisher_fts_idx")

    # --- Drop tables en ordre inverse (FK dependencies) ---
    op.drop_index("idx_unsourced_flags_account_id", table_name="unsourced_flags")
    op.drop_index("unsourced_flags_created_at_idx", table_name="unsourced_flags")
    op.drop_table("unsourced_flags")

    op.drop_index(
        "idx_simulation_factors_account_id", table_name="simulation_factors",
    )
    op.drop_index(
        "simulation_factors_code_uniq_idx", table_name="simulation_factors",
    )
    op.drop_table("simulation_factors")

    op.drop_index(
        "idx_required_documents_account_id", table_name="required_documents",
    )
    op.drop_table("required_documents")

    op.drop_index("idx_emission_factors_account_id", table_name="emission_factors")
    op.drop_index(
        "emission_factors_category_country_idx", table_name="emission_factors",
    )
    op.drop_index("emission_factors_code_uniq_idx", table_name="emission_factors")
    op.drop_table("emission_factors")

    op.drop_table("referential_indicators")

    op.drop_index("idx_referentials_account_id", table_name="referentials")
    op.drop_index("referentials_code_uniq_idx", table_name="referentials")
    op.drop_table("referentials")

    op.drop_index("idx_thresholds_account_id", table_name="thresholds")
    op.drop_index("thresholds_code_uniq_idx", table_name="thresholds")
    op.drop_table("thresholds")

    op.drop_index("idx_formulas_account_id", table_name="formulas")
    op.drop_index("formulas_code_uniq_idx", table_name="formulas")
    op.drop_table("formulas")

    op.drop_index("idx_criteria_account_id", table_name="criteria")
    op.drop_index("criteria_code_uniq_idx", table_name="criteria")
    op.drop_table("criteria")

    op.drop_index("idx_indicators_account_id", table_name="indicators")
    op.drop_index("indicators_code_uniq_idx", table_name="indicators")
    op.drop_table("indicators")

    op.drop_index("idx_sources_account_id", table_name="sources")
    op.drop_index("sources_publisher_idx", table_name="sources")
    op.drop_index("sources_verification_status_idx", table_name="sources")
    op.drop_index("sources_url_uniq_idx", table_name="sources")
    op.drop_table("sources")
