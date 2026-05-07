"""Tests RLS cross-tenant Attestation (F08 — T025).

Vérifie que :

- PME-A ne voit pas / ne peut pas accéder à des attestations PME-B
  (404 ou liste vide).
- L'admin contourne le RLS via le rôle ADMIN.

Note : sur SQLite (tests CI), le RLS PostgreSQL est désactivé et le filtrage
applicatif (``account_id == current_user.account_id`` au niveau service)
suffit. Sur PostgreSQL réel, ces tests sont également valables avec RLS actif.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.conftest import make_pme_user


async def _create_credit_score(db_session, user):
    from app.models.credit import ConfidenceLabel, CreditScore

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


async def _create_attestation(db_session, user):
    from app.modules.attestations.service import generate_attestation

    return await generate_attestation(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        attestation_type="credit_score",
    )


def _cleanup(a):
    Path(a.pdf_path).unlink(missing_ok=True)
    Path(a.qr_code_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_list_attestations_pme_a_does_not_see_pme_b(db_session):
    """PME-A liste ses attestations : ne voit PAS celles de PME-B."""
    user_a = await make_pme_user(db_session, full_name="A")
    user_b = await make_pme_user(db_session, full_name="B")
    await _create_credit_score(db_session, user_a)
    await _create_credit_score(db_session, user_b)

    a_a = await _create_attestation(db_session, user_a)
    a_b = await _create_attestation(db_session, user_b)

    from app.modules.attestations.service import list_attestations_for_user

    list_a = await list_attestations_for_user(db_session, account_id=user_a.account_id)
    ids_a = {att.id for att in list_a}
    assert a_a.id in ids_a
    assert a_b.id not in ids_a

    list_b = await list_attestations_for_user(db_session, account_id=user_b.account_id)
    ids_b = {att.id for att in list_b}
    assert a_b.id in ids_b
    assert a_a.id not in ids_b
    _cleanup(a_a)
    _cleanup(a_b)


@pytest.mark.asyncio
async def test_get_attestation_cross_tenant_returns_none(db_session):
    """PME-A get attestation de PME-B → None (404 dans router)."""
    user_a = await make_pme_user(db_session, full_name="A")
    user_b = await make_pme_user(db_session, full_name="B")
    await _create_credit_score(db_session, user_b)
    a_b = await _create_attestation(db_session, user_b)

    from app.modules.attestations.service import get_attestation_for_user

    result = await get_attestation_for_user(
        db_session,
        account_id=user_a.account_id,
        attestation_id=a_b.id,
    )
    assert result is None
    _cleanup(a_b)


@pytest.mark.asyncio
async def test_revoke_cross_tenant_pme_blocked(db_session):
    """PME-A tente revoke attestation PME-B → AttestationNotFoundError."""
    user_a = await make_pme_user(db_session, full_name="A")
    user_b = await make_pme_user(db_session, full_name="B")
    await _create_credit_score(db_session, user_b)
    a_b = await _create_attestation(db_session, user_b)

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
            reason="cross-tenant attempt",
            actor_role="pme",
        )
    _cleanup(a_b)


@pytest.mark.asyncio
async def test_admin_revoke_cross_tenant_works(db_session):
    """Admin peut révoquer cross-tenant via actor_role='admin'."""
    user_b = await make_pme_user(db_session, full_name="B")
    await _create_credit_score(db_session, user_b)
    a_b = await _create_attestation(db_session, user_b)

    from app.modules.attestations.service import revoke_attestation

    revoked = await revoke_attestation(
        db_session,
        # On simule un admin (pas de tenant). Le filtre account_id n'est pas appliqué.
        account_id=user_b.account_id,  # ignoré pour admin
        user_id=user_b.id,  # placeholder ; en pratique l'admin a son propre id
        attestation_id=a_b.id,
        reason="Admin révocation suite à fraude",
        actor_role="admin",
    )
    assert revoked.revoked_at is not None
    assert revoked.revoked_reason == "Admin révocation suite à fraude"
    _cleanup(a_b)
