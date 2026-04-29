"""add tools_offered column to tool_call_logs (story 10.2)

Revision ID: 10b2tools_offered
Revises: 018_interactive
Create Date: 2026-04-29 16:00:00.000000

Story 10.2 — filtrage des tools par contexte de page. Cette migration
ajoute la colonne `tools_offered` (JSONB nullable) pour journaliser la
liste des tools effectivement exposes au LLM a chaque tour. Aucun
backfill : les lignes existantes restent NULL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "10b2tools_offered"
down_revision: Union[str, None] = "018_interactive"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tool_call_logs",
        sa.Column(
            "tools_offered",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tool_call_logs", "tools_offered")
