"""F13 — Scoring ESG multi-référentiels : table referential_scores + seed + backfill.

Revision ID: 030_create_referential_scores
Revises: 028_offers_and_enrich
Create Date: 2026-05-07

Cette migration crée :

1. ENUM PostgreSQL ``referential_score_computed_by_enum`` (manual|llm|auto).
2. Table ``referential_scores`` avec FK ``account_id`` (RLS F02), ``assessment_id``
   (CASCADE), ``referential_id`` (RESTRICT), ``superseded_by`` (self-ref SET NULL),
   pillar_scores/covered_criteria/missing_criteria JSONB, scores Numeric, contraintes
   CHECK et trigger ``updated_at``.
3. Index unique partiel ``idx_referential_scores_current``
   (``WHERE superseded_by IS NULL``) garantissant un seul score courant par
   couple (assessment_id, referential_id) ; 3 index secondaires.
4. RLS PostgreSQL : ``ENABLE`` + ``FORCE ROW LEVEL SECURITY`` + policy
   ``referential_scores_account_isolation`` filtrant par
   ``current_setting('app.current_account_id')`` (cohérent avec F02).
5. Ajoute la valeur ``referential_version_evolved`` à l'ENUM ``reminder_type_enum``
   (F11 reuse pour notifier les PMEs des évolutions de version).
6. Seed des 5 référentiels MVP (``mefali`` UUID stable + GCF + IFC PS + BOAD ESS
   + GRI 2021) idempotent via ``ON CONFLICT (code) DO NOTHING``.
7. Backfill : pour chaque ``esg_assessments`` avec ``overall_score IS NOT NULL``,
   crée une ligne ``referential_scores`` Mefali (idempotent).

Sur SQLite (tests CI), les ENUMs et la RLS sont skippés. L'ajout d'une valeur
ENUM à reminder_type_enum est aussi skippé.

Downgrade : drop table referential_scores + drop enum + retire la valeur
``referential_version_evolved`` (PostgreSQL ne supporte pas DROP VALUE FROM
ENUM nativement avant PG 16 ; on laisse la valeur en best-effort).
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
revision: str = "030_create_referential_scores"
down_revision: Union[str, None] = "028_offers_and_enrich"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# UUID stable du référentiel Mefali — référencé par MEFALI_REFERENTIAL_UUID
# dans ``app/core/constants.py``.
MEFALI_REFERENTIAL_UUID_STR = "0e5f1310-1310-1310-1310-13101310f013"

# Codes des 5 référentiels MVP (cohérents avec REFERENTIAL_CODES_MVP).
MEFALI_CODE = "mefali"
GCF_CODE = "gcf"
IFC_PS_CODE = "ifc_ps"
BOAD_ESS_CODE = "boad_ess"
GRI_2021_CODE = "gri_2021"


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # --- 1. ENUM PostgreSQL pour computed_by ---
    if is_postgres:
        op.execute(
            "DO $$ BEGIN CREATE TYPE referential_score_computed_by_enum AS ENUM "
            "('manual','llm','auto'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
        )

    # --- 2. Table referential_scores ---
    computed_by_type = (
        postgresql.ENUM(
            "manual",
            "llm",
            "auto",
            name="referential_score_computed_by_enum",
            create_type=False,
        )
        if is_postgres
        else sa.String(length=20)
    )

    op.create_table(
        "referential_scores",
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
        sa.Column(
            "assessment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("esg_assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "referential_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("referentials.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("referential_version", sa.String(length=32), nullable=False),
        sa.Column(
            "superseded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("referential_scores.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("overall_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column(
            "pillar_scores",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            server_default=sa.text("'{}'::jsonb") if is_postgres else sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "coverage_rate",
            sa.Numeric(precision=4, scale=3),
            server_default="0.000",
            nullable=False,
        ),
        sa.Column(
            "covered_criteria",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            server_default=sa.text("'[]'::jsonb") if is_postgres else sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column(
            "missing_criteria",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            server_default=sa.text("'[]'::jsonb") if is_postgres else sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column("gap_to_threshold", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("eligibility", sa.Boolean(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("computed_by", computed_by_type, nullable=False),
        sa.Column(
            "computed_request_id", postgresql.UUID(as_uuid=True), nullable=True,
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
        sa.CheckConstraint(
            "coverage_rate >= 0 AND coverage_rate <= 1",
            name="ck_referential_scores_coverage_rate_range",
        ),
    )

    # --- 3. Indexes ---
    # Index unique partiel : un seul score « courant » par couple (assessment_id, referential_id).
    if is_postgres:
        op.execute(
            "CREATE UNIQUE INDEX idx_referential_scores_current "
            "ON referential_scores (assessment_id, referential_id) "
            "WHERE superseded_by IS NULL"
        )
    else:
        # SQLite supporte les indexes partiels avec WHERE
        op.execute(
            "CREATE UNIQUE INDEX idx_referential_scores_current "
            "ON referential_scores (assessment_id, referential_id) "
            "WHERE superseded_by IS NULL"
        )

    op.create_index(
        "idx_referential_scores_assessment_computed_at",
        "referential_scores",
        ["assessment_id", "computed_at"],
    )
    op.create_index(
        "idx_referential_scores_referential_computed_at",
        "referential_scores",
        ["referential_id", "computed_at"],
    )
    op.create_index(
        "idx_referential_scores_account_id",
        "referential_scores",
        ["account_id"],
    )

    # --- 4. RLS PostgreSQL ---
    if is_postgres:
        op.execute("ALTER TABLE referential_scores ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE referential_scores FORCE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY referential_scores_account_isolation "
            "ON referential_scores FOR ALL "
            "USING ("
            "  account_id = NULLIF(current_setting('app.current_account_id', true), '')::uuid "
            "  OR current_setting('app.current_role', true) = 'ADMIN'"
            ")"
        )

        # Trigger updated_at — réutilise la fonction utilitaire
        # (présente depuis la migration 019_multitenant)
        op.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_proc WHERE proname = 'update_updated_at_column'
                ) THEN
                    CREATE TRIGGER trigger_referential_scores_updated_at
                        BEFORE UPDATE ON referential_scores
                        FOR EACH ROW
                        EXECUTE FUNCTION update_updated_at_column();
                END IF;
            END $$;
            """
        )

    # --- 5. Ajouter la valeur 'referential_version_evolved' à reminder_type_enum (F11 reuse) ---
    if is_postgres:
        # ALTER TYPE ... ADD VALUE est idempotent en PG via IF NOT EXISTS
        op.execute(
            "ALTER TYPE reminder_type_enum ADD VALUE IF NOT EXISTS 'referential_version_evolved'"
        )

    # --- 6. Seed des 5 référentiels MVP (idempotent ON CONFLICT DO NOTHING) ---
    _seed_referentials(bind, is_postgres)

    # --- 7. Backfill EsgAssessment → referential_scores (Mefali) ---
    _backfill_assessments_to_mefali_scores(bind, is_postgres)


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Drop RLS policies + table
    if is_postgres:
        op.execute(
            "DROP POLICY IF EXISTS referential_scores_account_isolation "
            "ON referential_scores"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS trigger_referential_scores_updated_at "
            "ON referential_scores"
        )

    op.drop_index(
        "idx_referential_scores_account_id", table_name="referential_scores"
    )
    op.drop_index(
        "idx_referential_scores_referential_computed_at",
        table_name="referential_scores",
    )
    op.drop_index(
        "idx_referential_scores_assessment_computed_at",
        table_name="referential_scores",
    )
    if is_postgres:
        op.execute("DROP INDEX IF EXISTS idx_referential_scores_current")
    else:
        op.execute("DROP INDEX IF EXISTS idx_referential_scores_current")

    op.drop_table("referential_scores")

    # 2. Drop ENUM
    if is_postgres:
        op.execute("DROP TYPE IF EXISTS referential_score_computed_by_enum")

    # Note : on ne retire PAS la valeur 'referential_version_evolved' de
    # reminder_type_enum (PG ne supporte pas DROP VALUE FROM ENUM avant
    # PG 16, et nettoyer les données existantes serait risqué).
    # Pas de seed à dérouler : les référentiels seedés peuvent être
    # désactivés via publication_status='draft' si nécessaire.


