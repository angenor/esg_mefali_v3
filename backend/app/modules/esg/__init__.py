"""Module ESG : evaluation et scoring ESG contextualise pour les PME africaines."""

# F047 — Évaluation ESG-projet : import nécessaire pour enregistrement SQLAlchemy
# et inclusion automatique dans AUDITABLE_MODELS via le mixin Auditable.
from app.modules.esg.project_models import (  # noqa: F401
    ProjectEsgAssessment,
    ProjectEsgCriterionResponse,
)
