"""Tests unitaires pour les tools 049 — découverte des dossiers + fourniture
de documents de checklist depuis le chat.

Trois nouveaux tools :
- ``list_applications`` : lister les dossiers de l'utilisateur courant (sans arg).
- ``provide_checklist_document`` : rattacher un document à un item de checklist.
- ``detach_checklist_document`` : détacher le document d'un item.

Le flux visé : list_applications → get_application_checklist (item_keys) →
list_user_documents → provide_checklist_document.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.graph.tools.application_tools import (
    APPLICATION_TOOLS,
    detach_checklist_document,
    list_applications,
    provide_checklist_document,
)


# UUID du user de référence (= mock_config["configurable"]["user_id"]).
_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _make_application(**overrides):
    """Mock de FundApplication avec sections/checklist RÉELS (dict/list).

    ``compute_sections_progress`` / ``compute_checklist_progress`` opèrent sur
    ces structures : elles doivent être de vrais dict/list, pas des MagicMock.
    """
    app = MagicMock()
    fund = MagicMock()
    fund.name = "Green Climate Fund"
    project = MagicMock()
    project.name = "Mini-centrale solaire de Bamako"
    defaults = {
        "id": uuid.uuid4(),
        "user_id": _USER_ID,
        "account_id": uuid.UUID("00000000-0000-0000-0000-0000000000a1"),
        "fund": fund,
        "project": project,
        "target_type": "fund_direct",
        "status": "draft",
        "sections": {
            "company_presentation": {"status": "generated", "title": "Présentation"},
            "project_description": {"status": "not_generated", "title": "Projet"},
        },
        "checklist": [
            {
                "key": "company_registration",
                "name": "Registre de commerce (RCCM)",
                "status": "provided",
                "document_id": str(uuid.uuid4()),
                "required_by": "fund_direct",
            },
            {
                "key": "env_impact_study",
                "name": "Étude d'impact environnemental",
                "status": "missing",
                "document_id": None,
                "required_by": "fund_direct",
            },
        ],
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        setattr(app, key, value)
    return app


# =====================================================================
# list_applications
# =====================================================================


class TestListApplications:
    """Tests pour list_applications (découverte des dossiers)."""

    @pytest.mark.asyncio
    @patch("app.modules.applications.service.get_applications", new_callable=AsyncMock)
    async def test_list_success(self, mock_get_apps, mock_config):
        """Liste les dossiers avec fonds, projet, statut et progressions."""
        app = _make_application()
        mock_get_apps.return_value = ([app], 1)

        result = await list_applications.ainvoke({}, config=mock_config)

        # Fonds + projet + progression documentaire (1/2) remontent.
        assert "Green Climate Fund" in result
        assert "Mini-centrale solaire de Bamako" in result
        assert "1/2" in result  # 1 document fourni sur 2
        mock_get_apps.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.modules.applications.service.get_applications", new_callable=AsyncMock)
    async def test_list_idor_guard_scopes_to_current_user(self, mock_get_apps, mock_config):
        """Garde anti-IDOR : get_applications est scopé au user_id du config."""
        mock_get_apps.return_value = ([], 0)

        await list_applications.ainvoke({}, config=mock_config)

        _, kwargs = mock_get_apps.call_args
        assert kwargs.get("user_id") == _USER_ID

    @pytest.mark.asyncio
    @patch("app.modules.applications.service.get_applications", new_callable=AsyncMock)
    async def test_list_invalid_status_is_ignored(self, mock_get_apps, mock_config):
        """Un statut hors enum (texte libre LLM) est ignoré, pas transmis tel
        quel à la colonne PG enum (sinon DataError → transaction avortée)."""
        mock_get_apps.return_value = ([], 0)

        await list_applications.ainvoke({"status": "en cours"}, config=mock_config)

        _, kwargs = mock_get_apps.call_args
        assert kwargs.get("status") is None

    @pytest.mark.asyncio
    @patch("app.modules.applications.service.get_applications", new_callable=AsyncMock)
    async def test_list_valid_status_is_forwarded(self, mock_get_apps, mock_config):
        """Un statut valide d'ApplicationStatus est bien transmis au service."""
        mock_get_apps.return_value = ([], 0)

        await list_applications.ainvoke({"status": "draft"}, config=mock_config)

        _, kwargs = mock_get_apps.call_args
        assert kwargs.get("status") == "draft"

    @pytest.mark.asyncio
    @patch("app.modules.applications.service.get_applications", new_callable=AsyncMock)
    async def test_list_empty(self, mock_get_apps, mock_config):
        """Aucun dossier → message clair invitant à candidater."""
        mock_get_apps.return_value = ([], 0)

        result = await list_applications.ainvoke({}, config=mock_config)

        assert "aucun" in result.lower()

    @pytest.mark.asyncio
    @patch("app.modules.applications.service.get_applications", new_callable=AsyncMock)
    async def test_list_application_without_project(self, mock_get_apps, mock_config):
        """Un dossier sans projet lié ne casse pas la sérialisation."""
        app = _make_application(project=None)
        mock_get_apps.return_value = ([app], 1)

        result = await list_applications.ainvoke({}, config=mock_config)

        assert "Green Climate Fund" in result

    @pytest.mark.asyncio
    @patch(
        "app.modules.applications.service.get_applications",
        new_callable=AsyncMock,
        side_effect=Exception("DB error"),
    )
    async def test_list_handles_error(self, mock_get_apps, mock_config):
        """Erreur DB → message lisible (pas de stacktrace au LLM)."""
        result = await list_applications.ainvoke({}, config=mock_config)

        assert "Erreur" in result


