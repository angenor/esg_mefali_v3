"""Tests unitaires SigningKeyStore + sign/verify (F08 — T010)."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.modules.attestations.signing import (
    SigningKeyStore,
    build_canonical_payload,
    get_public_key_id,
    get_public_key_pem,
    sign_payload,
    verify_signature,
)


@pytest.fixture(autouse=True)
def reset_signing_store():
    """Réinitialise le singleton entre tests pour isolation."""
    SigningKeyStore._reset_for_testing()
    yield
    SigningKeyStore._reset_for_testing()


def test_signing_store_lazy_init_generates_ephemeral_key_in_dev():
    """En dev (key vide), une paire éphémère est générée."""
    store = SigningKeyStore.get_instance()
    assert store.public_key_id == "v1"
    assert isinstance(store.get_public_key_pem(), str)
    assert "BEGIN PUBLIC KEY" in store.get_public_key_pem()


def test_signing_store_singleton_same_instance():
    """``get_instance`` retourne toujours la même instance."""
    s1 = SigningKeyStore.get_instance()
    s2 = SigningKeyStore.get_instance()
    assert s1 is s2


def test_build_canonical_payload_is_deterministic():
    """Le JSON canonique est stable entre 2 appels avec mêmes données."""
    aid = uuid4()
    valid_from = datetime(2026, 5, 7, 10, 30, tzinfo=timezone.utc)
    valid_until = datetime(2027, 5, 7, 10, 30, tzinfo=timezone.utc)
    scores = {"combined": 73, "solvability": 68, "green_impact": 78, "esg_global": 65}
    refs = [{"name": "ESG Mefali", "version": "1.2", "published_at": "2026-03-15"}]
    pdf_hash = "a" * 64

    c1 = build_canonical_payload(
        attestation_id=aid,
        scores=scores,
        referential_snapshot=refs,
        pdf_hash_sha256=pdf_hash,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    c2 = build_canonical_payload(
        attestation_id=aid,
        scores=scores,
        referential_snapshot=refs,
        pdf_hash_sha256=pdf_hash,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    assert c1 == c2


def test_build_canonical_payload_keys_sorted():
    """Les clés sont alphabétiquement triées au top-level."""
    aid = uuid4()
    valid_from = datetime(2026, 5, 7, 10, 30, tzinfo=timezone.utc)
    valid_until = datetime(2027, 5, 7, 10, 30, tzinfo=timezone.utc)
    canonical = build_canonical_payload(
        attestation_id=aid,
        scores={"combined": 73},
        referential_snapshot=[],
        pdf_hash_sha256="b" * 64,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    parsed = json.loads(canonical)
    keys = list(parsed.keys())
    assert keys == sorted(keys), f"Clés non triées : {keys}"


def test_build_canonical_payload_no_whitespace():
    """Pas d'espace dans les séparateurs (compaction stricte)."""
    canonical = build_canonical_payload(
        attestation_id=uuid4(),
        scores={"combined": 50},
        referential_snapshot=[],
        pdf_hash_sha256="c" * 64,
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    assert ", " not in canonical
    assert ": " not in canonical


def test_sign_payload_returns_base64():
    """``sign_payload`` retourne une signature base64 ASCII (pas None, pas bytes)."""
    canonical = build_canonical_payload(
        attestation_id=uuid4(),
        scores={"combined": 50},
        referential_snapshot=[],
        pdf_hash_sha256="d" * 64,
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    sig = sign_payload(canonical)
    assert isinstance(sig, str)
    raw = base64.b64decode(sig)
    assert len(raw) == 64  # Ed25519 = 64 bytes


def test_sign_then_verify_round_trip():
    """sign(canonical) puis verify(sig, canonical) → True."""
    canonical = build_canonical_payload(
        attestation_id=uuid4(),
        scores={"combined": 75},
        referential_snapshot=[{"name": "GCF", "version": "2.3"}],
        pdf_hash_sha256="e" * 64,
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    sig = sign_payload(canonical)
    assert verify_signature(sig, canonical) is True


def test_verify_signature_rejects_corrupted():
    """Modifier le payload après signature → verify retourne False."""
    canonical_orig = build_canonical_payload(
        attestation_id=uuid4(),
        scores={"combined": 75},
        referential_snapshot=[],
        pdf_hash_sha256="f" * 64,
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    sig = sign_payload(canonical_orig)
    canonical_tampered = canonical_orig.replace('"75"', '"99"').replace("75", "99")
    if canonical_tampered == canonical_orig:
        # Si la modification n'a rien changé, on force.
        canonical_tampered = canonical_orig + " "
    assert verify_signature(sig, canonical_tampered) is False


def test_verify_signature_rejects_invalid_base64():
    """Signature non base64 → False (pas d'exception)."""
    canonical = "abc"
    assert verify_signature("!!!not-base64!!!", canonical) is False


def test_verify_signature_rejects_wrong_length():
    """Signature de longueur != 64 bytes → False."""
    short_sig = base64.b64encode(b"\x00" * 32).decode()
    assert verify_signature(short_sig, "anything") is False


def test_signing_idempotent_for_same_payload():
    """Signer 2 fois le même payload donne 2 signatures (Ed25519 est déterministe)."""
    canonical = build_canonical_payload(
        attestation_id=uuid4(),
        scores={"combined": 50},
        referential_snapshot=[],
        pdf_hash_sha256="0" * 64,
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    sig1 = sign_payload(canonical)
    sig2 = sign_payload(canonical)
    # Ed25519 est déterministe par construction (RFC 8032).
    assert sig1 == sig2


def test_get_public_key_pem():
    """``get_public_key_pem`` expose la clé publique au format PEM."""
    pem = get_public_key_pem()
    assert "-----BEGIN PUBLIC KEY-----" in pem
    assert "-----END PUBLIC KEY-----" in pem


def test_get_public_key_id_returns_v1_default():
    """Par défaut, le public_key_id vaut 'v1'."""
    assert get_public_key_id() == "v1"


def test_signing_store_loads_pem_from_settings(monkeypatch):
    """Charge une clé PEM fournie via settings."""
    # Génère une paire à la volée
    pk = Ed25519PrivateKey.generate()
    from cryptography.hazmat.primitives import serialization

    pem_bytes = pk.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pem_str = pem_bytes.decode("ascii")

    from app.core.config import settings

    monkeypatch.setattr(settings, "attestation_private_key_pem", pem_str)
    SigningKeyStore._reset_for_testing()

    store = SigningKeyStore.get_instance()
    assert store.public_key_id == "v1"
    # La clé chargée matche la clé d'origine ?
    canonical = "test-payload"
    sig_bytes = pk.sign(canonical.encode("utf-8"))
    sig_b64 = base64.b64encode(sig_bytes).decode("ascii")
    assert verify_signature(sig_b64, canonical) is True


def test_signing_store_rejects_invalid_pem(monkeypatch):
    """Une clé PEM invalide lève SigningKeyError."""
    from app.core.config import settings
    from app.modules.attestations.signing import SigningKeyError

    monkeypatch.setattr(
        settings, "attestation_private_key_pem",
        "-----BEGIN PRIVATE KEY-----\nNOT-A-VALID-KEY\n-----END PRIVATE KEY-----\n",
    )
    SigningKeyStore._reset_for_testing()

    with pytest.raises(SigningKeyError):
        SigningKeyStore.get_instance()


def test_signing_store_handles_escaped_newlines(monkeypatch):
    """Une clé PEM avec ``\\n`` littéraux (mono-ligne .env) est correctement décodée."""
    pk = Ed25519PrivateKey.generate()
    from cryptography.hazmat.primitives import serialization

    pem_bytes = pk.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pem_str = pem_bytes.decode("ascii")
    # Convertit les \n en \\n littéraux (cas .env mono-ligne)
    one_liner = pem_str.replace("\n", "\\n")

    from app.core.config import settings

    monkeypatch.setattr(settings, "attestation_private_key_pem", one_liner)
    SigningKeyStore._reset_for_testing()

    store = SigningKeyStore.get_instance()
    assert isinstance(store.get_public_key_pem(), str)


def test_signing_store_production_requires_key(monkeypatch):
    """En production, l'absence de clé lève SigningKeyError au boot."""
    from app.core.config import settings
    from app.modules.attestations.signing import SigningKeyError

    monkeypatch.setattr(settings, "attestation_private_key_pem", "")
    monkeypatch.setattr(settings, "env", "production")
    SigningKeyStore._reset_for_testing()

    with pytest.raises(SigningKeyError):
        SigningKeyStore.initialize()
