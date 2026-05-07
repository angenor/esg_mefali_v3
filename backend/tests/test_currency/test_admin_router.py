"""F04 — Tests endpoint admin /api/admin/currency/fetch-status."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.api.deps import get_current_admin
from app.core.constants import UserRole
from app.main import app as fastapi_app
from app.models.exchange_rate import ExchangeRate


@pytest.mark.asyncio
async def test_fetch_status_admin_only(client) -> None:
    """Sans admin override → l'endpoint exige une auth (401/403/404)."""
    resp = await client.get("/api/admin/currency/fetch-status")
    assert resp.status_code in (401, 403, 404, 422)


@pytest.mark.asyncio
async def test_fetch_status_returns_summary(client, db_session) -> None:
    db_session.add(
        ExchangeRate(
            id=uuid.uuid4(),
            base_currency="USD",
            quote_currency="XOF",
            rate=Decimal("615.20"),
            as_of=date(2026, 4, 15),
            source="exchangerate-api.com",
            fetched_at=datetime.now(timezone.utc),
        ),
    )
    await db_session.commit()

    mock_admin = MagicMock()
    mock_admin.id = uuid.uuid4()
    mock_admin.role = UserRole.ADMIN

    fastapi_app.dependency_overrides[get_current_admin] = lambda: mock_admin
    try:
        resp = await client.get("/api/admin/currency/fetch-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "last_success_at" in data
        assert "daily_quota_used" in data
        assert "daily_quota_max" in data
        assert "pairs_known" in data
        assert data["daily_quota_max"] == 50
        assert data["pairs_known"] >= 1
    finally:
        fastapi_app.dependency_overrides.pop(get_current_admin, None)
