"""Tests F18 — Parsers Mobile Money."""

from __future__ import annotations

import pytest

from app.modules.credit.alternative.mobile_money_parser import (
    MAX_FILE_SIZE_BYTES,
    ParserError,
    VALID_PROVIDERS,
    parse_file,
)


WAVE_CSV_VALID = b"""Date,Type,Amount,Counterparty,Balance
2026-04-01 10:30:00,Incoming,15000,+221770000001,52000
2026-04-02 14:00:00,Outgoing,5000,+221770000002,47000
2026-04-03 09:15:00,Incoming,12000,+221770000001,59000
"""

OM_CSV_VALID = b"""Date;Operation;Montant;Numero;Solde
2026-04-01 09:00:00;Reception;20000;221770000001;100000
2026-04-02 11:30:00;Envoi;7500;221770000003;92500
"""


def test_parse_file_wave_valid():
    """4 lignes valides → 3 transactions."""
    result = parse_file(WAVE_CSV_VALID, provider="wave")
    assert len(result.rows) == 3
    assert result.rejected_count == 0
    assert all(t.provider == "wave" for t in result.rows)
    assert all(t.currency == "XOF" for t in result.rows)
    # Counterparty hashé (64 chars hex SHA-256)
    assert all(len(t.counterparty_hash) == 64 for t in result.rows)


def test_parse_file_orange_money_semicolon():
    """Détection séparateur ; pour Orange Money."""
    result = parse_file(OM_CSV_VALID, provider="orange_money")
    assert len(result.rows) == 2
    assert result.rejected_count == 0
    assert result.rows[0].direction == "incoming"
    assert result.rows[1].direction == "outgoing"


def test_parse_file_invalid_provider_raises():
    with pytest.raises(ParserError, match="provider inconnu"):
        parse_file(b"date,type,amount,counterparty\n", provider="paypal")


def test_parse_file_too_large_raises():
    big = b"x" * (MAX_FILE_SIZE_BYTES + 1)
    with pytest.raises(ParserError, match="trop volumineux"):
        parse_file(big, provider="wave")


def test_parse_file_rejects_invalid_rows():
    """Lignes avec amount manquant comptées rejected."""
    csv = b"""Date,Type,Amount,Counterparty
2026-04-01 10:00:00,Incoming,,+22177
2026-04-02 11:00:00,Outgoing,abc,+22177
2026-04-03 12:00:00,Incoming,5000,+22177
"""
    result = parse_file(csv, provider="wave")
    assert len(result.rows) == 1
    assert result.rejected_count == 2
    assert "errors" in result.errors_summary
    assert len(result.errors_summary["errors"]) == 2


def test_counterparty_hash_deterministic():
    """Le hash counterparty est déterministe pour la déduplication."""
    csv = b"""Date,Type,Amount,Counterparty
2026-04-01 10:00:00,Incoming,5000,+221770000001
"""
    r1 = parse_file(csv, provider="wave")
    r2 = parse_file(csv, provider="wave")
    assert r1.rows[0].counterparty_hash == r2.rows[0].counterparty_hash


def test_valid_providers_constant():
    assert "wave" in VALID_PROVIDERS
    assert "orange_money" in VALID_PROVIDERS
    assert "mtn_momo" in VALID_PROVIDERS
    assert "moov_money" in VALID_PROVIDERS
    assert len(VALID_PROVIDERS) == 4


def test_parse_file_amount_with_comma_decimal():
    """Tolère séparateur décimal virgule (locale FR)."""
    csv = b"""Date,Type,Amount,Counterparty
2026-04-01 10:00:00,Incoming,"15000,50",+221770000001
"""
    result = parse_file(csv, provider="wave")
    assert len(result.rows) == 1
    assert str(result.rows[0].amount) == "15000.50"


def test_parse_file_empty_returns_empty():
    csv = b"Date,Type,Amount,Counterparty\n"
    result = parse_file(csv, provider="wave")
    assert len(result.rows) == 0
    assert result.rejected_count == 0
