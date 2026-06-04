"""Tests d'integration du routeur dossiers de candidature."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.main import app


# --- Fixtures ---


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.is_active = True
    return user


@pytest.fixture
def auth_override(mock_user):
    """Override FastAPI dependency pour l'authentification."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield mock_user
    app.dependency_overrides.pop(get_current_user, None)


def _make_fund():
    fund = MagicMock()
    fund.id = uuid.uuid4()
    fund.name = "FNDE"
    fund.organization = "Etat"
    fund.description = "Fonds national"
    fund.sectors_eligible = ["agriculture"]
    return fund


def _make_application(
    user_id: uuid.UUID | None = None,
    target_type: str = "fund_direct",
    status: str = "draft",
):
    fund = _make_fund()
    app_mock = MagicMock()
    app_mock.id = uuid.uuid4()
    app_mock.user_id = user_id or uuid.uuid4()
    app_mock.fund_id = fund.id
    app_mock.fund = fund
    app_mock.match_id = None
    app_mock.intermediary_id = None
    app_mock.intermediary = None
    # 050 — lien dossier↔projet. None par défaut (les builders de réponse
    # exposent alors project=null sans tenter de valider un auto-MagicMock).
    app_mock.project = None
    app_mock.target_type = MagicMock(value=target_type)
    app_mock.status = MagicMock(value=status)
    app_mock.sections = {
        "company_presentation": {
            "title": "Présentation de l'entreprise",
            "content": None,
            "status": "not_generated",
            "updated_at": None,
        },
    }
    app_mock.checklist = [
        {"key": "rccm", "name": "RCCM", "status": "missing", "document_id": None, "required_by": "fund_direct"}
    ]
    app_mock.intermediary_prep = None
    app_mock.simulation = None
    app_mock.created_at = datetime.now(timezone.utc)
    app_mock.updated_at = datetime.now(timezone.utc)
    app_mock.submitted_at = None
    return app_mock


# --- Tests POST / ---


@pytest.mark.asyncio
async def test_create_application_success(auth_override):
    """POST / : creation reussie."""
    application = _make_application(user_id=auth_override.id)

    with patch(
        "app.modules.applications.service.create_application",
        new_callable=AsyncMock,
        return_value=application,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/applications/",
                json={"fund_id": str(application.fund_id)},
                headers={"Authorization": "Bearer test"},
            )

    assert response.status_code == 201
    data = response.json()
    assert data["target_type"] == "fund_direct"
    assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_create_application_fund_not_found(auth_override):
    """POST / : fonds inexistant → 404."""
    with patch(
        "app.modules.applications.service.create_application",
        new_callable=AsyncMock,
        side_effect=ValueError("Fonds non trouve"),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/applications/",
                json={"fund_id": str(uuid.uuid4())},
                headers={"Authorization": "Bearer test"},
            )

    assert response.status_code == 404


# --- Tests GET / ---


