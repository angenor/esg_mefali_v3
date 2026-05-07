"""F19 — Tests unitaires du builder de payload SSE."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.models.action_plan import Reminder, ReminderType
from app.services.notifications.reminder_notifier import (
    build_reminder_payload,
)


pytestmark = pytest.mark.unit


def _make_reminder(
    *,
    type_: ReminderType = ReminderType.action_due,
    dedup_key: str | None = None,
    action_item_id: uuid.UUID | None = None,
) -> Reminder:
    """Crée un Reminder en mémoire (non persisté)."""
    r = Reminder(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        type=type_,
        message="Test message",
        scheduled_at=datetime.now(timezone.utc),
        sent=True,
        sent_at=datetime.now(timezone.utc),
        archived=False,
        read=False,
        dedup_key=dedup_key,
        action_item_id=action_item_id,
    )
    return r


def test_payload_basic_structure():
    """Le payload a les clés requises (id, type, message, metadata)."""
    r = _make_reminder()
    payload = build_reminder_payload(r)
    assert "id" in payload
    assert "type" in payload
    assert "message" in payload
    assert "scheduled_at" in payload
    assert "sent_at" in payload
    assert "metadata" in payload


def test_payload_action_url_for_fund_deadline():
    """fund_deadline → action_url contient /financing/{entity_id}."""
    fund_id = "abc-fund-123"
    r = _make_reminder(
        type_=ReminderType.fund_deadline,
        dedup_key=f"acct1:fund_deadline:{fund_id}:2026-06-01:J-30",
    )
    payload = build_reminder_payload(r)
    assert f"/financing/{fund_id}" == payload["metadata"]["action_url"]


def test_payload_action_url_for_assessment_renewal():
    """assessment_renewal → action_url = /esg."""
    r = _make_reminder(type_=ReminderType.assessment_renewal)
    payload = build_reminder_payload(r)
    assert payload["metadata"]["action_url"] == "/esg"


def test_payload_action_url_for_attestation_renewal():
    """attestation_renewal → action_url contient /applications/{id}/attestation."""
    att_id = "att-123"
    r = _make_reminder(
        type_=ReminderType.attestation_renewal,
        dedup_key=f"acct1:attestation_renewal:{att_id}:J-30",
    )
    payload = build_reminder_payload(r)
    assert f"/applications/{att_id}/attestation" == payload["metadata"]["action_url"]


def test_payload_action_url_for_intermediary_followup():
    """intermediary_followup → /applications/{id}."""
    app_id = "app-456"
    r = _make_reminder(
        type_=ReminderType.intermediary_followup,
        dedup_key=f"acct1:intermediary_followup:{app_id}:silence14",
    )
    payload = build_reminder_payload(r)
    assert f"/applications/{app_id}" == payload["metadata"]["action_url"]


def test_payload_action_url_for_action_due_default():
    """action_due → /action-plan."""
    r = _make_reminder(type_=ReminderType.action_due)
    payload = build_reminder_payload(r)
    assert payload["metadata"]["action_url"] == "/action-plan"


def test_payload_action_url_for_custom_default():
    """custom → /action-plan."""
    r = _make_reminder(type_=ReminderType.custom)
    payload = build_reminder_payload(r)
    assert payload["metadata"]["action_url"] == "/action-plan"


def test_payload_metadata_entity_type():
    """metadata.entity_type est correctement mappé par type."""
    cases = [
        (ReminderType.fund_deadline, "fund"),
        (ReminderType.assessment_renewal, "esg_assessment"),
        (ReminderType.attestation_renewal, "attestation"),
        (ReminderType.intermediary_followup, "fund_application"),
        (ReminderType.action_due, "action_item"),
        (ReminderType.custom, "action_item"),
    ]
    for type_, expected_entity in cases:
        r = _make_reminder(type_=type_)
        payload = build_reminder_payload(r)
        assert payload["metadata"]["entity_type"] == expected_entity


def test_payload_iso_dates():
    """scheduled_at et sent_at sont sérialisés au format ISO."""
    r = _make_reminder()
    payload = build_reminder_payload(r)
    assert isinstance(payload["scheduled_at"], str)
    # Format ISO compatible parsing.
    datetime.fromisoformat(payload["scheduled_at"])
    assert isinstance(payload["sent_at"], str)


def test_payload_json_serializable():
    """Le payload doit être JSON-serializable."""
    import json

    r = _make_reminder()
    payload = build_reminder_payload(r)
    json.dumps(payload)
