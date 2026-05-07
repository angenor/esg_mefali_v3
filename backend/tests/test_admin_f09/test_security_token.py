"""Tests unitaires F09 — token reset password (sécurité)."""

from __future__ import annotations

import pytest

from app.core.security import (
    generate_reset_token,
    hash_token,
    verify_token_match,
)


class TestGenerateResetToken:
    def test_returns_url_safe_string_min_32_chars(self) -> None:
        token = generate_reset_token()
        assert isinstance(token, str)
        assert len(token) >= 32
        # URL-safe: only A-Za-z0-9_-
        assert all(c.isalnum() or c in "-_" for c in token)

    def test_two_tokens_are_different(self) -> None:
        a = generate_reset_token()
        b = generate_reset_token()
        assert a != b


class TestHashToken:
    def test_deterministic_for_same_input(self) -> None:
        token = "sample_token_xyz_1234567890"
        assert hash_token(token) == hash_token(token)

    def test_different_inputs_produce_different_hashes(self) -> None:
        assert hash_token("token_a") != hash_token("token_b")

    def test_returns_hex_sha256_64_chars(self) -> None:
        result = hash_token("any-token-value")
        assert isinstance(result, str)
        assert len(result) == 64
        int(result, 16)  # vérifie que c'est bien hex


class TestVerifyTokenMatch:
    def test_match_returns_true(self) -> None:
        token = generate_reset_token()
        h = hash_token(token)
        assert verify_token_match(token, h) is True

    def test_mismatch_returns_false(self) -> None:
        h = hash_token("good-token")
        assert verify_token_match("wrong-token", h) is False

    def test_empty_returns_false(self) -> None:
        assert verify_token_match("", "any-hash") is False
        assert verify_token_match("token", "") is False
