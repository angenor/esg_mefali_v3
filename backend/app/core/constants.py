"""Constantes globales et enums liés à l'authentification et au multi-tenant (F02)."""

import enum


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


# Taille maximale (en bytes) tolérée pour les valeurs JSON stockées dans
# ``audit_log.old_value`` / ``audit_log.new_value``. Au-delà, la valeur est
# tronquée et remplacée par un marqueur ``{"_truncated": true, ...}``.
AUDIT_VALUE_MAX_BYTES: int = 10 * 1024  # 10 KiB