@pytest.mark.asyncio
async def test_list_applications(auth_override):
    """GET / : liste des dossiers."""
    application = _make_application(user_id=auth_override.id)

    with patch(
        "app.modules.applications.service.get_applications",
        new_callable=AsyncMock,
        return_value=([application], 1),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/applications/",
                headers={"Authorization": "Bearer test"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


# --- Tests GET /{id} ---


@pytest.mark.asyncio
async def test_get_application_detail(auth_override):
    """GET /{id} : detail d'un dossier."""
    application = _make_application(user_id=auth_override.id)

    with patch(
        "app.modules.applications.service.get_application_by_id",
        new_callable=AsyncMock,
        return_value=application,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/applications/{application.id}",
                headers={"Authorization": "Bearer test"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["target_type"] == "fund_direct"
    assert "sections" in data


@pytest.mark.asyncio
async def test_get_application_not_found(auth_override):
    """GET /{id} : dossier inexistant → 404."""
    with patch(
        "app.modules.applications.service.get_application_by_id",
        new_callable=AsyncMock,
        return_value=None,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/applications/{uuid.uuid4()}",
                headers={"Authorization": "Bearer test"},
            )

    assert response.status_code == 404


# --- Tests PATCH /{id}/status ---


@pytest.mark.asyncio
async def test_update_status_success(auth_override):
    """PATCH /{id}/status : transition valide."""
    application = _make_application(user_id=auth_override.id, status="draft")
    updated = _make_application(user_id=auth_override.id, status="preparing_documents")

    with (
        patch(
            "app.modules.applications.service.get_application_by_id",
            new_callable=AsyncMock,
            return_value=application,
        ),
        patch(
            "app.modules.applications.service.update_application_status",
            new_callable=AsyncMock,
            return_value=updated,
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/api/applications/{application.id}/status",
                json={"status": "preparing_documents"},
                headers={"Authorization": "Bearer test"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "preparing_documents"
    assert data["status_label"] == "Préparation des documents"


@pytest.mark.asyncio
async def test_update_status_invalid(auth_override):
    """PATCH /{id}/status : transition invalide → 422."""
    application = _make_application(user_id=auth_override.id, status="draft")

    with (
        patch(
            "app.modules.applications.service.get_application_by_id",
            new_callable=AsyncMock,
            return_value=application,
        ),
        patch(
            "app.modules.applications.service.update_application_status",
            new_callable=AsyncMock,
            side_effect=ValueError("Transition invalide"),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/api/applications/{application.id}/status",
                json={"status": "accepted"},
                headers={"Authorization": "Bearer test"},
            )

    assert response.status_code == 422


# --- Tests GET /{id}/checklist ---


@pytest.mark.asyncio
async def test_get_checklist(auth_override):
    """GET /{id}/checklist : recuperer la checklist."""
    application = _make_application(user_id=auth_override.id)

    with (
        patch(
            "app.modules.applications.service.get_application_by_id",
            new_callable=AsyncMock,
            return_value=application,
        ),
        patch(
            "app.modules.applications.service.get_checklist",
            new_callable=AsyncMock,
            return_value=application.checklist,
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/applications/{application.id}/checklist",
                headers={"Authorization": "Bearer test"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) == 1


# --- Tests POST /{id}/generate-section (US1) ---


@pytest.mark.asyncio
async def test_generate_section_success(auth_override):
    """POST /{id}/generate-section : generation reussie."""
    application = _make_application(user_id=auth_override.id)
    section_result = {
        "section_key": "company_presentation",
        "title": "Présentation de l'entreprise",
        "content": "<p>Contenu genere</p>",
        "status": "generated",
        "updated_at": "2026-03-31T10:00:00Z",
    }

    with (
        patch(
            "app.modules.applications.service.get_application_by_id",
            new_callable=AsyncMock,
            return_value=application,
        ),
        patch(
            "app.modules.applications.service.generate_section",
            new_callable=AsyncMock,
            return_value=section_result,
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/applications/{application.id}/generate-section",
                json={"section_key": "company_presentation"},
                headers={"Authorization": "Bearer test"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["section_key"] == "company_presentation"
    assert data["status"] == "generated"


# --- Tests PATCH /{id}/sections/{key} (US1) ---


@pytest.mark.asyncio
async def test_update_section_success(auth_override):
    """PATCH /{id}/sections/{key} : modification reussie."""
    application = _make_application(user_id=auth_override.id)
    section_result = {
        "section_key": "company_presentation",
        "title": "Présentation de l'entreprise",
        "content": "<p>Contenu modifie</p>",
        "status": "validated",
        "updated_at": "2026-03-31T10:00:00Z",
    }

    with (
        patch(
            "app.modules.applications.service.get_application_by_id",
            new_callable=AsyncMock,
            return_value=application,
        ),
        patch(
            "app.modules.applications.service.update_section",
            new_callable=AsyncMock,
            return_value=section_result,
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/api/applications/{application.id}/sections/company_presentation",
                json={"content": "<p>Contenu modifie</p>", "status": "validated"},
                headers={"Authorization": "Bearer test"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "validated"


# --- Tests POST /{id}/export (US1) ---


@pytest.mark.asyncio
async def test_export_pdf(auth_override):
    """POST /{id}/export : export PDF."""
    application = _make_application(user_id=auth_override.id)

    with (
        patch(
            "app.modules.applications.service.get_application_by_id",
            new_callable=AsyncMock,
            return_value=application,
        ),
        patch(
            "app.modules.applications.export.export_application",
            new_callable=AsyncMock,
            return_value=(b"%PDF-fake", "application/pdf", "dossier_fnde.pdf"),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/applications/{application.id}/export",
                json={"format": "pdf"},
                headers={"Authorization": "Bearer test"},
            )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


# --- Tests POST /{id}/prep-sheet (US3) ---


@pytest.mark.asyncio
async def test_prep_sheet_success(auth_override):
    """POST /{id}/prep-sheet : generation reussie."""
    application = _make_application(user_id=auth_override.id, target_type="intermediary_bank")

    with (
        patch(
            "app.modules.applications.service.get_application_by_id",
            new_callable=AsyncMock,
            return_value=application,
        ),
        patch(
            "app.modules.applications.prep_sheet.generate_prep_sheet",
            new_callable=AsyncMock,
            return_value=b"%PDF-prep",
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/applications/{application.id}/prep-sheet",
                headers={"Authorization": "Bearer test"},
            )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


@pytest.mark.asyncio
async def test_prep_sheet_fund_direct_error(auth_override):
    """POST /{id}/prep-sheet : erreur si fund_direct."""
    application = _make_application(user_id=auth_override.id, target_type="fund_direct")

    with patch(
        "app.modules.applications.service.get_application_by_id",
        new_callable=AsyncMock,
        return_value=application,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/applications/{application.id}/prep-sheet",
                headers={"Authorization": "Bearer test"},
            )

    assert response.status_code == 400
