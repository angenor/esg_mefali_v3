"""Helpers de gestion des tokens d'invitation d'équipe (F02).

Le token clair est généré par ``secrets.token_urlsafe`` (32 octets ⇒ 256 bits
d'entropie). En base on conserve :
- ``token_lookup`` : SHA256 hex du token (déterministe, pour lookup rapide).
- ``token_hash`` : bcrypt du token (pour vérification protégée des timing attacks).
"""

from __future__ import annotations

import hashlib
import secrets

import bcrypt


def generate_invite_token() -> str:
    """Générer un token d'invitation aléatoire URL-safe (32 octets)."""
    return secrets.token_urlsafe(32)


def hash_invite_token(token: str) -> str:
    """Hasher le token via bcrypt pour le stocker en base."""
    return bcrypt.hashpw(token.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_invite_token(token: str, hashed_token: str) -> bool:
    """Vérifier qu'un token clair correspond à son hash bcrypt."""
    try:
        return bcrypt.checkpw(token.encode("utf-8"), hashed_token.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def compute_token_lookup(token: str) -> str:
    """SHA256 hex déterministe pour le lookup rapide de l'invitation.

    Cette valeur est indexée en base (UNIQUE) et permet de retrouver l'unique
    invitation correspondant au token avant de vérifier le hash bcrypt.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
