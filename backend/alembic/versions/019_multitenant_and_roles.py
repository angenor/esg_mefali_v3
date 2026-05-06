"""F02 — Multi-tenant + Roles + Row-Level Security PostgreSQL.

Revision ID: 019_multitenant
Revises: 10b2tools_offered
Create Date: 2026-05-06 20:30:00.000000

Cette migration introduit :
- Trois nouvelles tables : `accounts`, `refresh_tokens`, `account_invitations`.
- Deux ENUMs : `user_role` (PME/ADMIN), `invitation_status`.
- L'extension du modèle `User` avec `role` et `account_id` (+ CHECK constraint).
- L'ajout d'une colonne `account_id` (NULLable au début → backfill → NOT NULL)
  sur les 14+ tables métier listées dans data-model.md.
- Le backfill : un `Account` est créé par valeur distincte de `users.company_name` ;
  les utilisateurs sans `company_name` sont rattachés à un Account `default`.
- L'activation de la Row-Level Security (`ENABLE` + `FORCE`) avec deux policies
  par table métier (`pme_access_own_account` et `admin_full_access`).

Downgrade : ordre inverse, en best-effort. Les données restent cohérentes
mais les `Account`, `RefreshToken` et `AccountInvitation` sont supprimés.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "019_multitenant"
down_revision: Union[str, None] = "10b2tools_offered"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Liste centrale des 14 tables métier qui reçoivent `account_id` + RLS.
# (cf. data-model.md §5)
METIER_TABLES: tuple[str, ...] = (
    "company_profiles",
    "documents",
    "esg_assessments",
    "carbon_assessments",
    "credit_scores",
    "fund_matches",
    "fund_applications",
    "action_plans",
    "action_items",
    "reminders",
    "conversations",
    "messages",
    "interactive_questions",
    "tool_call_logs",
    "reports",
)


def _enable_rls(table: str) -> None:
    """Activer ENABLE + FORCE RLS sur une table et créer les 2 policies."""
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    # Policy PME : l'utilisateur ne voit que son account.
    op.execute(
        f"""
        CREATE POLICY pme_access_own_account ON {table}
        FOR ALL
        USING (
            account_id IS NOT NULL
            AND current_setting('app.current_account_id', true) <> ''
            AND account_id = current_setting('app.current_account_id', true)::uuid
        )
        WITH CHECK (
            account_id IS NOT NULL
            AND current_setting('app.current_account_id', true) <> ''
            AND account_id = current_setting('app.current_account_id', true)::uuid
        )
        """
    )
    # Policy ADMIN : accès complet si rôle Admin.
    op.execute(
        f"""
        CREATE POLICY admin_full_access ON {table}
        FOR ALL
        USING (current_setting('app.current_role', true) = 'ADMIN')
        WITH CHECK (current_setting('app.current_role', true) = 'ADMIN')
        """
    )


def _disable_rls(table: str) -> None:
    """Désactiver les policies + RLS pour la downgrade."""
    op.execute(f"DROP POLICY IF EXISTS admin_full_access ON {table}")
    op.execute(f"DROP POLICY IF EXISTS pme_access_own_account ON {table}")
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # --- 1. ENUMs PostgreSQL ---
    if is_postgres:
        op.execute("DO $$ BEGIN CREATE TYPE user_role AS ENUM ('PME', 'ADMIN'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
        op.execute(
            "DO $$ BEGIN CREATE TYPE invitation_status AS ENUM "
            "('pending', 'accepted', 'expired', 'revoked'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
        )

    # --- 2. Table accounts ---
    op.create_table(
        "accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "plan",
            sa.String(length=32),
            server_default=sa.text("'free'"),
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
    )
    op.create_index("idx_accounts_is_active", "accounts", ["is_active"])

    # --- 3. Table refresh_tokens ---
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column("jti", sa.String(length=64), unique=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_jti", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    if is_postgres:
        op.execute(
            "CREATE INDEX idx_refresh_tokens_active ON refresh_tokens (user_id) "
            "WHERE revoked_at IS NULL"
        )

    # --- 4. Table account_invitations ---
    op.create_table(
        "account_invitations",
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
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("token_lookup", sa.String(length=64), nullable=False),
        sa.Column(
            "invited_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "accepted_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
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
    )
    op.create_index("idx_invitations_account_id", "account_invitations", ["account_id"])
    op.create_index(
        "idx_invitations_email_status", "account_invitations", ["email", "status"]
    )
    op.create_index(
        "idx_invitations_status_expires_at",
        "account_invitations",
        ["status", "expires_at"],
    )
    op.create_index(
        "idx_invitations_token_lookup",
        "account_invitations",
        ["token_lookup"],
        unique=True,
    )

    # --- 5. Extension users : role + account_id ---
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=16),
            server_default=sa.text("'PME'"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index("idx_users_account_id", "users", ["account_id"])
    op.create_index("idx_users_role", "users", ["role"])

    # --- 6. Backfill : créer 1 Account par company_name distinct, lier users ---
    if is_postgres:
        # 6.a Account par company_name distinct (non vide).
        op.execute(
            """
            INSERT INTO accounts (id, name, is_active, plan, created_at, updated_at)
            SELECT
                gen_random_uuid(),
                MIN(company_name),
                true,
                'free',
                NOW(),
                NOW()
            FROM users
            WHERE company_name IS NOT NULL AND company_name <> ''
            GROUP BY company_name
            """
        )
        # 6.b Lier users à leur Account (par jointure sur name).
        op.execute(
            """
            UPDATE users u
            SET account_id = a.id
            FROM accounts a
            WHERE u.company_name = a.name AND u.account_id IS NULL
            """
        )
        # 6.c Account 'default' pour les utilisateurs orphelins (PME).
        op.execute(
            """
            INSERT INTO accounts (id, name, is_active, plan, created_at, updated_at)
            SELECT gen_random_uuid(), 'default', true, 'free', NOW(), NOW()
            WHERE NOT EXISTS (SELECT 1 FROM accounts WHERE name = 'default')
            """
        )
        op.execute(
            """
            UPDATE users
            SET account_id = (SELECT id FROM accounts WHERE name = 'default' LIMIT 1)
            WHERE role = 'PME' AND account_id IS NULL
            """
        )
        # 6.d Backfill account_id sur chaque table métier via users.account_id.
        backfill_pairs = [
            ("company_profiles", "user_id"),
            ("documents", "user_id"),
            ("esg_assessments", "user_id"),
            ("carbon_assessments", "user_id"),
            ("credit_scores", "user_id"),
            ("fund_matches", "user_id"),
            ("fund_applications", "user_id"),
            ("action_plans", "user_id"),
            ("reminders", "user_id"),
            ("conversations", "user_id"),
            ("tool_call_logs", "user_id"),
            ("reports", "user_id"),
        ]
        for table, user_col in backfill_pairs:
            op.execute(
                f"""
                UPDATE {table} t
                SET account_id = u.account_id
                FROM users u
                WHERE t.{user_col} = u.id AND t.account_id IS NULL
                """
            )
        # action_items : héritent de action_plans.account_id
        op.execute(
            """
            UPDATE action_items ai
            SET account_id = ap.account_id
            FROM action_plans ap
            WHERE ai.plan_id = ap.id AND ai.account_id IS NULL
            """
        )
        # messages : héritent de conversations.account_id
        op.execute(
            """
            UPDATE messages m
            SET account_id = c.account_id
            FROM conversations c
            WHERE m.conversation_id = c.id AND m.account_id IS NULL
            """
        )
        # interactive_questions : héritent de conversations.account_id
        op.execute(
            """
            UPDATE interactive_questions iq
            SET account_id = c.account_id
            FROM conversations c
            WHERE iq.conversation_id = c.id AND iq.account_id IS NULL
            """
        )

    # --- 7. company_profiles : déduplication + UNIQUE partiel sur (account_id) ---
    # Le champ archived a été ajouté côté SQLAlchemy (server_default 'false').
    # Pour les profils en double sur un même account, on garde le plus récent.
    if is_postgres:
        op.execute(
            """
            UPDATE company_profiles cp
            SET archived = TRUE
            WHERE EXISTS (
                SELECT 1 FROM company_profiles cp2
                WHERE cp2.account_id = cp.account_id
                  AND cp2.account_id IS NOT NULL
                  AND cp2.created_at > cp.created_at
            )
            """
        )
        op.execute(
            "CREATE UNIQUE INDEX uq_company_profiles_account_active "
            "ON company_profiles (account_id) WHERE archived = false AND account_id IS NOT NULL"
        )

    # --- 8. ALTER COLUMN account_id NOT NULL sur les tables métier (PME) ---
    if is_postgres:
        for table in METIER_TABLES:
            op.execute(f"ALTER TABLE {table} ALTER COLUMN account_id SET NOT NULL")

    # --- 9. CHECK constraint sur users (role/account_id consistency) ---
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT users_role_account_consistency CHECK ("
        "(role = 'PME' AND account_id IS NOT NULL) OR "
        "(role = 'ADMIN' AND account_id IS NULL))"
    )

    # --- 10. Activation RLS sur les 14 tables métier ---
    if is_postgres:
        for table in METIER_TABLES:
            _enable_rls(table)


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # --- 1. Désactiver RLS sur les 14 tables métier ---
    if is_postgres:
        for table in METIER_TABLES:
            _disable_rls(table)

    # --- 2. Drop CHECK constraint users ---
    op.execute(
        "ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_account_consistency"
    )

    # --- 3. Drop UNIQUE partiel company_profiles ---
    if is_postgres:
        op.execute("DROP INDEX IF EXISTS uq_company_profiles_account_active")

    # --- 4. Drop colonne account_id sur tables métier ---
    for table in METIER_TABLES:
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS account_id")

    # --- 5. Drop colonne archived sur company_profiles ---
    op.execute("ALTER TABLE company_profiles DROP COLUMN IF EXISTS archived")

    # --- 6. Drop colonnes role + account_id sur users ---
    op.drop_index("idx_users_role", table_name="users")
    op.drop_index("idx_users_account_id", table_name="users")
    op.drop_column("users", "account_id")
    op.drop_column("users", "role")

    # --- 7. Drop tables ---
    op.drop_index("idx_invitations_token_lookup", table_name="account_invitations")
    op.drop_index("idx_invitations_status_expires_at", table_name="account_invitations")
    op.drop_index("idx_invitations_email_status", table_name="account_invitations")
    op.drop_index("idx_invitations_account_id", table_name="account_invitations")
    op.drop_table("account_invitations")

    if is_postgres:
        op.execute("DROP INDEX IF EXISTS idx_refresh_tokens_active")
    op.drop_index("idx_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("idx_accounts_is_active", table_name="accounts")
    op.drop_table("accounts")

    # --- 8. Drop ENUMs ---
    if is_postgres:
        op.execute("DROP TYPE IF EXISTS invitation_status")
        op.execute("DROP TYPE IF EXISTS user_role")
