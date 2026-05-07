"""Tests d'intégration HTTP du router Projects (F06).

Couvre :
- POST /api/projects (création)
- GET /api/projects (liste paginée + filtres)
- GET /api/projects/{id} (détail)
- PATCH /api/projects/{id} (update)
- DELETE /api/projects/{id} (soft delete + garde-fou)
- POST /api/projects/{id}/duplicate
- GET /api/projects/{id}/applications
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from unittest.mock import patch

from app.api.deps import get_current_user
from app.main import app
from tests.conftest import make_account, make_pme_user


@pytest.fixture
async def authed_user(db_session):
    """Crée un user PME et override get_current_user."""
    account = await make_account(db_session, name="TestCo")
    user = await make_pme_user(
        db_session, email="proj@test.com", account=account,
    )
    await db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_create_project_201(client: AsyncClient, authed_user):
    payload = {
        "name": "Mon projet",
        "description": "Description",
        "objective_env": ["renewable_energy"],
        "maturity": "pilot",
    }
    response = await client.post("/api/projects", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Mon projet"
    assert body["status"] == "draft"
    assert body["account_id"] == str(authed_user.account_id)


@pytest.mark.asyncio
async def test_create_project_400_invalid_objective_env(
    client: AsyncClient, authed_user,
):
    payload = {"name": "P", "objective_env": ["invalid"]}
    response = await client.post("/api/projects", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_project_400_missing_name(client: AsyncClient, authed_user):
    response = await client.post("/api/projects", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_projects_empty(client: AsyncClient, authed_user):
    response = await client.get("/api/projects")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []


@pytest.mark.asyncio
async def test_list_projects_after_create(client: AsyncClient, authed_user):
    await client.post("/api/projects", json={"name": "A"})
    await client.post("/api/projects", json={"name": "B"})
    response = await client.get("/api/projects")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_list_projects_filter_status(client: AsyncClient, authed_user):
    await client.post("/api/projects", json={"name": "A", "status": "draft"})
    await client.post(
        "/api/projects", json={"name": "B", "status": "seeking_funding"},
    )
    response = await client.get("/api/projects?status=seeking_funding")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "B"


@pytest.mark.asyncio
async def test_get_project_detail(client: AsyncClient, authed_user):
    create_resp = await client.post("/api/projects", json={"name": "Detail test"})
    project_id = create_resp.json()["id"]
    response = await client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == project_id
    assert body["name"] == "Detail test"
    assert "project_documents" in body


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient, authed_user):
    fake = uuid.uuid4()
    response = await client.get(f"/api/projects/{fake}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_project_partial(client: AsyncClient, authed_user):
    create_resp = await client.post("/api/projects", json={"name": "Old"})
    project_id = create_resp.json()["id"]
    response = await client.patch(
        f"/api/projects/{project_id}",
        json={"name": "New", "expected_jobs_created": 7},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "New"
    assert body["expected_jobs_created"] == 7


@pytest.mark.asyncio
async def test_patch_project_not_found(client: AsyncClient, authed_user):
    fake = uuid.uuid4()
    response = await client.patch(
        f"/api/projects/{fake}", json={"name": "x"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_soft(client: AsyncClient, authed_user):
    create_resp = await client.post("/api/projects", json={"name": "To delete"})
    project_id = create_resp.json()["id"]
    response = await client.delete(f"/api/projects/{project_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    # Vérifier que le statut est bien cancelled
    detail_resp = await client.get(f"/api/projects/{project_id}")
    assert detail_resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_delete_project_not_found(client: AsyncClient, authed_user):
    fake = uuid.uuid4()
    response = await client.delete(f"/api/projects/{fake}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_project_default_suffix(
    client: AsyncClient, authed_user,
):
    create_resp = await client.post(
        "/api/projects",
        json={
            "name": "Site A",
            "description": "Original",
            "objective_env": ["renewable_energy"],
            "status": "funded",
        },
    )
    project_id = create_resp.json()["id"]
    response = await client.post(
        f"/api/projects/{project_id}/duplicate", json={},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Site A (copie)"
    assert body["status"] == "draft"
    assert body["id"] != project_id
    assert body["objective_env"] == ["renewable_energy"]
    assert body["description"] == "Original"


@pytest.mark.asyncio
async def test_duplicate_project_with_new_name(client: AsyncClient, authed_user):
    create_resp = await client.post("/api/projects", json={"name": "Site A"})
    project_id = create_resp.json()["id"]
    response = await client.post(
        f"/api/projects/{project_id}/duplicate",
        json={"new_name": "Site B"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Site B"
    assert body["status"] == "draft"


@pytest.mark.asyncio
async def test_duplicate_project_not_found(client: AsyncClient, authed_user):
    fake = uuid.uuid4()
    response = await client.post(
        f"/api/projects/{fake}/duplicate", json={},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_project_applications_empty(
    client: AsyncClient, authed_user,
):
    create_resp = await client.post("/api/projects", json={"name": "P"})
    project_id = create_resp.json()["id"]
    response = await client.get(f"/api/projects/{project_id}/applications")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_project_applications_not_found(
    client: AsyncClient, authed_user,
):
    fake = uuid.uuid4()
    response = await client.get(f"/api/projects/{fake}/applications")
    assert response.status_code == 404
