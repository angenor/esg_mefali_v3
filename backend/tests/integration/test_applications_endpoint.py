"""T021 (F048 US3) — Endpoint POST /api/applications/ (parité UI).

Réf. contracts/application-creation.md T3–T5.

- ``offer_id`` + ``project_id`` → 201, dossier lié au projet/offre ;
- ``offer_id`` inexistant → 404 ;
- ``project_id`` d'un autre compte → 403 (RLS F02).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.core.database import get_db
from app.main import app
from app.models.account import Account
from app.models.project import Project
from app.models.user import User

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def endpoint_client(
    db_session, f048_pme_user,
) -> AsyncGenerator[tuple[AsyncClient, User], None]:
    """Client HTTP dont get_db yield la session de test + auth = user PME réel."""

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: f048_pme_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
        ) as client:
            yield client, f048_pme_user
    finally:
        # Restaurer l'override get_db global du conftest (override_get_db).
        from tests.conftest import override_get_db
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides.pop(get_current_user, None)


async def test_t3_create_with_offer_and_project_returns_201(
    endpoint_client, f048_offer, f048_project,
):
    """T3 — offer_id + project_id → 201, dossier lié."""
    client, _user = endpoint_client
    resp = await client.post(
        "/api/applications/",
        json={"offer_id": str(f048_offer.id), "project_id": str(f048_project.id)},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "draft"
    assert data["fund"]["id"] == str(f048_offer.fund_id)
    # 050 — le dossier expose le projet auquel il se rapporte (lien 1:1, F06).
    assert data["project"] is not None
    assert data["project"]["id"] == str(f048_project.id)
    assert data["project"]["name"] == "Solarisation Boulangerie Dakar"


async def test_t4_unknown_offer_returns_404(endpoint_client):
    """T4 — offer_id inexistant → 404."""
    client, _user = endpoint_client
    resp = await client.post(
        "/api/applications/",
        json={"offer_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404, resp.text


async def test_t5_cross_account_project_returns_403(
    endpoint_client, db_session, f048_offer,
):
    """T5 — project_id d'un autre compte → 403."""
    client, _user = endpoint_client

    other_account = Account(name=f"Other-{uuid.uuid4().hex[:6]}")
    db_session.add(other_account)
    await db_session.flush()
    other_project = Project(
        account_id=other_account.id, name="Projet d'un autre compte", status="draft",
    )
    db_session.add(other_project)
    await db_session.flush()

    resp = await client.post(
        "/api/applications/",
        json={"offer_id": str(f048_offer.id), "project_id": str(other_project.id)},
    )
    assert resp.status_code == 403, resp.text