# --- Helpers de seed et backfill ---


def _seed_referentials(bind, is_postgres: bool) -> None:
    """Seed des 5 référentiels MVP (idempotent).

    Pour chaque référentiel :
    - Crée une Source ``system://mefali/referential-<code>`` si absente.
    - Crée le Referential via INSERT … ON CONFLICT (code) DO NOTHING.

    Si aucun user n'existe (DB vide en CI), on skip (seed runtime via script
    au lieu de migration).
    """
    # Récupérer 1-2 admins (sinon 1-2 users) pour la Source 4-yeux
    admins = bind.execute(
        sa.text("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 2")
    ).fetchall()
    if len(admins) < 2:
        admins = bind.execute(
            sa.text("SELECT id FROM users ORDER BY id LIMIT 2")
        ).fetchall()
    if len(admins) == 0:
        logger.info(
            "Aucun user en base : skip seed F13 referentials. "
            "Le seed runtime via script fera le job en environnement live."
        )
        return

    captured_id = admins[0].id
    has_verified = len(admins) > 1
    verified_id = admins[1].id if has_verified else None

    referentials = [
        {
            "uuid": MEFALI_REFERENTIAL_UUID_STR,
            "code": MEFALI_CODE,
            "label": "ESG Mefali",
            "description": (
                "Référentiel synthétique Mefali (vue par défaut). 30 critères E/S/G "
                "adaptés au contexte africain UEMOA/CEDEAO."
            ),
            "version": "1.0",
        },
        {
            "uuid": None,  # UUID auto-généré pour les autres
            "code": GCF_CODE,
            "label": "Green Climate Fund",
            "description": (
                "Référentiel GCF (Green Climate Fund) pour mitigation et adaptation "
                "climatique. Critères : impact paradigmatique, additionnalité "
                "financière, durabilité du développement, besoins du pays récipiendaire."
            ),
            "version": "1.0",
        },
        {
            "uuid": None,
            "code": IFC_PS_CODE,
            "label": "IFC Performance Standards 2012",
            "description": (
                "Référentiel IFC Performance Standards 2012 (8 piliers PS1-PS8). "
                "Évaluation des risques environnementaux et sociaux pour les projets "
                "financés par la Banque Mondiale."
            ),
            "version": "1.0",
        },
        {
            "uuid": None,
            "code": BOAD_ESS_CODE,
            "label": "BOAD ESS",
            "description": (
                "Référentiel ESS (Environnement et Sustainable Standards) de la "
                "Banque Ouest-Africaine de Développement. Adapté aux PME UEMOA, "
                "intègre les taxonomies vertes BCEAO."
            ),
            "version": "1.0",
        },
        {
            "uuid": None,
            "code": GRI_2021_CODE,
            "label": "GRI 2021",
            "description": (
                "Référentiel Global Reporting Initiative 2021. Standards "
                "internationaux de reporting de durabilité (GRI 1-3 universels + "
                "topic-specific)."
            ),
            "version": "1.0",
        },
    ]

    for ref in referentials:
        # 1. Source
        source_url = f"system://mefali/referential-{ref['code']}"
        src_row = bind.execute(
            sa.text("SELECT id FROM sources WHERE url = :url LIMIT 1"),
            {"url": source_url},
        ).first()

        if src_row is None:
            source_uuid = str(uuid.uuid4())
            if has_verified:
                if is_postgres:
                    bind.execute(
                        sa.text(
                            "INSERT INTO sources (id, url, title, publisher, version, "
                            "  date_publi, captured_by, created_by_user_id, "
                            "  verified_by, verified_at, verification_status) "
                            "VALUES (:sid, :url, :title, :pub, '1.0', "
                            "  CURRENT_DATE, :cid, :cid, :vid, NOW(), 'verified')"
                        ),
                        {
                            "sid": source_uuid,
                            "url": source_url,
                            "title": f"Référentiel — {ref['label']}",
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
                            "VALUES (:sid, :url, :title, :pub, '1.0', "
                            "  CURRENT_DATE, :cid, :cid, :vid, datetime('now'), 'verified')"
                        ),
                        {
                            "sid": source_uuid,
                            "url": source_url,
                            "title": f"Référentiel — {ref['label']}",
                            "pub": "Mefali",
                            "cid": captured_id,
                            "vid": verified_id,
                        },
                    )
            else:
                date_fn = "CURRENT_DATE"
                bind.execute(
                    sa.text(
                        f"INSERT INTO sources (id, url, title, publisher, version, "
                        f"  date_publi, captured_by, created_by_user_id, "
                        f"  verification_status) "
                        f"VALUES (:sid, :url, :title, :pub, '1.0', "
                        f"  {date_fn}, :cid, :cid, 'draft')"
                    ),
                    {
                        "sid": source_uuid,
                        "url": source_url,
                        "title": f"Référentiel — {ref['label']}",
                        "pub": "Mefali",
                        "cid": captured_id,
                    },
                )
            source_id = source_uuid
        else:
            source_id = src_row.id

        # 2. Referential (idempotent ON CONFLICT (code) DO NOTHING)
        ref_uuid = ref["uuid"] or str(uuid.uuid4())
        if is_postgres:
            bind.execute(
                sa.text(
                    "INSERT INTO referentials "
                    "  (id, code, label, description, source_id, "
                    "   publication_status, account_id, created_by_user_id, "
                    "   version, valid_from) "
                    "VALUES (:rid, :code, :label, :description, :sid, "
                    "  'published', NULL, :cid, :version, CURRENT_DATE) "
                    "ON CONFLICT (code) DO NOTHING"
                ),
                {
                    "rid": ref_uuid,
                    "code": ref["code"],
                    "label": ref["label"],
                    "description": ref["description"],
                    "sid": source_id,
                    "cid": captured_id,
                    "version": ref["version"],
                },
            )
        else:
            existing = bind.execute(
                sa.text("SELECT id FROM referentials WHERE code = :code LIMIT 1"),
                {"code": ref["code"]},
            ).first()
            if existing is None:
                bind.execute(
                    sa.text(
                        "INSERT INTO referentials "
                        "  (id, code, label, description, source_id, "
                        "   publication_status, account_id, created_by_user_id, "
                        "   version, valid_from, created_at, updated_at) "
                        "VALUES (:rid, :code, :label, :description, :sid, "
                        "  'published', NULL, :cid, :version, "
                        "  date('now'), datetime('now'), datetime('now'))"
                    ),
                    {
                        "rid": ref_uuid,
                        "code": ref["code"],
                        "label": ref["label"],
                        "description": ref["description"],
                        "sid": source_id,
                        "cid": captured_id,
                        "version": ref["version"],
                    },
                )


