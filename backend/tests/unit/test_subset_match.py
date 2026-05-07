"""Tests TDD F22 — helper ``subset_match`` (matching tolerant golden set).

Verifie que le helper reconnait correctement les payloads sous-ensembles
(cles requises presentes, valeurs identiques, recursion sur dicts/listes).

Reference : ``specs/032-decision-tree-with-retry-eval/spec.md`` FR-014.
"""

from __future__ import annotations

import pytest

from tests.llm_eval.conftest import subset_match


pytestmark = pytest.mark.unit


class TestSubsetMatchPositive:
    """subset_match retourne True quand expected ⊆ actual."""

    def test_simple_dict_subset(self):
        assert subset_match({"a": 1, "b": 2}, {"a": 1}) is True

    def test_full_match(self):
        assert subset_match({"a": 1, "b": 2}, {"a": 1, "b": 2}) is True

    def test_empty_expected(self):
        assert subset_match({"a": 1}, {}) is True

    def test_nested_dict_subset(self):
        assert subset_match({"a": {"b": 1, "c": 2}}, {"a": {"b": 1}}) is True

    def test_list_exact_match(self):
        assert subset_match([1, 2, 3], [1, 2, 3]) is True

    def test_list_of_dicts_subset(self):
        actual = [{"k": 1, "v": "a"}, {"k": 2, "v": "b"}]
        expected = [{"k": 1}, {"k": 2}]
        assert subset_match(actual, expected) is True

    def test_none_both_sides(self):
        assert subset_match(None, None) is True


class TestSubsetMatchNegative:
    """subset_match retourne False quand expected n'est pas inclus."""

    def test_value_mismatch(self):
        assert subset_match({"a": 1}, {"a": 2}) is False

    def test_missing_key(self):
        assert subset_match({}, {"a": 1}) is False

    def test_actual_none_expected_present(self):
        assert subset_match(None, {"a": 1}) is False

    def test_nested_value_mismatch(self):
        assert subset_match({"a": {"b": 1}}, {"a": {"b": 2}}) is False

    def test_list_length_mismatch(self):
        assert subset_match([1, 2], [1, 2, 3]) is False

    def test_dict_vs_list(self):
        assert subset_match({"a": 1}, [1, 2]) is False


class TestSubsetMatchEdgeCases:
    """Cas limites : valeurs primitives identiques, types incompatibles."""

    def test_primitive_int_match(self):
        assert subset_match(42, 42) is True

    def test_primitive_string_match(self):
        assert subset_match("hello", "hello") is True

    def test_primitive_mismatch(self):
        assert subset_match(42, 43) is False

    def test_expected_none_passthrough(self):
        # None côté expected = pas de contrainte.
        assert subset_match("anything", None) is True

    def test_empty_lists(self):
        assert subset_match([], []) is True

    def test_deeply_nested(self):
        actual = {
            "user": {
                "profile": {
                    "sector": "agriculture",
                    "country": "CI",
                    "extra": "ignored",
                }
            }
        }
        expected = {"user": {"profile": {"sector": "agriculture"}}}
        assert subset_match(actual, expected) is True
