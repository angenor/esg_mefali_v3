"""Modèles SQLAlchemy — importer tous les modèles pour Alembic."""

from app.models.base import Base  # noqa: F401

# F02 — multi-tenant : Account doit être importé avant les modèles qui le
# référencent via FK (tous les modèles métier).
from app.models.account import Account  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.refresh_token import RefreshToken  # noqa: F401
from app.models.account_invitation import AccountInvitation  # noqa: F401
from app.models.conversation import Conversation  # noqa: F401
from app.models.message import Message  # noqa: F401
from app.models.company import CompanyProfile  # noqa: F401
from app.models.document import Document, DocumentAnalysis, DocumentChunk  # noqa: F401
from app.models.esg import ESGAssessment  # noqa: F401
from app.models.report import Report  # noqa: F401
from app.models.carbon import CarbonAssessment, CarbonEmissionEntry  # noqa: F401
from app.models.financing import (  # noqa: F401
    FinancingChunk,
    Fund,
    FundIntermediary,
    FundMatch,
    Intermediary,
)
from app.models.application import FundApplication  # noqa: F401
# F07 — Entité Offre (Couple Fonds × Intermédiaire)
from app.models.offer import Offer  # noqa: F401
from app.models.credit import CreditDataPoint, CreditScore  # noqa: F401
from app.models.action_plan import (  # noqa: F401
    ActionItem,
    ActionPlan,
    Badge,
    Reminder,
)
from app.models.tool_call_log import ToolCallLog  # noqa: F401
from app.models.interactive_question import (  # noqa: F401
    InteractiveQuestion,
    InteractiveQuestionState,
    InteractiveQuestionType,
)

# F01 — Catalogue de sources verifiees
from app.models.source import (  # noqa: F401
    PublicationStatus,
    Source,
    VerificationStatus,
)

# F03 — Audit log append-only
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.indicator import (  # noqa: F401
    Criterion,
    Formula,
    Indicator,
    Threshold,
)
from app.models.referential import Referential, ReferentialIndicator  # noqa: F401
from app.models.emission_factor import EmissionFactor  # noqa: F401
from app.models.required_document import RequiredDocument  # noqa: F401
from app.models.simulation_factor import SimulationFactor  # noqa: F401
from app.models.unsourced_flag import UnsourcedFlag  # noqa: F401

# F04 — Versioning + Money + Multi-devises
from app.models.exchange_rate import ExchangeRate  # noqa: F401

# F12 — Mémoire contextuelle pgvector (chunks de messages indexés pour recherche sémantique)
from app.models.message_chunk import MessageChunk  # noqa: F401

# F06 — Entité Projet Vert (Module 1.3)
from app.models.project import Project  # noqa: F401
from app.models.project_document import ProjectDocument  # noqa: F401

# F08 — Attestation Vérifiable Ed25519
from app.models.attestation import Attestation  # noqa: F401

# F05 — RGPD : Consentement granulaire
from app.models.consent import Consent  # noqa: F401

# F13 — Scoring ESG multi-référentiels
from app.models.referential_score import ComputedByEnum, ReferentialScore  # noqa: F401
