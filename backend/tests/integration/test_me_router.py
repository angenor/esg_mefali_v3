"""F05 — Tests d'intégration du router ``/api/me/*``.

Couvre les 7 endpoints + isolation multi-tenant + audit log + 7 consentements
+ suppression compte (verify-password, schedule-deletion, cancel-deletion).
"""

from __future__ import annotations

import io
import uuid
import zipfile
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.models.account import Account
from app.models.audit_log import AuditLog
from app.models.consent import Consent
from app.models.user import User
from tests.conftest import make_account, make_pme_user


async def _create_user_with_password(db_session, password: str = "TestPwd123!"):
    """Crée user + account avec un vrai bcrypt hash pour les tests password."""
    account = await make_account(db_session, name="TestCo")
    user = User(
        email=f"test-{uuid.uuid4().hex[:8]}@x.com",
        hashed_password=hash_password(password),
        full_name="Test",
        company_name="TestCo",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user, account


def _bearer(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


# ----------------------------------------------------------------------
# Inventory endpoint (T022)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inventory_returns_counts(client, db_session) -> None:
    user, account = await _create_user_with_password(db_session)
    res = await client.get("/api/me/data/inventory", headers=_bearer(user))
    assert res.status_code == 200
    body = res.json()
    assert "counts" in body
    assert "last_modified" in body
    for key in (
        "profile",
        "projects",
        "applications",
        "esg_assessments",
        "carbon_assessments",
        "credit_scores",
        "documents",
        "conversations",
        "messages",
        "attestations",
        "consents",
    ):
        assert key in body["counts"]


@pytest.mark.asyncio
async def test_inventory_requires_auth(client) -> None:
    res = await client.get("/api/me/data/inventory")
    assert res.status_code == 401


# ----------------------------------------------------------------------
# Export endpoint (T023, T024, T026)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_sync_returns_zip(client, db_session) -> None:
    user, account = await _create_user_with_password(db_session)
    res = await client.get(
        "/api/me/data/export?format=json",
        headers=_bearer(user),
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    # Vérifier la structure du ZIP
    z = zipfile.ZipFile(io.BytesIO(res.content))
    names = z.namelist()
    assert "data.json" in names
    assert "README.md" in names
    assert "documents/manifest.json" in names


@pytest.mark.asyncio
async def test_export_audit_log_logged(client, db_session) -> None:
    user, account = await _create_user_with_password(db_session)
    await client.get("/api/me/data/export?format=json", headers=_bearer(user))
    # Vérifier qu'un audit_log de type data_exported a été inséré.
    logs = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.account_id == account.id)
        )
    ).scalars().all()
    matched = [
        l
        for l in logs
        if isinstance(l.actor_metadata, dict)
        and l.actor_metadata.get("action_kind") == "data_exported"
    ]
    assert len(matched) >= 1


@pytest.mark.asyncio
async def test_export_isolation_by_account_id(client, db_session) -> None:
    """L'export ne contient QUE les données du compte connecté."""
    userA, accountA = await _create_user_with_password(db_session)
    userB, accountB = await _create_user_with_password(db_session)
    # Crée un consentement chez B
    db_session.add(
        Consent(
            account_id=accountB.id,
            user_id=userB.id,
            consent_type="public_data_analysis",
            granted=True,
            legal_basis="consent",
            version="v1.0",
        )
    )
    await db_session.commit()
    # Connecté en A : export ne doit pas contenir B
    res = await client.get(
        "/api/me/data/export?format=json", headers=_bearer(userA)
    )
    assert res.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(res.content))
    import json as _json

    data = _json.loads(z.read("data.json").decode("utf-8"))
    consents = data.get("consents", [])
    for c in consents:
        # Les consentements présents ne doivent pas être ceux de B
        assert c.get("account_id") != str(accountB.id)


# ----------------------------------------------------------------------
# Consents endpoint (T043-T049)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_consents_returns_7_default(client, db_session) -> None:
    user, account = await _create_user_with_password(db_session)
    res = await client.get("/api/me/consents", headers=_bearer(user))
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 7
    types = {item["type"] for item in items}
    expected = {
        "profile_analysis",
        "document_analysis_ai",
        "mobile_money_analysis",
        "photos_ia_analysis",
        "public_data_analysis",
        "credit_certificate_generation",
        "product_communications",
    }
    assert types == expected


