"""Constantes globales et enums liés à l'authentification et au multi-tenant (F02)."""

import enum
import uuid
from decimal import Decimal


class UserRole(str, enum.Enum):
    """Rôle d'un utilisateur sur la plateforme."""

    PME = "PME"
    ADMIN = "ADMIN"


class InvitationStatus(str, enum.Enum):
    """Statut d'une invitation d'équipe PME."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


# --- Configuration valeurs par défaut F02 ---

# TTL des tokens d'invitation (jours).
INVITE_TOKEN_TTL_DAYS_DEFAULT = 7

# Fenêtre de grâce pour la rotation des refresh tokens (secondes).
REFRESH_TOKEN_GRACE_WINDOW_SECONDS = 5

# Durée de vie des refresh tokens (jours).
REFRESH_TOKEN_EXPIRE_DAYS = 30


# --- F03 — Audit log append-only ---


class AuditAction(str, enum.Enum):
    """Action enregistrée dans l'audit log (mappé sur l'ENUM PG ``audit_action``)."""

    create = "create"
    update = "update"
    delete = "delete"
    view_admin = "view_admin"


class AuditSourceOfChange(str, enum.Enum):
    """Source de mutation tracée par l'audit log (ENUM PG ``audit_source``).

    Note : ``import_`` (avec underscore final) est utilisé côté Python car
    ``import`` est un mot-clé réservé. La valeur stockée en BDD est ``"import"``.
    """

    manual = "manual"
    llm = "llm"
    import_ = "import"
    admin = "admin"
    extension = "extension"


# Taille maximale (en bytes) tolérée pour les valeurs JSON stockées dans
# ``audit_log.old_value`` / ``audit_log.new_value``. Au-delà, la valeur est
# tronquée et remplacée par un marqueur ``{"_truncated": true, ...}``.
AUDIT_VALUE_MAX_BYTES: int = 10 * 1024  # 10 KiB


# --- F04 — Devises et conversion Money ---

# Peg fixe FCFA-EUR (Banque de France/BCEAO).
# Source : 1 EUR = 655,957 XOF (parité fixe depuis 1999, garantie par la
# Banque de France via le Trésor public français pour la zone UEMOA).
FCFA_EUR_PEG: Decimal = Decimal("655.957")

# Quota journalier d'appels HTTP exchangerate-api.com (free tier 1500/mois).
# Notre usage : 1 fetch/jour suffit (un appel retourne toutes les paires).
EXCHANGERATE_DAILY_QUOTA_MAX: int = 50

# Devises supportées par la plateforme (alignées sur app.core.money.Currency).
SUPPORTED_CURRENCIES: tuple[str, ...] = ("XOF", "EUR", "USD", "GBP", "JPY")


# --- F13 — Codes des référentiels MVP pour le scoring multi-référentiels ---

MEFALI_REFERENTIAL_CODE = "mefali"
GCF_REFERENTIAL_CODE = "gcf"
IFC_PS_REFERENTIAL_CODE = "ifc_ps"
BOAD_ESS_REFERENTIAL_CODE = "boad_ess"
GRI_2021_REFERENTIAL_CODE = "gri_2021"

REFERENTIAL_CODES_MVP: tuple[str, ...] = (
    MEFALI_REFERENTIAL_CODE,
    GCF_REFERENTIAL_CODE,
    IFC_PS_REFERENTIAL_CODE,
    BOAD_ESS_REFERENTIAL_CODE,
    GRI_2021_REFERENTIAL_CODE,
)

# UUID stable du référentiel Mefali — utilisé par la migration de seed
# et le fallback ESG Mefali quand fund.referential_id IS NULL. Le UUID est
# arbitrairement fixé à une valeur reconnaissable mais non triviale (les
# UUIDs avec uniquement des zéros et un seul caractère non-zéro déclenchent
# un edge case dans la sérialisation SQLAlchemy 2.0 sur SQLite, cf. tests).
MEFALI_REFERENTIAL_UUID: uuid.UUID = uuid.UUID("0e5f1310-1310-1310-1310-13101310f013")

# Seuils par défaut F13 (scoring multi-référentiels).
DEFAULT_MIN_COVERAGE_FOR_PDF: float = 0.5
DEFAULT_REFERENTIAL_THRESHOLD: float = 50.0
