"""F21 — Tests unitaires du filtre format_date_fr."""

from datetime import date, datetime, timezone

import pytest

from app.lib.date_fr import format_date_fr


class TestFormatDateFr:
    def test_none_returns_empty(self) -> None:
        assert format_date_fr(None) == ""

    def test_empty_string_returns_empty(self) -> None:
        assert format_date_fr("") == ""

    def test_date_object(self) -> None:
        assert format_date_fr(date(2025, 5, 8)) == "08/05/2025"

    def test_datetime_object(self) -> None:
        dt = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)
        assert format_date_fr(dt) == "31/12/2025"

    def test_iso_string(self) -> None:
        assert format_date_fr("2025-01-15") == "15/01/2025"

    def test_iso_string_with_time(self) -> None:
        assert format_date_fr("2025-01-15T10:30:00") == "15/01/2025"

    def test_iso_with_z_timezone(self) -> None:
        assert format_date_fr("2025-01-15T10:30:00Z") == "15/01/2025"

    def test_unparseable_string_returned_as_is(self) -> None:
        assert format_date_fr("pas-une-date") == "pas-une-date"
