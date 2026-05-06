"""F01 — Catalogue de sources verifiables (sourcage obligatoire).

Revision ID: 020_sources_catalog
Revises: 10b2tools_offered
Create Date: 2026-05-06

Cette migration introduit 11 nouvelles tables :
- sources : entite de premier rang (workflow 4-yeux)
- indicators, criteria, formulas, thresholds : entites factuelles ESG
- referentials, referential_indicators : referentiels (jointure N-N)
- emission_factors : facteurs d'emission ADEME/IPCC/IEA
- required_documents : documents exiges par fonds/intermediaire
- simulation_factors : constantes de simulation (status pending/verified)
- unsourced_flags : journal append-only des flag_unsourced

Contraintes structurelles :
- sources : CHECK 4-yeux (verified_by != captured_by)
- sources : CHECK coherence verification_status / verified_by / verified_at
- simulation_factors : CHECK status='verified' XOR source_id NULL

Trigger PostgreSQL :
- enforce_published_requires_verified_sources sur 7 tables
  (indicators, criteria, formulas, thresholds, emission_factors,
   referentials, required_documents) : empeche le passage `published` si
  la source liee n'est pas en verification_status='verified'.

Migration additive : aucune table existante n'est modifiee. Les colonnes
`publication_status` sur funds/intermediaires sont laissees a F07
(refactor catalogue offre fonds-intermediaire).

Marqueurs F02/F03 documentes en commentaires SQLAlchemy : la colonne
`account_id` sera ajoutee en F02 multi-tenant ; le mixin Auditable sera
applique en F03 audit log.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "020_sources_catalog"
down_revision: Union[str, None] = "10b2tools_offered"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- helpers ---


def _has_pgvector() -> bool:
    """Detecter si l'extension pgvector est installee."""
    bind = op.get_bind()
    try:
        result = bind.execute(
            sa.text(
                "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
            )
        )
        return result.scalar() is not None
    except Exception:
        return False


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


# --- upgrade ---