@pytest.mark.asyncio
async def test_grant_consent_creates_active_row(client, db_session) -> None:
    user, account = await _create_user_with_password(db_session)
    res = await client.post(
        "/api/me/consents/mobile_money_analysis/grant",
        headers=_bearer(user),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "mobile_money_analysis"
    assert body["granted"] is True
    # Vérifier en BDD
    rows = (
        await db_session.execute(
            select(Consent).where(
                Consent.account_id == account.id,
                Consent.consent_type == "mobile_money_analysis",
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].revoked_at is None


@pytest.mark.asyncio
async def test_grant_idempotent_when_already_granted(
    client, db_session
) -> None:
    user, account = await _create_user_with_password(db_session)
    await client.post(
        "/api/me/consents/mobile_money_analysis/grant",
        headers=_bearer(user),
    )
    await client.post(
        "/api/me/consents/mobile_money_analysis/grant",
        headers=_bearer(user),
    )
    rows = (
        await db_session.execute(
            select(Consent).where(
                Consent.account_id == account.id,
                Consent.consent_type == "mobile_money_analysis",
            )
        )
    ).scalars().all()
    # Une seule row active après 2 grants successifs.
    active = [r for r in rows if r.revoked_at is None and r.granted]
    assert len(active) == 1


@pytest.mark.asyncio
async def test_revoke_marks_revoked_at(client, db_session) -> None:
    user, account = await _create_user_with_password(db_session)
    await client.post(
        "/api/me/consents/mobile_money_analysis/grant",
        headers=_bearer(user),
    )
    res = await client.post(
        "/api/me/consents/mobile_money_analysis/revoke",
        headers=_bearer(user),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["granted"] is False
    assert body["revoked_at"] is not None


@pytest.mark.asyncio
async def test_revoke_idempotent_when_no_active(client, db_session) -> None:
    user, account = await _create_user_with_password(db_session)
    res = await client.post(
        "/api/me/consents/mobile_money_analysis/revoke",
        headers=_bearer(user),
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_consent_audit_log_logged(client, db_session) -> None:
    user, account = await _create_user_with_password(db_session)
    await client.post(
        "/api/me/consents/photos_ia_analysis/grant",
        headers=_bearer(user),
    )
    logs = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.account_id == account.id)
        )
    ).scalars().all()
    matched = [
        l
        for l in logs
        if isinstance(l.actor_metadata, dict)
        and l.actor_metadata.get("action_kind") == "consent_granted"
    ]
    assert len(matched) >= 1


@pytest.mark.asyncio
async def test_consent_invalid_type_returns_422(client, db_session) -> None:
    user, account = await _create_user_with_password(db_session)
    res = await client.post(
        "/api/me/consents/totally_invalid_type/grant",
        headers=_bearer(user),
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_consents_isolated_by_account_id(client, db_session) -> None:
    userA, accountA = await _create_user_with_password(db_session)
    userB, accountB = await _create_user_with_password(db_session)
    # B grant consent
    await client.post(
        "/api/me/consents/public_data_analysis/grant",
        headers=_bearer(userB),
    )
    # A consults consents : public_data_analysis must remain default false
    res = await client.get("/api/me/consents", headers=_bearer(userA))
    items = res.json()
    pda = next(c for c in items if c["type"] == "public_data_analysis")
    assert pda["granted"] is False


# ----------------------------------------------------------------------
# Verify password (T057)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_password_success(client, db_session) -> None:
    user, account = await _create_user_with_password(db_session, "TestPwd123!")
    res = await client.post(
        "/api/me/account/verify-password",
        headers=_bearer(user),
        json={"password": "TestPwd123!"},
    )
    assert res.status_code == 200
    assert res.json() == {"verified": True}


@pytest.mark.asyncio
async def test_verify_password_failure(client, db_session) -> None:
    user, account = await _create_user_with_password(db_session, "TestPwd123!")
    res = await client.post(
        "/api/me/account/verify-password",
        headers=_bearer(user),
        json={"password": "WrongPwd"},
    )
    assert res.status_code == 401


# ----------------------------------------------------------------------
# Schedule deletion (T058-T061)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schedule_deletion_pme_role(client, db_session) -> None:
    user, account = await _create_user_with_password(db_session, "TestPwd123!")
    res = await client.post(
        "/api/me/account/schedule-deletion",
        headers=_bearer(user),
        json={"password": "TestPwd123!", "confirmation_text": "SUPPRIMER"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "deletion_scheduled_at" in body
    # Vérifier en BDD
    refreshed = (
        await db_session.execute(select(Account).where(Account.id == account.id))
    ).scalar_one()
    assert refreshed.deletion_scheduled_at is not None


@pytest.mark.asyncio
async def test_schedule_deletion_invalid_password_returns_401(
    client, db_session
) -> None:
    user, account = await _create_user_with_password(db_session, "TestPwd123!")
    res = await client.post(
        "/api/me/account/schedule-deletion",
        headers=_bearer(user),
        json={"password": "wrong", "confirmation_text": "SUPPRIMER"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_schedule_deletion_invalid_confirmation_returns_422(
    client, db_session
) -> None:
    user, account = await _create_user_with_password(db_session, "TestPwd123!")
    res = await client.post(
        "/api/me/account/schedule-deletion",
        headers=_bearer(user),
        json={"password": "TestPwd123!", "confirmation_text": "wrong"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_schedule_deletion_already_scheduled_returns_409(
    client, db_session
) -> None:
    user, account = await _create_user_with_password(db_session, "TestPwd123!")
    # Premier schedule
    res1 = await client.post(
        "/api/me/account/schedule-deletion",
        headers=_bearer(user),
        json={"password": "TestPwd123!", "confirmation_text": "SUPPRIMER"},
    )
    assert res1.status_code == 200
    # Deuxième schedule → 409
    res2 = await client.post(
        "/api/me/account/schedule-deletion",
        headers=_bearer(user),
        json={"password": "TestPwd123!", "confirmation_text": "SUPPRIMER"},
    )
    assert res2.status_code == 409


# ----------------------------------------------------------------------
# Cancel deletion (T062)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_deletion_via_jwt(client, db_session) -> None:
    user, account = await _create_user_with_password(db_session, "TestPwd123!")
    await client.post(
        "/api/me/account/schedule-deletion",
        headers=_bearer(user),
        json={"password": "TestPwd123!", "confirmation_text": "SUPPRIMER"},
    )
    res = await client.post(
        "/api/me/account/cancel-deletion",
        headers=_bearer(user),
    )
    assert res.status_code == 200
    refreshed = (
        await db_session.execute(select(Account).where(Account.id == account.id))
    ).scalar_one()
    assert refreshed.deletion_scheduled_at is None


@pytest.mark.asyncio
async def test_cancel_deletion_via_token_signed(client, db_session) -> None:
    user, account = await _create_user_with_password(db_session, "TestPwd123!")
    sched = await client.post(
        "/api/me/account/schedule-deletion",
        headers=_bearer(user),
        json={"password": "TestPwd123!", "confirmation_text": "SUPPRIMER"},
    )
    cancel_url = sched.json()["cancel_url"]
    # Extraire le token
    assert "token=" in cancel_url
    token = cancel_url.split("token=")[1]
    # Mode no-auth via token
    res = await client.post(f"/api/me/account/cancel-deletion?token={token}")
    assert res.status_code == 200


# ----------------------------------------------------------------------
# Test export download via signed token (T027-T028)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_download_token_signed(client, db_session) -> None:
    user, account = await _create_user_with_password(db_session)
    from app.core.url_signer import sign_export_url

    token = sign_export_url(
        {"account_id": str(account.id), "user_id": str(user.id)},
        salt="export-async",
    )
    res = await client.get(f"/api/me/data/export/download?token={token}")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"


@pytest.mark.asyncio
async def test_export_download_token_invalid_returns_401(client) -> None:
    res = await client.get("/api/me/data/export/download?token=invalid_token_xx")
    assert res.status_code == 401
