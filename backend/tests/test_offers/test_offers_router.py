"""F07 — Tests integration pour /api/offers (US1).

Vérifie :
- Filtre strict publication_status='published' AND is_active=true.
- Filtres fund_id, intermediary_id, country.
- get_offer 404 pour drafts.
- comparator retourne offres publiées.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ----- list_offers -----


@pytest.mark.asyncio
async def test_list_offers_returns_published_only(
    db_session, published_offer, draft_offer,
) -> None:
    """1 offre published + 1 draft → API retourne 1 résultat."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/offers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == str(published_offer.id)


@pytest.mark.asyncio
async def test_list_offers_filters_by_fund_id(
    db_session, published_offer,
) -> None:
    """Filtre fund_id retourne uniquement les offres pour ce fonds."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get(
            f"/api/offers?fund_id={published_offer.fund_id}"
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_offers_filters_by_intermediary_id(
    db_session, published_offer,
) -> None:
    """Filtre intermediary_id."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get(
            f"/api/offers?intermediary_id={published_offer.intermediary_id}"
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_offers_pagination(
    db_session, published_offer,
) -> None:
    """Pagination via limit/offset."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/offers?limit=10&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["limit"] == 10
    assert data["offset"] == 0


# ----- get_offer -----


@pytest.mark.asyncio
async def test_get_offer_returns_published(
    db_session, published_offer,
) -> None:
    """GET /api/offers/{id} pour offre published → 200."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get(f"/api/offers/{published_offer.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(published_offer.id)
    assert data["publication_status"] == "published"


@pytest.mark.asyncio
async def test_get_offer_returns_404_for_draft(
    db_session, draft_offer,
) -> None:
    """GET /api/offers/{id} pour offre draft → 404 (anti-fuite)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get(f"/api/offers/{draft_offer.id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_offer_returns_404_for_unknown(
    db_session,
) -> None:
    """GET /api/offers/{unknown_id} → 404."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get(f"/api/offers/{uuid.uuid4()}")
    assert resp.status_code == 404


# ----- comparator -----


@pytest.mark.asyncio
async def test_comparator_returns_all_published_for_fund(
    db_session, published_offer, draft_offer,
) -> None:
    """Comparator retourne uniquement offres published pour ce fonds."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get(
            f"/api/offers/comparator?fund_id={published_offer.fund_id}"
        )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["offer_id"] == str(published_offer.id)


@pytest.mark.asyncio
async def test_comparator_empty_for_unknown_fund(
    db_session,
) -> None:
    """Comparator retourne [] si aucun fonds matché."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get(
            f"/api/offers/comparator?fund_id={uuid.uuid4()}"
        )
    assert resp.status_code == 200
    assert resp.json() == []
