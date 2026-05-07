"""F04 — Tests des endpoints HTTP /api/currency."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models.exchange_rate import ExchangeRate


@pytest.mark.asyncio
async def test_get_rates_latest_returns_pegs(client) -> None:
    resp = await client.get("/api/currency/rates/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert "rates" in body
    assert "peg_pairs" in body
    pegs = body["peg_pairs"]
    assert len(pegs) == 2
    base_quote = {(p["base_currency"], p["quote_currency"]) for p in pegs}
    assert ("EUR", "XOF") in base_quote
    assert ("XOF", "EUR") in base_quote


@pytest.mark.asyncio
async def test_post_convert_peg_xof_to_eur(client) -> None:
    body = {
        "amount": "655957",
        "source_currency": "XOF",
        "target_currency": "EUR",
    }
    resp = await client.post("/api/currency/convert", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["target"]["amount"] == "1000.00"
    assert data["target"]["currency"] == "EUR"
    assert data["method"] == "peg_fixed"


@pytest.mark.asyncio
async def test_post_convert_table_usd_to_xof(client, db_session) -> None:
    db_session.add(
        ExchangeRate(
            id=uuid.uuid4(),
            base_currency="USD",
            quote_currency="XOF",
            rate=Decimal("615.20"),
            as_of=date(2026, 4, 15),
            source="test-fixture",
        ),
    )
    await db_session.commit()
    body = {
        "amount": "1000",
        "source_currency": "USD",
        "target_currency": "XOF",
        "date": "2026-04-15",
    }
    resp = await client.post("/api/currency/convert", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["target"]["amount"] == "615200.00"
    assert data["target"]["currency"] == "XOF"
    assert data["method"] == "table"


@pytest.mark.asyncio
async def test_post_convert_404_when_no_rate(client) -> None:
    body = {
        "amount": "100",
        "source_currency": "USD",
        "target_currency": "JPY",
    }
    resp = await client.post("/api/currency/convert", json=body)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_post_convert_422_invalid_currency(client) -> None:
    body = {
        "amount": "100",
        "source_currency": "ABC",
        "target_currency": "XOF",
    }
    resp = await client.post("/api/currency/convert", json=body)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_convert_422_negative_amount(client) -> None:
    body = {
        "amount": "-100",
        "source_currency": "XOF",
        "target_currency": "EUR",
    }
    resp = await client.post("/api/currency/convert", json=body)
    assert resp.status_code == 422
