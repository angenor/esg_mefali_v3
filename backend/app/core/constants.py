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