# =====================================================================
# provide_checklist_document
# =====================================================================


class TestProvideChecklistDocument:
    """Tests pour provide_checklist_document (rattachement)."""

    @pytest.mark.asyncio
    @patch(
        "app.modules.applications.service.attach_checklist_document",
        new_callable=AsyncMock,
    )
    @patch(
        "app.modules.applications.service.get_application_by_id",
        new_callable=AsyncMock,
    )
    async def test_provide_success(self, mock_get_app, mock_attach, mock_config):
        """Rattacher un RCCM à l'item registre → item « fourni »."""
        app = _make_application()
        mock_get_app.return_value = app
        doc_id = uuid.uuid4()
        mock_attach.return_value = {
            "item": {
                "key": "company_registration",
                "name": "Registre de commerce (RCCM)",
                "status": "provided",
                "document_id": str(doc_id),
                "document": {"original_filename": "rccm.pdf"},
            },
            "checklist_progress": {"provided": 2, "total": 2},
        }

        result = await provide_checklist_document.ainvoke(
            {
                "application_id": str(app.id),
                "item_key": "company_registration",
                "document_id": str(doc_id),
            },
            config=mock_config,
        )

        assert "Registre de commerce (RCCM)" in result
        assert "fourni" in result.lower()
        assert "2/2" in result  # progression mise à jour
        mock_attach.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(
        "app.modules.applications.service.get_application_by_id",
        new_callable=AsyncMock,
    )
    async def test_provide_app_not_found(self, mock_get_app, mock_config):
        """Dossier introuvable → message d'erreur, pas d'appel attach."""
        mock_get_app.return_value = None

        result = await provide_checklist_document.ainvoke(
            {
                "application_id": str(uuid.uuid4()),
                "item_key": "company_registration",
                "document_id": str(uuid.uuid4()),
            },
            config=mock_config,
        )

        assert "introuvable" in result.lower()

    @pytest.mark.asyncio
    @patch(
        "app.modules.applications.service.attach_checklist_document",
        new_callable=AsyncMock,
    )
    @patch(
        "app.modules.applications.service.get_application_by_id",
        new_callable=AsyncMock,
    )
    async def test_provide_idor_guard(self, mock_get_app, mock_attach, mock_config):
        """Dossier d'un AUTRE utilisateur → traité comme introuvable (anti-IDOR).

        Le service de rattachement NE doit PAS être appelé (pas de fuite/mutation).
        """
        app = _make_application(user_id=uuid.uuid4())  # autre propriétaire
        mock_get_app.return_value = app

        result = await provide_checklist_document.ainvoke(
            {
                "application_id": str(app.id),
                "item_key": "company_registration",
                "document_id": str(uuid.uuid4()),
            },
            config=mock_config,
        )

        assert "introuvable" in result.lower()
        mock_attach.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(
        "app.modules.applications.service.attach_checklist_document",
        new_callable=AsyncMock,
    )
    @patch(
        "app.modules.applications.service.get_application_by_id",
        new_callable=AsyncMock,
    )
    async def test_provide_item_not_found(self, mock_get_app, mock_attach, mock_config):
        """item_key inexistant → 404 service mappé en message clair (FR-016)."""
        from app.modules.applications.service import ApplicationItemNotFound

        app = _make_application()
        mock_get_app.return_value = app
        mock_attach.side_effect = ApplicationItemNotFound("inconnu")

        result = await provide_checklist_document.ainvoke(
            {
                "application_id": str(app.id),
                "item_key": "inconnu",
                "document_id": str(uuid.uuid4()),
            },
            config=mock_config,
        )

        assert "item" in result.lower() or "checklist" in result.lower()

    @pytest.mark.asyncio
    @patch(
        "app.modules.applications.service.attach_checklist_document",
        new_callable=AsyncMock,
    )
    @patch(
        "app.modules.applications.service.get_application_by_id",
        new_callable=AsyncMock,
    )
    async def test_provide_document_not_found(self, mock_get_app, mock_attach, mock_config):
        """document_id inexistant → message clair (FR-016)."""
        from app.modules.applications.service import DocumentNotFound

        app = _make_application()
        mock_get_app.return_value = app
        mock_attach.side_effect = DocumentNotFound("doc")

        result = await provide_checklist_document.ainvoke(
            {
                "application_id": str(app.id),
                "item_key": "company_registration",
                "document_id": str(uuid.uuid4()),
            },
            config=mock_config,
        )

        assert "document" in result.lower() and "introuvable" in result.lower()

    @pytest.mark.asyncio
    @patch(
        "app.modules.applications.service.attach_checklist_document",
        new_callable=AsyncMock,
    )
    @patch(
        "app.modules.applications.service.get_application_by_id",
        new_callable=AsyncMock,
    )
    async def test_provide_cross_account(self, mock_get_app, mock_attach, mock_config):
        """Document d'un autre compte → refus (FR-010, SC-003)."""
        from app.modules.applications.service import DocumentCrossAccount

        app = _make_application()
        mock_get_app.return_value = app
        mock_attach.side_effect = DocumentCrossAccount("doc")

        result = await provide_checklist_document.ainvoke(
            {
                "application_id": str(app.id),
                "item_key": "company_registration",
                "document_id": str(uuid.uuid4()),
            },
            config=mock_config,
        )

        assert "compte" in result.lower() or "organisation" in result.lower()

    @pytest.mark.asyncio
    @patch(
        "app.modules.applications.service.attach_checklist_document",
        new_callable=AsyncMock,
    )
    @patch(
        "app.modules.applications.service.get_application_by_id",
        new_callable=AsyncMock,
    )
    async def test_provide_replacement_does_not_short_circuit(
        self, mock_get_app, mock_attach, mock_config,
    ):
        """US4/FR-007 — remplacer un document sur un item DÉJÀ « provided » : le
        tool ne court-circuite pas, il rappelle bien le service (qui écrase)."""
        app = _make_application()
        mock_get_app.return_value = app
        new_doc = uuid.uuid4()
        mock_attach.return_value = {
            "item": {"name": "Registre de commerce (RCCM)", "status": "provided"},
            "checklist_progress": {"provided": 1, "total": 2},
        }

        result = await provide_checklist_document.ainvoke(
            {
                "application_id": str(app.id),
                # item déjà « provided » dans _make_application
                "item_key": "company_registration",
                "document_id": str(new_doc),
            },
            config=mock_config,
        )

        mock_attach.assert_awaited_once()
        # Le nouveau document_id est bien transmis au service.
        _, kwargs = mock_attach.call_args
        assert kwargs.get("document_id") == new_doc
        assert "fourni" in result.lower()

    @pytest.mark.asyncio
    async def test_provide_handles_missing_db(self, mock_config_no_db):
        """Config sans session DB → message d'erreur lisible (pas de stacktrace)."""
        result = await provide_checklist_document.ainvoke(
            {
                "application_id": str(uuid.uuid4()),
                "item_key": "company_registration",
                "document_id": str(uuid.uuid4()),
            },
            config=mock_config_no_db,
        )

        assert "Erreur" in result


