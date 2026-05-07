"""Writer CSV streaming UTF-8 BOM (F03 — export audit log)."""

from __future__ import annotations

import csv
import io
import json
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from app.modules.audit.schemas import AuditEvent

# BOM UTF-8 — déclencheur de détection auto par Microsoft Excel.
UTF8_BOM = b"\xef\xbb\xbf"

# Colonnes exportées (ordre stable).
CSV_HEADERS: tuple[str, ...] = (
    "id",
    "timestamp",
    "user_email",
    "user_id",
    "account_id",
    "entity_type",
    "entity_id",
    "action",
    "field",
    "old_value",
    "new_value",
    "source_of_change",
    "actor_metadata",
)


def _json_default(obj: Any) -> Any:
    """Sérialise types non-natifs JSON (UUID, Decimal, datetime, Enum, set)."""
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (set, frozenset)):
        return sorted(obj, key=str)
    return str(obj)


def _format_value(value: Any) -> str:
    """Formate une valeur pour CSV (sérialisation JSON pour dict/list)."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=_json_default)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return str(value)


def _format_row(event: AuditEvent) -> list[str]:
    return [
        str(event.id),
        event.timestamp.isoformat() if event.timestamp else "",
        event.user_email or "",
        str(event.user_id),
        str(event.account_id),
        event.entity_type,
        str(event.entity_id),
        event.action.value if isinstance(event.action, Enum) else str(event.action),
        event.field or "",
        _format_value(event.old_value),
        _format_value(event.new_value),
        event.source_of_change.value
        if isinstance(event.source_of_change, Enum)
        else str(event.source_of_change),
        _format_value(event.actor_metadata),
    ]


async def stream_csv(
    events: AsyncIterator[AuditEvent],
) -> AsyncIterator[bytes]:
    """Génère un export CSV UTF-8 BOM en streaming.

    - Yield 1 : BOM + en-têtes
    - Yields suivants : 1 ligne par événement
    """
    # BOM (yield isolé pour faciliter la détection en test)
    yield UTF8_BOM

    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(CSV_HEADERS)
    yield buffer.getvalue().encode("utf-8")
    buffer.seek(0)
    buffer.truncate(0)

    async for event in events:
        writer.writerow(_format_row(event))
        yield buffer.getvalue().encode("utf-8")
        buffer.seek(0)
        buffer.truncate(0)


async def stream_json(
    events: AsyncIterator[AuditEvent],
) -> AsyncIterator[bytes]:
    """Génère un export JSON array en streaming."""
    yield b"["
    first = True
    async for event in events:
        prefix = b"" if first else b","
        first = False
        # Utilise model_dump pour sérialiser puis json.dumps avec default
        payload = event.model_dump(mode="json")
        yield prefix + json.dumps(
            payload, ensure_ascii=False, default=_json_default
        ).encode("utf-8")
    yield b"]"
