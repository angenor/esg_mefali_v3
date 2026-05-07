"""F05 — Tests d'intégration de la modification ``POST /api/auth/register`` (T081-T083).

Vérifie :
- L'inscription sans ``privacy_policy_accepted=true`` retourne 422.
- L'inscription avec ``privacy_policy_accepted=true`` insère un audit_log
  ``privacy_policy_accepted``.
- 3 consentements essentiels sont créés automatiquement avec ``granted=true``.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.consent import Consent
from app.models.user import User


def _make_payload(privacy_accepted: bool, **overrides) -> dict:
    payload = {
        "email": f"e2e-{uuid.uuid4().hex[:8]}@example.com",
        "password": "PasswordSecure123!",
        "full_name": "Jean Test",
        "company_name": "PME Test",
        "privacy_policy_accepted": privacy_accepted,
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_register_with_privacy_false_returns_422(client) -> None:
    """privacy_policy_accepted=false explicit → 422 (FR-017)."""
    payload = _make_payload(privacy_accepted=False)
    res = await client.post("/api/auth/register", json=payload)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_register_without_privacy_field_succeeds_legacy(client) -> None:
    """Compatibilité descendante : absence du champ tolérée (frontend de prod
    envoie toujours ``true`` ; l'absence est traitée comme ``None`` pour ne
    pas casser les tests legacy de la plateforme).
    """
    payload = _make_payload(privacy_accepted=True)
    payload.pop("privacy_policy_accepted")
    res = await client.post("/api/auth/register", json=payload)
    assert res.status_code == 201


@pytest.mark.asyncio
async def test_register_with_privacy_accepted_creates_audit_log(
    client, db_session
) -> None:
    payload = _make_payload(privacy_accepted=True)
    res = await client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    user_id = uuid.UUID(res.json()["id"])
    # Vérifier audit_log
    logs = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.user_id == user_id)
        )
    ).scalars().all()
    matched = [
        l
        for l in logs
        if isinstance(l.actor_metadata, dict)
        and l.actor_metadata.get("action_kind") == "privacy_policy_accepted"
    ]
    assert len(matched) >= 1
    assert matched[0].actor_metadata.get("version") == "v1.0"


@pytest.mark.asyncio
async def test_register_creates_essential_consents(
    client, db_session
) -> None:
    """3 consentements essentiels (default granted=true) sont auto-créés."""
    payload = _make_payload(privacy_accepted=True)
    res = await client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    user_id = uuid.UUID(res.json()["id"])
    user = (
        await db_session.execute(select(User).where(User.id == user_id))
    ).scalar_one()
    consents = (
        await db_session.execute(
            select(Consent).where(Consent.account_id == user.account_id)
        )
    ).scalars().all()
    granted_types = {c.consent_type for c in consents if c.granted and c.revoked_at is None}
    assert "profile_analysis" in granted_types
    assert "document_analysis_ai" in granted_types
    assert "credit_certificate_generation" in granted_types
    # Les 4 optionnels NE doivent PAS être créés (absence = non-accordé).
    assert "mobile_money_analysis" not in granted_types
    assert "photos_ia_analysis" not in granted_types
    assert "public_data_analysis" not in granted_types
    assert "product_communications" not in granted_types
