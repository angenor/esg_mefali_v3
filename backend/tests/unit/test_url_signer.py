"""F05 — Tests du helper ``url_signer`` (T009).

Vérifie : sign + verify roundtrip, expiration, signature corrompue.
"""

from __future__ import annotations

import time

import pytest
from itsdangerous import BadSignature, SignatureExpired

from app.core.url_signer import sign_export_url, verify_export_url


def test_sign_verify_roundtrip() -> None:
    payload = {"account_id": "00000000-0000-0000-0000-000000000001"}
    token = sign_export_url(payload)
    decoded = verify_export_url(token, max_age_seconds=3600)
    assert decoded == payload


def test_sign_verify_with_custom_salt() -> None:
    payload = {"account_id": "x", "action": "cancel_deletion"}
    token = sign_export_url(payload, salt="cancel-del")
    decoded = verify_export_url(token, max_age_seconds=3600, salt="cancel-del")
    assert decoded == payload


def test_verify_rejects_wrong_salt() -> None:
    payload = {"account_id": "x"}
    token = sign_export_url(payload, salt="A")
    with pytest.raises(BadSignature):
        verify_export_url(token, max_age_seconds=3600, salt="B")


def test_verify_corrupted_signature_raises() -> None:
    token = sign_export_url({"a": 1})
    corrupted = token[:-3] + "abc"
    with pytest.raises(BadSignature):
        verify_export_url(corrupted, max_age_seconds=3600)


def test_verify_expired_raises() -> None:
    token = sign_export_url({"a": 1})
    time.sleep(2.5)
    with pytest.raises(SignatureExpired):
        verify_export_url(token, max_age_seconds=1)