def upgrade() -> None:
    """Creer les 11 tables du catalogue F01 + trigger publication-gating."""

    has_pgvector = _has_pgvector()

    # ============================
    # 1. Table `sources`
    # ============================
    sources_columns = [
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), nullable=False,
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("publisher", sa.String(100), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("date_publi", sa.Date(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(200), nullable=True),
        sa.Column(
            "captured_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column("captured_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "verification_status", sa.String(20),
            server_default="draft", nullable=False,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outdated_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    ]

    if has_pgvector:
        # Embedding optionnel pour search_source hybride.
        sources_columns.append(
            sa.Column(
                "embedding",
                postgresql.ARRAY(sa.Float),  # placeholder, alembic ne supporte pas Vector natif
                nullable=True,
            )
        )

    op.create_table(
        "sources",
        *sources_columns,
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["captured_by"], ["users.id"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["verified_by"], ["users.id"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "verified_by IS NULL OR verified_by != captured_by",
            name="sources_four_eyes_chk",
        ),
        sa.CheckConstraint(
            "verification_status IN ('draft','pending','verified','outdated')",
            name="sources_status_chk",
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

    op.create_index(
        "sources_url_uniq_idx", "sources", ["url"], unique=True,
    )
    op.create_index("sources_publisher_idx", "sources", ["publisher"])
    op.create_index(
        "sources_verification_status_idx", "sources", ["verification_status"],
    )

    # Index full-text francais sur (title || publisher || section)
    op.execute(sa.text(
        "CREATE INDEX sources_title_publisher_fts_idx ON sources "
        "USING GIN (to_tsvector('french', "
        "coalesce(title,'') || ' ' || coalesce(publisher,'') || ' ' "
        "|| coalesce(section,'')))"
    ))

    if has_pgvector:
        # Index HNSW sur embedding (pgvector). Best-effort : ignorer si echec.
        # En pratique on convertira la colonne ARRAY en vector(1536) via ALTER
        # une fois pgvector confirmee.
        op.execute(sa.text(
            "ALTER TABLE sources DROP COLUMN embedding"
        ))
        op.execute(sa.text(
            "ALTER TABLE sources ADD COLUMN embedding vector(1536)"
        ))
        op.execute(sa.text(
            "CREATE INDEX sources_embedding_hnsw_idx ON sources "
            "USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        ))

    # ============================
    # 2. Table `indicators`
    # ============================
    op.create_table(
        "indicators",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), nullable=False,
        ),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("pillar", sa.String(20), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "publication_status", sa.String(20),
            server_default="draft", nullable=False,
        ),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="indicators_code_uniq"),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT",
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

    # ============================
    # 3. Table `referentials`
    # ============================
    op.create_table(
        "referentials",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), nullable=False,
        ),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "publication_status", sa.String(20),
            server_default="draft", nullable=False,
        ),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="referentials_code_uniq"),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "publication_status IN ('draft','published')",
            name="referentials_publication_status_chk",
        ),
    )

    # ============================
    # 4. Table `referential_indicators` (jointure N-N)
    # ============================
    op.create_table(
        "referential_indicators",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), nullable=False,
        ),
        sa.Column(
            "referential_id", postgresql.UUID(as_uuid=True), nullable=False,
        ),
        sa.Column(
            "indicator_id", postgresql.UUID(as_uuid=True), nullable=False,
        ),
        sa.Column(
            "weight", sa.Numeric(4, 2), server_default="1.00", nullable=False,
        ),
        sa.Column("threshold", sa.Numeric(10, 2), nullable=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["referential_id"], ["referentials.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["indicator_id"], ["indicators.id"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "referential_id", "indicator_id", name="referential_indicators_uniq",
        ),
    )

    # ============================
    # 5. Table `criteria`
    # ============================
    op.create_table(
        "criteria",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), nullable=False,
        ),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("expression", postgresql.JSONB(), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "publication_status", sa.String(20),
            server_default="draft", nullable=False,
        ),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="criteria_code_uniq"),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "publication_status IN ('draft','published')",
            name="criteria_publication_status_chk",
        ),
    )

    # ============================
    # 6. Table `formulas`
    # ============================
    op.create_table(
        "formulas",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), nullable=False,
        ),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("expression", sa.Text(), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "publication_status", sa.String(20),
            server_default="draft", nullable=False,
        ),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="formulas_code_uniq"),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "publication_status IN ('draft','published')",
            name="formulas_publication_status_chk",
        ),
    )

    # ============================
    # 7. Table `thresholds`
    # ============================
    op.create_table(
        "thresholds",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), nullable=False,
        ),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("value", sa.Numeric(20, 2), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("scope", sa.String(100), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "publication_status", sa.String(20),
            server_default="draft", nullable=False,
        ),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="thresholds_code_uniq"),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "publication_status IN ('draft','published')",
            name="thresholds_publication_status_chk",
        ),
    )

    # ============================
    # 8. Table `emission_factors`
    # ============================
    op.create_table(
        "emission_factors",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), nullable=False,
        ),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("country", sa.String(50), nullable=False),
        sa.Column("value", sa.Numeric(10, 4), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "publication_status", sa.String(20),
            server_default="draft", nullable=False,
        ),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="emission_factors_code_uniq"),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "publication_status IN ('draft','published')",
            name="emission_factors_publication_status_chk",
        ),
    )
    op.create_index(
        "emission_factors_category_idx", "emission_factors", ["category"],
    )
    op.create_index(
        "emission_factors_category_country_idx",
        "emission_factors", ["category", "country"],
    )

    # ============================
    # 9. Table `required_documents`
    # ============================
    # Detection des tables liees (peut etre absente sur installations partielles).
    has_funds = _table_exists("funds")
    has_intermediaries = _table_exists("intermediaries")

    rd_fk_constraints: list = []
    if has_funds:
        rd_fk_constraints.append(
            sa.ForeignKeyConstraint(
                ["fund_id"], ["funds.id"], ondelete="CASCADE",
            )
        )
    if has_intermediaries:
        rd_fk_constraints.append(
            sa.ForeignKeyConstraint(
                ["intermediary_id"], ["intermediaries.id"], ondelete="CASCADE",
            )
        )

    op.create_table(
        "required_documents",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), nullable=False,
        ),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("fund_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "intermediary_id", postgresql.UUID(as_uuid=True), nullable=True,
        ),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "publication_status", sa.String(20),
            server_default="draft", nullable=False,
        ),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        *rd_fk_constraints,
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT",
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

    # ============================
    # 10. Table `simulation_factors`
    # ============================
    op.create_table(
        "simulation_factors",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), nullable=False,
        ),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("value", sa.Numeric(20, 6), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("scope", sa.String(100), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status", sa.String(20),
            server_default="pending", nullable=False,
        ),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="simulation_factors_code_uniq"),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('verified','pending')",
            name="simulation_factors_status_chk",
        ),
        sa.CheckConstraint(
            "(status = 'verified' AND source_id IS NOT NULL) "
            "OR (status = 'pending' AND source_id IS NULL)",
            name="simulation_factors_source_required_chk",
        ),
    )

    # ============================
    # 11. Table `unsourced_flags`
    # ============================
    op.create_table(
        "unsourced_flags",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), nullable=False,
        ),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "conversation_id", postgresql.UUID(as_uuid=True), nullable=True,
        ),
        sa.Column(
            "message_id", postgresql.UUID(as_uuid=True), nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["messages.id"], ondelete="SET NULL",
        ),
    )
    op.create_index(
        "unsourced_flags_created_at_idx", "unsourced_flags", ["created_at"],
    )

    # ============================
    # Trigger : enforce_published_requires_verified_sources
    # ============================
    # Defense-in-depth : empeche le passage en `published` si la source n'est
    # pas en `verified`. Le service applicatif fait aussi le check pour un
    # message d'erreur lisible.
    op.execute(sa.text(
        """
        CREATE OR REPLACE FUNCTION assert_source_verified()
        RETURNS TRIGGER AS $$
        DECLARE
            source_status VARCHAR(20);
        BEGIN
            IF NEW.publication_status = 'published'
               AND OLD.publication_status = 'draft' THEN
                SELECT verification_status INTO source_status
                FROM sources WHERE id = NEW.source_id;
                IF source_status IS DISTINCT FROM 'verified' THEN
                    RAISE EXCEPTION
                        'Cannot publish: source % not verified (status=%)',
                        NEW.source_id, source_status
                        USING ERRCODE = '23514';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    ))

    for table in (
        "indicators", "criteria", "formulas", "thresholds",
        "emission_factors", "referentials", "required_documents",
    ):
        op.execute(sa.text(
            f"""
            CREATE TRIGGER {table}_publication_gating
            BEFORE UPDATE OF publication_status ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION assert_source_verified();
            """
        ))


def downgrade() -> None:
    """Rollback : drop des 11 tables, fonction trigger, et indexes."""
    # Drop triggers (dependent functions).
    for table in (
        "indicators", "criteria", "formulas", "thresholds",
        "emission_factors", "referentials", "required_documents",
    ):
        op.execute(sa.text(
            f"DROP TRIGGER IF EXISTS {table}_publication_gating ON {table}"
        ))
    op.execute(sa.text("DROP FUNCTION IF EXISTS assert_source_verified()"))

    # Drop tables in FK-respecting order.
    op.drop_index(
        "unsourced_flags_created_at_idx", table_name="unsourced_flags",
    )
    op.drop_table("unsourced_flags")
    op.drop_table("simulation_factors")
    op.drop_table("required_documents")
    op.drop_index(
        "emission_factors_category_country_idx", table_name="emission_factors",
    )
    op.drop_index(
        "emission_factors_category_idx", table_name="emission_factors",
    )
    op.drop_table("emission_factors")
    op.drop_table("thresholds")
    op.drop_table("formulas")
    op.drop_table("criteria")
    op.drop_table("referential_indicators")
    op.drop_table("referentials")
    op.drop_table("indicators")

    # Drop sources indexes (FTS / HNSW best-effort).
    op.execute(sa.text("DROP INDEX IF EXISTS sources_embedding_hnsw_idx"))
    op.execute(sa.text("DROP INDEX IF EXISTS sources_title_publisher_fts_idx"))
    op.drop_index(
        "sources_verification_status_idx", table_name="sources",
    )
    op.drop_index("sources_publisher_idx", table_name="sources")
    op.drop_index("sources_url_uniq_idx", table_name="sources")
    op.drop_table("sources")
