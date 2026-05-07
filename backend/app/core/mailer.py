"""F05 — Mailer SMTP avec stub MVP.

Service unifié d'envoi d'email transactionnel. En MVP, si ``SMTP_HOST`` n'est
pas configuré, l'envoi devient un stub qui logue le payload dans
``audit_log`` (entity_type='email', action='sent_stub'). En production avec
SMTP configuré, utilise ``aiosmtplib`` pour un envoi async.

Cohérent avec ``CLAUDE.md`` : « Email : un service d'envoi d'email
transactionnel est disponible. Si le projet n'en dispose pas encore, F05
utilise un stub ``app/core/mailer.py`` qui logge les emails ».
"""

from __future__ import annotations

import logging
from email.message import EmailMessage
from typing import Any
from uuid import UUID

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_email(
    *,
    to: str | list[str],
    subject: str,
    body_text: str,
    body_html: str | None = None,
    audit_log_payload: dict[str, Any] | None = None,
) -> bool:
    """Envoyer un email transactionnel via SMTP (réel ou stub).

    Args:
        to: adresse(s) email du destinataire.
        subject: sujet de l'email.
        body_text: contenu texte plain (toujours requis).
        body_html: contenu HTML alternatif (optionnel).
        audit_log_payload: champs supplémentaires pour le stub log
            (action, account_id, etc.).

    Returns:
        True si envoi réussi (ou stub réussi), False en cas d'erreur SMTP.
    """
    recipients = [to] if isinstance(to, str) else list(to)

    if not settings.smtp_host:
        # Mode stub MVP : on logue uniquement.
        logger.info(
            "[MAILER STUB] to=%s subject=%r body_text_preview=%r",
            recipients,
            subject,
            body_text[:120],
        )
        # Le caller peut consigner un audit_log si besoin (par ex. avec
        # ``action='sent_stub'``) ; on laisse cette responsabilité au service
        # appelant pour préserver l'idempotence et le contexte (account_id).
        return True

    try:
        import aiosmtplib

        message = EmailMessage()
        message["From"] = settings.email_from
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        message.set_content(body_text)
        if body_html:
            message.add_alternative(body_html, subtype="html")

        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            use_tls=False,
            start_tls=True if settings.smtp_user else None,
        )
        logger.info(
            "[MAILER] sent to=%s subject=%r", recipients, subject,
        )
        return True
    except Exception as exc:  # pragma: no cover — défensif
        logger.error(
            "[MAILER] échec envoi to=%s subject=%r erreur=%s",
            recipients,
            subject,
            exc,
        )
        return False


def format_deletion_scheduled_email(
    *,
    account_name: str,
    deletion_date_iso: str,
    cancel_url: str,
) -> tuple[str, str]:
    """Sujet + corps de l'email de confirmation de suppression programmée."""
    subject = "Confirmation de suppression de votre compte ESG Mefali"
    body = (
        f"Bonjour,\n\n"
        f"Vous avez programmé la suppression de votre compte ESG Mefali "
        f"« {account_name} ».\n\n"
        f"Date prévue de suppression effective : {deletion_date_iso}\n\n"
        f"Vous pouvez annuler cette suppression à tout moment d'ici cette date "
        f"en cliquant sur le lien suivant :\n{cancel_url}\n\n"
        f"Au-delà de cette date, votre compte et toutes ses données seront "
        f"effacés définitivement (sauf l'historique d'audit anonymisé pour "
        f"conformité légale).\n\n"
        f"L'équipe ESG Mefali — privacy@esg-mefali.com"
    )
    return subject, body


def format_deletion_cancelled_email(account_name: str) -> tuple[str, str]:
    """Sujet + corps de l'email de confirmation d'annulation."""
    subject = "Suppression annulée — votre compte ESG Mefali reste actif"
    body = (
        f"Bonjour,\n\n"
        f"La suppression programmée de votre compte ESG Mefali "
        f"« {account_name} » a été annulée.\n\n"
        f"Votre compte reste actif et toutes vos données sont préservées.\n\n"
        f"L'équipe ESG Mefali — privacy@esg-mefali.com"
    )
    return subject, body


def format_deletion_completed_email(account_name: str) -> tuple[str, str]:
    """Sujet + corps de l'email de confirmation finale post-purge."""
    subject = "Votre compte ESG Mefali a été supprimé"
    body = (
        f"Bonjour,\n\n"
        f"Conformément à votre demande, votre compte ESG Mefali "
        f"« {account_name} » et toutes ses données ont été supprimés "
        f"définitivement.\n\n"
        f"Seul un historique d'audit anonymisé est conservé pour conformité "
        f"légale (RGPD Art. 17, durée 6 ans).\n\n"
        f"L'équipe ESG Mefali — privacy@esg-mefali.com"
    )
    return subject, body


def format_export_ready_email(
    *,
    account_name: str,
    download_url: str,
    expires_at_iso: str,
) -> tuple[str, str]:
    """Sujet + corps de l'email de notification d'export RGPD prêt."""
    subject = "Votre export RGPD ESG Mefali est prêt"
    body = (
        f"Bonjour,\n\n"
        f"L'export complet des données de votre compte ESG Mefali "
        f"« {account_name} » est prêt.\n\n"
        f"Vous pouvez télécharger le fichier ZIP via ce lien sécurisé :\n"
        f"{download_url}\n\n"
        f"Ce lien expire le {expires_at_iso}.\n\n"
        f"L'équipe ESG Mefali — privacy@esg-mefali.com"
    )
    return subject, body


__all__ = [
    "send_email",
    "format_deletion_scheduled_email",
    "format_deletion_cancelled_email",
    "format_deletion_completed_email",
    "format_export_ready_email",
]
