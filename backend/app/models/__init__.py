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
