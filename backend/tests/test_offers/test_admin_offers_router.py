"""F07 — Tests integration pour /api/admin/offers/* (US2 + US6).

Vérifie :
- compute endpoint retourne OfferDraft sans persistance.
- 403 pour non-admin.
- create_offer persiste en draft.
- patch publication_status bloque si prérequis manquent.
- patch publication_status réussit si tous prérequis OK.
- list admin retourne aussi les drafts.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_admin
from app.main import app


@pytest.fixture
async def admin_override():
    """Override get_current_admin avec un mock admin pour les tests."""
    mock_admin = MagicMock()
    mock_admin.id = uuid.uuid4()
    mock_admin.email = "admin@test.com"
    mock_admin.role = "ADMIN"
    mock_admin.is_active = True

    app.dependency_overrides[get_current_admin] = lambda: mock_admin
    yield mock_admin
    del app.dependency_overrides[get_current_admin]


# ----- compute -----


@pytest.mark.asyncio
async def test_compute_endpoint_returns_draft(
    db_session, basic_fund, basic_intermediary, basic_fund_intermediary,
    admin_override,
) -> None:
    """POST /api/admin/offers/compute → OfferDraft (sans persistance)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            f"/api/admin/offers/compute?fund_id={basic_fund.id}"
            f"&intermediary_id={basic_intermediary.id}"
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["fund_id"] == str(basic_fund.id)
    assert data["intermediary_id"] == str(basic_intermediary.id)
    assert "effective_criteria" in data
    assert "effective_required_documents" in data
    assert "accepted_languages_hint" in data


@pytest.mark.asyncio
async def test_compute_endpoint_404_for_unknown_fund(
    db_session, basic_intermediary, admin_override,
) -> None:
    """POST compute avec fund_id introuvable → 404."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            f"/api/admin/offers/compute?fund_id={uuid.uuid4()}"
            f"&intermediary_id={basic_intermediary.id}"
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_compute_endpoint_403_for_non_admin(
    db_session, basic_fund, basic_intermediary,
) -> None:
    """POST compute sans auth admin → 403/401."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            f"/api/admin/offers/compute?fund_id={basic_fund.id}"
            f"&intermediary_id={basic_intermediary.id}"
        )
    assert resp.status_code in (401, 403)


# ----- create -----


@pytest.mark.asyncio
async def test_create_offer_persists_in_draft(
    db_session, basic_fund, basic_intermediary, verified_source,
    admin_override,
) -> None:
    """POST /api/admin/offers crée une offre en draft + inactive."""
    payload = {
        "fund_id": str(basic_fund.id),
        "intermediary_id": str(basic_intermediary.id),
        "name": "Test Offer Created",
        "source_id": str(verified_source.id),
        "publication_status": "draft",
        "version": "1.0",
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/api/admin/offers", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Test Offer Created"
    assert data["publication_status"] == "draft"
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_create_offer_409_on_duplicate(
    db_session, published_offer, verified_source,
    admin_override,
) -> None:
    """POST /api/admin/offers en doublon (même fund/interm/version) → 409."""
    payload = {
        "fund_id": str(published_offer.fund_id),
        "intermediary_id": str(published_offer.intermediary_id),
        "name": "Doublon",
        "source_id": str(verified_source.id),
        "publication_status": "draft",
        "version": "1.0",  # même version → doublon
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/api/admin/offers", json=payload)
    assert resp.status_code == 409


# ----- patch -----


@pytest.mark.asyncio
async def test_patch_publication_status_blocks_unmet_prerequisites(
    db_session, basic_fund, basic_intermediary, verified_source,
    admin_override,
) -> None:
    """PATCH draft→published bloqué si fund en draft."""
    # Mettre fund en draft
    basic_fund.publication_status = "draft"
    await db_session.commit()

    # Créer offre draft
    from app.models.offer import Offer
    from datetime import date as _date
    offer = Offer(
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
        name="Test",
        source_id=verified_source.id,
        publication_status="draft",
        is_active=False,
        version="3.0",
        valid_from=_date.today(),
    )
    db_session.add(offer)
    await db_session.commit()

    # Tenter passage à published → 422
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.patch(
            f"/api/admin/offers/{offer.id}",
            json={"publication_status": "published"},
        )
    assert resp.status_code == 422
    body = resp.json()
    assert "missing_prerequisites" in body["detail"]
    assert "fund_not_published" in body["detail"]["missing_prerequisites"]


@pytest.mark.asyncio
async def test_patch_publication_status_blocks_unverified_source(
    db_session, basic_fund, basic_intermediary, draft_source,
    admin_override,
) -> None:
    """PATCH draft→published bloqué si source non verified."""
    from app.models.offer import Offer
    from datetime import date as _date
    offer = Offer(
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
        name="Test",
        source_id=draft_source.id,  # source en draft
        publication_status="draft",
        is_active=False,
        version="4.0",
        valid_from=_date.today(),
    )
    db_session.add(offer)
    await db_session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.patch(
            f"/api/admin/offers/{offer.id}",
            json={"publication_status": "published"},
        )
    assert resp.status_code == 422
    assert "source_not_verified" in resp.json()["detail"]["missing_prerequisites"]


@pytest.mark.asyncio
async def test_patch_publication_status_succeeds_when_all_ok(
    db_session, basic_fund, basic_intermediary, basic_fund_intermediary,
    verified_source, admin_override,
) -> None:
    """Tous prérequis OK → PATCH réussit, offre devient published+active."""
    from app.models.offer import Offer
    from datetime import date as _date
    offer = Offer(
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
        name="Test",
        source_id=verified_source.id,
        publication_status="draft",
        is_active=False,
        version="5.0",
        valid_from=_date.today(),
    )
    db_session.add(offer)
    await db_session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.patch(
            f"/api/admin/offers/{offer.id}",
            json={"publication_status": "published"},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["publication_status"] == "published"
    assert data["is_active"] is True


# ----- list admin -----


@pytest.mark.asyncio
async def test_admin_list_includes_drafts(
    db_session, published_offer, draft_offer, admin_override,
) -> None:
    """GET /api/admin/offers retourne aussi les drafts."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/admin/offers?include_drafts=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2  # au moins 1 published + 1 draft


@pytest.mark.asyncio
async def test_admin_list_403_without_auth(
    db_session, published_offer,
) -> None:
    """GET /api/admin/offers sans auth admin → 401/403."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/admin/offers?include_drafts=true")
    assert resp.status_code in (401, 403)
