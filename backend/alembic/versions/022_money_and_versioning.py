"""F04 — Money typed + Versioning + Multi-devises.

Revision ID: 022_money_and_versioning
Revises: 021_audit_log
Create Date: 2026-05-07

Cette migration introduit :
- Une nouvelle table ``exchange_rates`` (référentiel public global, sans
  ``account_id``) avec ses index et CHECK constraints.
- 4 colonnes versioning ``(version, valid_from, valid_to, superseded_by)``
  sur 12 tables catalogue (Source utilise déjà un champ ``version`` métier
  → on ajoute ``catalog_version`` à la place).
- Fonction PL/pgSQL ``prevent_supersede_cycle()`` + 13 triggers BEFORE
  INSERT/UPDATE pour défense en profondeur (PostgreSQL only ; skip SQLite).
- Snapshot immuable ``snapshot_at`` + ``snapshot_data`` (JSONB) sur
  ``fund_applications``.
- Paires Money ``<field>_amount`` (NUMERIC(20,2)) + ``<field>_currency``
  (CHAR(3)) sur 4 tables financières (Fund x2 fields, CompanyProfile,
  ActionItem). ``CarbonAssessment.savings_*`` est skippé : la colonne
  legacy ``savings_fcfa`` n'existe pas dans le modèle actuel (cf. spec
  data-model §4 « si présent »).
- Backfill SQL idempotent ``<field>_amount = <field>_xof`` /
  ``<field>_currency = 'XOF'``.
- Seed initial 8 entrées ``exchange_rates`` (USD↔{XOF,EUR,GBP,JPY} +
  inverses calculées).

Downgrade : drop colonnes + drop table + drop function/triggers en ordre
inverse. Les anciennes colonnes ``*_xof`` ne sont JAMAIS droppées (phase 2
hors-scope F04).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "022_money_and_versioning"
down_revision: Union[str, None] = "021_audit_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables catalogue qui reçoivent les 4 colonnes versioning standard
# (version, valid_from, valid_to, superseded_by). 12 tables.
CATALOG_TABLES_VERSION = (
    "indicators",
    "criteria",
    "formulas",
    "thresholds",
    "referentials",
    "referential_indicators",
    "emission_factors",
    "required_documents",
    "simulation_factors",
    "funds",
    "intermediaries",
    "fund_intermediaries",
)

# La table "sources" a déjà un champ version (sémantique métier : version du
# document externe ex "v2.3", "AR6"). On ajoute donc 'catalog_version' pour
# F04 sans toucher à 'version'. On ajoute aussi les 3 autres colonnes
# (valid_from, valid_to, superseded_by) avec ce nom de version dédié.
SOURCES_TABLE = "sources"

# Tables financières qui reçoivent une paire Money par champ legacy.
MONEY_FIELDS = [
    ("funds", "min_amount_xof", "min_amount", "min_amount_currency"),
    ("funds", "max_amount_xof", "max_amount", "max_amount_currency"),
    ("company_profiles", "annual_revenue_xof", "annual_revenue_amount",
     "annual_revenue_currency"),
    ("action_items", "estimated_cost_xof", "estimated_cost_amount",
     "estimated_cost_currency"),
]


def _add_versioning_columns(table: str, version_col: str = "version") -> None:
    """Ajoute les 4 colonnes versioning à une table catalogue.

    ``version_col`` permet d'utiliser un autre nom (ex 'catalog_version' pour
    la table sources où 'version' existe déjà).
    """
    op.add_column(
        table,
        sa.Column(version_col, sa.String(50), nullable=False, server_default="1.0"),
    )
    op.add_column(
        table,
        sa.Column(
            "valid_from", sa.Date, nullable=False,
            server_default=sa.text("CURRENT_DATE"),
        ),
    )
    op.add_column(
        table, sa.Column("valid_to", sa.Date, nullable=True),
    )
    op.add_column(
        table,
        sa.Column(
            "superseded_by",
            sa.dialects.postgresql.UUID(as_uuid=True).with_variant(
                sa.String(36), "sqlite",
            ),
            sa.ForeignKey(f"{table}.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    # CHECK regex sur version_col (PostgreSQL only — SQLite ignore les CHECK regex)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.create_check_constraint(
            f"{table}_{version_col}_format_chk",
            table,
            f"{version_col} ~ '^\\d+\\.\\d+$'",
        )
    # Index pour la recherche de version active
    op.create_index(f"{table}_valid_to_idx", table, ["valid_to"])
    op.create_index(
        f"{table}_superseded_by_idx", table, ["superseded_by"],
        postgresql_where=sa.text("superseded_by IS NOT NULL"),
    )


def _drop_versioning_columns(table: str, version_col: str = "version") -> None:
    """Supprime les 4 colonnes versioning + index + CHECK."""
    op.drop_index(f"{table}_superseded_by_idx", table_name=table)
    op.drop_index(f"{table}_valid_to_idx", table_name=table)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "
            f"{table}_{version_col}_format_chk",
        )
    op.drop_column(table, "superseded_by")
    op.drop_column(table, "valid_to")
    op.drop_column(table, "valid_from")
    op.drop_column(table, version_col)


def _add_money_pair(
    table: str, amount_col: str, currency_col: str, legacy_col: str,
) -> None:
    """Ajoute une paire (amount, currency) avec backfill XOF idempotent."""
    op.add_column(
        table, sa.Column(amount_col, sa.Numeric(20, 2), nullable=True),
    )
    op.add_column(
        table, sa.Column(currency_col, sa.String(3), nullable=True),
    )
    # CHECK : currency dans l'enum (sans NULL) + paire cohérente.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.create_check_constraint(
            f"{table}_{currency_col}_chk",
            table,
            f"{currency_col} IS NULL OR "
            f"{currency_col} IN ('XOF', 'EUR', 'USD', 'GBP', 'JPY')",
        )
        op.create_check_constraint(
            f"{table}_{amount_col}_pair_chk",
            table,
            f"({amount_col} IS NULL AND {currency_col} IS NULL) OR "
            f"({amount_col} IS NOT NULL AND {currency_col} IS NOT NULL)",
        )
    # Backfill idempotent
    op.execute(
        f"UPDATE {table} SET "
        f"  {amount_col} = COALESCE({amount_col}, {legacy_col}), "
        f"  {currency_col} = COALESCE({currency_col}, 'XOF') "
        f"WHERE {legacy_col} IS NOT NULL "
        f"  AND ({amount_col} IS NULL OR {currency_col} IS NULL)",
    )


def _drop_money_pair(table: str, amount_col: str, currency_col: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "
            f"{table}_{amount_col}_pair_chk",
        )
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "
            f"{table}_{currency_col}_chk",
        )
    op.drop_column(table, currency_col)
    op.drop_column(table, amount_col)


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Nouvelle table exchange_rates
    op.create_table(
        "exchange_rates",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True).with_variant(
                sa.String(36), "sqlite",
            ),
            primary_key=True,
        ),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("quote_currency", sa.String(3), nullable=False),
        sa.Column("rate", sa.Numeric(20, 10), nullable=False),
        sa.Column("as_of", sa.Date, nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            "base_currency IN ('XOF', 'EUR', 'USD', 'GBP', 'JPY')",
            name="exchange_rates_base_currency_chk",
        ),
        sa.CheckConstraint(
            "quote_currency IN ('XOF', 'EUR', 'USD', 'GBP', 'JPY')",
            name="exchange_rates_quote_currency_chk",
        ),
        sa.CheckConstraint("rate > 0", name="exchange_rates_rate_positive_chk"),
        sa.UniqueConstraint(
            "base_currency", "quote_currency", "as_of",
            name="exchange_rates_pair_uniq",
        ),
    )
    op.create_index(
        "exchange_rates_lookup_idx", "exchange_rates",
        ["base_currency", "quote_currency", "as_of"],
    )

    # 2. Fonction PL/pgSQL anti-cycle (PostgreSQL only).
    if is_postgres:
        op.execute(
            """
            CREATE OR REPLACE FUNCTION prevent_supersede_cycle()
            RETURNS trigger AS $$
            DECLARE
                cur uuid := NEW.superseded_by;
                seen uuid[] := ARRAY[NEW.id];
                table_name text := TG_TABLE_NAME;
                query text;
                next_cur uuid;
                max_depth int := 100;
                depth int := 0;
            BEGIN
                IF NEW.superseded_by IS NULL THEN
                    RETURN NEW;
                END IF;
                WHILE cur IS NOT NULL LOOP
                    IF cur = ANY(seen) THEN
                        RAISE EXCEPTION
                            'Supersede cycle detected on table % (id=%)',
                            table_name, NEW.id;
                    END IF;
                    IF depth > max_depth THEN
                        RAISE EXCEPTION
                            'Supersede chain too deep on table % (max % levels)',
                            table_name, max_depth;
                    END IF;
                    seen := seen || cur;
                    depth := depth + 1;
                    query := format(
                        'SELECT superseded_by FROM %I WHERE id = $1', table_name);
                    EXECUTE query INTO next_cur USING cur;
                    cur := next_cur;
                END LOOP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """,
        )

    # 3. Versioning columns sur 12 tables catalogue + sources (catalog_version)
    for table in CATALOG_TABLES_VERSION:
        _add_versioning_columns(table, version_col="version")
        if is_postgres:
            op.execute(
                f"""
                CREATE TRIGGER {table}_supersede_cycle_trg
                    BEFORE INSERT OR UPDATE OF superseded_by ON {table}
                    FOR EACH ROW EXECUTE FUNCTION prevent_supersede_cycle();
                """,
            )

    _add_versioning_columns(SOURCES_TABLE, version_col="catalog_version")
    if is_postgres:
        op.execute(
            f"""
            CREATE TRIGGER {SOURCES_TABLE}_supersede_cycle_trg
                BEFORE INSERT OR UPDATE OF superseded_by ON {SOURCES_TABLE}
                FOR EACH ROW EXECUTE FUNCTION prevent_supersede_cycle();
            """,
        )

    # 4. Snapshot fields sur fund_applications
    op.add_column(
        "fund_applications",
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "fund_applications",
        sa.Column(
            "snapshot_data",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()).with_variant(
                sa.JSON(), "sqlite",
            ),
            nullable=True,
        ),
    )

    # 5. Money pairs sur 4 tables financières (avec backfill)
    for table, legacy_col, amount_col, currency_col in MONEY_FIELDS:
        _add_money_pair(table, amount_col, currency_col, legacy_col)

    # 6. Seed initial exchange_rates
    op.execute(
        """
        INSERT INTO exchange_rates
            (id, base_currency, quote_currency, rate, as_of, source, fetched_at)
        VALUES
            ('11111111-1111-1111-1111-111111111111', 'USD', 'XOF',
             615.20, '2026-04-15', 'exchangerate-api.com', NOW()),
            ('22222222-2222-2222-2222-222222222222', 'USD', 'EUR',
             0.92, '2026-04-15', 'exchangerate-api.com', NOW()),
            ('33333333-3333-3333-3333-333333333333', 'USD', 'GBP',
             0.79, '2026-04-15', 'exchangerate-api.com', NOW()),
            ('44444444-4444-4444-4444-444444444444', 'USD', 'JPY',
             152.50, '2026-04-15', 'exchangerate-api.com', NOW()),
            ('55555555-5555-5555-5555-555555555555', 'XOF', 'USD',
             0.0016255686, '2026-04-15', 'computed', NOW()),
            ('66666666-6666-6666-6666-666666666666', 'EUR', 'USD',
             1.0869565217, '2026-04-15', 'computed', NOW()),
            ('77777777-7777-7777-7777-777777777777', 'GBP', 'USD',
             1.2658227848, '2026-04-15', 'computed', NOW()),
            ('88888888-8888-8888-8888-888888888888', 'JPY', 'USD',
             0.0065573770, '2026-04-15', 'computed', NOW())
        ON CONFLICT DO NOTHING
        """ if is_postgres else
        """
        INSERT INTO exchange_rates
            (id, base_currency, quote_currency, rate, as_of, source, fetched_at)
        VALUES
            ('11111111-1111-1111-1111-111111111111', 'USD', 'XOF',
             615.20, '2026-04-15', 'exchangerate-api.com', CURRENT_TIMESTAMP),
            ('22222222-2222-2222-2222-222222222222', 'USD', 'EUR',
             0.92, '2026-04-15', 'exchangerate-api.com', CURRENT_TIMESTAMP),
            ('33333333-3333-3333-3333-333333333333', 'USD', 'GBP',
             0.79, '2026-04-15', 'exchangerate-api.com', CURRENT_TIMESTAMP),
            ('44444444-4444-4444-4444-444444444444', 'USD', 'JPY',
             152.50, '2026-04-15', 'exchangerate-api.com', CURRENT_TIMESTAMP),
            ('55555555-5555-5555-5555-555555555555', 'XOF', 'USD',
             0.0016255686, '2026-04-15', 'computed', CURRENT_TIMESTAMP),
            ('66666666-6666-6666-6666-666666666666', 'EUR', 'USD',
             1.0869565217, '2026-04-15', 'computed', CURRENT_TIMESTAMP),
            ('77777777-7777-7777-7777-777777777777', 'GBP', 'USD',
             1.2658227848, '2026-04-15', 'computed', CURRENT_TIMESTAMP),
            ('88888888-8888-8888-8888-888888888888', 'JPY', 'USD',
             0.0065573770, '2026-04-15', 'computed', CURRENT_TIMESTAMP)
        """,
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # Drop money pairs
    for table, _, amount_col, currency_col in reversed(MONEY_FIELDS):
        _drop_money_pair(table, amount_col, currency_col)

    # Drop snapshot fields
    op.drop_column("fund_applications", "snapshot_data")
    op.drop_column("fund_applications", "snapshot_at")

    # Drop versioning columns
    if is_postgres:
        op.execute(
            f"DROP TRIGGER IF EXISTS {SOURCES_TABLE}_supersede_cycle_trg "
            f"ON {SOURCES_TABLE}",
        )
    _drop_versioning_columns(SOURCES_TABLE, version_col="catalog_version")

    for table in reversed(CATALOG_TABLES_VERSION):
        if is_postgres:
            op.execute(
                f"DROP TRIGGER IF EXISTS {table}_supersede_cycle_trg ON {table}",
            )
        _drop_versioning_columns(table, version_col="version")

    # Drop trigger function
    if is_postgres:
        op.execute("DROP FUNCTION IF EXISTS prevent_supersede_cycle()")

    # Drop exchange_rates
    op.drop_index("exchange_rates_lookup_idx", table_name="exchange_rates")
    op.drop_table("exchange_rates")
