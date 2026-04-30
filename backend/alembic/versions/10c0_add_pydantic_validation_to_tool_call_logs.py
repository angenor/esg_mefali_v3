"""add pydantic validation columns to tool_call_logs (story 10.4)

Revision ID: 10c0pydantic_validation
Revises: 10b2tools_offered
Create Date: 2026-04-29 17:00:00.000000

Story 10.4 — boucle de correction Pydantic (1 retry max + fallback texte).
Cette migration ajoute :
- `validation_status` (String(30) nullable) : statut applicatif de la
  boucle de validation Pydantic. Valeurs canoniques :
    * "valid" — payload valide au 1er essai
    * "valid_after_retry" — invalide puis valide au retry
    * "failed_after_retry" — invalide deux fois -> fallback texte declenche
    * NULL — log runtime non-Pydantic (compat couche with_retry)
- `pydantic_errors` (JSONB nullable) : sortie filtree de `exc.errors()`
  Pydantic v2 (sans `input` pour eviter de stocker des secrets).
- Index `ix_tool_call_logs_validation_status` pour requetes d'audit.

Aucun backfill : les lignes existantes restent NULL.
La colonne `retry_count` existe deja (story 012) et n'est PAS recreee.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "10c0pydantic_validation"
down_revision: Union[str, None] = "10b2tools_offered"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tool_call_logs",
        sa.Column(
            "validation_status",
            sa.String(length=30),
            nullable=True,
        ),
    )
    op.add_column(
        "tool_call_logs",
        sa.Column(
            "pydantic_errors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_tool_call_logs_validation_status",
        "tool_call_logs",
        ["validation_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tool_call_logs_validation_status",
        table_name="tool_call_logs",
    )
    op.drop_column("tool_call_logs", "pydantic_errors")
    op.drop_column("tool_call_logs", "validation_status")
