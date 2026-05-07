"""F19 — Reminder dedup_key + sent_at + archived + read + attestation_renewal enum.

Revision ID: 034_reminder_dedup_key
Revises: 033_create_skills
Create Date: 2026-05-07

Ajoute les colonnes nécessaires au cron dispatcher F19 :

- ``dedup_key VARCHAR(255) NULL`` : clé d'idempotence pour l'auto-création
  (ex. ``"{account_id}:fund_deadline:{fund_id}:2026-06-01:J-30"``).
- ``sent_at TIMESTAMPTZ NULL`` : horodatage du dispatch effectif.
- ``archived BOOLEAN NOT NULL DEFAULT false`` : housekeeping (purge soft).
- ``read BOOLEAN NOT NULL DEFAULT false`` : suivi lecture côté UI (si absent).

Ajoute aussi la valeur ``attestation_renewal`` à l'enum ``reminder_type_enum``
(rappel J-30 expiration attestation F08).

Indexes :
- ``idx_reminders_dedup_key_unique`` : index unique partiel sur
  ``(account_id, dedup_key)`` quand ``dedup_key IS NOT NULL`` (idempotence
  auto-création).
- ``idx_reminders_archived_pending`` : recherche rapide des reminders à
  dispatcher (archived=false, sent=false).

Compatibilité SQLite (tests) : enum extension skip, index unique standard.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "034_reminder_dedup_key"
down_revision: Union[str, None] = "033_create_skills"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ajoute colonnes dedup_key/sent_at/archived/read + extension enum."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # --- Colonnes (nullable défaut puis NOT NULL après backfill server_default) ---
    op.add_column(
        "reminders",
        sa.Column("dedup_key", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "reminders",
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "reminders",
        sa.Column(
            "archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # ``read`` peut déjà exister sur une base pré-existante : on le crée
    # uniquement s'il manque.
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("reminders")}
    if "read" not in cols:
        op.add_column(
            "reminders",
            sa.Column(
                "read",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    # --- Extension enum reminder_type_enum (PG only) ---
    if is_postgres:
        # ALTER TYPE ADD VALUE IF NOT EXISTS doit être hors transaction.
        with op.get_context().autocommit_block():
            op.execute(
                "ALTER TYPE reminder_type_enum "
                "ADD VALUE IF NOT EXISTS 'attestation_renewal'"
            )

    # --- Index unique partiel pour dedup ---
    if is_postgres:
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_reminders_dedup_key_unique "
            "ON reminders (account_id, dedup_key) "
            "WHERE dedup_key IS NOT NULL"
        )
    else:
        # SQLite : pas de support des index partiels avec WHERE complexe en
        # tous cas, on utilise un index unique simple sur (account_id, dedup_key).
        op.create_index(
            "idx_reminders_dedup_key_unique",
            "reminders",
            ["account_id", "dedup_key"],
            unique=True,
        )

    # --- Index secondaire pour le dispatcher ---
    op.create_index(
        "idx_reminders_archived_pending",
        "reminders",
        ["archived", "sent"],
    )


def downgrade() -> None:
    """Supprime les colonnes/indexes ajoutés (pas la valeur enum, limitation PG)."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.drop_index("idx_reminders_archived_pending", table_name="reminders")

    if is_postgres:
        op.execute("DROP INDEX IF EXISTS idx_reminders_dedup_key_unique")
    else:
        op.drop_index("idx_reminders_dedup_key_unique", table_name="reminders")

    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("reminders")}
    if "read" in cols:
        op.drop_column("reminders", "read")
    op.drop_column("reminders", "archived")
    op.drop_column("reminders", "sent_at")
    op.drop_column("reminders", "dedup_key")

    # Note : on ne retire pas la valeur enum 'attestation_renewal' (PG ne
    # supporte pas DROP VALUE FROM ENUM proprement).
