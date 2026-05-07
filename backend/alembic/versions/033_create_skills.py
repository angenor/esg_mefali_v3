"""F23 — Create ``skills`` table for Playbooks Métier.

Revision ID: 033_create_skills
Revises: 032_add_validation_error_tool_call_logs
Create Date: 2026-05-07

Crée la table ``skills`` (cf. ``specs/033-skills-playbooks-metier/data-model.md``).

Colonnes (18) :

- id (UUID PK), name (VARCHAR(100) UNIQUE), domain (VARCHAR(50) — enum check 7
  valeurs), version (VARCHAR(50) default "1.0.0"), prompt_expert (TEXT),
  procedure (TEXT), tool_whitelist (JSONB), sources (JSONB), activation_rules
  (JSONB), golden_examples (JSONB), status (VARCHAR(20) default "draft" —
  enum check), created_by (UUID FK users RESTRICT), verified_by (UUID FK users
  RESTRICT NULLABLE), valid_from (DATE), valid_to (DATE NULLABLE), superseded_by
  (UUID self-FK SET NULL NULLABLE), created_at, updated_at (TIMESTAMP TZ).

Contraintes CHECK :
- ``skills_domain_chk`` : 7 valeurs autorisées.
- ``skills_status_chk`` : draft / published.
- ``skills_four_eyes_chk`` : ``verified_by`` ≠ ``created_by`` (4-yeux).

Indexes :
- ``skills_pkey``, ``skills_name_key`` (auto).
- ``ix_skills_domain_status_validto`` BTREE (domain, status, valid_to).
- ``ix_skills_status`` BTREE (status).
- ``ix_skills_activation_rules_gin`` GIN sur activation_rules (PG only).

Compatibilité SQLite (tests) : JSONB → JSON, pas d'index GIN, pas d'ENUM
PostgreSQL natif (les CHECK constraints suffisent).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "033_create_skills"
down_revision: Union[str, None] = "032_add_validation_error_tool_call_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crée la table ``skills`` + indexes + CheckConstraints."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    json_type = postgresql.JSONB() if is_postgres else sa.JSON()

    op.create_table(
        "skills",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("domain", sa.String(50), nullable=False),
        sa.Column(
            "version",
            sa.String(50),
            nullable=False,
            server_default="1.0.0",
        ),
        sa.Column("prompt_expert", sa.Text, nullable=False),
        sa.Column("procedure", sa.Text, nullable=False),
        sa.Column("tool_whitelist", json_type, nullable=False),
        sa.Column("sources", json_type, nullable=False),
        sa.Column("activation_rules", json_type, nullable=False),
        sa.Column("golden_examples", json_type, nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "created_by",
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
            "valid_from",
            sa.Date,
            nullable=False,
            server_default=sa.func.current_date(),
        ),
        sa.Column("valid_to", sa.Date, nullable=True),
        sa.Column(
            "superseded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("skills.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
        sa.UniqueConstraint("name", name="skills_name_key"),
        sa.CheckConstraint(
            "domain IN ('diagnostic_esg', 'scoring_referentiel', 'carbon_calc', "
            "'dossier', 'intermediaire', 'attestation', 'credit_score')",
            name="skills_domain_chk",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published')",
            name="skills_status_chk",
        ),
        sa.CheckConstraint(
            "verified_by IS NULL OR verified_by != created_by",
            name="skills_four_eyes_chk",
        ),
    )

    op.create_index(
        "ix_skills_domain_status_validto",
        "skills",
        ["domain", "status", "valid_to"],
    )
    op.create_index(
        "ix_skills_status",
        "skills",
        ["status"],
    )

    # Index GIN sur activation_rules : PostgreSQL only.
    if is_postgres:
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_skills_activation_rules_gin "
            "ON skills USING gin (activation_rules)"
        )


def downgrade() -> None:
    """Drop la table ``skills`` + ses indexes."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP INDEX IF EXISTS ix_skills_activation_rules_gin")
    op.drop_index("ix_skills_status", table_name="skills")
    op.drop_index("ix_skills_domain_status_validto", table_name="skills")
    op.drop_table("skills")
