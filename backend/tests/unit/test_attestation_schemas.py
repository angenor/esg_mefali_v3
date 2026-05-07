"""Tests unitaires schémas Pydantic Attestation (F08 — T008)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.modules.attestations.schemas import (
    AttestationCreate,
    AttestationRevoke,
    AttestationSummary,
    AuthenticVerification,
    ExpiredVerification,
    InvalidVerification,
    PublicKeyResponse,
    RevokedVerification,
    VerificationResult,
)


# ----------------------------------------------------------------------
# AttestationCreate
# ----------------------------------------------------------------------


def test_attestation_create_accepts_valid_types():
    for t in ("credit_score", "esg_assessment", "combined"):
        c = AttestationCreate(attestation_type=t)
        assert c.attestation_type == t


def test_attestation_create_rejects_invalid_type():
    with pytest.raises(ValidationError):
        AttestationCreate(attestation_type="random")


def test_attestation_create_rejects_extra_fields():
    with pytest.raises(ValidationError):
        AttestationCreate(attestation_type="combined", extra="leak")


# ----------------------------------------------------------------------
# AttestationRevoke
# ----------------------------------------------------------------------


def test_attestation_revoke_requires_min_10_chars():
    with pytest.raises(ValidationError):
        AttestationRevoke(reason="court")  # 5 chars
    with pytest.raises(ValidationError):
        AttestationRevoke(reason="9chars--")  # 8


def test_attestation_revoke_accepts_valid():
    r = AttestationRevoke(reason="Mise à jour du profil financier")
    assert r.reason.startswith("Mise")


def test_attestation_revoke_caps_at_500_chars():
    with pytest.raises(ValidationError):
        AttestationRevoke(reason="x" * 501)


# ----------------------------------------------------------------------
# AuthenticVerification
# ----------------------------------------------------------------------


def _build_authentic(**overrides) -> dict:
    base = {
        "status": "authentic",
        "verified_at": datetime(2026, 5, 7, tzinfo=timezone.utc),
        "message": "Attestation authentique",
        "attestation_id": uuid4(),
        "display_id": "ATT-2026-00001",
        "attestation_type": "combined",
        "valid_from": datetime(2026, 5, 7, tzinfo=timezone.utc),
        "valid_until": datetime(2027, 5, 7, tzinfo=timezone.utc),
        "issued_at": datetime(2026, 5, 7, tzinfo=timezone.utc),
        "scores": {"combined": 73, "solvability": 68},
        "referentials": [{"name": "ESG Mefali", "version": "1.2"}],
        "pdf_hash_sha256": "a" * 64,
        "public_key_id": "v1",
    }
    base.update(overrides)
    return base


def test_authentic_verification_validates():
    a = AuthenticVerification(**_build_authentic())
    assert a.status == "authentic"


def test_authentic_verification_rejects_extra_field():
    data = _build_authentic()
    data["company_name"] = "PME XYZ"  # PII non autorisé
    with pytest.raises(ValidationError):
        AuthenticVerification(**data)


# ----------------------------------------------------------------------
# RevokedVerification
# ----------------------------------------------------------------------


def test_revoked_verification_validates():
    r = RevokedVerification(
        verified_at=datetime.now(tz=timezone.utc),
        message="Attestation révoquée",
        attestation_id=uuid4(),
        display_id="ATT-2026-00002",
        attestation_type="credit_score",
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
        issued_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        scores={"combined": 60},
        referentials=[],
        pdf_hash_sha256="b" * 64,
        public_key_id="v1",
        revoked_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        revoked_reason="Mise à jour majeure",
        revoked_by_role="pme",
    )
    assert r.status == "revoked"
    assert r.revoked_by_role == "pme"


def test_revoked_verification_rejects_invalid_role():
    with pytest.raises(ValidationError):
        RevokedVerification(
            verified_at=datetime.now(tz=timezone.utc),
            message="x",
            attestation_id=uuid4(),
            display_id="ATT-2026-00003",
            attestation_type="credit_score",
            valid_from=datetime.now(tz=timezone.utc),
            valid_until=datetime.now(tz=timezone.utc),
            issued_at=datetime.now(tz=timezone.utc),
            scores={},
            referentials=[],
            pdf_hash_sha256="c" * 64,
            public_key_id="v1",
            revoked_at=datetime.now(tz=timezone.utc),
            revoked_reason="ok",
            revoked_by_role="other",  # invalide
        )


# ----------------------------------------------------------------------
# ExpiredVerification
# ----------------------------------------------------------------------


def test_expired_verification_validates():
    e = ExpiredVerification(
        verified_at=datetime.now(tz=timezone.utc),
        message="Attestation expirée",
        attestation_id=uuid4(),
        display_id="ATT-2025-00099",
        attestation_type="esg_assessment",
        valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2025, 1, 1, tzinfo=timezone.utc),
        issued_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        scores={"esg_global": 70},
        referentials=[],
        pdf_hash_sha256="d" * 64,
        public_key_id="v1",
        expired_since=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    assert e.status == "expired"


# ----------------------------------------------------------------------
# InvalidVerification
# ----------------------------------------------------------------------


def test_invalid_verification_minimal():
    i = InvalidVerification(
        verified_at=datetime.now(tz=timezone.utc),
        message="Cet identifiant n'existe pas ou la signature est invalide",
    )
    assert i.status == "invalid"


def test_invalid_verification_rejects_extra_field():
    """Pas d'attestation_id ni autre champ technique pour empêcher l'énumération."""
    with pytest.raises(ValidationError):
        InvalidVerification(
            verified_at=datetime.now(tz=timezone.utc),
            message="x",
            attestation_id=uuid4(),  # interdit
        )


# ----------------------------------------------------------------------
# Discriminated union
# ----------------------------------------------------------------------


def test_verification_result_dispatches_authentic():
    adapter = TypeAdapter(VerificationResult)
    a = adapter.validate_python(_build_authentic())
    assert isinstance(a, AuthenticVerification)


def test_verification_result_dispatches_invalid():
    adapter = TypeAdapter(VerificationResult)
    i = adapter.validate_python({
        "status": "invalid",
        "verified_at": datetime.now(tz=timezone.utc),
        "message": "Cet identifiant n'existe pas ou la signature est invalide",
    })
    assert isinstance(i, InvalidVerification)


# ----------------------------------------------------------------------
# AttestationSummary
# ----------------------------------------------------------------------


def test_attestation_summary_validates():
    s = AttestationSummary(
        id=uuid4(),
        display_id="ATT-2026-00010",
        attestation_type="combined",
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
        verification_url="https://esg-mefali.com/verify/abc",
        pdf_hash_sha256="e" * 64,
        public_key_id="v1",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert s.display_id == "ATT-2026-00010"


# ----------------------------------------------------------------------
# PublicKeyResponse
# ----------------------------------------------------------------------


def test_public_key_response_default_algorithm():
    r = PublicKeyResponse(
        public_key_id="v1",
        public_key_pem="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----\n",
        issued_at=datetime.now(tz=timezone.utc),
    )
    assert r.algorithm == "ed25519"
