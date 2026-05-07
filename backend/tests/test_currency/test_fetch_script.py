"""F04 — Tests script CLI fetch_exchange_rates (cap 1/jour, mock httpx)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.exchange_rate import ExchangeRate
from app.modules.currency.exceptions import FetchFailedError
from app.scripts.fetch_exchange_rates import fetch_one_shot


# --- Mock httpx response helper ---


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError(
                "boom", request=None, response=None,  # type: ignore[arg-type]
            )

    def json(self) -> dict:
        return self._payload


@pytest.mark.asyncio
async def test_fetch_skipped_when_no_api_key(db_session) -> None:
    """Si la clé API est vide → mode dégradé, skip silencieux."""
    original = settings.exchangerate_api_key
    settings.exchangerate_api_key = ""
    try:
        result = await fetch_one_shot(db_session)
        assert result["inserted"] == 0
        assert result["source"] == "skipped_no_key"
    finally:
        settings.exchangerate_api_key = original


@pytest.mark.asyncio
async def test_fetch_skipped_when_recent_fetch(db_session) -> None:
    """Si la dernière fetched_at < 24h → skip cap quotidien."""
    db_session.add(
        ExchangeRate(
            id=uuid.uuid4(),
            base_currency="USD",
            quote_currency="XOF",
            rate=Decimal("615"),
            as_of=date.today(),
            source="exchangerate-api.com",
            fetched_at=datetime.now(timezone.utc),
        ),
    )
    await db_session.commit()
    original = settings.exchangerate_api_key
    settings.exchangerate_api_key = "fake-key"
    try:
        result = await fetch_one_shot(db_session)
        assert result["inserted"] == 0
        assert result["source"] == "skipped_cap"
    finally:
        settings.exchangerate_api_key = original


@pytest.mark.asyncio
async def test_fetch_inserts_pairs_and_inverses(db_session) -> None:
    """Un fetch réussi insère USD→{XOF,EUR,GBP,JPY} + 4 paires inverses."""
    payload = {
        "result": "success",
        "conversion_rates": {
            "USD": 1.0,
            "XOF": 615.20,
            "EUR": 0.92,
            "GBP": 0.79,
            "JPY": 152.50,
        },
    }
    original = settings.exchangerate_api_key
    settings.exchangerate_api_key = "fake-key"

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            return _FakeResponse(payload)

    try:
        with patch(
            "app.scripts.fetch_exchange_rates.httpx.AsyncClient",
            _FakeClient,
        ):
            result = await fetch_one_shot(db_session, force=True)
        assert result["inserted"] == 8  # 4 directs + 4 inverses
        rows = await db_session.execute(select(ExchangeRate))
        all_rates = list(rows.scalars().all())
        # Au moins les 8 nouvelles paires
        assert len(all_rates) >= 8
    finally:
        settings.exchangerate_api_key = original


@pytest.mark.asyncio
async def test_fetch_raises_on_http_error(db_session) -> None:
    """Si le HTTP échoue → FetchFailedError, log structuré."""
    import httpx

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            raise httpx.ConnectTimeout("timeout")

    original = settings.exchangerate_api_key
    settings.exchangerate_api_key = "fake-key"
    try:
        with patch(
            "app.scripts.fetch_exchange_rates.httpx.AsyncClient",
            _FakeClient,
        ):
            with pytest.raises(FetchFailedError):
                await fetch_one_shot(db_session, force=True)
    finally:
        settings.exchangerate_api_key = original
