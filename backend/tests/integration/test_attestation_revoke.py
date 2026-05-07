"""Tests intégration POST /api/attestations/{id}/revoke (F08 — T056)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.conftest import make_pme_user


async def _create_attestation_for(db_session, user):
    from app.models.credit import ConfidenceLabel, CreditScore
    from app.modules.attestations.service import generate_attestation

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

    a = await generate_attestation(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        attestation_type="credit_score",
    )
    return a


def _cleanup(a):
    Path(a.pdf_path).unlink(missing_ok=True)
    Path(a.qr_code_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_revoke_pme_own_attestation_via_service(db_session):
    """PME révoque sa propre attestation via le service."""
    user = await make_pme_user(db_session)
    a = await _create_attestation_for(db_session, user)

    from app.modules.attestations.service import revoke_attestation

    revoked = await revoke_attestation(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        attestation_id=a.id,
        reason="Mise à jour majeure",
        actor_role="pme",
    )
    assert revoked.revoked_at is not None
    assert revoked.revoked_reason == "Mise à jour majeure"
    assert revoked.revoked_by_user_id == user.id
    _cleanup(a)


@pytest.mark.asyncio
async def test_revoke_already_revoked_raises(db_session):
    """Révoquer une attestation déjà révoquée → AlreadyRevokedError."""
    user = await make_pme_user(db_session)
    a = await _create_attestation_for(db_session, user)

    from app.modules.attestations.service import (
        AttestationAlreadyRevokedError,
        revoke_attestation,
    )

    await revoke_attestation(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        attestation_id=a.id,
        reason="raison initiale",
    )
    with pytest.raises(AttestationAlreadyRevokedError):
        await revoke_attestation(
            db_session,
            account_id=user.account_id,
            user_id=user.id,
            attestation_id=a.id,
            reason="raison seconde",
        )
    _cleanup(a)


@pytest.mark.asyncio
async def test_revoke_unknown_attestation_raises(db_session):
    """Révoquer un UUID inexistant → NotFoundError."""
    user = await make_pme_user(db_session)
    from app.modules.attestations.service import (
        AttestationNotFoundError,
        revoke_attestation,
    )

    with pytest.raises(AttestationNotFoundError):
        await revoke_attestation(
            db_session,
            account_id=user.account_id,
            user_id=user.id,
            attestation_id=uuid.uuid4(),
            reason="ne devrait pas marcher",
        )


@pytest.mark.asyncio
async def test_revoke_cross_tenant_pme_raises(db_session):
    """PME-A tente de révoquer une attestation appartenant à PME-B → 404."""
    user_a = await make_pme_user(db_session, full_name="A")
    user_b = await make_pme_user(db_session, full_name="B")
    a_b = await _create_attestation_for(db_session, user_b)

    from app.modules.attestations.service import (
        AttestationNotFoundError,
        revoke_attestation,
    )

    with pytest.raises(AttestationNotFoundError):
        await revoke_attestation(
            db_session,
            account_id=user_a.account_id,
            user_id=user_a.id,
            attestation_id=a_b.id,
            reason="cross-tenant",
            actor_role="pme",
        )
    _cleanup(a_b)


@pytest.mark.asyncio
async def test_revoke_endpoint_returns_409_already_revoked(
    client, db_session, override_auth,
):
    """API: révoquer une attestation déjà révoquée → 409."""
    user = await make_pme_user(db_session)
    override_auth.id = user.id
    override_auth.account_id = user.account_id
    override_auth.role = user.role
    a = await _create_attestation_for(db_session, user)

    # 1ère révocation OK
    r1 = await client.post(
        f"/api/attestations/{a.id}/revoke",
        json={"reason": "Mise à jour profil"},
    )
    assert r1.status_code == 200, r1.text

    # 2e révocation → 409
    r2 = await client.post(
        f"/api/attestations/{a.id}/revoke",
        json={"reason": "Encore une fois"},
    )
    assert r2.status_code == 409
    _cleanup(a)


@pytest.mark.asyncio
async def test_revoke_endpoint_validates_reason_min_10_chars(
    client, db_session, override_auth,
):
    """API: raison trop courte → 422 (Pydantic validation)."""
    user = await make_pme_user(db_session)
    override_auth.id = user.id
    override_auth.account_id = user.account_id
    override_auth.role = user.role
    a = await _create_attestation_for(db_session, user)

    response = await client.post(
        f"/api/attestations/{a.id}/revoke",
        json={"reason": "court"},
    )
    assert response.status_code == 422
    _cleanup(a)
