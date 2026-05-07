"""F06 — Entité Projet Vert : tables projects, project_documents + lien fund_applications.project_id.

Revision ID: 025_create_projects
Revises: 024_carbone_mix_uemoa
Create Date: 2026-05-07

Cette migration ajoute :

1. Table ``projects`` (multi-tenant F02, Auditable F03, Money typed F04).
2. Table de jointure ``project_documents``.
3. Colonne ``project_id`` UUID FK NOT NULL sur ``fund_applications`` (en deux
   temps : NULL transitoire avec backfill, puis NOT NULL).

Backfill : pour chaque ``FundApplication`` orpheline, génère un ``Project``
auto-généré (``auto_generated=true``) afin de matérialiser le triangle
``Entreprise 1—N Projets 1—N Candidatures vers Offres``.

RLS PostgreSQL F02 héritée : ENABLE+FORCE + 2 policies sur les 2 nouvelles
tables.
"""

from __future__ import annotations

import logging
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


logger = logging.getLogger(__name__)


# revision identifiers, used by Alembic.
revision: str = "025_create_projects"
down_revision: Union[str, None] = "024_carbone_mix_uemoa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # ============================================================
    # 1. CREATE TABLE projects
    # ============================================================
    op.create_table(
        "projects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"),
            primary_key=True,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "objective_env",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("maturity", sa.String(32), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("target_amount_amount", sa.Numeric(20, 2), nullable=True),
        sa.Column("target_amount_currency", sa.String(3), nullable=True),
        sa.Column("duration_months", sa.Integer(), nullable=True),
        sa.Column("financing_structure", sa.String(32), nullable=True),
        sa.Column("expected_impact_tco2e", sa.Numeric(20, 4), nullable=True),
        sa.Column("expected_jobs_created", sa.Integer(), nullable=True),
        sa.Column("expected_beneficiaries", sa.Integer(), nullable=True),
        sa.Column("expected_hectares_restored", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "expected_other_impacts",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column("location_country", sa.String(2), nullable=True),
        sa.Column("location_region", sa.String(100), nullable=True),
        sa.Column(
            "auto_generated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
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
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(target_amount_amount IS NULL AND target_amount_currency IS NULL) "
            "OR (target_amount_amount IS NOT NULL AND target_amount_currency IS NOT NULL)",
            name="projects_target_amount_pair_chk",
        ),
        sa.CheckConstraint(
            "target_amount_amount IS NULL OR target_amount_amount >= 0",
            name="projects_target_amount_positive_chk",
        ),
        sa.CheckConstraint(
            "target_amount_currency IS NULL OR target_amount_currency IN "
            "('XOF','EUR','USD','GBP','JPY')",
            name="projects_target_amount_currency_chk",
        ),
        sa.CheckConstraint(
            "duration_months IS NULL OR duration_months > 0",
            name="projects_duration_months_positive_chk",
        ),
        sa.CheckConstraint(
            "expected_jobs_created IS NULL OR expected_jobs_created >= 0",
            name="projects_expected_jobs_positive_chk",
        ),
        sa.CheckConstraint(
            "expected_beneficiaries IS NULL OR expected_beneficiaries >= 0",
            name="projects_expected_beneficiaries_positive_chk",
        ),
        sa.CheckConstraint(
            "expected_hectares_restored IS NULL OR expected_hectares_restored >= 0",
            name="projects_expected_hectares_positive_chk",
        ),
        sa.CheckConstraint(
            "expected_impact_tco2e IS NULL OR expected_impact_tco2e >= 0",
            name="projects_expected_impact_tco2e_positive_chk",
        ),
        sa.CheckConstraint(
            "status IN ('draft','seeking_funding','funded','in_execution',"
            "'closed','cancelled')",
            name="projects_status_chk",
        ),
        sa.CheckConstraint(
            "maturity IS NULL OR maturity IN "
            "('ideation','pre_feasibility','pilot','scale','replication')",
            name="projects_maturity_chk",
        ),
        sa.CheckConstraint(
            "financing_structure IS NULL OR financing_structure IN "
            "('subvention','pret_concessionnel','equity','blending','mixte')",
            name="projects_financing_structure_chk",
        ),
        sa.CheckConstraint(
            "location_country IS NULL OR length(location_country) = 2",
            name="projects_location_country_chk",
        ),
    )
    op.create_index(
        "idx_projects_account_status",
        "projects",
        ["account_id", "status"],
    )
    op.create_index(
        "idx_projects_account_maturity",
        "projects",
        ["account_id", "maturity"],
    )

    # ============================================================
    # 2. CREATE TABLE project_documents
    # ============================================================
    op.create_table(
        "project_documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"),
            primary_key=True,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"),
            nullable=False,
        ),
        sa.Column("doc_type", sa.String(32), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "document_id", name="project_documents_unique",
        ),
        sa.CheckConstraint(
            "doc_type IN ('feasibility_study','business_plan',"
            "'impact_assessment','support_letter','other')",
            name="project_documents_doc_type_chk",
        ),
    )
    op.create_index(
        "idx_project_documents_project_id",
        "project_documents",
        ["project_id"],
    )
    op.create_index(
        "idx_project_documents_document_id",
        "project_documents",
        ["document_id"],
    )

    # ============================================================
    # 3. ALTER TABLE fund_applications ADD COLUMN project_id (NULLABLE)
    # ============================================================
    op.add_column(
        "fund_applications",
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fund_applications_project_id_fkey",
        "fund_applications",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "idx_fund_applications_project_id",
        "fund_applications",
        ["project_id"],
    )

    # ============================================================
    # 4. Backfill : pour chaque fund_application orpheline, créer un projet auto-généré.
    # ============================================================
    if is_postgres:
        # CTE PostgreSQL : créer 1 projet par application orpheline.
        # On utilise une jointure par UUID stable (UPDATE+RETURNING avec FROM).
        bind.execute(sa.text("""
            WITH orphans AS (
              SELECT
                fa.id AS application_id,
                fa.account_id AS account_id,
                fa.created_at AS created_at,
                fa.updated_at AS updated_at,
                COALESCE(f.name, '(fonds inconnu)') AS fund_name,
                CASE
                  WHEN fa.status::text = 'accepted' THEN 'funded'
                  ELSE 'seeking_funding'
                END AS status,
                gen_random_uuid() AS new_project_id
              FROM fund_applications fa
              LEFT JOIN funds f ON f.id = fa.fund_id
              WHERE fa.project_id IS NULL
                AND fa.account_id IS NOT NULL
            ),
            inserted AS (
              INSERT INTO projects (
                id, account_id, name, description, objective_env,
                status, auto_generated, created_at, updated_at
              )
              SELECT
                o.new_project_id,
                o.account_id,
                LEFT(
                  'Projet hérité — ' || o.fund_name ||
                  ' (' || TO_CHAR(o.created_at, 'YYYY-MM') || ')',
                  200
                ),
                'Projet créé automatiquement lors de la migration F06.',
                '[]'::jsonb,
                o.status,
                TRUE,
                o.created_at,
                o.updated_at
              FROM orphans o
              RETURNING id
            )
            UPDATE fund_applications fa
            SET project_id = o.new_project_id
            FROM orphans o
            WHERE fa.id = o.application_id
              AND fa.project_id IS NULL;
        """))

        result = bind.execute(sa.text(
            "SELECT COUNT(*) FROM fund_applications WHERE project_id IS NULL"
        ))
        remaining = result.scalar() or 0
        if remaining > 0:
            logger.warning(
                "[F06 migration] %d fund_applications n'ont pas pu "
                "être backfillées (account_id NULL ou autre).",
                remaining,
            )
            print(
                f"[F06 migration] WARNING : {remaining} fund_applications "
                "n'ont pas pu être backfillées (account_id NULL ou autre)."
            )
    else:
        # SQLite (tests) : Python loop équivalent.
        from datetime import datetime as _dt

        meta = sa.MetaData()
        meta.reflect(bind=bind)
        applications_t = meta.tables["fund_applications"]
        funds_t = meta.tables["funds"]
        projects_t = meta.tables["projects"]

        orphans = bind.execute(
            sa.select(applications_t).where(
                applications_t.c.project_id.is_(None)
            )
        ).fetchall()
        for app in orphans:
            if app.account_id is None:
                continue
            fund = bind.execute(
                sa.select(funds_t).where(funds_t.c.id == app.fund_id)
            ).first()
            fund_name = fund.name if fund is not None else "(fonds inconnu)"
            project_id = uuid.uuid4()
            project_status = (
                "funded" if str(app.status) == "accepted" else "seeking_funding"
            )
            created_at = app.created_at or _dt.utcnow()
            updated_at = app.updated_at or created_at
            ym = (
                created_at.strftime("%Y-%m")
                if hasattr(created_at, "strftime")
                else "????-??"
            )
            label = (
                f"Projet hérité — {fund_name} ({ym})"
            )[:200]
            description = (
                "Projet créé automatiquement lors de la migration F06."
            )
            bind.execute(
                sa.insert(projects_t).values(
                    id=str(project_id),
                    account_id=str(app.account_id),
                    name=label,
                    description=description,
                    objective_env=[],
                    status=project_status,
                    auto_generated=True,
                    created_at=created_at,
                    updated_at=updated_at,
                )
            )
            bind.execute(
                sa.update(applications_t)
                .where(applications_t.c.id == app.id)
                .values(project_id=str(project_id))
            )

    # ============================================================
    # 5. ALTER TABLE fund_applications ALTER COLUMN project_id SET NOT NULL
    #    (uniquement si toutes les lignes ont été backfillées)
    # ============================================================
    if is_postgres:
        # Vérifier qu'aucune ligne ne reste NULL avant d'imposer NOT NULL.
        result = bind.execute(sa.text(
            "SELECT COUNT(*) FROM fund_applications WHERE project_id IS NULL"
        ))
        if (result.scalar() or 0) == 0:
            op.alter_column("fund_applications", "project_id", nullable=False)
        else:
            logger.warning(
                "[F06 migration] project_id reste NULL pour certaines lignes : "
                "NOT NULL non appliqué (rejouer la migration après nettoyage)."
            )
    else:
        # SQLite : ALTER COLUMN ... SET NOT NULL n'est pas supporté.
        # On laisse nullable=True ; les tests Python valident la contrainte
        # via Pydantic / service.
        pass

    # ============================================================
    # 6. RLS PostgreSQL — ENABLE+FORCE + 2 policies par table
    # ============================================================
    if is_postgres:
        for table in ("projects", "project_documents"):
            bind.execute(
                sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            )
            bind.execute(
                sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            )

        # Policies sur projects
        bind.execute(sa.text("""
            CREATE POLICY pme_access_own_account ON projects
              FOR ALL
              USING (
                current_setting('app.current_account_id', true)::uuid = account_id
                AND current_setting('app.current_role', true) = 'PME'
              );
        """))
        bind.execute(sa.text("""
            CREATE POLICY admin_full_access ON projects
              FOR ALL
              USING (current_setting('app.current_role', true) = 'ADMIN');
        """))

        # Policies sur project_documents (filtrage via FK projects)
        bind.execute(sa.text("""
            CREATE POLICY pme_access_via_project ON project_documents
              FOR ALL
              USING (
                EXISTS (
                  SELECT 1 FROM projects p
                  WHERE p.id = project_documents.project_id
                    AND current_setting('app.current_account_id', true)::uuid = p.account_id
                    AND current_setting('app.current_role', true) = 'PME'
                )
              );
        """))
        bind.execute(sa.text("""
            CREATE POLICY admin_full_access ON project_documents
              FOR ALL
              USING (current_setting('app.current_role', true) = 'ADMIN');
        """))


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Drop RLS policies
    if is_postgres:
        for table in ("projects", "project_documents"):
            bind.execute(sa.text(
                f"DROP POLICY IF EXISTS pme_access_own_account ON {table}"
            ))
            bind.execute(sa.text(
                f"DROP POLICY IF EXISTS admin_full_access ON {table}"
            ))
        bind.execute(sa.text(
            "DROP POLICY IF EXISTS pme_access_via_project ON project_documents"
        ))

    # 2. ALTER TABLE fund_applications ALTER COLUMN project_id DROP NOT NULL
    if is_postgres:
        op.alter_column("fund_applications", "project_id", nullable=True)

    # 3. DROP CONSTRAINT FK + INDEX
    op.drop_index("idx_fund_applications_project_id", "fund_applications")
    op.drop_constraint(
        "fund_applications_project_id_fkey",
        "fund_applications",
        type_="foreignkey",
    )

    # 4. DROP COLUMN project_id sur fund_applications
    op.drop_column("fund_applications", "project_id")

    # 5. DROP TABLE project_documents
    op.drop_index("idx_project_documents_document_id", "project_documents")
    op.drop_index("idx_project_documents_project_id", "project_documents")
    op.drop_table("project_documents")

    # 6. DROP TABLE projects
    op.drop_index("idx_projects_account_maturity", "projects")
    op.drop_index("idx_projects_account_status", "projects")
    op.drop_table("projects")
