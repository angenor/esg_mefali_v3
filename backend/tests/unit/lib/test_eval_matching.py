"""Tests unitaires pour ``app.lib.eval_matching`` (DRY F22/F23)."""

from __future__ import annotations

from app.lib.eval_matching import match_payload_contains, match_tool_called


class TestMatchToolCalled:
    """Couvre les variantes string / liste / None."""

    def test_exact_match_string(self) -> None:
        assert match_tool_called("create_fund_application", "create_fund_application")

    def test_string_mismatch(self) -> None:
        assert not match_tool_called("search_funds", "create_fund_application")

    def test_whitelist_match(self) -> None:
        assert match_tool_called("search_funds", ["create_fund_application", "search_funds"])

    def test_whitelist_mismatch(self) -> None:
        assert not match_tool_called("unknown_tool", ["a", "b", "c"])

    def test_actual_none_returns_false(self) -> None:
        assert not match_tool_called(None, "any_tool")
        assert not match_tool_called(None, ["a", "b"])


class TestMatchPayloadContains:
    """Couvre subset shallow + cas limites None."""

    def test_expected_none_returns_true(self) -> None:
        assert match_payload_contains({"a": 1}, None)

    def test_expected_empty_returns_true(self) -> None:
        assert match_payload_contains({"a": 1}, {})

    def test_actual_none_with_expected_returns_false(self) -> None:
        assert not match_payload_contains(None, {"a": 1})

    def test_subset_match(self) -> None:
        actual = {"fund_id": "GCF", "intermediary_id": "BOAD", "extra": 42}
        expected = {"fund_id": "GCF", "intermediary_id": "BOAD"}
        assert match_payload_contains(actual, expected)

    def test_missing_key(self) -> None:
        assert not match_payload_contains({"a": 1}, {"b": 2})

    def test_value_mismatch(self) -> None:
        assert not match_payload_contains({"fund_id": "GCF"}, {"fund_id": "FEM"})
