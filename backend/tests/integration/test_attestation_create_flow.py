"""Tests intégration POST /api/attestations (F08 — T023)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.attestation import Attestation
from tests.conftest import make_pme_user


async def _create_credit_score(db_session, user):
    """Insère un CreditScore minimal pour tester la génération."""
    from app.models.credit import ConfidenceLabel, CreditScore

    score = CreditScore(
        user_id=user.id,
        account_id=user.account_id,
        version=1,
        solvability_score=68.0,
        green_impact_score=78.0,
        combined_score=73.0,
        score_breakdown={"solvability": {}, "green_impact": {}},
        data_sources={},
        confidence_level=0.85,
        confidence_label=ConfidenceLabel.good,
        generated_at=datetime.now(tz=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(score)
    await db_session.commit()
    return score


@pytest.mark.asyncio
async def test_generate_attestation_creates_db_row(db_session):
    """Service.generate_attestation crée une ligne avec tous les champs requis."""
    user = await make_pme_user(db_session, full_name="Fatou", company_name="Eco PME")
    await _create_credit_score(db_session, user)

    from app.modules.attestations.service import generate_attestation

    a = await generate_attestation(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        attestation_type="combined",
    )
    assert a.id is not None
    assert a.account_id == user.account_id
    assert a.user_id == user.id
    assert a.attestation_type == "combined"
    assert a.public_key_id == "v1"
    assert a.signature_ed25519 != ""
    assert re.match(r"^[0-9a-f]{64}$", a.pdf_hash_sha256)
    assert re.match(r"^ATT-\d{4}-\d{5}$", a.display_id)
    assert a.valid_from is not None
    assert a.valid_until > a.valid_from
    assert a.revoked_at is None
    assert a.verification_url.startswith("http")
    # Compteur scopé : doit être ATT-YYYY-00001 pour la première.
    assert a.display_id.endswith("00001")


@pytest.mark.asyncio
async def test_generate_attestation_writes_pdf_and_qr(db_session):
    """Service.generate_attestation écrit le PDF et le QR sur disque."""
    user = await make_pme_user(db_session)
    await _create_credit_score(db_session, user)

    from app.modules.attestations.service import generate_attestation

    a = await generate_attestation(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        attestation_type="credit_score",
    )
    assert Path(a.pdf_path).exists()
    assert Path(a.qr_code_path).exists()
    # Cleanup pour ne pas polluer le filesystem en tests.
    Path(a.pdf_path).unlink(missing_ok=True)
    Path(a.qr_code_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_generate_attestation_combined_requires_credit_score(db_session):
    """Sans CreditScore, génération combined → CreditScoreMissingError."""
    user = await make_pme_user(db_session)

    from app.modules.attestations.service import (
        CreditScoreMissingError,
        generate_attestation,
    )

    with pytest.raises(CreditScoreMissingError):
        await generate_attestation(
            db_session,
            account_id=user.account_id,
            user_id=user.id,
            attestation_type="combined",
        )


@pytest.mark.asyncio
async def test_generate_attestation_increments_display_id_counter(db_session):
    """Plusieurs attestations sur le même account incrémentent NNNNN."""
    user = await make_pme_user(db_session)
    await _create_credit_score(db_session, user)

    from app.modules.attestations.service import generate_attestation

    a1 = await generate_attestation(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        attestation_type="credit_score",
    )
    a2 = await generate_attestation(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        attestation_type="credit_score",
    )
    # Cleanup PDFs
    for a in (a1, a2):
        Path(a.pdf_path).unlink(missing_ok=True)
        Path(a.qr_code_path).unlink(missing_ok=True)

    assert a1.display_id != a2.display_id
    n1 = int(a1.display_id.split("-")[-1])
    n2 = int(a2.display_id.split("-")[-1])
    assert n2 == n1 + 1


@pytest.mark.asyncio
async def test_signature_is_verifiable(db_session):
    """La signature stockée doit être valide pour le payload canonique."""
    user = await make_pme_user(db_session)
    await _create_credit_score(db_session, user)

    from app.modules.attestations.service import generate_attestation
    from app.modules.attestations.signing import (
        build_canonical_payload,
        verify_signature,
    )

    a = await generate_attestation(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        attestation_type="credit_score",
    )

    canonical = build_canonical_payload(
        attestation_id=a.id,
        scores=a.payload["scores"],
        referential_snapshot=a.referential_snapshot,
        pdf_hash_sha256=a.pdf_hash_sha256,
        valid_from=a.valid_from,
        valid_until=a.valid_until,
    )
    assert verify_signature(a.signature_ed25519, canonical) is True
    Path(a.pdf_path).unlink(missing_ok=True)
    Path(a.qr_code_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_post_endpoint_creates_attestation(client, db_session, override_auth):
    """POST /api/attestations/ via API → 201 avec champs attendus."""
    # `override_auth` injecte un user fixed UUID. Il faut créer ce user en DB.
    user = await make_pme_user(db_session)
    override_auth.id = user.id
    override_auth.account_id = user.account_id
    override_auth.role = user.role

    await _create_credit_score(db_session, user)

    response = await client.post(
        "/api/attestations",
        json={"attestation_type": "credit_score"},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert "id" in data
    assert "display_id" in data
    assert data["attestation_type"] == "credit_score"
    assert "pdf_hash_sha256" in data
    assert "verification_url" in data
    # Cleanup
    a_uuid = uuid.UUID(data["id"])
    res = await db_session.execute(
        select(Attestation).where(Attestation.id == a_uuid)
    )
    a = res.scalar_one()
    Path(a.pdf_path).unlink(missing_ok=True)
    Path(a.qr_code_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_post_endpoint_returns_422_when_no_credit_score(
    client, db_session, override_auth,
):
    """Sans CreditScore, POST avec type='combined' → 422."""
    user = await make_pme_user(db_session)
    override_auth.id = user.id
    override_auth.account_id = user.account_id
    override_auth.role = user.role

    response = await client.post(
        "/api/attestations",
        json={"attestation_type": "combined"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_list_returns_user_attestations(client, db_session, override_auth):
    """GET /api/attestations → liste les attestations du tenant."""
    user = await make_pme_user(db_session)
    override_auth.id = user.id
    override_auth.account_id = user.account_id
    override_auth.role = user.role

    await _create_credit_score(db_session, user)

    from app.modules.attestations.service import generate_attestation

    a = await generate_attestation(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        attestation_type="credit_score",
    )

    response = await client.get("/api/attestations")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(item["id"] == str(a.id) for item in data)
    Path(a.pdf_path).unlink(missing_ok=True)
    Path(a.qr_code_path).unlink(missing_ok=True)
