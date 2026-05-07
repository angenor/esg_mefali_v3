"""Tests unitaires de la troncature 10 KB (T006)."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum

import pytest

from app.core.auditable import _json_default, _truncate_value
from app.core.constants import AUDIT_VALUE_MAX_BYTES


class TestJsonDefault:
    def test_uuid_serialized(self) -> None:
        u = uuid.uuid4()
        assert _json_default(u) == str(u)

    def test_decimal_to_string(self) -> None:
        d = Decimal("12345.67")
        assert _json_default(d) == "12345.67"

    def test_datetime_iso(self) -> None:
        dt = datetime(2026, 5, 6, 14, 23, 45, tzinfo=timezone.utc)
        assert _json_default(dt) == dt.isoformat()

    def test_date_iso(self) -> None:
        d = date(2026, 5, 6)
        assert _json_default(d) == "2026-05-06"

    def test_enum_value(self) -> None:
        class MyEnum(str, Enum):
            foo = "foo"
            bar = "bar"

        assert _json_default(MyEnum.foo) == "foo"

    def test_set_sorted(self) -> None:
        result = _json_default({3, 1, 2})
        assert result == [1, 2, 3]

    def test_unknown_falls_back_to_str(self) -> None:
        class Custom:
            def __str__(self) -> str:
                return "custom_repr"

        assert _json_default(Custom()) == "custom_repr"


class TestTruncateValue:
    def test_none_returned_as_none(self) -> None:
        assert _truncate_value(None) is None

    def test_short_string_unchanged(self) -> None:
        assert _truncate_value("hello") == "hello"

    def test_short_dict_unchanged(self) -> None:
        d = {"sector": "agriculture", "year": 2026}
        assert _truncate_value(d) == d

    def test_value_below_max_unchanged(self) -> None:
        # JSON ~ 100 octets : largement sous 10 KB
        v = {"name": "test", "items": [1, 2, 3] * 5}
        assert _truncate_value(v) == v

    def test_exactly_at_max_unchanged(self) -> None:
        # On construit une string dont la sérialisation JSON fait pile 10 KB.
        # JSON pour "xxxx...": ouvre/ferme = 2 octets de guillemets.
        target = AUDIT_VALUE_MAX_BYTES - 2
        s = "a" * target
        assert _truncate_value(s) == s

    def test_above_max_returns_truncation_marker(self) -> None:
        s = "a" * (AUDIT_VALUE_MAX_BYTES * 2)
        result = _truncate_value(s)
        assert isinstance(result, dict)
        assert result["_truncated"] is True
        assert result["_truncated_size"] > AUDIT_VALUE_MAX_BYTES
        assert isinstance(result["_preview"], str)
        assert len(result["_preview"].encode("utf-8")) <= 8 * 1024 + 2

    def test_above_max_dict_truncated(self) -> None:
        big = {"data": "x" * (AUDIT_VALUE_MAX_BYTES * 2)}
        result = _truncate_value(big)
        assert isinstance(result, dict)
        assert result["_truncated"] is True
        # Le _preview doit contenir le début du JSON sérialisé.
        assert result["_preview"].startswith('{"data":"x')

    def test_truncate_preserves_serializability(self) -> None:
        # Le marqueur tronqué doit être sérialisable JSON sans erreur.
        s = "z" * (AUDIT_VALUE_MAX_BYTES * 3)
        result = _truncate_value(s)
        json.dumps(result)  # ne doit pas lever
