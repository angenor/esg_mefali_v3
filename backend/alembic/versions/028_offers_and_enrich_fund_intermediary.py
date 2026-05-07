"""F07 — Entité Offre = Couple Fonds × Intermédiaire + enrichissement.

Revision ID: 028_offers_and_enrich
Revises: 027_consents_and_deletion
Create Date: 2026-05-07

Cette migration crée :

1. Enrichissement ``funds`` (instruments, theme, submission_mode, source_id,
   publication_status, submission_calendar) + renommage enum ``fund_type``
   (``international`` → ``multilateral``, etc.).
2. Enrichissement ``intermediaries`` (code, required_documents,
   fees_structured, processing_time, disbursement_time,
   submission_portal_url, success_rate, total_funded_volume,
   source_id, publication_status).
3. Enrichissement ``fund_intermediaries`` (accredited_from NOT NULL,
   accredited_to, max_amount_per_fund, accreditation_source_id).
4. Nouvelle table ``offers`` (16 colonnes business + 4 versioning + indexes
   + CHECK constraints + UNIQUE composite).
5. Nouvelle colonne ``fund_applications.offer_id`` (NOT NULL post-backfill).
6. Backfill : seed Source ``system://mefali/direct-singleton`` puis
   intermédiaire singleton ``code='DIRECT'`` puis création offres pour
   toutes les paires existantes + tous les fonds direct, puis liaison
   ``fund_applications.offer_id``.

Sur SQLite (tests CI), CHECK regex et certains aspects PostgreSQL-only
sont skippés.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

logger = logging.getLogger(__name__)


# revision identifiers, used by Alembic.
revision: str = "028_offers_and_enrich"
down_revision: Union[str, None] = "027_consents_and_deletion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Constantes — code du singleton DIRECT (intermédiaire représentant la
# soumission directe, utilisé pour uniformiser le modèle Offer).
DIRECT_SINGLETON_CODE = "DIRECT"
DIRECT_SOURCE_URL = "system://mefali/direct-singleton"


def _is_postgres() -> bool:
    bind = op.get_bind()
    return bind.dialect.name == "postgresql"


def _jsonb_type():
    """Type JSON portable PG (JSONB) / SQLite (JSON)."""
    if _is_postgres():
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def _uuid_type():
    """Type UUID portable PG / SQLite."""
    return postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite")


# ---------------------------------------------------------------------------
# UPGRADE
# ---------------------------------------------------------------------------


def upgrade() -> None:
    is_pg = _is_postgres()

    # =====================================================================
    # 1. ENRICHISSEMENT funds
    # =====================================================================

    op.add_column(
        "funds",
        sa.Column(
            "instruments", _jsonb_type(),
            nullable=False, server_default="[]",
        ),
    )
    op.add_column(
        "funds",
        sa.Column(
            "theme", _jsonb_type(),
            nullable=False, server_default="[]",
        ),
    )
    op.add_column(
        "funds",
        sa.Column(
            "submission_mode", sa.String(30),
            nullable=False, server_default="rolling",
        ),
    )
    op.add_column(
        "funds",
        sa.Column("submission_calendar", _jsonb_type(), nullable=True),
    )
    op.add_column(
        "funds",
        sa.Column(
            "source_id", _uuid_type(),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=True,  # NOT NULL post-backfill
        ),
    )
    op.add_column(
        "funds",
        sa.Column(
            "publication_status", sa.String(20),
            nullable=False, server_default="draft",
        ),
    )

    # CHECK constraints sur funds
    if is_pg:
        op.create_check_constraint(
            "funds_submission_mode_chk", "funds",
            "submission_mode IN ('rolling', 'call_for_proposals')",
        )
        op.create_check_constraint(
            "funds_publication_status_chk", "funds",
            "publication_status IN ('draft', 'published')",
        )
        # Indexes
        op.create_index(
            "idx_funds_theme_gin", "funds", ["theme"],
            postgresql_using="gin",
            postgresql_ops={"theme": "jsonb_path_ops"},
        )
        op.create_index(
            "idx_funds_instruments_gin", "funds", ["instruments"],
            postgresql_using="gin",
            postgresql_ops={"instruments": "jsonb_path_ops"},
        )
        op.create_index(
            "idx_funds_publication_status", "funds", ["publication_status"],
        )

    # =====================================================================
    # 1b. RENOMMAGE enum fund_type (postgres only — sqlite garde VARCHAR)
    # =====================================================================
    if is_pg:
        # 1. Création nouveau type enum v2
        op.execute(
            "CREATE TYPE fund_type_v2_enum AS ENUM ("
            "'multilateral','bilateral','regional','national','private','carbon_marketplace')"
        )
        # 2. Conversion des valeurs existantes via USING
        op.execute(
            "ALTER TABLE funds ALTER COLUMN fund_type TYPE fund_type_v2_enum "
            "USING (CASE fund_type::text "
            "  WHEN 'international' THEN 'multilateral' "
            "  WHEN 'regional' THEN 'regional' "
            "  WHEN 'national' THEN 'national' "
            "  WHEN 'carbon_market' THEN 'carbon_marketplace' "
            "  WHEN 'local_bank_green_line' THEN 'private' "
            "  ELSE 'private' "
            "END::fund_type_v2_enum)"
        )
        # 3. Drop ancien type
        op.execute("DROP TYPE fund_type_enum")
        # 4. Rename pour cohérence
        op.execute("ALTER TYPE fund_type_v2_enum RENAME TO fund_type_enum")

    # =====================================================================
    # 2. ENRICHISSEMENT intermediaries
    # =====================================================================

    op.add_column("intermediaries", sa.Column("code", sa.String(50), nullable=True))
    op.add_column(
        "intermediaries",
        sa.Column(
            "required_documents", _jsonb_type(),
            nullable=False, server_default="[]",
        ),
    )
    op.add_column(
        "intermediaries",
        sa.Column("fees_structured", _jsonb_type(), nullable=True),
    )
    op.add_column(
        "intermediaries",
        sa.Column("processing_time_days_min", sa.Integer(), nullable=True),
    )
    op.add_column(
        "intermediaries",
        sa.Column("processing_time_days_max", sa.Integer(), nullable=True),
    )
    op.add_column(
        "intermediaries",
        sa.Column("disbursement_time_days_min", sa.Integer(), nullable=True),
    )
    op.add_column(
        "intermediaries",
        sa.Column("disbursement_time_days_max", sa.Integer(), nullable=True),
    )
    op.add_column(
        "intermediaries",
        sa.Column("submission_portal_url", sa.String(500), nullable=True),
    )
    op.add_column(
        "intermediaries",
        sa.Column("success_rate", sa.Numeric(5, 4), nullable=True),
    )
    op.add_column(
        "intermediaries",
        sa.Column("total_funded_volume_amount", sa.Numeric(20, 2), nullable=True),
    )
    op.add_column(
        "intermediaries",
        sa.Column("total_funded_volume_currency", sa.String(3), nullable=True),
    )
    op.add_column(
        "intermediaries",
        sa.Column(
            "source_id", _uuid_type(),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=True,  # NOT NULL post-backfill
        ),
    )
    op.add_column(
        "intermediaries",
        sa.Column(
            "publication_status", sa.String(20),
            nullable=False, server_default="draft",
        ),
    )

    if is_pg:
        # CHECK constraints
        op.create_check_constraint(
            "intermediaries_processing_time_chk", "intermediaries",
            "processing_time_days_min IS NULL OR processing_time_days_max IS NULL "
            "OR processing_time_days_min <= processing_time_days_max",
        )
        op.create_check_constraint(
            "intermediaries_disbursement_time_chk", "intermediaries",
            "disbursement_time_days_min IS NULL OR disbursement_time_days_max IS NULL "
            "OR disbursement_time_days_min <= disbursement_time_days_max",
        )
        op.create_check_constraint(
            "intermediaries_success_rate_chk", "intermediaries",
            "success_rate IS NULL OR (success_rate >= 0 AND success_rate <= 1)",
        )
        op.create_check_constraint(
            "intermediaries_total_funded_volume_pair_chk", "intermediaries",
            "(total_funded_volume_amount IS NULL AND total_funded_volume_currency IS NULL) "
            "OR (total_funded_volume_amount IS NOT NULL AND total_funded_volume_currency IS NOT NULL)",
        )
        op.create_check_constraint(
            "intermediaries_publication_status_chk", "intermediaries",
            "publication_status IN ('draft', 'published')",
        )
        # Indexes
        op.create_index(
            "uq_intermediaries_code", "intermediaries", ["code"],
            unique=True, postgresql_where=sa.text("code IS NOT NULL"),
        )
        op.create_index("idx_intermediaries_country", "intermediaries", ["country"])
        op.create_index(
            "idx_intermediaries_publication_status", "intermediaries",
            ["publication_status"],
        )

    # =====================================================================
    # 3. ENRICHISSEMENT fund_intermediaries
    # =====================================================================

    op.add_column(
        "fund_intermediaries",
        sa.Column("accredited_from", sa.Date(), nullable=True),  # NOT NULL post-backfill
    )
    op.add_column(
        "fund_intermediaries",
        sa.Column("accredited_to", sa.Date(), nullable=True),
    )
    op.add_column(
        "fund_intermediaries",
        sa.Column(
            "max_amount_per_fund_amount", sa.Numeric(20, 2), nullable=True,
        ),
    )
    op.add_column(
        "fund_intermediaries",
        sa.Column(
            "max_amount_per_fund_currency", sa.String(3), nullable=True,
        ),
    )
    op.add_column(
        "fund_intermediaries",
        sa.Column(
            "accreditation_source_id", _uuid_type(),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )

    if is_pg:
        op.create_check_constraint(
            "fund_intermediaries_max_amount_pair_chk", "fund_intermediaries",
            "(max_amount_per_fund_amount IS NULL AND max_amount_per_fund_currency IS NULL) "
            "OR (max_amount_per_fund_amount IS NOT NULL AND max_amount_per_fund_currency IS NOT NULL)",
        )
        op.create_index(
            "idx_fund_intermediaries_accredited_to", "fund_intermediaries",
            ["accredited_to"],
            postgresql_where=sa.text("accredited_to IS NOT NULL"),
        )

    # =====================================================================
    # 4. CRÉATION TABLE offers
    # =====================================================================

    op.create_table(
        "offers",
        sa.Column(
            "id", _uuid_type(), primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_pg else None,
        ),
        sa.Column(
            "fund_id", _uuid_type(),
            sa.ForeignKey("funds.id", ondelete="RESTRICT"),
            nullable=False, index=True,
        ),
        sa.Column(
            "intermediary_id", _uuid_type(),
            sa.ForeignKey("intermediaries.id", ondelete="RESTRICT"),
            nullable=False, index=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "accepted_languages", _jsonb_type(),
            nullable=False, server_default='["FR"]',
        ),
        sa.Column("target_sector", _jsonb_type(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # Champs effectifs
        sa.Column(
            "effective_criteria", _jsonb_type(),
            nullable=False, server_default="{}",
        ),
        sa.Column(
            "effective_required_documents", _jsonb_type(),
            nullable=False, server_default="[]",
        ),
        sa.Column(
            "effective_fees", _jsonb_type(),
            nullable=False, server_default="{}",
        ),
        sa.Column("effective_processing_time_days_min", sa.Integer(), nullable=True),
        sa.Column("effective_processing_time_days_max", sa.Integer(), nullable=True),
        sa.Column("effective_disbursement_time_days_min", sa.Integer(), nullable=True),
        sa.Column("effective_disbursement_time_days_max", sa.Integer(), nullable=True),
        # Statut commercial
        sa.Column(
            "is_active", sa.Boolean(),
            nullable=False, server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "publication_status", sa.String(20),
            nullable=False, server_default="draft",
        ),
        # F01 — Source obligatoire
        sa.Column(
            "source_id", _uuid_type(),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # F04 — Versioning
        sa.Column(
            "version", sa.String(50),
            nullable=False, server_default="1.0",
        ),
        sa.Column(
            "valid_from", sa.Date(),
            nullable=False, server_default=sa.text("CURRENT_DATE"),
        ),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column(
            "superseded_by", _uuid_type(),
            sa.ForeignKey("offers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Timestamps
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        # Constraints
        sa.UniqueConstraint(
            "fund_id", "intermediary_id", "version",
            name="uq_offers_fund_intermediary_version",
        ),
        sa.CheckConstraint(
            "publication_status IN ('draft', 'published')",
            name="offers_publication_status_chk",
        ),
        sa.CheckConstraint(
            "effective_processing_time_days_min IS NULL "
            "OR effective_processing_time_days_max IS NULL "
            "OR effective_processing_time_days_min <= effective_processing_time_days_max",
            name="offers_processing_time_consistency_chk",
        ),
        sa.CheckConstraint(
            "effective_disbursement_time_days_min IS NULL "
            "OR effective_disbursement_time_days_max IS NULL "
            "OR effective_disbursement_time_days_min <= effective_disbursement_time_days_max",
            name="offers_disbursement_time_consistency_chk",
        ),
        sa.CheckConstraint(
            "publication_status = 'draft' OR is_active = TRUE",
            name="offers_published_active_chk",
        ),
    )

    # Indexes complémentaires
    if is_pg:
        op.create_index(
            "idx_offers_publication_active", "offers",
            ["publication_status", "is_active"],
            postgresql_where=sa.text(
                "publication_status = 'published' AND is_active = TRUE"
            ),
        )
    op.create_index(
        "idx_offers_fund_intermediary_valid_to", "offers",
        ["fund_id", "intermediary_id", "valid_to"],
    )

    # =====================================================================
    # 5. AJOUT colonne offer_id sur fund_applications
    # =====================================================================
    op.add_column(
        "fund_applications",
        sa.Column(
            "offer_id", _uuid_type(),
            sa.ForeignKey("offers.id", ondelete="RESTRICT"),
            nullable=True,  # NOT NULL post-backfill
        ),
    )
    op.create_index(
        "idx_fund_applications_offer_id", "fund_applications", ["offer_id"],
    )

    # =====================================================================
    # 6. BACKFILL — seed Source DIRECT + singleton intermediary DIRECT
    #    + offers pour toutes paires existantes + fonds direct
    # =====================================================================
    _backfill_data(is_pg=is_pg)

    # =====================================================================
    # 7. NOT NULL post-backfill
    # =====================================================================
    if is_pg:
        op.alter_column("funds", "source_id", nullable=False)
        op.alter_column("intermediaries", "source_id", nullable=False)
        op.alter_column("fund_intermediaries", "accredited_from", nullable=False)
        op.alter_column("fund_applications", "offer_id", nullable=False)


# ---------------------------------------------------------------------------
# DOWNGRADE
# ---------------------------------------------------------------------------


def downgrade() -> None:
    is_pg = _is_postgres()

    # 1. fund_applications : drop offer_id index + colonne
    op.drop_index("idx_fund_applications_offer_id", table_name="fund_applications")
    op.drop_column("fund_applications", "offer_id")

    # 2. Drop table offers (et ses indexes/constraints/FKs auto)
    if is_pg:
        op.drop_index("idx_offers_publication_active", table_name="offers")
    op.drop_index("idx_offers_fund_intermediary_valid_to", table_name="offers")
    op.drop_table("offers")

    # 3. fund_intermediaries : drop colonnes
    if is_pg:
        op.drop_index(
            "idx_fund_intermediaries_accredited_to",
            table_name="fund_intermediaries",
        )
        op.execute(
            "ALTER TABLE fund_intermediaries DROP CONSTRAINT IF EXISTS "
            "fund_intermediaries_max_amount_pair_chk"
        )
    op.drop_column("fund_intermediaries", "accreditation_source_id")
    op.drop_column("fund_intermediaries", "max_amount_per_fund_currency")
    op.drop_column("fund_intermediaries", "max_amount_per_fund_amount")
    op.drop_column("fund_intermediaries", "accredited_to")
    op.drop_column("fund_intermediaries", "accredited_from")

    # 4. intermediaries : drop colonnes
    if is_pg:
        op.drop_index("idx_intermediaries_publication_status", table_name="intermediaries")
        op.drop_index("idx_intermediaries_country", table_name="intermediaries")
        op.drop_index("uq_intermediaries_code", table_name="intermediaries")
        for c in (
            "intermediaries_publication_status_chk",
            "intermediaries_total_funded_volume_pair_chk",
            "intermediaries_success_rate_chk",
            "intermediaries_disbursement_time_chk",
            "intermediaries_processing_time_chk",
        ):
            op.execute(f"ALTER TABLE intermediaries DROP CONSTRAINT IF EXISTS {c}")
    op.drop_column("intermediaries", "publication_status")
    op.drop_column("intermediaries", "source_id")
    op.drop_column("intermediaries", "total_funded_volume_currency")
    op.drop_column("intermediaries", "total_funded_volume_amount")
    op.drop_column("intermediaries", "success_rate")
    op.drop_column("intermediaries", "submission_portal_url")
    op.drop_column("intermediaries", "disbursement_time_days_max")
    op.drop_column("intermediaries", "disbursement_time_days_min")
    op.drop_column("intermediaries", "processing_time_days_max")
    op.drop_column("intermediaries", "processing_time_days_min")
    op.drop_column("intermediaries", "fees_structured")
    op.drop_column("intermediaries", "required_documents")
    op.drop_column("intermediaries", "code")

    # 5. funds : restaurer enum + drop colonnes
    if is_pg:
        # Restaurer enum fund_type ancien
        op.execute(
            "CREATE TYPE fund_type_legacy_enum AS ENUM ("
            "'international','regional','national','carbon_market','local_bank_green_line')"
        )
        op.execute(
            "ALTER TABLE funds ALTER COLUMN fund_type TYPE fund_type_legacy_enum "
            "USING (CASE fund_type::text "
            "  WHEN 'multilateral' THEN 'international' "
            "  WHEN 'regional' THEN 'regional' "
            "  WHEN 'national' THEN 'national' "
            "  WHEN 'carbon_marketplace' THEN 'carbon_market' "
            "  WHEN 'private' THEN 'local_bank_green_line' "
            "  WHEN 'bilateral' THEN 'international' "
            "  ELSE 'international' "
            "END::fund_type_legacy_enum)"
        )
        op.execute("DROP TYPE fund_type_enum")
        op.execute("ALTER TYPE fund_type_legacy_enum RENAME TO fund_type_enum")

        op.drop_index("idx_funds_publication_status", table_name="funds")
        op.drop_index("idx_funds_instruments_gin", table_name="funds")
        op.drop_index("idx_funds_theme_gin", table_name="funds")
        for c in ("funds_submission_mode_chk", "funds_publication_status_chk"):
            op.execute(f"ALTER TABLE funds DROP CONSTRAINT IF EXISTS {c}")

    op.drop_column("funds", "publication_status")
    op.drop_column("funds", "source_id")
    op.drop_column("funds", "submission_calendar")
    op.drop_column("funds", "submission_mode")
    op.drop_column("funds", "theme")
    op.drop_column("funds", "instruments")

    # NB : on NE supprime PAS le singleton DIRECT (résiduel sans impact).


# ---------------------------------------------------------------------------
# BACKFILL helpers
# ---------------------------------------------------------------------------


def _backfill_data(*, is_pg: bool) -> None:
    """Seed Source DIRECT, intermédiaire singleton DIRECT, offres pour toutes
    paires fund_intermediaries existantes + tous fonds access_type='direct'.

    Liaison fund_applications.offer_id pour toutes les applications existantes.
    Idempotent.
    """
    bind = op.get_bind()

    # 6.0. Si PostgreSQL et tables vides → skip backfill (pas de données à migrer)
    # Les seeds en environnement seront créés par les fixtures de tests / seed_direct.
    funds_count = bind.execute(sa.text("SELECT COUNT(*) FROM funds")).scalar() or 0
    fi_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM fund_intermediaries")
    ).scalar() or 0
    fa_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM fund_applications")
    ).scalar() or 0

    if funds_count == 0 and fi_count == 0 and fa_count == 0:
        # Base vide — pas de backfill nécessaire mais on crée le singleton DIRECT
        # (Source + Intermediary) pour les seeds futurs.
        direct_source_id, _ = _ensure_direct_singleton(is_pg=is_pg)
        if direct_source_id is not None:
            # Si DIRECT existait déjà (re-upgrade après downgrade) → backfill
            # son source_id qui aurait été perdu lors du downgrade.
            bind.execute(
                sa.text(
                    "UPDATE intermediaries SET source_id = :sid "
                    "WHERE source_id IS NULL"
                ),
                {"sid": direct_source_id},
            )
        return

    # 6.1. Source DIRECT singleton + intermédiaire DIRECT (avant tout backfill)
    direct_source_id, direct_intermediary_id = _ensure_direct_singleton(is_pg=is_pg)

    # 6.2. Pour chaque fund existant sans source_id → assigner Source DIRECT
    bind.execute(
        sa.text(
            "UPDATE funds SET source_id = :sid WHERE source_id IS NULL"
        ),
        {"sid": str(direct_source_id) if not is_pg else direct_source_id},
    )
    # 6.3. Pour chaque intermediary sans source_id → assigner Source DIRECT
    bind.execute(
        sa.text(
            "UPDATE intermediaries SET source_id = :sid WHERE source_id IS NULL"
        ),
        {"sid": str(direct_source_id) if not is_pg else direct_source_id},
    )
    # 6.4. accredited_from : par défaut CURRENT_DATE
    bind.execute(
        sa.text(
            "UPDATE fund_intermediaries SET accredited_from = CURRENT_DATE "
            "WHERE accredited_from IS NULL"
        ),
    )

    # 6.5. Création offres pour chaque paire fund_intermediaries existante
    pairs = bind.execute(
        sa.text(
            "SELECT fi.fund_id, fi.intermediary_id, f.name AS fund_name, "
            "       i.name AS interm_name "
            "FROM fund_intermediaries fi "
            "JOIN funds f ON f.id = fi.fund_id "
            "JOIN intermediaries i ON i.id = fi.intermediary_id "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM offers o "
            "  WHERE o.fund_id = fi.fund_id "
            "    AND o.intermediary_id = fi.intermediary_id "
            "    AND o.version = '1.0'"
            ")"
        )
    ).fetchall()

    for row in pairs:
        offer_name = f"{row.fund_name} via {row.interm_name}"[:200]
        _insert_offer_draft(
            bind, fund_id=row.fund_id, intermediary_id=row.intermediary_id,
            name=offer_name, source_id=direct_source_id, is_pg=is_pg,
        )

    # 6.6. Création offres pour chaque fund avec access_type='direct'
    direct_funds = bind.execute(
        sa.text(
            "SELECT id, name FROM funds "
            "WHERE access_type = 'direct' "
            "  AND NOT EXISTS ("
            "    SELECT 1 FROM offers o "
            "    WHERE o.fund_id = funds.id "
            "      AND o.intermediary_id = :iid "
            "      AND o.version = '1.0'"
            "  )"
        ),
        {"iid": str(direct_intermediary_id) if not is_pg else direct_intermediary_id},
    ).fetchall()

    for row in direct_funds:
        offer_name = f"{row.name} (accès direct)"[:200]
        _insert_offer_draft(
            bind, fund_id=row.id, intermediary_id=direct_intermediary_id,
            name=offer_name, source_id=direct_source_id, is_pg=is_pg,
        )

    # 6.7. Lier fund_applications.offer_id
    # Cas 1 : intermediary_id renseigné → matcher (fund_id, intermediary_id)
    bind.execute(
        sa.text(
            "UPDATE fund_applications fa "
            "SET offer_id = ("
            "  SELECT o.id FROM offers o "
            "  WHERE o.fund_id = fa.fund_id "
            "    AND o.intermediary_id = fa.intermediary_id "
            "  LIMIT 1"
            ") "
            "WHERE fa.intermediary_id IS NOT NULL "
            "  AND fa.offer_id IS NULL"
        )
    )
    # Cas 2 : intermediary_id NULL → matcher (fund_id, DIRECT)
    bind.execute(
        sa.text(
            "UPDATE fund_applications fa "
            "SET offer_id = ("
            "  SELECT o.id FROM offers o "
            "  WHERE o.fund_id = fa.fund_id "
            "    AND o.intermediary_id = :iid "
            "  LIMIT 1"
            ") "
            "WHERE fa.intermediary_id IS NULL "
            "  AND fa.offer_id IS NULL"
        ),
        {"iid": str(direct_intermediary_id) if not is_pg else direct_intermediary_id},
    )


def _ensure_direct_singleton(*, is_pg: bool):
    """Crée la Source ``system://mefali/direct-singleton`` et l'intermédiaire
    singleton ``code='DIRECT'`` si absents. Retourne ``(source_id, intermediary_id)``.

    Idempotent.
    """
    bind = op.get_bind()

    # 1. Vérifier/créer Source DIRECT
    src_row = bind.execute(
        sa.text("SELECT id FROM sources WHERE url = :url LIMIT 1"),
        {"url": DIRECT_SOURCE_URL},
    ).first()
    if src_row is None:
        # Pour respecter le 4-eyes (captured_by != verified_by), on cherche
        # 2 admins distincts. Si insuffisant, on insère la Source en 'draft'
        # (verified_by=NULL) — F09 admin pourra la publier plus tard.
        admins = bind.execute(
            sa.text("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 2")
        ).fetchall()
        # Fallback sur tous les users
        if len(admins) < 2:
            admins = bind.execute(
                sa.text("SELECT id FROM users ORDER BY id LIMIT 2")
            ).fetchall()
        if len(admins) == 0:
            # Aucun user → on ne peut pas créer la Source (FK NOT NULL).
            # On retourne None — appelants doivent gérer le cas (typiquement
            # base vide en migration initiale). seed_direct.py runtime fera le job.
            return None, None

        captured_id = admins[0].id
        has_verified = len(admins) > 1
        verified_id = admins[1].id if has_verified else None

        if has_verified:
            # Source verified : 4-eyes respecté
            if is_pg:
                bind.execute(
                    sa.text(
                        "INSERT INTO sources (id, url, title, publisher, version, "
                        "  date_publi, captured_by, created_by_user_id, "
                        "  verified_by, verified_at, verification_status) "
                        "VALUES (gen_random_uuid(), :url, :title, :pub, '1.0', "
                        "  CURRENT_DATE, :cid, :cid, :vid, NOW(), 'verified')"
                    ),
                    {
                        "url": DIRECT_SOURCE_URL,
                        "title": "Singleton DIRECT — soumission directe sans intermédiaire",
                        "pub": "Mefali",
                        "cid": captured_id,
                        "vid": verified_id,
                    },
                )
            else:
                bind.execute(
                    sa.text(
                        "INSERT INTO sources (id, url, title, publisher, version, "
                        "  date_publi, captured_by, created_by_user_id, "
                        "  verified_by, verified_at, verification_status) "
                        "VALUES (lower(hex(randomblob(16))), :url, :title, :pub, '1.0', "
                        "  CURRENT_DATE, :cid, :cid, :vid, datetime('now'), 'verified')"
                    ),
                    {
                        "url": DIRECT_SOURCE_URL,
                        "title": "Singleton DIRECT — soumission directe sans intermédiaire",
                        "pub": "Mefali",
                        "cid": captured_id,
                        "vid": verified_id,
                    },
                )
        else:
            # Source draft (1 seul user disponible) : F09 admin pourra la valider plus tard
            if is_pg:
                bind.execute(
                    sa.text(
                        "INSERT INTO sources (id, url, title, publisher, version, "
                        "  date_publi, captured_by, created_by_user_id, "
                        "  verification_status) "
                        "VALUES (gen_random_uuid(), :url, :title, :pub, '1.0', "
                        "  CURRENT_DATE, :cid, :cid, 'draft')"
                    ),
                    {
                        "url": DIRECT_SOURCE_URL,
                        "title": "Singleton DIRECT — soumission directe sans intermédiaire",
                        "pub": "Mefali",
                        "cid": captured_id,
                    },
                )
            else:
                bind.execute(
                    sa.text(
                        "INSERT INTO sources (id, url, title, publisher, version, "
                        "  date_publi, captured_by, created_by_user_id, "
                        "  verification_status) "
                        "VALUES (lower(hex(randomblob(16))), :url, :title, :pub, '1.0', "
                        "  CURRENT_DATE, :cid, :cid, 'draft')"
                    ),
                    {
                        "url": DIRECT_SOURCE_URL,
                        "title": "Singleton DIRECT — soumission directe sans intermédiaire",
                        "pub": "Mefali",
                        "cid": captured_id,
                    },
                )
        src_row = bind.execute(
            sa.text("SELECT id FROM sources WHERE url = :url LIMIT 1"),
            {"url": DIRECT_SOURCE_URL},
        ).first()

    direct_source_id = src_row.id

    # 2. Vérifier/créer Intermediary DIRECT
    interm_row = bind.execute(
        sa.text(
            "SELECT id FROM intermediaries WHERE code = :c LIMIT 1"
        ),
        {"c": DIRECT_SINGLETON_CODE},
    ).first()
    if interm_row is None:
        if is_pg:
            bind.execute(
                sa.text(
                    "INSERT INTO intermediaries (id, name, intermediary_type, "
                    "  organization_type, country, city, accreditations, "
                    "  services_offered, eligibility_for_sme, is_active, "
                    "  source_id, publication_status, code, required_documents, "
                    "  version, valid_from, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), :name, 'accredited_entity', "
                    "  'un_agency', 'ALL', 'N/A', '[]'::jsonb, '{}'::jsonb, "
                    "  '{}'::jsonb, true, :sid, 'published', :code, '[]'::jsonb, "
                    "  '1.0', CURRENT_DATE, NOW(), NOW())"
                ),
                {
                    "name": "Direct (sans intermédiaire)",
                    "sid": direct_source_id,
                    "code": DIRECT_SINGLETON_CODE,
                },
            )
        else:
            bind.execute(
                sa.text(
                    "INSERT INTO intermediaries (id, name, intermediary_type, "
                    "  organization_type, country, city, accreditations, "
                    "  services_offered, eligibility_for_sme, is_active, "
                    "  source_id, publication_status, code, required_documents, "
                    "  version, valid_from, created_at, updated_at) "
                    "VALUES (lower(hex(randomblob(16))), :name, 'accredited_entity', "
                    "  'un_agency', 'ALL', 'N/A', '[]', '{}', "
                    "  '{}', 1, :sid, 'published', :code, '[]', "
                    "  '1.0', date('now'), datetime('now'), datetime('now'))"
                ),
                {
                    "name": "Direct (sans intermédiaire)",
                    "sid": direct_source_id,
                    "code": DIRECT_SINGLETON_CODE,
                },
            )
        interm_row = bind.execute(
            sa.text(
                "SELECT id FROM intermediaries WHERE code = :c LIMIT 1"
            ),
            {"c": DIRECT_SINGLETON_CODE},
        ).first()

    direct_intermediary_id = interm_row.id
    return direct_source_id, direct_intermediary_id


def _insert_offer_draft(
    bind, *, fund_id, intermediary_id, name: str, source_id, is_pg: bool,
) -> None:
    """Insère une offre minimale en draft (is_active=false). Idempotent."""
    if is_pg:
        bind.execute(
            sa.text(
                "INSERT INTO offers (id, fund_id, intermediary_id, name, "
                "  accepted_languages, effective_criteria, "
                "  effective_required_documents, effective_fees, "
                "  is_active, publication_status, source_id, version, "
                "  valid_from, created_at, updated_at) "
                "VALUES (gen_random_uuid(), :fid, :iid, :name, "
                "  '[\"FR\"]'::jsonb, '{}'::jsonb, '[]'::jsonb, '{}'::jsonb, "
                "  FALSE, 'draft', :sid, '1.0', CURRENT_DATE, NOW(), NOW())"
            ),
            {
                "fid": fund_id, "iid": intermediary_id,
                "name": name, "sid": source_id,
            },
        )
    else:
        bind.execute(
            sa.text(
                "INSERT INTO offers (id, fund_id, intermediary_id, name, "
                "  accepted_languages, effective_criteria, "
                "  effective_required_documents, effective_fees, "
                "  is_active, publication_status, source_id, version, "
                "  valid_from, created_at, updated_at) "
                "VALUES (lower(hex(randomblob(16))), :fid, :iid, :name, "
                "  '[\"FR\"]', '{}', '[]', '{}', "
                "  0, 'draft', :sid, '1.0', date('now'), "
                "  datetime('now'), datetime('now'))"
            ),
            {
                "fid": fund_id, "iid": intermediary_id,
                "name": name, "sid": source_id,
            },
        )
