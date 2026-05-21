"""Drop la FK rigide reports.assessment_id -> esg_assessments.

reports.assessment_id est polymorphe : il peut référencer soit un
esg_assessments.id, soit un carbon_assessments.id, selon la valeur de
report_type. Garder une FK sur une seule des deux tables provoque un
ForeignKeyViolationError quand on génère un rapport carbone.

Stratégie : drop la FK (le code applicatif filtre déjà par report_type
avant les lookups, et CASCADE n'est plus géré par PG mais par les
services métier). Index conservé pour les recherches.

Revision ID: 045_reports_polymorphic_assessment_fk
Revises: 043_embeddings_voyage_dim
Create Date: 2026-05-21
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "045_reports_polymorphic_assessment_fk"
down_revision = "044_add_carbon_to_report_type_enum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop la FK rigide pour permettre les references polymorphes."""
    op.execute(
        "ALTER TABLE reports DROP CONSTRAINT IF EXISTS reports_assessment_id_fkey"
    )


def downgrade() -> None:
    """Restaurer la FK vers esg_assessments (rétro-compat avant carbon)."""
    # NB : echoue si des rapports carbone existent deja avec
    # assessment_id pointant vers carbon_assessments (FK violation).
    # Dans ce cas, il faut d'abord nettoyer les rapports carbone.
    op.execute(
        "ALTER TABLE reports "
        "ADD CONSTRAINT reports_assessment_id_fkey "
        "FOREIGN KEY (assessment_id) REFERENCES esg_assessments(id) "
        "ON DELETE CASCADE"
    )
