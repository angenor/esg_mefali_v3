"""Tests F18 — Consent gating (SC-001)."""

from __future__ import annotations

import io

import pytest

from app.main import app


@pytest.mark.asyncio
async def test_mm_upload_without_consent_returns_403(client, db_session):
    """SC-001 — appel sans consentement actif → 403 consent_required."""
    from tests.conftest import make_pme_user
    from app.api.deps import get_current_user

    user = await make_pme_user(db_session)
    await db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        files = {"file": ("test.csv", io.BytesIO(b"date,type,amount,counterparty\n"), "text/csv")}
        data = {"provider": "wave"}
        resp = await client.post(
            "/api/credit/mobile-money/upload", data=data, files=files
        )
        assert resp.status_code == 403
        body = resp.json()
        # Le helper consent_dependency renvoie un detail dict structuré
        detail = body.get("detail", {})
        if isinstance(detail, dict):
            assert detail.get("consent_type") == "mobile_money_analysis"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_public_data_declare_without_consent_returns_403(client, db_session):
    from tests.conftest import make_pme_user
    from app.api.deps import get_current_user

    user = await make_pme_user(db_session)
    await db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        resp = await client.post(
            "/api/credit/public-data/declare",
            json={
                "source_type": "google_my_business",
                "url": "https://maps.google.com/?cid=1",
                "declared_rating": 4.3,
                "declared_reviews_count": 27,
            },
        )
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_methodology_endpoint_no_auth_required(client):
    """L'endpoint méthodologie est public (pas de 401/403 sans token)."""
    resp = await client.get("/api/credit/methodology")
    # 200 même vide (factors=[])
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_mm_upload_with_consent_succeeds(client, db_session):
    """Avec consentement actif → upload accepté."""
    from datetime import datetime, timezone

    from app.api.deps import get_current_user
    from app.models.consent import Consent
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)
    db_session.add(
        Consent(
            account_id=user.account_id,
            consent_type="mobile_money_analysis",
            granted=True,
            legal_basis="consent",
            version="1.0",
            granted_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        csv_content = (
            b"Date,Type,Amount,Counterparty,Balance\n"
            b"2026-04-01 10:00:00,Incoming,15000,+221770000001,52000\n"
            b"2026-04-02 14:00:00,Outgoing,5000,+221770000002,47000\n"
        )
        files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
        data = {"provider": "wave"}
        resp = await client.post(
            "/api/credit/mobile-money/upload", data=data, files=files
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["imported_rows"] == 2
        assert body["rejected_rows"] == 0
        assert body["analysis"] is not None
    finally:
        app.dependency_overrides.pop(get_current_user, None)
