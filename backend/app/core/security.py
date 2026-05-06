"""Fonctions de sécurité : hashing, JWT, vérification.

F02 — extension : refresh tokens avec claim `jti` pour la rotation, helpers
de décodage qui retournent le payload complet.
"""

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    """Hasher un mot de passe avec bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifier un mot de passe contre son hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def create_access_token(subject: str) -> str:
    """Créer un access token JWT."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    to_encode = {"sub": subject, "exp": expire, "type": "access"}
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> tuple[str, str, datetime]:
    """Créer un refresh token JWT avec un claim ``jti``.

    Retourne le tuple ``(token, jti, expires_at)`` afin de pouvoir persister
    une trace en base ``refresh_tokens`` pour la rotation et la révocation.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    jti = uuid.uuid4().hex
    to_encode = {
        "sub": subject,
        "exp": expire,
        "type": "refresh",
        "jti": jti,
    }
    token = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.jwt_algorithm
    )
    return token, jti, expire


def decode_token(token: str, expected_type: str = "access") -> str | None:
    """Décoder un token JWT et retourner le subject (user id).

    Retourne None si le token est invalide ou expiré.
    """
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        token_type = payload.get("type")
        subject: str | None = payload.get("sub")
        if token_type != expected_type or subject is None:
            return None
        return subject
    except JWTError:
        return None


def decode_refresh_token_full(token: str) -> dict | None:
    """Décoder un refresh token et retourner son payload complet (avec jti).

    Retourne None si le token est invalide ou expiré.
    """
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("type") != "refresh":
            return None
        if "sub" not in payload or "jti" not in payload:
            return None
        return payload
    except JWTError:
        return None
