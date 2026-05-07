"""F10 — Extend interactive_questions for 9 new widgets (yes_no/select/...)

Revision ID: 031_extend_interactive_questions
Revises: 030_create_referential_scores
Create Date: 2026-05-07

Étend la table satellite ``interactive_questions`` (introduite F18) pour
supporter 9 nouveaux types de widgets bottom sheet :

1. **Enum élargi** ``interactivequestiontype`` : ajoute ``yes_no``, ``select``,
   ``number``, ``date``, ``date_range``, ``rating``, ``file_upload``, ``form``,
   ``summary_card`` aux 4 valeurs F18 (``qcu``, ``qcm``, ``qcu_justification``,
   ``qcm_justification``). Sur PostgreSQL, ``ALTER TYPE ... ADD VALUE IF NOT
   EXISTS`` dans un ``autocommit_block``. Sur SQLite (tests), le ``question_type``
   reste un VARCHAR(24) sans enum natif → aucune action requise.

2. **Colonne ``payload jsonb NOT NULL DEFAULT '{}'``** : stocke les paramètres
   spécifiques par variante (bornes numériques, devise, fichiers acceptés,
   champs formulaire, etc.). Validé Pydantic via union discriminée.

3. **Colonne ``response_payload jsonb NULL``** : stocke la réponse structurée
   au-delà de ``response_values`` (ex : ``{value: 1200000, currency: "XOF"}``
   pour ``ask_number``).

4. **Contrainte étendue** ``ck_iq_max_le_8_or_select_form`` : remplace
   ``ck_iq_max_le_8`` pour permettre ``max_selections > 8`` sur les types
   ``select`` (jusqu'à 200) et ``form``.

Réf : ``specs/031-widgets-bottom-sheet-complets/{spec,plan,data-model}.md``.

Downgrade : refuse si des lignes utilisent les nouvelles valeurs d'enum
(invariant SC-009 — pas de perte). PostgreSQL ne supporte pas DROP VALUE FROM
ENUM avant PG 16 ; les valeurs d'enum restent en best-effort si downgrade.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "031_extend_interactive_questions"
down_revision: Union[str, None] = "030_create_referential_scores"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Les 9 nouvelles valeurs d'enum F10
NEW_ENUM_VALUES: tuple[str, ...] = (
    "yes_no",
    "select",
    "number",
    "date",
    "date_range",
    "rating",
    "file_upload",
    "form",
    "summary_card",
)


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # ─── 1. Étendre l'enum PostgreSQL (si applicable) ───────────────────
    if is_postgres:
        # Le projet n'utilise actuellement pas un type ENUM PostgreSQL natif
        # pour `question_type` (cf. migration 018 : c'est un VARCHAR(24)).
        # Si une feature ultérieure crée le type, ce bloc l'étend ; sinon, no-op.
        with op.get_context().autocommit_block():
            for value in NEW_ENUM_VALUES:
                op.execute(
                    "DO $$ BEGIN "
                    "IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'interactivequestiontype') THEN "
                    f"ALTER TYPE interactivequestiontype ADD VALUE IF NOT EXISTS '{value}'; "
                    "END IF; "
                    "EXCEPTION WHEN OTHERS THEN NULL; END $$;"
                )

    # ─── 2. Ajouter la colonne `payload jsonb NOT NULL DEFAULT '{}'` ────
    if is_postgres:
        op.add_column(
            "interactive_questions",
            sa.Column(
                "payload",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )
    else:
        op.add_column(
            "interactive_questions",
            sa.Column(
                "payload",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            ),
        )

    # ─── 3. Ajouter la colonne `response_payload jsonb NULL` ────────────
    if is_postgres:
        op.add_column(
            "interactive_questions",
            sa.Column("response_payload", postgresql.JSONB(), nullable=True),
        )
    else:
        op.add_column(
            "interactive_questions",
            sa.Column("response_payload", sa.JSON(), nullable=True),
        )

    # ─── 4. Relâcher la contrainte ck_iq_max_le_8 ───────────────────────
    # SQLite ne supporte pas ALTER TABLE DROP CONSTRAINT directement, mais
    # `op.drop_constraint` + `create_check_constraint` fonctionnent via batch_op.
    if is_postgres:
        op.drop_constraint("ck_iq_max_le_8", "interactive_questions", type_="check")
        op.create_check_constraint(
            "ck_iq_max_le_8_or_select_form",
            "interactive_questions",
            "max_selections <= 8 OR question_type IN ('select', 'form')",
        )
    else:
        # SQLite : recréer la table via batch_op pour modifier les contraintes.
        with op.batch_alter_table("interactive_questions") as batch_op:
            try:
                batch_op.drop_constraint("ck_iq_max_le_8", type_="check")
            except Exception:
                # Best effort : si la contrainte n'existe pas, on continue.
                pass
            batch_op.create_check_constraint(
                "ck_iq_max_le_8_or_select_form",
                "max_selections <= 8 OR question_type IN ('select', 'form')",
            )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # ─── 1. Vérifier qu'aucune ligne n'utilise les nouvelles valeurs ────
    new_values_csv = ",".join(f"'{v}'" for v in NEW_ENUM_VALUES)
    result = bind.execute(
        sa.text(
            f"SELECT COUNT(*) FROM interactive_questions "
            f"WHERE question_type IN ({new_values_csv})"
        )
    )
    count = result.scalar() or 0
    if count > 0:
        raise RuntimeError(
            f"Downgrade impossible : {count} lignes utilisent les nouvelles "
            "valeurs d'enum F10 (yes_no/select/number/...). Migrez ces lignes "
            "manuellement (UPDATE state='expired' ou DELETE) avant downgrade."
        )

    # ─── 2. Restaurer la contrainte initiale ck_iq_max_le_8 ─────────────
    if is_postgres:
        op.drop_constraint(
            "ck_iq_max_le_8_or_select_form",
            "interactive_questions",
            type_="check",
        )
        op.create_check_constraint(
            "ck_iq_max_le_8",
            "interactive_questions",
            "max_selections <= 8",
        )
    else:
        with op.batch_alter_table("interactive_questions") as batch_op:
            try:
                batch_op.drop_constraint(
                    "ck_iq_max_le_8_or_select_form", type_="check",
                )
            except Exception:
                pass
            batch_op.create_check_constraint(
                "ck_iq_max_le_8", "max_selections <= 8",
            )

    # ─── 3. Drop colonnes (jsonb data perdue, log warning) ──────────────
    op.drop_column("interactive_questions", "response_payload")
    op.drop_column("interactive_questions", "payload")

    # Note : PostgreSQL ne supporte pas DROP VALUE FROM ENUM avant PG 16.
    # Les valeurs d'enum F10 restent dans le type — c'est sans impact tant
    # que aucune ligne ne les utilise (vérifié au début de downgrade).
