"""F17 — Carbone mix UEMOA + facteurs sources + categorie Achats.

Revision ID: 024_carbone_mix_uemoa
Revises: 023_create_message_chunks
Create Date: 2026-05-07

Cette migration introduit :

- Colonne ``year`` (Integer NOT NULL) sur ``emission_factors`` avec
  backfill 2024 pour les lignes existantes F01.
- Index composite ``idx_emission_factors_lookup`` (category, country, year).
- Contrainte UNIQUE ``emission_factors_cat_country_year_uniq``
  (category, country, year).
- Seed des ~33 facteurs F17 (8 pays UEMOA electricite x 2 annees,
  3 combustibles, 7 transport, 3 dechets, 6 achats matieres premieres).
  Idempotent : ``ON CONFLICT (code) DO NOTHING`` au niveau de la requete.
- Colonnes ``source_id`` et ``factor_id`` (UUID FK NOT NULL) sur
  ``carbon_emission_entries``, avec backfill par matching strict
  ``subcategory`` -> ``emission_factors.code``, fallback generique global
  + source ADEME generique.
- Conservation legacy ``source_description`` (clarification Q5) — pas de
  drop dans cette migration.

Downgrade : symetrie inversee sans drop ``source_description`` (legacy
2 sprints).
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


logger = logging.getLogger(__name__)


# revision identifiers, used by Alembic.
revision: str = "024_carbone_mix_uemoa"
down_revision: Union[str, None] = "023_create_message_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Default fallback year pour le backfill des entries existantes.
_DEFAULT_BACKFILL_YEAR = 2024


def _seed_factors_via_orm(connection) -> int:
    """Seed les facteurs F17 via le service ``seed_emission_factors``.

    Resout l'ID d'un user admin systeme (cree par F01 si non present)
    pour servir de ``created_by_user_id``.

    Returns:
        Nombre de facteurs inseres (skip si deja presents).
    """
    from app.models.user import User
    from app.models.source import VerificationStatus
    from app.models.source import Source
    from app.modules.carbon.seed_factors import SEED_DATA
    from app.models.emission_factor import EmissionFactor
    from app.models.source import PublicationStatus
    import uuid

    # Resoudre admin systeme : prendre le 1er user role=ADMIN.
    admin_id_row = connection.execute(
        sa.text(
            "SELECT id FROM users WHERE role = 'ADMIN' "
            "ORDER BY created_at LIMIT 1"
        )
    ).fetchone()
    if admin_id_row is None:
        logger.warning(
            "Aucun user ADMIN trouve : seed F17 emission_factors ignore. "
            "Lancer le seed F01 (sources) d'abord pour creer system-curator."
        )
        return 0
    admin_id = admin_id_row[0]

    # Resoudre les sources verified par publisher.
    publisher_to_source: dict[str, str] = {}
    for publisher in ("ADEME", "IEA", "IPCC"):
        # Preferer titre specifique si dispo.
        title_filters = {
            "ADEME": "Base Carbone",
            "IEA": "Africa Energy Outlook",
            "IPCC": "Working Group III",
        }
        ideal_row = connection.execute(
            sa.text(
                "SELECT id FROM sources "
                "WHERE publisher = :pub "
                "AND verification_status = 'verified' "
                "AND title ILIKE :title_pattern "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"pub": publisher, "title_pattern": f"%{title_filters[publisher]}%"},
        ).fetchone()
        if ideal_row is not None:
            publisher_to_source[publisher] = ideal_row[0]
            continue
        any_row = connection.execute(
            sa.text(
                "SELECT id FROM sources "
                "WHERE publisher = :pub "
                "AND verification_status = 'verified' "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"pub": publisher},
        ).fetchone()
        if any_row is not None:
            publisher_to_source[publisher] = any_row[0]

    if not publisher_to_source:
        logger.warning(
            "Aucune source ADEME/IEA/IPCC verified trouvee : seed F17 ignore."
        )
        return 0

    inserted = 0
    for seed in SEED_DATA:
        source_id = publisher_to_source.get(seed.publisher)
        if source_id is None:
            continue

        # Idempotence : SELECT before INSERT.
        existing = connection.execute(
            sa.text("SELECT 1 FROM emission_factors WHERE code = :code"),
            {"code": seed.code},
        ).fetchone()
        if existing is not None:
            continue

        connection.execute(
            sa.text(
                "INSERT INTO emission_factors "
                "(id, code, label, category, country, year, value, unit, "
                "source_id, publication_status, account_id, "
                "created_by_user_id, created_at, updated_at, version, "
                "valid_from) "
                "VALUES (:id, :code, :label, :category, :country, :year, "
                ":value, :unit, :source_id, :pub_status, NULL, "
                ":admin_id, NOW(), NOW(), '1.0', CURRENT_DATE)"
            ),
            {
                "id": str(uuid.uuid4()),
                "code": seed.code,
                "label": seed.label,
                "category": seed.category,
                "country": seed.country,
                "year": seed.year,
                "value": seed.value,
                "unit": seed.unit,
                "source_id": source_id,
                "pub_status": "published",
                "admin_id": admin_id,
            },
        )
        inserted += 1

    return inserted


def _backfill_carbon_entries(connection) -> tuple[int, int]:
    """Backfill ``source_id`` + ``factor_id`` sur ``carbon_emission_entries``.

    Strategie (clarification Q3) :
        1. Matching strict ``subcategory`` -> ``emission_factors.code``.
        2. Si pas de match : facteur generique global de la categorie
           (``<category>_global_2024`` ou similar).
        3. Si toujours pas de match : log warning, laisser NULL
           (sera bloque par le NOT NULL ulterieur — rare cas exotique).

    Returns:
        (matched_strict, matched_fallback)
    """
    matched_strict = 0
    matched_fallback = 0

    # 1. Matching strict subcategory -> emission_factors.code.
    res_strict = connection.execute(
        sa.text(
            "UPDATE carbon_emission_entries e "
            "SET factor_id = ef.id, source_id = ef.source_id "
            "FROM emission_factors ef "
            "WHERE e.subcategory = ef.code "
            "AND e.factor_id IS NULL"
        )
    )
    matched_strict = res_strict.rowcount or 0

    # 2. Fallback : matching par prefix (ex. e.subcategory='electricity_ci'
    #    -> ef.code='electricity_ci_2024'). On prend le facteur le plus recent.
    res_prefix = connection.execute(
        sa.text(
            "UPDATE carbon_emission_entries e "
            "SET factor_id = ef.id, source_id = ef.source_id "
            "FROM emission_factors ef "
            "WHERE e.factor_id IS NULL "
            "AND ef.code LIKE e.subcategory || '_%' "
            "AND ef.id = ("
            "  SELECT ef2.id FROM emission_factors ef2 "
            "  WHERE ef2.code LIKE e.subcategory || '_%' "
            "  ORDER BY ef2.year DESC LIMIT 1"
            ")"
        )
    )
    matched_fallback += res_prefix.rowcount or 0

    # 3. Fallback ultime : facteur generique de la categorie.
    #    On mappe les categories utilisateur -> categorie F17 generique.
    category_fallback = {
        "energy": "electricity_global_2024",
        "transport": "transport_personal_diesel_2024",
        "waste": "waste_landfill_global_2024",
        "industrial": "purchases_other_global_2024",
        "agriculture": "purchases_food_global_2024",
        "purchases": "purchases_other_global_2024",
    }
    for user_cat, fallback_code in category_fallback.items():
        res_cat = connection.execute(
            sa.text(
                "UPDATE carbon_emission_entries e "
                "SET factor_id = ef.id, source_id = ef.source_id "
                "FROM emission_factors ef "
                "WHERE ef.code = :code "
                "AND e.category = :user_cat "
                "AND e.factor_id IS NULL"
            ),
            {"code": fallback_code, "user_cat": user_cat},
        )
        matched_fallback += res_cat.rowcount or 0

    return matched_strict, matched_fallback


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # --- 1. Colonne ``year`` sur emission_factors ---
    op.add_column(
        "emission_factors",
        sa.Column("year", sa.Integer(), nullable=True),
    )
    op.execute(
        f"UPDATE emission_factors SET year = {_DEFAULT_BACKFILL_YEAR} "
        "WHERE year IS NULL"
    )
    op.alter_column("emission_factors", "year", nullable=False)

    # --- 2. Index composite + UNIQUE constraint ---
    op.create_index(
        "idx_emission_factors_lookup",
        "emission_factors",
        ["category", "country", "year"],
    )
    op.create_unique_constraint(
        "emission_factors_cat_country_year_uniq",
        "emission_factors",
        ["category", "country", "year"],
    )

    # --- 3. Colonnes source_id + factor_id sur carbon_emission_entries ---
    op.add_column(
        "carbon_emission_entries",
        sa.Column("source_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "carbon_emission_entries",
        sa.Column("factor_id", sa.UUID(as_uuid=True), nullable=True),
    )

    # --- 4. Seed des facteurs F17 (PostgreSQL only) ---
    if is_postgres:
        try:
            inserted = _seed_factors_via_orm(bind)
            logger.info("F17 seed : %d emission_factors inseres", inserted)
        except Exception as exc:  # pragma: no cover - logged only.
            logger.warning(
                "F17 seed emission_factors a echoue (%s) — la migration "
                "continue ; relancer manuellement si besoin.",
                exc,
            )

    # --- 5. Backfill carbon_emission_entries (PostgreSQL only) ---
    if is_postgres:
        try:
            strict, fallback = _backfill_carbon_entries(bind)
            logger.info(
                "F17 backfill : %d strict, %d fallback (entries lies)",
                strict,
                fallback,
            )
        except Exception as exc:  # pragma: no cover - logged only.
            logger.warning(
                "F17 backfill carbon_emission_entries a echoue (%s) — "
                "les entries sans factor_id resteront NULL.",
                exc,
            )

    # --- 6. FK constraints (PostgreSQL only ; SQLite ignore les FK
    #         supplementaires sur ALTER TABLE) ---
    if is_postgres:
        op.create_foreign_key(
            "fk_carbon_entries_source",
            "carbon_emission_entries",
            "sources",
            ["source_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.create_foreign_key(
            "fk_carbon_entries_factor",
            "carbon_emission_entries",
            "emission_factors",
            ["factor_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    # --- 7. NOT NULL après backfill (PostgreSQL only ; on garde nullable
    #        en SQLite pour les tests qui n'executent pas le seed).
    #        On ne force NOT NULL que si toutes les lignes ont ete backfillees.
    if is_postgres:
        # Compter les NULL restants.
        null_count_row = bind.execute(
            sa.text(
                "SELECT COUNT(*) FROM carbon_emission_entries "
                "WHERE factor_id IS NULL OR source_id IS NULL"
            )
        ).fetchone()
        null_count = (null_count_row[0] if null_count_row else 0) or 0
        if null_count == 0:
            op.alter_column(
                "carbon_emission_entries",
                "source_id",
                nullable=False,
            )
            op.alter_column(
                "carbon_emission_entries",
                "factor_id",
                nullable=False,
            )
        else:
            logger.warning(
                "F17 : %d entries restent avec factor_id/source_id NULL ; "
                "les contraintes NOT NULL ne sont PAS appliquees. "
                "Verifier manuellement avant de re-deployer.",
                null_count,
            )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # --- 1. FK constraints + colonnes carbon_emission_entries ---
    if is_postgres:
        # Drop NOT NULL si applicable (idempotent).
        op.alter_column(
            "carbon_emission_entries",
            "source_id",
            nullable=True,
        )
        op.alter_column(
            "carbon_emission_entries",
            "factor_id",
            nullable=True,
        )
        op.drop_constraint(
            "fk_carbon_entries_factor",
            "carbon_emission_entries",
            type_="foreignkey",
        )
        op.drop_constraint(
            "fk_carbon_entries_source",
            "carbon_emission_entries",
            type_="foreignkey",
        )

    op.drop_column("carbon_emission_entries", "factor_id")
    op.drop_column("carbon_emission_entries", "source_id")
    # NB : ``source_description`` est conserve (legacy 2 sprints — Q5).

    # --- 2. Rollback seed F17 emission_factors ---
    if is_postgres:
        # Liste les codes seedés F17 (depuis SEED_DATA).
        try:
            from app.modules.carbon.seed_factors import SEED_DATA

            codes = [s.code for s in SEED_DATA]
            if codes:
                op.execute(
                    sa.text(
                        "DELETE FROM emission_factors WHERE code = ANY(:codes)"
                    ).bindparams(sa.bindparam("codes", value=codes))
                )
        except ImportError:  # pragma: no cover.
            pass

    # --- 3. Drop UNIQUE + index ---
    op.drop_constraint(
        "emission_factors_cat_country_year_uniq",
        "emission_factors",
        type_="unique",
    )
    op.drop_index("idx_emission_factors_lookup", "emission_factors")

    # --- 4. Drop colonne year ---
    op.drop_column("emission_factors", "year")
