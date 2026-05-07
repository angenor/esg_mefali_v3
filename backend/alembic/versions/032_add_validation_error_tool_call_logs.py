"""F22 — Add validation_error JSONB column to tool_call_logs

Revision ID: 032_add_validation_error_tool_call_logs
Revises: 031_extend_interactive_questions
Create Date: 2026-05-07

Ajoute la colonne ``validation_error: jsonb | null`` à la table ``tool_call_logs``
(F22 — Decision Tree + with_retry effectif + Golden Set 50 cas).

Format stocké :
    [
        {
            "type": "missing",
            "loc": ["sector"],
            "msg": "Field required",
            "input": {...}
        }
    ]

C'est le résultat de ``pydantic.ValidationError.errors()`` sérialisé. La colonne
est ``null`` quand le tool a réussi du premier coup (cas majoritaire) ou quand
l'erreur n'est pas une ValidationError (ex : runtime exception).

L'endpoint admin ``GET /api/admin/metrics/validation-failures`` (F22) agrège
ces lignes pour identifier les tools dont la définition est imprécise.

La migration est zero-downtime : la colonne est nullable et a une valeur par
défaut ``null``, donc aucun backfill n'est requis. Le déploiement peut se
faire en plusieurs étapes (ajout colonne → déploiement code lecteur → écriture).

Réf : ``specs/032-decision-tree-with-retry-eval/{spec,plan,data-model}.md``.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "032_add_validation_error_tool_call_logs"
down_revision: Union[str, None] = "031_extend_interactive_questions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ajoute ``validation_error`` à ``tool_call_logs``."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.add_column(
            "tool_call_logs",
            sa.Column(
                "validation_error",
                postgresql.JSONB(),
                nullable=True,
                comment=(
                    "Pydantic ValidationError.errors() sérialisée en jsonb. "
                    "Null si succès du premier coup ou erreur non-Pydantic."
                ),
            ),
        )
    else:
        # SQLite (tests) : utilise JSON générique, pas de comment.
        op.add_column(
            "tool_call_logs",
            sa.Column("validation_error", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    """Retire la colonne ``validation_error``."""
    op.drop_column("tool_call_logs", "validation_error")
