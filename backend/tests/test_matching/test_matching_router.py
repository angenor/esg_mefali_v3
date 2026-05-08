"""Tests d'intégration HTTP du router Matching (F14)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.api.deps import get_current_user
from app.main import app
from tests.conftest import make_account, make_pme_user


@pytest.fixture
async def authed_user(db_session):
    """User PME authentifié."""
    account = await make_account(db_session, name="MatchingCo")
    user = await make_pme_user(
        db_session, email="match@test.com", account=account,
    )
    await db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_list_matches_empty_returns_200(client: AsyncClient, authed_user):
    """Pas de matches : 200 + liste vide."""
    project_id = uuid.uuid4()
    response = await client.get(f"/api/projects/{project_id}/matches")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_list_matches_invalid_bottleneck_422(
    client: AsyncClient, authed_user,
):
    """Bottleneck invalide → 422."""
    project_id = uuid.uuid4()
    response = await client.get(
        f"/api/projects/{project_id}/matches?bottleneck=foo",
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_matches_filters_accepted(
    client: AsyncClient, authed_user,
):
    """Filtres min_score/bottleneck/fund_id sont acceptés."""
    project_id = uuid.uuid4()
    response = await client.get(
        f"/api/projects/{project_id}/matches"
        f"?min_score=80&bottleneck=balanced",
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_match_details_404_when_not_found(
    client: AsyncClient, authed_user,
):
    """match-details renvoie 404 si introuvable."""
    project_id = uuid.uuid4()
    offer_id = uuid.uuid4()
    response = await client.get(
        f"/api/projects/{project_id}/match-details/{offer_id}",
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_match_alerts_404_when_not_subscribed(
    client: AsyncClient, authed_user,
):
    """GET /match-alerts → 404 si pas de souscription."""
    project_id = uuid.uuid4()
    response = await client.get(
        f"/api/projects/{project_id}/match-alerts",
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_match_alerts_creates_subscription(
    client: AsyncClient, authed_user,
):
    """PATCH /match-alerts crée la souscription si absente (UPSERT comportemental)."""
    project_id = uuid.uuid4()
    response = await client.patch(
        f"/api/projects/{project_id}/match-alerts",
        json={"is_active": False, "min_global_score": 70},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_active"] is False
    assert body["min_global_score"] == 70


@pytest.mark.asyncio
async def test_patch_match_alerts_rejects_invalid_score(
    client: AsyncClient, authed_user,
):
    """PATCH refuse min_global_score > 100."""
    project_id = uuid.uuid4()
    response = await client.patch(
        f"/api/projects/{project_id}/match-alerts",
        json={"min_global_score": 150},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_recompute_matches_returns_202(
    client: AsyncClient, authed_user, db_session,
):
    """POST /recompute-matches retourne 202 + recompute_request_id."""
    from app.models.project import Project

    project = Project(
        account_id=authed_user.account_id,
        name="Test",
        objective_env=["mitigation"],
        status="draft",
    )
    db_session.add(project)
    await db_session.commit()

    response = await client.post(
        f"/api/projects/{project.id}/recompute-matches",
    )
    assert response.status_code == 202
    body = response.json()
    assert "recompute_request_id" in body
    assert "total_offers_to_compute" in body


@pytest.mark.asyncio
async def test_compare_offers_empty_returns_200(
    client: AsyncClient, authed_user,
):
    """GET /compare avec fund_id sans offres → 200 + structure vide."""
    project_id = uuid.uuid4()
    fund_id = uuid.uuid4()
    response = await client.get(
        f"/api/projects/{project_id}/compare?fund_id={fund_id}",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["fund_id"] == str(fund_id)
    assert body["subjects"] == []
    assert body["rows"] == []


@pytest.mark.asyncio
async def test_compare_offers_missing_fund_id_422(
    client: AsyncClient, authed_user,
):
    """GET /compare sans fund_id → 422."""
    project_id = uuid.uuid4()
    response = await client.get(f"/api/projects/{project_id}/compare")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_endpoints_unauthenticated_returns_401_or_403(
    client: AsyncClient,
):
    """Sans auth, les endpoints sont protégés."""
    # No authed_user fixture → app.dependency_overrides[get_current_user] absent
    project_id = uuid.uuid4()
    response = await client.get(f"/api/projects/{project_id}/matches")
    assert response.status_code in (401, 403)
