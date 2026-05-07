"""F05 — Helper de signature/vérification d'URLs temporaires.

Utilisé pour les liens d'export RGPD (téléchargement signé 24h pour les
documents, 7 jours pour le ZIP final asynchrone, 30 jours pour le lien
d'annulation de suppression de compte). Repose sur ``itsdangerous`` qui
embarque expiration et signature HMAC-SHA256 dans le token (pas de stockage
BDD nécessaire).
"""

from __future__ import annotations

from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import settings


def _serializer(salt: str = "f05-export") -> URLSafeTimedSerializer:
    """Construit un serializer ``itsdangerous`` avec la clé secrète projet."""
    return URLSafeTimedSerializer(
        secret_key=settings.export_url_signing_key or settings.secret_key,
        salt=salt,
    )


def sign_export_url(
    payload: dict[str, Any],
    *,
    salt: str = "f05-export",
) -> str:
    """Signe un payload arbitraire et retourne un token URL-safe.

    Args:
        payload: dictionnaire JSON-serializable (ex. ``{'account_id': '...'}``).
        salt: salt distinct par usage (export download, cancel deletion, etc.)
            pour éviter les confusions de tokens.

    Returns:
        Token signé URL-safe (utilisable dans un query param).
    """
    return _serializer(salt=salt).dumps(payload)


def verify_export_url(
    token: str,
    *,
    max_age_seconds: int,
    salt: str = "f05-export",
) -> dict[str, Any]:
    """Vérifie la signature et l'âge maximal du token.

    Args:
        token: token signé renvoyé par :func:`sign_export_url`.
        max_age_seconds: âge maximal autorisé (24h=86400, 7j=604800, 30j=2592000).
        salt: doit correspondre au salt utilisé lors du sign.

    Returns:
        Le payload original si la signature et l'âge sont valides.

    Raises:
        SignatureExpired: token expiré.
        BadSignature: signature invalide ou corrompue.
    """
    return _serializer(salt=salt).loads(token, max_age=max_age_seconds)


__all__ = [
    "sign_export_url",
    "verify_export_url",
    "BadSignature",
    "SignatureExpired",
]
