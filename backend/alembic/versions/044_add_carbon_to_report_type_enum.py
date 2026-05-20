"""F21 — ajouter la valeur 'carbon' à l'enum PostgreSQL report_type_enum.

Contexte : la migration ``006_reports`` créait l'enum ``report_type_enum``
avec la seule valeur ``esg_compliance``. L'enum Python ``ReportTypeEnum``
a depuis été enrichi de ``carbon`` (F21 — rapport carbone PDF) sans
migration correspondante côté base. Résultat : tout SELECT/INSERT filtrant
``WHERE report_type = 'carbon'`` lève
``InvalidTextRepresentationError: invalid input value for enum
report_type_enum: "carbon"`` (500 sur ``GET /api/reports/?type=carbon``).

Important : ``ALTER TYPE ... ADD VALUE`` ne tourne pas dans une
transaction Alembic — on utilise ``COMMIT`` puis ``ADD VALUE IF NOT
EXISTS`` pour rester idempotent.

Downgrade : PostgreSQL ne supporte pas le retrait d'une valeur d'enum
sans recréer le type complet. Le ``downgrade`` est donc no-op (best
effort, voir avertissement dans la docstring).

Revision ID: 044_add_carbon_to_report_type_enum
Revises: 043_normalize_users_email_lowercase
Create Date: 2026-05-20 12:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "044_add_carbon_to_report_type_enum"
down_revision: Union[str, None] = "043_normalize_users_email_lowercase"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ajoute la valeur 'carbon' à l'enum ``report_type_enum`` (PostgreSQL).

    No-op pour SQLite (tests in-memory n'utilisent pas d'ENUM natif).
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # ALTER TYPE ... ADD VALUE doit s'exécuter hors transaction.
    op.execute("COMMIT")
    op.execute(
        "ALTER TYPE report_type_enum ADD VALUE IF NOT EXISTS 'carbon'"
    )


def downgrade() -> None:
    """No-op : PostgreSQL ne supporte pas DROP VALUE sur un enum.

    Pour retirer ``carbon``, il faudrait recréer ``report_type_enum``
    sans cette valeur (CREATE TYPE _new + UPDATE + ALTER COLUMN +
    DROP TYPE + RENAME). Hors scope tant que des lignes ``carbon``
    peuvent exister en prod.
    """
    return
