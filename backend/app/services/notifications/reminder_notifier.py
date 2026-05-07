"""F19 — Builder de payloads SSE pour les évènements ``reminder_due``.

Construit le payload conforme au schema
``contracts/reminder_dispatched_event_schema.json`` à partir d'un
``Reminder`` SQLAlchemy. Calcule l'``action_url`` cible selon le type.
"""

from __future__ import annotations

from typing import Any

from app.models.action_plan import Reminder, ReminderType


# Mapping ReminderType → format URL frontend (avec placeholder ``{entity_id}``).
_ACTION_URL_TEMPLATE: dict[ReminderType, str] = {
    ReminderType.fund_deadline: "/financing/{entity_id}",
    ReminderType.assessment_renewal: "/esg",
    ReminderType.attestation_renewal: "/applications/{entity_id}/attestation",
    ReminderType.intermediary_followup: "/applications/{entity_id}",
    ReminderType.action_due: "/action-plan",
    ReminderType.custom: "/action-plan",
}


def _resolve_entity_id(reminder: Reminder) -> str | None:
    """Extrait l'entity_id pertinent depuis un Reminder.

    Pour les reminders adossés à une ActionItem, on remonte vers
    ``action_item_id`` (id de l'action). Pour les autres, on tente de
    parser le ``dedup_key`` qui contient l'id de l'entité (fund/application).
    """
    # Fallback : tenter de parser depuis la dedup_key au format
    # ``{account_id}:{type}:{entity_id}:...``.
    if reminder.dedup_key:
        parts = reminder.dedup_key.split(":")
        if len(parts) >= 3:
            return parts[2]
    if reminder.action_item_id:
        return str(reminder.action_item_id)
    return None


def _build_action_url(reminder: Reminder) -> str:
    """Calcule l'URL frontend de destination pour un reminder."""
    template = _ACTION_URL_TEMPLATE.get(reminder.type, "/action-plan")
    entity_id = _resolve_entity_id(reminder)
    if entity_id is not None:
        return template.format(entity_id=entity_id)
    # Si pas d'entity_id, on garde l'URL générique (action-plan / esg).
    return template.replace("/{entity_id}", "")


def build_reminder_payload(reminder: Reminder) -> dict[str, Any]:
    """Construit le payload SSE pour un reminder dispatché.

    Schema :

    ```json
    {
        "id": "uuid",
        "type": "fund_deadline",
        "message": "...",
        "scheduled_at": "2026-05-07T08:00:00Z",
        "sent_at": "2026-05-07T08:01:23Z",
        "metadata": {
            "entity_id": "uuid",
            "entity_type": "fund",
            "action_url": "/financing/abc",
            "intermediary_name": null
        }
    }
    ```
    """
    entity_id = _resolve_entity_id(reminder)
    entity_type_map = {
        ReminderType.fund_deadline: "fund",
        ReminderType.assessment_renewal: "esg_assessment",
        ReminderType.attestation_renewal: "attestation",
        ReminderType.intermediary_followup: "fund_application",
        ReminderType.action_due: "action_item",
        ReminderType.custom: "action_item",
    }

    metadata: dict[str, Any] = {
        "entity_id": entity_id,
        "entity_type": entity_type_map.get(reminder.type),
        "action_url": _build_action_url(reminder),
    }

    # Snapshot intermédiaire si action item lié et données présentes.
    if reminder.action_item is not None:
        if reminder.action_item.intermediary_name:
            metadata["intermediary_name"] = reminder.action_item.intermediary_name

    return {
        "id": str(reminder.id),
        "type": reminder.type.value,
        "message": reminder.message,
        "scheduled_at": reminder.scheduled_at.isoformat() if reminder.scheduled_at else None,
        "sent_at": reminder.sent_at.isoformat() if reminder.sent_at else None,
        "read": reminder.read,
        "archived": reminder.archived,
        "metadata": metadata,
    }
