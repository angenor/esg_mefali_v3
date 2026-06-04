"""Tests unitaires pour les tools application/candidature."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.graph.tools.application_tools import (
    APPLICATION_TOOLS,
    export_application,
    generate_application_section,
    get_application_checklist,
    simulate_financing,
    update_application_section,
)


def _make_application(**overrides):
    """Creer un mock de FundApplication."""
    app = MagicMock()
    defaults = {
        "id": uuid.uuid4(),
        "user_id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
        "fund_id": uuid.uuid4(),
        "status": "draft",
        "sections": {},
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        setattr(app, key, value)
    return app


class TestGenerateApplicationSection:
    """Tests pour generate_application_section."""

    @pytest.mark.asyncio
    @patch("app.modules.applications.service.generate_section", new_callable=AsyncMock)
    @patch("app.modules.applications.service.get_application_by_id", new_callable=AsyncMock)
    async def test_generate_success(self, mock_get_app, mock_gen, mock_config):
        """Generation d'une section retourne le contenu."""
        app = _make_application()
        mock_get_app.return_value = app
        mock_gen.return_value = {
            "section_key": "company_presentation",
            "content": "EcoAfrik est une entreprise...",
            "status": "generated",
        }

        result = await generate_application_section.ainvoke(
            {"application_id": str(app.id), "section_key": "company_presentation"},
            config=mock_config,
        )

        assert "company_presentation" in result or "section" in result.lower()
        mock_gen.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.modules.applications.service.get_application_by_id", new_callable=AsyncMock)
    async def test_generate_app_not_found(self, mock_get_app, mock_config):
        """Application introuvable retourne un message d'erreur."""
        mock_get_app.return_value = None

        result = await generate_application_section.ainvoke(
            {"application_id": str(uuid.uuid4()), "section_key": "company_presentation"},
            config=mock_config,
        )

        assert "introuvable" in result.lower() or "Erreur" in result


class TestUpdateApplicationSection:
    """Tests pour update_application_section."""

    @pytest.mark.asyncio
    @patch("app.modules.applications.service.update_section", new_callable=AsyncMock)
    @patch("app.modules.applications.service.get_application_by_id", new_callable=AsyncMock)
    async def test_update_success(self, mock_get_app, mock_update, mock_config):
        """Mise a jour d'une section retourne la confirmation."""
        app = _make_application()
        mock_get_app.return_value = app
        mock_update.return_value = {"section_key": "budget", "status": "edited"}

        result = await update_application_section.ainvoke(
            {
                "application_id": str(app.id),
                "section_key": "budget",
                "content": "Budget revise : 100M FCFA",
            },
            config=mock_config,
        )

        assert "budget" in result.lower() or "mise" in result.lower()


class TestGetApplicationChecklist:
    """Tests pour get_application_checklist."""

    @pytest.mark.asyncio
    @patch("app.modules.applications.service.get_checklist", new_callable=AsyncMock)
    @patch("app.modules.applications.service.get_application_by_id", new_callable=AsyncMock)
    async def test_checklist_success(self, mock_get_app, mock_checklist, mock_config):
        """Checklist : parité FR-019 — lecture de la forme réelle des items
        (`{key, name, status, document_id, required_by}`)."""
        app = _make_application()
        app.user_id = mock_config["configurable"]["user_id"]
        mock_get_app.return_value = app
        # 049 — forme RÉELLE stockée (et non l'ancienne forme fictive
        # `{label, required, provided}` qui n'existe nulle part).
        mock_checklist.return_value = [
            {
                "key": "company_registration",
                "name": "Registre de commerce (RCCM)",
                "status": "provided",
                "document_id": str(uuid.uuid4()),
                "required_by": "fund_direct",
            },
            {
                "key": "financial_statements",
                "name": "Plan financier",
                "status": "missing",
                "document_id": None,
                "required_by": "fund_direct",
            },
        ]

        result = await get_application_checklist.ainvoke(
            {"application_id": str(app.id)},
            config=mock_config,
        )

        # Le libellé `name` remonte, le comptage utilise status == "provided".
        assert "Registre de commerce (RCCM)" in result
        assert "Plan financier" in result
        assert "1/2 documents fournis" in result
        # 049 — l'item_key DOIT être exposé : sans lui, provide_checklist_document
        # ne peut pas être appelé (le LLM ne voit sinon que le libellé).
        assert "company_registration" in result
        assert "financial_statements" in result


class TestSimulateFinancing:
    """Tests pour simulate_financing."""

    @pytest.mark.asyncio
    @patch("app.graph.tools.application_tools._simulate_financing", new_callable=AsyncMock)
    @patch("app.modules.applications.service.get_application_by_id", new_callable=AsyncMock)
    async def test_simulate_success(self, mock_get_app, mock_simulate, mock_config):
        """Simulation retourne les resultats."""
        app = _make_application()
        mock_get_app.return_value = app
        mock_simulate.return_value = {
            "eligible_amount": 200000000,
            "roi_estimate": "15%",
            "timeline_months": 18,
        }

        result = await simulate_financing.ainvoke(
            {"application_id": str(app.id)},
            config=mock_config,
        )

        assert "200" in result or "simulat" in result.lower()


class TestExportApplication:
    """Tests pour export_application."""

    @pytest.mark.asyncio
    @patch("app.graph.tools.application_tools._export_application", new_callable=AsyncMock)
    @patch("app.modules.applications.service.get_application_by_id", new_callable=AsyncMock)
    async def test_export_pdf(self, mock_get_app, mock_export, mock_config):
        """Export PDF retourne l'URL (gating ignoré : ni projet ni offre liés)."""
        app = _make_application()
        # F048 — pas de gating sans project_id/offer_id ; user_id = celui du config.
        app.user_id = mock_config["configurable"]["user_id"]
        app.project_id = None
        app.offer_id = None
        app.account_id = None
        mock_get_app.return_value = app
        # F048 — _export_application retourne désormais un dict (D3).
        mock_export.return_value = {
            "storage_path": "uploads/applications/dossier.pdf",
            "filename": "dossier.pdf",
            "document_id": str(uuid.uuid4()),
        }

        result = await export_application.ainvoke(
            {"application_id": str(app.id), "format": "pdf"},
            config=mock_config,
        )

        assert "pdf" in result.lower() or "export" in result.lower()
        mock_export.assert_awaited_once()


class TestApplicationToolsExport:
    """Tests pour l'export du module."""

    def test_tools_list_count(self):
        """APPLICATION_TOOLS contient 9 tools (6 + 3 tools 049 découverte/checklist)."""
        assert len(APPLICATION_TOOLS) == 9

    def test_tool_names(self):
        """Les tools ont les bons noms."""
        names = {t.name for t in APPLICATION_TOOLS}
        assert names == {
            "create_fund_application",
            "generate_application_section",
            "update_application_section",
            "get_application_checklist",
            "simulate_financing",
            "export_application",
            # 049 — découverte des dossiers + fourniture des documents de checklist.
            "list_applications",
            "provide_checklist_document",
            "detach_checklist_document",
        }

    def test_tools_have_french_descriptions(self):
        """Les descriptions des tools sont en francais."""
        for t in APPLICATION_TOOLS:
            assert any(
                word in t.description.lower()
                for word in ["dossier", "section", "candidature", "checklist", "simulat", "export"]
            ), f"Description manque de termes francais : {t.description}"
