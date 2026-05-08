"""F14 — OfferMatch + MatchAlertSubscription tables.

Revision ID: 036_offer_matches_and_alerts
Revises: 035_admin_publication_status_workflow
Create Date: 2026-05-08

Cette migration crée les 2 tables F14 :

1. ``offer_matches`` : score décomposé Project ↔ Offer (16 colonnes, 5 CHECK,
   UNIQUE (project_id, offer_id), 5 indexes).
2. ``match_alerts_subscriptions`` : souscription par projet aux alertes
   nouvelles offres compatibles (UNIQUE (project_id), 1 CHECK).

RLS PostgreSQL ENABLE+FORCE + 2 policies par table (cohérent F02).

Backfill best-effort ``fund_matches`` → ``offer_matches`` :
- Pour chaque ``FundMatch`` actif, infère ``project_id`` (dernier projet actif
  du même ``account_id``) et ``offer_id`` (offre DIRECT publiée la plus récente
  pour le ``fund_id``). Les fund_match orphelins sont ignorés (best-effort).

Compatibilité enum F19 : ALTER TYPE ``reminder_type_enum`` ADD VALUE IF NOT
EXISTS ``new_offer_alert`` (idempotent en PG via IF NOT EXISTS).

Sur SQLite (tests CI), les ENUMs et la RLS sont skippés.

Downgrade : DROP TABLE des 2 tables (la valeur enum reste, PG ne supporte pas
DROP VALUE FROM ENUM avant PG 16). ``fund_matches`` non touchée (legacy 2 sprints).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "036_offer_matches_and_alerts"
down_revision: Union[str, None] = "035_admin_publication_status_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # --- 1. Table offer_matches ---
    op.create_table(
        "offer_matches",
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
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "offer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("offers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("global_score", sa.Integer(), nullable=False),
        sa.Column("fund_score", sa.Integer(), nullable=False),
        sa.Column("intermediary_score", sa.Integer(), nullable=False),
        sa.Column(
            "score_breakdown",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("bottleneck", sa.String(length=20), nullable=False),
        sa.Column(
            "recommended_actions",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="suggested",
        ),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_notified_at",
            sa.DateTime(timezone=True),
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
        sa.UniqueConstraint(
            "project_id", "offer_id", name="uq_offer_matches_project_offer",
        ),
        sa.CheckConstraint(
            "global_score BETWEEN 0 AND 100",
            name="offer_matches_global_score_chk",
        ),
        sa.CheckConstraint(
            "fund_score BETWEEN 0 AND 100",
            name="offer_matches_fund_score_chk",
        ),
        sa.CheckConstraint(
            "intermediary_score BETWEEN 0 AND 100",
            name="offer_matches_intermediary_score_chk",
        ),
        sa.CheckConstraint(
            "bottleneck IN ('fund','intermediary','balanced')",
            name="offer_matches_bottleneck_chk",
        ),
        sa.CheckConstraint(
            "status IN ('suggested','viewed','dismissed','converted')",
            name="offer_matches_status_chk",
        ),
    )

    op.create_index(
        "idx_offer_matches_account_id", "offer_matches", ["account_id"],
    )
    op.create_index(
        "idx_offer_matches_project_computed",
        "offer_matches",
        ["project_id", "computed_at"],
    )
    op.create_index(
        "idx_offer_matches_account_expires",
        "offer_matches",
        ["account_id", "expires_at"],
    )
    op.create_index(
        "idx_offer_matches_offer", "offer_matches", ["offer_id"],
    )
    op.create_index(
        "idx_offer_matches_account_score",
        "offer_matches",
        ["account_id", "global_score"],
    )

    # --- 2. Table match_alerts_subscriptions ---
    op.create_table(
        "match_alerts_subscriptions",
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
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "min_global_score",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true() if is_postgres else sa.text("1"),
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
            "project_id", name="uq_match_alerts_subscription_project",
        ),
        sa.CheckConstraint(
            "min_global_score BETWEEN 0 AND 100",
            name="match_alerts_subscription_min_score_chk",
        ),
    )
    op.create_index(
        "idx_match_alerts_account_id",
        "match_alerts_subscriptions",
        ["account_id"],
    )
    op.create_index(
        "idx_match_alerts_account_active",
        "match_alerts_subscriptions",
        ["account_id", "is_active"],
    )

    # --- 3. RLS PostgreSQL ---
    if is_postgres:
        for table in ("offer_matches", "match_alerts_subscriptions"):
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

    # --- 4. ALTER TYPE reminder_type_enum ADD VALUE 'new_offer_alert' (F19 reuse) ---
    if is_postgres:
        # ALTER TYPE ADD VALUE doit s'exécuter hors transaction (autocommit).
        # Pattern : sortir de la transaction Alembic via op.execute autonome.
        with op.get_context().autocommit_block():
            op.execute(
                "ALTER TYPE reminder_type_enum ADD VALUE IF NOT EXISTS 'new_offer_alert'"
            )

    # --- 5. Backfill best-effort fund_matches → offer_matches ---
    # En PostgreSQL : SQL pur idempotent. En SQLite (tests) : skip car
    # complexité des sous-requêtes peut diverger.
    if is_postgres:
        op.execute(
            """
            INSERT INTO offer_matches (
                id, account_id, project_id, offer_id,
                global_score, fund_score, intermediary_score,
                score_breakdown, bottleneck, recommended_actions,
                status, computed_at, expires_at, last_notified_at,
                created_at, updated_at
            )
            SELECT
                gen_random_uuid(),
                fm.account_id,
                (SELECT p.id FROM projects p
                 WHERE p.account_id = fm.account_id
                   AND p.status NOT IN ('cancelled','closed')
                 ORDER BY p.created_at DESC LIMIT 1),
                (SELECT o.id FROM offers o
                 JOIN intermediaries i ON i.id = o.intermediary_id
                 WHERE o.fund_id = fm.fund_id
                   AND i.code = 'DIRECT'
                   AND o.publication_status = 'published'
                 ORDER BY o.version DESC LIMIT 1),
                fm.compatibility_score,
                fm.compatibility_score,
                fm.compatibility_score,
                '{}'::jsonb,
                'balanced',
                '[]'::jsonb,
                'suggested',
                now(),
                now() + interval '30 days',
                NULL,
                fm.created_at,
                fm.created_at
            FROM fund_matches fm
            WHERE fm.account_id IS NOT NULL
              AND EXISTS (
                  SELECT 1 FROM projects p
                  WHERE p.account_id = fm.account_id
                    AND p.status NOT IN ('cancelled','closed')
              )
              AND EXISTS (
                  SELECT 1 FROM offers o
                  JOIN intermediaries i ON i.id = o.intermediary_id
                  WHERE o.fund_id = fm.fund_id
                    AND i.code = 'DIRECT'
                    AND o.publication_status = 'published'
              )
            ON CONFLICT (project_id, offer_id) DO NOTHING
            """
        )

    # --- 6. Backfill match_alerts_subscriptions pour projets actifs ---
    if is_postgres:
        op.execute(
            """
            INSERT INTO match_alerts_subscriptions (
                id, account_id, project_id, min_global_score, is_active,
                created_at, updated_at
            )
            SELECT
                gen_random_uuid(), p.account_id, p.id, 60, true,
                now(), now()
            FROM projects p
            WHERE p.status NOT IN ('cancelled','closed')
            ON CONFLICT (project_id) DO NOTHING
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        for table in ("offer_matches", "match_alerts_subscriptions"):
            op.execute(
                f"DROP POLICY IF EXISTS {table}_pme_access_own_account ON {table}"
            )
            op.execute(
                f"DROP POLICY IF EXISTS {table}_admin_full_access ON {table}"
            )

    op.drop_index(
        "idx_match_alerts_account_active",
        table_name="match_alerts_subscriptions",
    )
    op.drop_index(
        "idx_match_alerts_account_id",
        table_name="match_alerts_subscriptions",
    )
    op.drop_table("match_alerts_subscriptions")

    op.drop_index(
        "idx_offer_matches_account_score", table_name="offer_matches",
    )
    op.drop_index("idx_offer_matches_offer", table_name="offer_matches")
    op.drop_index(
        "idx_offer_matches_account_expires", table_name="offer_matches",
    )
    op.drop_index(
        "idx_offer_matches_project_computed", table_name="offer_matches",
    )
    op.drop_index("idx_offer_matches_account_id", table_name="offer_matches")
    op.drop_table("offer_matches")

    # Note : on ne retire PAS la valeur 'new_offer_alert' de reminder_type_enum
    # (PG ne supporte pas DROP VALUE FROM ENUM avant PG 16, et nettoyer les
    # données existantes serait risqué).