# =====================================================================
# detach_checklist_document
# =====================================================================


class TestDetachChecklistDocument:
    """Tests pour detach_checklist_document (détachement)."""

    @pytest.mark.asyncio
    @patch(
        "app.modules.applications.service.detach_checklist_document",
        new_callable=AsyncMock,
    )
    @patch(
        "app.modules.applications.service.get_application_by_id",
        new_callable=AsyncMock,
    )
    async def test_detach_success(self, mock_get_app, mock_detach, mock_config):
        """Détacher un document → item repasse « manquant »."""
        app = _make_application()
        mock_get_app.return_value = app
        mock_detach.return_value = {
            "item": {
                "key": "company_registration",
                "name": "Registre de commerce (RCCM)",
                "status": "missing",
                "document_id": None,
                "document": None,
            },
            "checklist_progress": {"provided": 0, "total": 2},
        }

        result = await detach_checklist_document.ainvoke(
            {"application_id": str(app.id), "item_key": "company_registration"},
            config=mock_config,
        )

        assert "Registre de commerce (RCCM)" in result
        assert "manquant" in result.lower() or "détaché" in result.lower()
        mock_detach.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(
        "app.modules.applications.service.detach_checklist_document",
        new_callable=AsyncMock,
    )
    @patch(
        "app.modules.applications.service.get_application_by_id",
        new_callable=AsyncMock,
    )
    async def test_detach_idor_guard(self, mock_get_app, mock_detach, mock_config):
        """Dossier d'un autre utilisateur → introuvable, pas de mutation."""
        app = _make_application(user_id=uuid.uuid4())
        mock_get_app.return_value = app

        result = await detach_checklist_document.ainvoke(
            {"application_id": str(app.id), "item_key": "company_registration"},
            config=mock_config,
        )

        assert "introuvable" in result.lower()
        mock_detach.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(
        "app.modules.applications.service.detach_checklist_document",
        new_callable=AsyncMock,
    )
    @patch(
        "app.modules.applications.service.get_application_by_id",
        new_callable=AsyncMock,
    )
    async def test_detach_item_not_found(self, mock_get_app, mock_detach, mock_config):
        """item_key inexistant → message clair (FR-016)."""
        from app.modules.applications.service import ApplicationItemNotFound

        app = _make_application()
        mock_get_app.return_value = app
        mock_detach.side_effect = ApplicationItemNotFound("inconnu")

        result = await detach_checklist_document.ainvoke(
            {"application_id": str(app.id), "item_key": "inconnu"},
            config=mock_config,
        )

        assert "item" in result.lower() or "checklist" in result.lower()

    @pytest.mark.asyncio
    async def test_detach_handles_missing_db(self, mock_config_no_db):
        """Config sans session DB → message d'erreur lisible (pas de stacktrace)."""
        result = await detach_checklist_document.ainvoke(
            {"application_id": str(uuid.uuid4()), "item_key": "company_registration"},
            config=mock_config_no_db,
        )

        assert "Erreur" in result


# =====================================================================
# Export du module
# =====================================================================


class TestApplicationChecklistToolsExport:
    """APPLICATION_TOOLS doit exposer les 3 nouveaux tools (9 au total)."""

    def test_tools_list_count(self):
        assert len(APPLICATION_TOOLS) == 9

    def test_new_tool_names_present(self):
        names = {t.name for t in APPLICATION_TOOLS}
        assert {
            "list_applications",
            "provide_checklist_document",
            "detach_checklist_document",
        } <= names

    def test_new_tools_have_french_descriptions(self):
        by_name = {t.name for t in APPLICATION_TOOLS}
        assert "list_applications" in by_name
        for t in APPLICATION_TOOLS:
            if t.name in {
                "list_applications",
                "provide_checklist_document",
                "detach_checklist_document",
            }:
                assert any(
                    word in t.description.lower()
                    for word in ["dossier", "document", "checklist", "rattach", "fourni"]
                ), f"Description non française : {t.description}"
