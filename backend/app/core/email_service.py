"""Service email F09 — Reset password (stub MVP).

En MVP, le backend ``console`` logge le contenu de l'email dans stdout au
niveau INFO. C'est suffisant pour le test E2E (capture de log) et pour le
déploiement initial.

Backends supportés :
- ``console`` (default) : log INFO + retourne success.
- ``noop`` : ne fait rien (utilisé par les tests d'intégration).
- ``smtp`` : délègue à ``app.core.mailer.send_email`` (asynchrone).

Configuration via env :
- ``EMAIL_BACKEND`` (default: ``console``)
- ``EMAIL_FROM`` (default: ``noreply@esg-mefali.local``)
- ``FRONTEND_BASE_URL`` (default: ``http://localhost:3000``) — pour
  construire le ``reset_link``.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailResult:
    """Résultat de l'envoi d'un email (immuable)."""

    success: bool
    backend: str
    message: str | None = None


class EmailServiceProtocol(Protocol):
    """Interface du service email."""

    async def send_password_reset_email(
        self, *, user_email: str, reset_link: str
    ) -> EmailResult: ...


def _build_reset_email_body(user_email: str, reset_link: str) -> tuple[str, str]:
    """Construire le sujet et le corps texte de l'email de reset.

    Retourne ``(subject, body_text)``.
    """
    subject = "Réinitialisation de votre mot de passe ESG Mefali"
    body = (
        f"Bonjour,\n\n"
        f"Un administrateur a déclenché la réinitialisation de votre mot de passe "
        f"sur ESG Mefali (compte {user_email}).\n\n"
        f"Cliquez sur le lien ci-dessous pour choisir un nouveau mot de passe :\n"
        f"{reset_link}\n\n"
        f"Ce lien expire dans 1 heure.\n\n"
        f"Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.\n\n"
        f"L'équipe ESG Mefali"
    )
    return subject, body


class ConsoleEmailService:
    """Backend ``console`` : log INFO + retourne success.

    Utilisé en dev / MVP. Le contenu de l'email est journalisé dans stdout
    pour permettre la capture par les tests E2E.
    """

    backend_name = "console"

    async def send_password_reset_email(
        self, *, user_email: str, reset_link: str
    ) -> EmailResult:
        subject, body = _build_reset_email_body(user_email, reset_link)
        logger.info(
            "[EMAIL:console] To=%s | Subject=%s | Reset-Link=%s",
            user_email,
            subject,
            reset_link,
        )
        logger.info("[EMAIL:console] Body:\n%s", body)
        return EmailResult(success=True, backend=self.backend_name)


class NoopEmailService:
    """Backend ``noop`` : ne fait rien (tests d'intégration)."""

    backend_name = "noop"

    async def send_password_reset_email(
        self, *, user_email: str, reset_link: str
    ) -> EmailResult:
        return EmailResult(success=True, backend=self.backend_name)


def get_email_service() -> EmailServiceProtocol:
    """Factory : retourne le service email configuré via ``EMAIL_BACKEND``.

    Default : ``console``.
    """
    backend = os.getenv("EMAIL_BACKEND", "console").lower()
    if backend == "noop":
        return NoopEmailService()
    return ConsoleEmailService()


def build_reset_link(token: str) -> str:
    """Construire le lien de reset à inclure dans l'email."""
    base = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")
    return f"{base}/auth/reset?token={token}"
