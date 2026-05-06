"""Service de livraison d'emails (F02).

En MVP F02, l'unique implémentation est ``LoggingEmailDelivery`` : le contenu
de l'email (sujet + corps + lien) est journalisé sur stdout en INFO. Aucun
branchement SMTP/SendGrid/SES n'est introduit.

Une interface ``EmailDeliveryService`` (Protocol) permet le swap futur sans
modification d'appelants (pattern SOLID Dependency Inversion).
"""

from __future__ import annotations

import logging
from typing import Protocol

from app.models.account_invitation import AccountInvitation

logger = logging.getLogger(__name__)


class EmailDeliveryService(Protocol):
    """Interface de livraison d'email."""

    async def send(self, to: str, subject: str, body: str) -> None:
        """Envoyer un email."""
        ...


class LoggingEmailDelivery:
    """Implémentation MVP : journalisation INFO du contenu de l'email."""

    async def send(self, to: str, subject: str, body: str) -> None:
        """Journaliser l'email plutôt que de l'envoyer réellement."""
        logger.info(
            "[EMAIL DELIVERY STUB] to=%s subject=%s body=%s",
            to,
            subject,
            body,
        )


def format_invitation_subject(account_name: str) -> str:
    """Construire le sujet d'un email d'invitation."""
    return f"Invitation à rejoindre {account_name} sur ESG Mefali"


def format_invitation_body(invitation: AccountInvitation, invitation_url: str) -> str:
    """Construire le corps d'un email d'invitation.

    Le corps inclut le lien d'inscription avec le token clair en query string.
    En MVP F02 ce corps est uniquement journalisé (pas d'envoi réel), donc le
    token transite via les logs serveur — acceptable pour un environnement de
    développement.
    """
    return (
        "Bonjour,\n\n"
        "Vous avez été invité(e) à rejoindre une équipe sur ESG Mefali.\n\n"
        f"Pour accepter cette invitation, cliquez sur le lien suivant :\n{invitation_url}\n\n"
        f"Cette invitation expire le {invitation.expires_at.strftime('%d/%m/%Y à %H:%M UTC')}.\n\n"
        "Si vous n'attendiez pas cette invitation, vous pouvez ignorer cet email.\n\n"
        "L'équipe ESG Mefali"
    )
