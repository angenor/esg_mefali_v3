"""Tests unitaires pour csv_writer (T032)."""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone

import pytest

from app.modules.audit.csv_writer import (
    CSV_HEADERS,
    UTF8_BOM,
    _format_row,
    stream_csv,
    stream_json,
)
from app.modules.audit.schemas import AuditEvent


def make_event(**overrides) -> AuditEvent:
    base = {
        "id": uuid.uuid4(),
        "timestamp": datetime(2026, 5, 6, 14, 23, 45, tzinfo=timezone.utc),
        "user_id": uuid.uuid4(),
        "user_email": "user@example.com",
        "account_id": uuid.uuid4(),
        "entity_type": "company_profile",
        "entity_id": uuid.uuid4(),
        "action": "update",
        "field": "sector",
        "old_value": "agriculture",
        "new_value": "énergie renouvelable",
        "source_of_change": "manual",
        "actor_metadata": {"endpoint": "/api/companies/me"},
    }
    base.update(overrides)
    return AuditEvent(**base)


class TestFormatRow:
    def test_basic_row(self):
        e = make_event()
        row = _format_row(e)
        assert len(row) == len(CSV_HEADERS)
        assert "agriculture" in row
        assert "énergie renouvelable" in row
        assert "manual" in row

    def test_actor_metadata_serialized(self):
        e = make_event()
        row = _format_row(e)
        am_value = row[CSV_HEADERS.index("actor_metadata")]
        assert "endpoint" in am_value


@pytest.mark.asyncio
class TestStreamCsv:
    async def test_starts_with_bom(self):
        async def empty_iter():
            return
            yield  # type: ignore[unreachable]

        chunks = []
        async for chunk in stream_csv(empty_iter()):
            chunks.append(chunk)
        assert chunks[0] == UTF8_BOM

    async def test_contains_header_and_french_accents(self):
        async def gen():
            yield make_event(new_value="énergie ç à è")

        chunks = []
        async for chunk in stream_csv(gen()):
            chunks.append(chunk)
        full = b"".join(chunks)
        decoded = full.decode("utf-8-sig")
        assert "id,timestamp" in decoded
        assert "énergie ç à è" in decoded

    async def test_csv_parses_round_trip(self):
        events = [
            make_event(field="sector", new_value="énergie"),
            make_event(field="city", new_value="Dakar, Sénégal"),
        ]

        async def gen():
            for e in events:
                yield e

        chunks = []
        async for chunk in stream_csv(gen()):
            chunks.append(chunk)
        full = b"".join(chunks)
        decoded = full.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(decoded))
        rows = list(reader)
        # 1 header + 2 events
        assert len(rows) == 3
        assert rows[0] == list(CSV_HEADERS)
        assert "énergie" in rows[1]
        # Virgule embedded dans une valeur ne casse pas le CSV
        assert "Dakar, Sénégal" in rows[2]


@pytest.mark.asyncio
class TestStreamJson:
    async def test_empty_returns_empty_array(self):
        async def empty_iter():
            return
            yield  # type: ignore[unreachable]

        chunks = []
        async for chunk in stream_json(empty_iter()):
            chunks.append(chunk)
        full = b"".join(chunks)
        assert full == b"[]"

    async def test_with_events_returns_array(self):
        async def gen():
            yield make_event(field="sector")
            yield make_event(field="city")

        chunks = []
        async for chunk in stream_json(gen()):
            chunks.append(chunk)
        full = b"".join(chunks)
        data = json.loads(full)
        assert isinstance(data, list)
        assert len(data) == 2
