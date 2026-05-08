"""F20 — Create ``resources`` table for Bibliothèque Ressources.

Revision ID: 038_create_resources
Revises: 037_alternative_credit_data
Create Date: 2026-05-08

Crée la table ``resources`` pour la bibliothèque pédagogique
(cf. ``specs/038-bibliotheque-ressources/plan.md``).

Contraintes CHECK :
- ``resources_type_chk`` : 5 valeurs (guide/template_doc/video/faq/intermediary_guide).
- ``resources_language_chk`` : fr / en.
- ``resources_publication_status_chk`` : draft / published / archived.
- ``resources_four_eyes_chk`` : ``verified_by`` ≠ ``created_by`` (4-yeux).
- ``resources_view_count_chk`` : >= 0.
- ``resources_duration_chk`` : NULL ou >= 0.

Indexes :
- ``resources_pkey``, ``ix_resources_slug`` UNIQUE.
- ``ix_resources_lookup`` BTREE (type, publication_status, valid_to).
- ``ix_resources_intermediary`` BTREE (intermediary_id).
- ``ix_resources_views`` BTREE (view_count).
- ``ix_resources_search_gin`` GIN trigram (PG only) sur (title || ' ' || description).

Compatibilité SQLite (tests) : JSONB → JSON, pas d'index GIN trigram, pas
d'extension pg_trgm.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "038_create_resources"
down_revision: Union[str, None] = "037_alternative_credit_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crée la table ``resources`` + indexes + CheckConstraints."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    json_type = postgresql.JSONB() if is_postgres else sa.JSON()

    op.create_table(
        "resources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("content_md", sa.Text, nullable=True),
        sa.Column("file_url", sa.String(500), nullable=True),
        sa.Column("video_url", sa.String(500), nullable=True),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("category", json_type, nullable=False, server_default="[]"),
        sa.Column(
            "target_audience", json_type, nullable=False, server_default="[]"
        ),
        sa.Column(
            "language",
            sa.String(2),
            nullable=False,
            server_default="fr",
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "intermediary_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intermediaries.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "version",
            sa.String(50),
            nullable=False,
            server_default="1.0.0",
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
            sa.ForeignKey("resources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "publication_status",
            sa.String(20),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "view_count",
            sa.Integer,
            nullable=False,
            server_default="0",
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
        sa.UniqueConstraint("slug", name="resources_slug_key"),
        sa.CheckConstraint(
            "type IN ('guide','template_doc','video','faq','intermediary_guide')",
            name="resources_type_chk",
        ),
        sa.CheckConstraint(
            "language IN ('fr','en')",
            name="resources_language_chk",
        ),
        sa.CheckConstraint(
            "publication_status IN ('draft','published','archived')",
            name="resources_publication_status_chk",
        ),
        sa.CheckConstraint(
            "verified_by IS NULL OR verified_by != created_by",
            name="resources_four_eyes_chk",
        ),
        sa.CheckConstraint("view_count >= 0", name="resources_view_count_chk"),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="resources_duration_chk",
        ),
    )

    op.create_index(
        "ix_resources_lookup",
        "resources",
        ["type", "publication_status", "valid_to"],
    )
    op.create_index(
        "ix_resources_intermediary",
        "resources",
        ["intermediary_id"],
    )
    op.create_index(
        "ix_resources_views",
        "resources",
        ["view_count"],
    )

    # Index GIN trigram sur title + description : PostgreSQL only.
    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_resources_search_gin "
            "ON resources USING gin ((title || ' ' || description) gin_trgm_ops)"
        )


def downgrade() -> None:
    """Drop la table ``resources`` + ses indexes."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP INDEX IF EXISTS ix_resources_search_gin")
    op.drop_index("ix_resources_views", table_name="resources")
    op.drop_index("ix_resources_intermediary", table_name="resources")
    op.drop_index("ix_resources_lookup", table_name="resources")
    op.drop_table("resources")
