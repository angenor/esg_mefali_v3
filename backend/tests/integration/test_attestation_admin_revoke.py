"""Tests endpoint admin GET/POST /api/admin/attestations (F08 — T062)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.core.constants import UserRole
from app.models.user import User
from tests.conftest import make_pme_user


async def _create_admin_user(db_session) -> User:
    """Crée un user admin (sans account_id selon convention F02)."""
    admin = User(
        email=f"admin-{uuid.uuid4().hex[:6]}@mefali.com",
        hashed_password="x",
        full_name="Admin",
        company_name="Mefali",
        account_id=None,
        role=UserRole.ADMIN.value,
    )
    db_session.add(admin)
    await db_session.flush()
    return admin


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


async def _create_attestation_for_pme(db_session, user):
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
async def test_admin_list_cross_tenant_via_service(db_session):
    """Admin liste TOUTES les attestations cross-tenant via le service."""
    user_a = await make_pme_user(db_session, full_name="A")
    user_b = await make_pme_user(db_session, full_name="B")
    await _create_credit_score(db_session, user_a)
    await _create_credit_score(db_session, user_b)

    a_a = await _create_attestation_for_pme(db_session, user_a)
    a_b = await _create_attestation_for_pme(db_session, user_b)

    from app.modules.attestations.service import list_all_attestations_admin

    all_atts = await list_all_attestations_admin(db_session)
    ids = {a.id for a in all_atts}
    assert a_a.id in ids
    assert a_b.id in ids
    _cleanup(a_a)
    _cleanup(a_b)


@pytest.mark.asyncio
async def test_admin_filter_by_status(db_session):
    """Admin peut filtrer par status authentic/revoked/expired."""
    user = await make_pme_user(db_session)
    await _create_credit_score(db_session, user)
    a = await _create_attestation_for_pme(db_session, user)

    from app.modules.attestations.service import (
        list_all_attestations_admin,
        revoke_attestation,
    )

    # 1. Filtrer authentic — doit contenir notre attestation
    auth = await list_all_attestations_admin(db_session, status="authentic")
    assert any(att.id == a.id for att in auth)

    # 2. Révoquer + filtrer revoked
    await revoke_attestation(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        attestation_id=a.id,
        reason="Test révocation",
    )
    revoked = await list_all_attestations_admin(db_session, status="revoked")
    assert any(att.id == a.id for att in revoked)
    # Ne doit plus apparaître dans authentic
    auth_after = await list_all_attestations_admin(db_session, status="authentic")
    assert not any(att.id == a.id for att in auth_after)
    _cleanup(a)


@pytest.mark.asyncio
async def test_admin_endpoint_requires_admin_role(client, db_session, override_auth):
    """PME (non admin) accède /api/admin/attestations → 403."""
    user = await make_pme_user(db_session)
    override_auth.id = user.id
    override_auth.account_id = user.account_id
    override_auth.role = UserRole.PME.value

    response = await client.get("/api/admin/attestations")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_endpoint_lists_cross_tenant(client, db_session, override_auth):
    """Admin via API → retourne toutes les attestations."""
    admin = await _create_admin_user(db_session)
    user_a = await make_pme_user(db_session, full_name="PME-A")
    await _create_credit_score(db_session, user_a)
    a_a = await _create_attestation_for_pme(db_session, user_a)

    override_auth.id = admin.id
    override_auth.account_id = admin.account_id
    override_auth.role = UserRole.ADMIN.value

    response = await client.get("/api/admin/attestations")
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
    assert any(item["id"] == str(a_a.id) for item in data)
    _cleanup(a_a)
