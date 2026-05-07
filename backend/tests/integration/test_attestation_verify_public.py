"""Tests intégration GET /api/public/verify/{id} (F08 — T041)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import update

from app.models.attestation import Attestation
from tests.conftest import make_pme_user


async def _create_credit_score_and_attestation(db_session):
    """Helper : crée user + score + attestation."""
    from app.models.credit import ConfidenceLabel, CreditScore
    from app.modules.attestations.service import generate_attestation

    user = await make_pme_user(db_session)
    score = CreditScore(
        user_id=user.id,
        account_id=user.account_id,
        version=1,
        solvability_score=68.0,
        green_impact_score=78.0,
        combined_score=73.0,
        score_breakdown={},
        data_sources={},
        confidence_level=0.85,
        confidence_label=ConfidenceLabel.good,
        generated_at=datetime.now(tz=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(score)
    await db_session.commit()

    attestation = await generate_attestation(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        attestation_type="credit_score",
    )
    return user, attestation


def _cleanup(attestation):
    Path(attestation.pdf_path).unlink(missing_ok=True)
    Path(attestation.qr_code_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_verify_public_authentic(client, db_session):
    """GET /api/public/verify/{id} sur attestation valide → status='authentic'."""
    user, a = await _create_credit_score_and_attestation(db_session)
    response = await client.get(f"/api/public/verify/{a.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "authentic"
    assert body["attestation_id"] == str(a.id)
    assert body["display_id"] == a.display_id
    assert body["pdf_hash_sha256"] == a.pdf_hash_sha256
    assert body["public_key_id"] == "v1"
    assert "scores" in body
    _cleanup(a)


@pytest.mark.asyncio
async def test_verify_public_invalid_uuid_inexistant(client, db_session):
    """UUID inexistant → status='invalid' (pas 404)."""
    bogus = uuid.uuid4()
    response = await client.get(f"/api/public/verify/{bogus}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "invalid"
    # Aucune fuite de l'existence — pas de attestation_id retourné.
    assert "attestation_id" not in body


@pytest.mark.asyncio
async def test_verify_public_malformed_uuid(client, db_session):
    """UUID malformé → status='invalid'."""
    response = await client.get("/api/public/verify/not-a-uuid")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "invalid"


@pytest.mark.asyncio
async def test_verify_public_corrupted_signature(client, db_session):
    """Signature corrompue en base → status='invalid'."""
    user, a = await _create_credit_score_and_attestation(db_session)
    # Corrompre la signature en base directement
    await db_session.execute(
        update(Attestation)
        .where(Attestation.id == a.id)
        .values(signature_ed25519="aGVsbG8=")  # base64 valide mais signature fausse
    )
    await db_session.commit()
    response = await client.get(f"/api/public/verify/{a.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "invalid"
    _cleanup(a)


@pytest.mark.asyncio
async def test_verify_public_revoked(client, db_session):
    """Attestation révoquée → status='revoked' avec revoked_at, revoked_reason, revoked_by_role."""
    user, a = await _create_credit_score_and_attestation(db_session)
    from app.modules.attestations.service import revoke_attestation

    await revoke_attestation(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        attestation_id=a.id,
        reason="Mise à jour majeure du profil",
        actor_role="pme",
    )
    response = await client.get(f"/api/public/verify/{a.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "revoked"
    assert body["revoked_reason"] == "Mise à jour majeure du profil"
    assert body["revoked_by_role"] == "pme"
    # Pas de nom du révocateur exposé
    assert "revoked_by_user_id" not in body
    _cleanup(a)


@pytest.mark.asyncio
async def test_verify_public_expired(client, db_session):
    """Attestation expirée → status='expired'."""
    user, a = await _create_credit_score_and_attestation(db_session)

    # Reculer valid_from + valid_until dans le passé (avec valid_until > valid_from).
    past_from = datetime.now(tz=timezone.utc) - timedelta(days=400)
    past_until = datetime.now(tz=timezone.utc) - timedelta(days=10)

    # On doit re-signer car la signature couvre valid_from/valid_until.
    from app.modules.attestations.signing import (
        build_canonical_payload,
        sign_payload,
    )

    canonical = build_canonical_payload(
        attestation_id=a.id,
        scores=a.payload["scores"],
        referential_snapshot=a.referential_snapshot,
        pdf_hash_sha256=a.pdf_hash_sha256,
        valid_from=past_from,
        valid_until=past_until,
    )
    sig = sign_payload(canonical)

    await db_session.execute(
        update(Attestation)
        .where(Attestation.id == a.id)
        .values(
            valid_from=past_from,
            valid_until=past_until,
            signature_ed25519=sig,
        )
    )
    await db_session.commit()

    response = await client.get(f"/api/public/verify/{a.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "expired", f"Body={body}"
    assert "expired_since" in body
    _cleanup(a)


@pytest.mark.asyncio
async def test_verify_public_endpoint_no_auth_required(client, db_session):
    """L'endpoint public ne demande pas d'authentification."""
    response = await client.get("/api/public/verify/00000000-0000-0000-0000-000000000000")
    # Pas de 401 même sans token
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_verify_public_invalid_does_not_leak_field(client, db_session):
    """Pour status='invalid', aucun champ technique n'est exposé."""
    response = await client.get("/api/public/verify/00000000-0000-0000-0000-000000000000")
    body = response.json()
    forbidden_fields = {
        "attestation_id",
        "display_id",
        "scores",
        "pdf_hash_sha256",
        "public_key_id",
        "signature_ed25519",
        "valid_from",
        "valid_until",
    }
    leaks = forbidden_fields.intersection(set(body.keys()))
    assert not leaks, f"Fuite de champs : {leaks}"


@pytest.mark.asyncio
async def test_public_key_endpoint(client):
    """GET /api/public/attestation-public-key → expose la clé publique."""
    response = await client.get("/api/public/attestation-public-key")
    assert response.status_code == 200
    body = response.json()
    assert body["public_key_id"] == "v1"
    assert body["algorithm"] == "ed25519"
    assert "BEGIN PUBLIC KEY" in body["public_key_pem"]
