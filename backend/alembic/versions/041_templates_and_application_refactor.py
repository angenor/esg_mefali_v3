"""F15 — Create ``templates_dossier`` + extend ``fund_applications``.

Revision ID: 041_templates_and_application_refactor
Revises: 038_create_resources
Create Date: 2026-05-08

Migration F15 : génération de dossiers par offre.

Crée la table ``templates_dossier`` (catalogue admin-only) qui
matérialise le modèle officiel de dossier pour une Offre F07 ou un
fallback générique par instrument. Liée à une Skill F23 et à une
Source F01 (NOT NULL). Versioning F04, workflow draft/published F09
avec 4-yeux.

Étend ``fund_applications`` avec 4 colonnes (``template_id``,
``language``, ``attestation_id``, ``export_path``) et un index unique
partiel ``(project_id, offer_id) WHERE status != 'cancelled'`` pour
l'idempotence FR-023.

Contraintes CHECK :
- ``templates_dossier_instrument_chk`` (5 valeurs)
- ``templates_dossier_language_chk`` (fr/en)
- ``templates_dossier_status_chk`` (draft/published)
- ``templates_dossier_four_eyes_chk`` (verified_by ≠ captured_by)
- ``templates_dossier_published_requires_verifier_chk``

Compatibilité SQLite (tests) : JSONB → JSON, pas d'index GIN, pas de
RLS (skip si dialect != postgresql).

NOTE backfill : la colonne ``template_id`` est ajoutée NULLABLE en
phase 1 ; le passage en NOT NULL est différé à une migration séparée
post-MVP (étend la table ``fund_applications`` sans bloquer les tests
legacy SQLite).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "041_templates_and_application_refactor"
down_revision: Union[str, None] = "038_create_resources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crée la table ``templates_dossier`` + extension ``fund_applications``."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    json_type = postgresql.JSONB() if is_postgres else sa.JSON()

    # --- 1. CREATE TABLE templates_dossier ---
    op.create_table(
        "templates_dossier",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "offer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("offers.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("instrument_type", sa.String(50), nullable=False),
        sa.Column(
            "language",
            sa.String(2),
            nullable=False,
            server_default="fr",
        ),
        sa.Column("sections", json_type, nullable=False),
        sa.Column("required_documents", json_type, nullable=False),
        sa.Column("tone", sa.String(100), nullable=False),
        sa.Column("vocabulary_hints", json_type, nullable=True),
        sa.Column("anti_patterns", json_type, nullable=True),
        sa.Column(
            "skill_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("skills.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # VersioningMixin F04
        sa.Column(
            "version", sa.String(50), nullable=False, server_default="1.0",
        ),
        sa.Column(
            "valid_from", sa.Date, nullable=False,
            server_default=sa.text("CURRENT_DATE"),
        ),
        sa.Column("valid_to", sa.Date, nullable=True),
        sa.Column(
            "superseded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("templates_dossier.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Workflow F09
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="draft",
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
        sa.UniqueConstraint("name", name="templates_dossier_name_key"),
        sa.CheckConstraint(
            "instrument_type IN ('subvention', 'prêt_concessionnel', 'equity', "
            "'blending', 'mixte')",
            name="templates_dossier_instrument_chk",
        ),
        sa.CheckConstraint(
            "language IN ('fr', 'en')",
            name="templates_dossier_language_chk",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published')",
            name="templates_dossier_status_chk",
        ),
        sa.CheckConstraint(
            "verified_by IS NULL OR verified_by != captured_by",
            name="templates_dossier_four_eyes_chk",
        ),
        sa.CheckConstraint(
            "status = 'draft' OR verified_by IS NOT NULL",
            name="templates_dossier_published_requires_verifier_chk",
        ),
    )

    op.create_index(
        "idx_templates_offer_lang_status",
        "templates_dossier",
        ["offer_id", "language", "status"],
    )
    op.create_index(
        "idx_templates_instrument_lang_status",
        "templates_dossier",
        ["instrument_type", "language", "status"],
    )
    op.create_index(
        "idx_templates_skill",
        "templates_dossier",
        ["skill_id"],
    )

    # RLS PostgreSQL only
    if is_postgres:
        op.execute("ALTER TABLE templates_dossier ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE templates_dossier FORCE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY templates_public_read_published "
            "ON templates_dossier FOR SELECT "
            "USING (status = 'published' AND valid_to IS NULL)"
        )
        op.execute(
            "CREATE POLICY templates_admin_full_access "
            "ON templates_dossier FOR ALL "
            "USING (current_setting('app.current_role', true) = 'ADMIN') "
            "WITH CHECK (current_setting('app.current_role', true) = 'ADMIN')"
        )

    # --- 2. ALTER TABLE fund_applications (4 nouvelles colonnes) ---
    op.add_column(
        "fund_applications",
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("templates_dossier.id", ondelete="RESTRICT"),
            nullable=True,  # NULLABLE en phase 1, NOT NULL post-backfill (migration séparée)
        ),
    )
    op.add_column(
        "fund_applications",
        sa.Column(
            "language",
            sa.String(2),
            nullable=False,
            server_default="fr",
        ),
    )
    op.add_column(
        "fund_applications",
        sa.Column(
            "attestation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("attestations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "fund_applications",
        sa.Column("export_path", sa.String(500), nullable=True),
    )

    # CHECK language enum
    op.create_check_constraint(
        "fund_applications_language_chk",
        "fund_applications",
        "language IN ('fr', 'en')",
    )

    # Index unique partiel (idempotence FR-023) — PostgreSQL only.
    # NOTE F15 : l'enum ``application_status_enum`` actuel ne contient pas
    # 'cancelled' (statuts terminaux : accepted/rejected). Le filtre
    # WHERE est donc construit sur les statuts actifs (tout sauf
    # ``rejected``) — la sémantique d'idempotence FR-023 est préservée :
    # une candidature ``rejected`` n'empêche pas la PME de re-candidater
    # à la même paire (project, offer).
    if is_postgres:
        op.execute(
            "CREATE UNIQUE INDEX idx_fund_applications_project_offer_unique "
            "ON fund_applications (project_id, offer_id) "
            "WHERE status != 'rejected'"
        )


def downgrade() -> None:
    """Rollback — supprime tout ce que ``upgrade`` a créé."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # Supprimer index unique partiel (PG only)
    if is_postgres:
        op.execute(
            "DROP INDEX IF EXISTS idx_fund_applications_project_offer_unique"
        )

    # Drop CHECK constraint
    op.drop_constraint(
        "fund_applications_language_chk",
        "fund_applications",
        type_="check",
    )

    # Drop colonnes ajoutées sur fund_applications
    op.drop_column("fund_applications", "export_path")
    op.drop_column("fund_applications", "attestation_id")
    op.drop_column("fund_applications", "language")
    op.drop_column("fund_applications", "template_id")

    # Drop policies + table templates_dossier
    if is_postgres:
        op.execute(
            "DROP POLICY IF EXISTS templates_admin_full_access ON templates_dossier"
        )
        op.execute(
            "DROP POLICY IF EXISTS templates_public_read_published ON templates_dossier"
        )

    op.drop_index("idx_templates_skill", table_name="templates_dossier")
    op.drop_index(
        "idx_templates_instrument_lang_status", table_name="templates_dossier",
    )
    op.drop_index(
        "idx_templates_offer_lang_status", table_name="templates_dossier",
    )
    op.drop_table("templates_dossier")
