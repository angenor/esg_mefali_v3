"""F047 — Evaluation ESG-projet : tables project_esg_assessments + responses + extension criteria.

Revision ID: 047_project_esg_assessments
Revises: 046_matching_projet_centric
Create Date: 2026-05-21

Migration F047 :
- ``criteria`` : ajoute weight (NUMERIC(4,2), defaut 1.00), is_required (BOOL),
  applies_to_project (BOOL), referential_id (UUID NULL FK referentials) pour
  permettre la pondération F13 au niveau projet (research.md D9). Additif et
  réversible — aucune donnée F01 existante impactée (valeurs par défaut).
- Nouvelle table ``project_esg_assessments`` (multi-tenant F02, audit F03 via
  mixin Auditable, versioning F04 via colonnes referential_version/snapshot_data,
  RLS ENABLE+FORCE + 2 policies pme_access_own_account/admin_full_access).
- Nouvelle table ``project_esg_criterion_responses`` (1..N de l'évaluation,
  XOR source_id/unsourced, UNIQUE (assessment_id, criterion_id), RLS strict).
- Indexes BTREE lookup + partial WHERE state='finalized' + partial WHERE
  unsourced=true (audit qualité SC-009).

Round-trip up/down/up validé sur PostgreSQL (test_migration_047_round_trip.py).

Reference : specs/047-evaluation-esg-projet/data-model.md §Table 1+2,
research.md D8+D9+D10.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "047_project_esg_assessments"
down_revision: Union[str, None] = "046_matching_projet_centric"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_type(is_postgres: bool):
    return postgresql.JSONB() if is_postgres else sa.JSON()


def _uuid_type(is_postgres: bool):
    return postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36)


def _ts_type(is_postgres: bool):
    return postgresql.TIMESTAMP(timezone=True) if is_postgres else sa.DateTime()


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    json_empty_array = sa.text("'[]'::jsonb") if is_postgres else sa.text("'[]'")
    json_empty_obj = sa.text("'{}'::jsonb") if is_postgres else sa.text("'{}'")

    # ---------- 1) Extension table criteria (F13) ----------
    op.add_column(
        "criteria",
        sa.Column(
            "weight",
            sa.Numeric(4, 2),
            nullable=False,
            server_default=sa.text("1.00"),
        ),
    )
    op.add_column(
        "criteria",
        sa.Column(
            "is_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "criteria",
        sa.Column(
            "applies_to_project",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "criteria",
        sa.Column(
            "referential_id",
            _uuid_type(is_postgres),
            sa.ForeignKey("referentials.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "criteria_weight_chk",
        "criteria",
        "weight >= 0 AND weight <= 100",
    )
    op.create_index(
        "idx_criteria_applies_to_project",
        "criteria",
        ["applies_to_project", "referential_id"],
    )

    # ---------- 2) project_esg_assessments ----------
    op.create_table(
        "project_esg_assessments",
        sa.Column(
            "id",
            _uuid_type(is_postgres),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
        ),
        sa.Column(
            "account_id",
            _uuid_type(is_postgres),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            _uuid_type(is_postgres),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "referential_id",
            _uuid_type(is_postgres),
            sa.ForeignKey("referentials.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("referential_version", sa.String(16), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column(
            "pillar_scores",
            _json_type(is_postgres),
            nullable=False,
            server_default=json_empty_obj,
        ),
        sa.Column(
            "covered_criteria",
            _json_type(is_postgres),
            nullable=False,
            server_default=json_empty_array,
        ),
        sa.Column(
            "missing_criteria",
            _json_type(is_postgres),
            nullable=False,
            server_default=json_empty_array,
        ),
        sa.Column("coverage_rate", sa.Numeric(4, 3), nullable=True),
        sa.Column("snapshot_data", _json_type(is_postgres), nullable=True),
        sa.Column("finalized_at", _ts_type(is_postgres), nullable=True),
        sa.Column("superseded_at", _ts_type(is_postgres), nullable=True),
        sa.Column(
            "created_by",
            _uuid_type(is_postgres),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            _ts_type(is_postgres),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            _ts_type(is_postgres),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "state IN ('draft','finalized')",
            name="pea_state_chk",
        ),
        sa.CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="pea_score_range_chk",
        ),
        sa.CheckConstraint(
            "coverage_rate IS NULL OR (coverage_rate >= 0 AND coverage_rate <= 1)",
            name="pea_coverage_range_chk",
        ),
        sa.CheckConstraint(
            "(state = 'finalized' AND score IS NOT NULL AND finalized_at IS NOT NULL)"
            " OR state = 'draft'",
            name="pea_finalized_score_present_chk",
        ),
    )

    op.create_index(
        "idx_pea_lookup",
        "project_esg_assessments",
        ["account_id", "project_id", "referential_id"],
    )
    op.create_index(
        "idx_pea_state_account",
        "project_esg_assessments",
        ["account_id", "state"],
    )
    # Index partiel uniquement en PostgreSQL
    if is_postgres:
        op.execute(
            "CREATE INDEX idx_pea_finalized_active "
            "ON project_esg_assessments (project_id, referential_id) "
            "WHERE state = 'finalized' AND superseded_at IS NULL"
        )
        op.execute(
            "CREATE UNIQUE INDEX uq_pea_finalized_active_per_ref "
            "ON project_esg_assessments (account_id, project_id, referential_id) "
            "WHERE state = 'finalized' AND superseded_at IS NULL"
        )

    # ---------- 3) project_esg_criterion_responses ----------
    op.create_table(
        "project_esg_criterion_responses",
        sa.Column(
            "id",
            _uuid_type(is_postgres),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
        ),
        sa.Column(
            "account_id",
            _uuid_type(is_postgres),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assessment_id",
            _uuid_type(is_postgres),
            sa.ForeignKey("project_esg_assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "criterion_id",
            _uuid_type(is_postgres),
            sa.ForeignKey("criteria.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("response_type", sa.String(32), nullable=False),
        sa.Column("response_value", _json_type(is_postgres), nullable=False),
        sa.Column("normalized_score", sa.Numeric(4, 3), nullable=False),
        sa.Column(
            "source_id",
            _uuid_type(is_postgres),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "unsourced",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            _ts_type(is_postgres),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            _ts_type(is_postgres),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "assessment_id",
            "criterion_id",
            name="uq_one_response_per_criterion_per_assessment",
        ),
        sa.CheckConstraint(
            "response_type IN ('qcu','qcm','qcu_justification','qcm_justification',"
            "'numeric','money','free_text')",
            name="pecr_response_type_chk",
        ),
        sa.CheckConstraint(
            "normalized_score >= 0 AND normalized_score <= 1",
            name="pecr_normalized_score_range_chk",
        ),
        sa.CheckConstraint(
            "(source_id IS NOT NULL AND unsourced = false) "
            "OR (source_id IS NULL AND unsourced = true)",
            name="pecr_source_or_unsourced_chk",
        ),
    )

    op.create_index(
        "idx_pecr_assessment",
        "project_esg_criterion_responses",
        ["assessment_id"],
    )
    op.create_index(
        "idx_pecr_lookup",
        "project_esg_criterion_responses",
        ["account_id", "assessment_id", "criterion_id"],
    )
    if is_postgres:
        op.execute(
            "CREATE INDEX idx_pecr_unsourced "
            "ON project_esg_criterion_responses (assessment_id) "
            "WHERE unsourced = true"
        )

    # ---------- 4) RLS F02 (PostgreSQL uniquement) ----------
    if is_postgres:
        for table in ("project_esg_assessments", "project_esg_criterion_responses"):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
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
            op.execute(
                f"""
                CREATE POLICY admin_full_access ON {table}
                FOR ALL
                USING (current_setting('app.current_role', true) = 'ADMIN')
                WITH CHECK (current_setting('app.current_role', true) = 'ADMIN')
                """
            )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        for table in ("project_esg_criterion_responses", "project_esg_assessments"):
            op.execute(f"DROP POLICY IF EXISTS admin_full_access ON {table}")
            op.execute(f"DROP POLICY IF EXISTS pme_access_own_account ON {table}")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

        op.execute("DROP INDEX IF EXISTS idx_pecr_unsourced")
        op.execute("DROP INDEX IF EXISTS uq_pea_finalized_active_per_ref")
        op.execute("DROP INDEX IF EXISTS idx_pea_finalized_active")

    op.drop_index("idx_pecr_lookup", table_name="project_esg_criterion_responses")
    op.drop_index("idx_pecr_assessment", table_name="project_esg_criterion_responses")
    op.drop_table("project_esg_criterion_responses")

    op.drop_index("idx_pea_state_account", table_name="project_esg_assessments")
    op.drop_index("idx_pea_lookup", table_name="project_esg_assessments")
    op.drop_table("project_esg_assessments")

    op.drop_index("idx_criteria_applies_to_project", table_name="criteria")
    op.drop_constraint("criteria_weight_chk", "criteria", type_="check")
    op.drop_column("criteria", "referential_id")
    op.drop_column("criteria", "applies_to_project")
    op.drop_column("criteria", "is_required")
    op.drop_column("criteria", "weight")
