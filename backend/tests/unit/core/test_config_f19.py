"""F19 — Tests unitaires des nouvelles env vars de config."""

from __future__ import annotations

import pytest

from app.core.config import Settings


pytestmark = pytest.mark.unit


def test_default_apscheduler_disabled():
    """Par défaut, APScheduler est désactivé (sécurité)."""
    s = Settings()
    assert s.apscheduler_enabled is False


def test_default_admin_debug_scheduler_disabled():
    """Par défaut, les endpoints debug sont désactivés."""
    s = Settings()
    assert s.admin_debug_scheduler is False


def test_default_silence_radio_delay():
    """Délai silence radio = 14 j."""
    s = Settings()
    assert s.silence_radio_delay_days == 14


def test_default_assessment_renewal_grace():
    """Délai renewal ESG = 30 j."""
    s = Settings()
    assert s.assessment_renewal_grace_days == 30


def test_default_attestation_expiration_grace():
    """Délai expiration attestation = 30 j."""
    s = Settings()
    assert s.attestation_expiration_grace_days == 30


def test_default_dispatch_batch_limit():
    """batch limit dispatcher = 100."""
    s = Settings()
    assert s.dispatch_batch_limit == 100


def test_default_purge_after_days():
    """Purge après 90 j (housekeeping)."""
    s = Settings()
    assert s.purge_old_reminders_after_days == 90


def test_default_deadline_reminder_days_csv():
    """Liste J-N par défaut = [30, 7, 1]."""
    s = Settings()
    assert s.deadline_reminder_days_list == [30, 7, 1]


def test_deadline_reminder_days_parse_custom():
    """Parsing CSV custom."""
    s = Settings(deadline_reminder_days="14,3")
    assert s.deadline_reminder_days_list == [14, 3]


def test_deadline_reminder_days_parse_invalid_fallback():
    """CSV invalide → fallback [30,7,1]."""
    s = Settings(deadline_reminder_days="abc,xyz")
    assert s.deadline_reminder_days_list == [30, 7, 1]


def test_deadline_reminder_days_parse_empty():
    """Chaîne vide → fallback [30,7,1]."""
    s = Settings(deadline_reminder_days="")
    assert s.deadline_reminder_days_list == [30, 7, 1]
