"""F045 - Matching projet-centric : +5 colonnes projects, +4 colonnes offer_matches.

Revision ID: 046_matching_projet_centric
Revises: 045_reports_polymorphic_assessment_fk
Create Date: 2026-05-21

Migration F045 :
- ``projects`` : ajoute taxonomie_verte_uemoa_aligned, gcf_priority_themes,
  gender_inclusion, vulnerable_populations, project_esg_score (+ CHECK 0..100,
  index BTREE taxonomie, index GIN gcf_priority_themes en PG).
- ``offer_matches`` : ajoute project_score, company_score (NOT NULL DEFAULT 0
  + CHECK 0..100), project_score_breakdown (JSONB NOT NULL DEFAULT '{}'),
  divergence_explanation (TEXT NULL), index composite (project_id, project_score,
  company_score).
- Backfill : project_score = company_score = global_score, project_score_breakdown
  = COALESCE(score_breakdown, '{}'), divergence_explanation NULL.

Round-trip up/down/up valide PostgreSQL.

Reference : specs/045-matching-projet-centric/data-model.md §1+§2, research.md R12.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "046_matching_projet_centric"
down_revision: Union[str, None] = "045_reports_polymorphic_assessment_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_type(is_postgres: bool):
    return postgresql.JSONB() if is_postgres else sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    json_empty_array = sa.text("'[]'::jsonb") if is_postgres else sa.text("'[]'")
    json_empty_obj = sa.text("'{}'::jsonb") if is_postgres else sa.text("'{}'")

    # ---------- projects : +5 colonnes ----------
    op.add_column(
        "projects",
        sa.Column(
            "taxonomie_verte_uemoa_aligned", sa.Boolean(), nullable=True,
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "gcf_priority_themes",
            _json_type(is_postgres),
            nullable=False,
            server_default=json_empty_array,
        ),
    )
    op.add_column(
        "projects",
        sa.Column("gender_inclusion", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column(
            "vulnerable_populations",
            _json_type(is_postgres),
            nullable=False,
            server_default=json_empty_array,
        ),
    )
    op.add_column(
        "projects",
        sa.Column("project_esg_score", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "projects_project_esg_score_chk",
        "projects",
        "project_esg_score IS NULL OR "
        "(project_esg_score >= 0 AND project_esg_score <= 100)",
    )
    # Index BTREE sur taxonomie_verte_uemoa_aligned
    op.create_index(
        "idx_projects_taxonomie_uemoa",
        "projects",
        ["taxonomie_verte_uemoa_aligned"],
    )
    # Index GIN sur gcf_priority_themes (PG only)
    if is_postgres:
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_projects_gcf_themes_gin "
            "ON projects USING GIN (gcf_priority_themes)"
        )

    # ---------- offer_matches : +4 colonnes ----------
    op.add_column(
        "offer_matches",
        sa.Column(
            "project_score",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "offer_matches",
        sa.Column(
            "company_score",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "offer_matches",
        sa.Column(
            "project_score_breakdown",
            _json_type(is_postgres),
            nullable=False,
            server_default=json_empty_obj,
        ),
    )
    op.add_column(
        "offer_matches",
        sa.Column(
            "divergence_explanation",
            sa.String(length=4000),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "offer_matches_project_score_chk",
        "offer_matches",
        "project_score BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "offer_matches_company_score_chk",
        "offer_matches",
        "company_score BETWEEN 0 AND 100",
    )
    op.create_index(
        "idx_offer_matches_project_company_score",
        "offer_matches",
        ["project_id", "project_score", "company_score"],
    )

    # ---------- Backfill ----------
    # project_score / company_score / project_score_breakdown depuis F14.
    if is_postgres:
        op.execute(
            "UPDATE offer_matches "
            "SET project_score = global_score, "
            "    company_score = global_score, "
            "    project_score_breakdown = COALESCE(score_breakdown, '{}'::jsonb) "
            "WHERE TRUE"
        )
    else:
        op.execute(
            "UPDATE offer_matches "
            "SET project_score = global_score, "
            "    company_score = global_score, "
            "    project_score_breakdown = COALESCE(score_breakdown, '{}')"
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # offer_matches : drop indexes, CHECK, colonnes (ordre inverse)
    op.drop_index(
        "idx_offer_matches_project_company_score", table_name="offer_matches",
    )
    op.drop_constraint(
        "offer_matches_company_score_chk", "offer_matches", type_="check",
    )
    op.drop_constraint(
        "offer_matches_project_score_chk", "offer_matches", type_="check",
    )
    op.drop_column("offer_matches", "divergence_explanation")
    op.drop_column("offer_matches", "project_score_breakdown")
    op.drop_column("offer_matches", "company_score")
    op.drop_column("offer_matches", "project_score")

    # projects : drop indexes, CHECK, colonnes
    if is_postgres:
        op.execute("DROP INDEX IF EXISTS idx_projects_gcf_themes_gin")
    op.drop_index("idx_projects_taxonomie_uemoa", table_name="projects")
    op.drop_constraint(
        "projects_project_esg_score_chk", "projects", type_="check",
    )
    op.drop_column("projects", "project_esg_score")
    op.drop_column("projects", "vulnerable_populations")
    op.drop_column("projects", "gender_inclusion")
    op.drop_column("projects", "gcf_priority_themes")
    op.drop_column("projects", "taxonomie_verte_uemoa_aligned")