def _backfill_assessments_to_mefali_scores(bind, is_postgres: bool) -> None:
    """Pour chaque ESGAssessment finalisée, crée une ligne referential_scores
    avec referential_id=Mefali (idempotent).

    Skip si aucun assessment n'existe ou si Mefali n'a pas pu être seedé
    (pas d'user en base).
    """
    # Vérifier que Mefali a bien été seedé
    mefali_row = bind.execute(
        sa.text(
            "SELECT id FROM referentials WHERE code = :code LIMIT 1"
        ),
        {"code": MEFALI_CODE},
    ).first()
    if mefali_row is None:
        logger.info(
            "Mefali non seedé : skip backfill F13 (cohérent avec absence de users)."
        )
        return

    mefali_id = mefali_row.id

    # Récupérer tous les ESGAssessment avec overall_score IS NOT NULL et account_id NOT NULL
    rows = bind.execute(
        sa.text(
            "SELECT id, account_id, overall_score, environment_score, "
            "  social_score, governance_score, "
            "  COALESCE(updated_at, created_at) AS computed_at "
            "FROM esg_assessments "
            "WHERE overall_score IS NOT NULL "
            "  AND account_id IS NOT NULL"
        )
    ).fetchall()

    if not rows:
        logger.info("Aucune ESGAssessment finalisée à backfiller.")
        return

    for row in rows:
        # Construire pillar_scores JSONB
        pillar_scores = {
            "environment": {
                "score": float(row.environment_score) if row.environment_score is not None else 0.0,
                "weight": 0.33,
                "criteria_count": 0,
                "criteria_renseignés": 0,
            },
            "social": {
                "score": float(row.social_score) if row.social_score is not None else 0.0,
                "weight": 0.33,
                "criteria_count": 0,
                "criteria_renseignés": 0,
            },
            "governance": {
                "score": float(row.governance_score) if row.governance_score is not None else 0.0,
                "weight": 0.34,
                "criteria_count": 0,
                "criteria_renseignés": 0,
            },
        }

        import json as _json

        gap = float(row.overall_score) - 50.0 if row.overall_score is not None else None
        eligibility = (
            float(row.overall_score) >= 50.0 if row.overall_score is not None else None
        )

        if is_postgres:
            # ON CONFLICT cible l'index unique partiel WHERE superseded_by IS NULL.
            bind.execute(
                sa.text(
                    "INSERT INTO referential_scores "
                    "  (id, account_id, assessment_id, referential_id, "
                    "   referential_version, overall_score, pillar_scores, "
                    "   coverage_rate, covered_criteria, missing_criteria, "
                    "   gap_to_threshold, eligibility, computed_at, computed_by) "
                    "VALUES (gen_random_uuid(), :aid, :asid, :rid, "
                    "  '1.0', :score, CAST(:pillars AS jsonb), "
                    "  0.000, '[]'::jsonb, '[]'::jsonb, "
                    "  :gap, :elig, :cat, 'auto') "
                    "ON CONFLICT (assessment_id, referential_id) "
                    "WHERE superseded_by IS NULL DO NOTHING"
                ),
                {
                    "aid": row.account_id,
                    "asid": row.id,
                    "rid": mefali_id,
                    "score": float(row.overall_score),
                    "pillars": _json.dumps(pillar_scores),
                    "gap": gap,
                    "elig": eligibility,
                    "cat": row.computed_at,
                },
            )
        else:
            # SQLite : check manuel d'unicité
            existing = bind.execute(
                sa.text(
                    "SELECT id FROM referential_scores "
                    "WHERE assessment_id = :asid AND referential_id = :rid "
                    "  AND superseded_by IS NULL LIMIT 1"
                ),
                {"asid": row.id, "rid": mefali_id},
            ).first()
            if existing is None:
                bind.execute(
                    sa.text(
                        "INSERT INTO referential_scores "
                        "  (id, account_id, assessment_id, referential_id, "
                        "   referential_version, overall_score, pillar_scores, "
                        "   coverage_rate, covered_criteria, missing_criteria, "
                        "   gap_to_threshold, eligibility, computed_at, "
                        "   computed_by, created_at, updated_at) "
                        "VALUES (lower(hex(randomblob(16))), :aid, :asid, :rid, "
                        "  '1.0', :score, :pillars, "
                        "  0.000, '[]', '[]', "
                        "  :gap, :elig, :cat, 'auto', "
                        "  datetime('now'), datetime('now'))"
                    ),
                    {
                        "aid": row.account_id,
                        "asid": row.id,
                        "rid": mefali_id,
                        "score": float(row.overall_score),
                        "pillars": _json.dumps(pillar_scores),
                        "gap": gap,
                        "elig": eligibility,
                        "cat": row.computed_at,
                    },
                )

    logger.info("Backfilled %d ESGAssessment(s) → referential_scores (Mefali).", len(rows))
