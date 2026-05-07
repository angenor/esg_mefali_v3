"""F05 — Tests du mailer stub (T010).

Vérifie le comportement en mode stub (sans SMTP_HOST configuré) :
- ``send_email`` retourne True.
- Pas d'erreur de bibliothèque SMTP.
- Les helpers de formatage produisent le contenu attendu.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.mailer import (
    format_deletion_cancelled_email,
    format_deletion_completed_email,
    format_deletion_scheduled_email,
    format_export_ready_email,
    send_email,
)


@pytest.mark.asyncio
async def test_send_email_stub_returns_true() -> None:
    """Sans SMTP_HOST configuré, l'envoi est un stub réussi."""
    with patch("app.core.mailer.settings") as mock_settings:
        mock_settings.smtp_host = ""
        mock_settings.email_from = "noreply@test.com"
        result = await send_email(
            to="user@example.com",
            subject="Test",
            body_text="hello",
        )
    assert result is True


@pytest.mark.asyncio
async def test_send_email_stub_accepts_list_of_recipients() -> None:
    with patch("app.core.mailer.settings") as mock_settings:
        mock_settings.smtp_host = ""
        result = await send_email(
            to=["a@x.com", "b@x.com"],
            subject="Test",
            body_text="hello",
        )
    assert result is True


def test_format_deletion_scheduled_email_contains_url_and_date() -> None:
    subject, body = format_deletion_scheduled_email(
        account_name="ACME",
        deletion_date_iso="2026-06-06",
        cancel_url="https://app/cancel?token=abc",
    )
    assert "ESG Mefali" in subject
    assert "ACME" in body
    assert "2026-06-06" in body
    assert "https://app/cancel?token=abc" in body
    assert "privacy@esg-mefali.com" in body


def test_format_deletion_cancelled_email() -> None:
    subject, body = format_deletion_cancelled_email("ACME")
    assert "annulée" in subject.lower() or "annulee" in subject.lower() or "annulé" in subject.lower() or "annule" in subject.lower()
    assert "ACME" in body


def test_format_deletion_completed_email() -> None:
    subject, body = format_deletion_completed_email("ACME")
    assert "supprimé" in subject or "supprime" in subject
    assert "ACME" in body


def test_format_export_ready_email() -> None:
    subject, body = format_export_ready_email(
        account_name="ACME",
        download_url="https://app/dl?token=xyz",
        expires_at_iso="2026-05-14",
    )
    assert "export" in subject.lower() or "Export" in subject
    assert "https://app/dl?token=xyz" in body
    assert "2026-05-14" in body
