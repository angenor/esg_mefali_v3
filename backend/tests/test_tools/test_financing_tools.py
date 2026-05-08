"""Tests unitaires pour les tools financement."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.graph.tools.application_tools import create_fund_application
from app.graph.tools.financing_tools import (
    FINANCING_TOOLS,
    get_fund_details,
    save_fund_interest,
    search_compatible_funds,
)


def _make_fund_match(**overrides):
    """Creer un mock de FundMatch."""
    match = MagicMock()
    defaults = {
        "id": uuid.uuid4(),
        "fund_id": uuid.uuid4(),
        "user_id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
        "compatibility_score": 78,
        "status": MagicMock(value="matched"),
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        setattr(match, key, value)
    # Mock fund relation
    fund = MagicMock()
    fund.id = uuid.uuid4()
    fund.name = "Fonds Vert GCF"
    fund.fund_type = MagicMock(value="grant")
    fund.min_amount_xof = 50000
    fund.max_amount_xof = 500000
    fund.access_type = MagicMock(value="direct")
    match.fund = fund
    return match


def _make_fund(**overrides):
    """Creer un mock de Fund."""
    fund = MagicMock()
    defaults = {
        "id": uuid.uuid4(),
        "name": "Fonds Vert GCF",
        "organization": "Green Climate Fund",
        "fund_type": MagicMock(value="grant"),
        "description": "Fonds pour la lutte contre le changement climatique",
        "min_amount_xof": 50000,
        "max_amount_xof": 500000,
        "sectors_eligible": ["agriculture", "energy"],
        "eligibility_criteria": {"countries": ["CI", "SN", "ML"]},
        "access_type": MagicMock(value="direct"),
        "status": MagicMock(value="active"),
        "fund_intermediaries": [],
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        setattr(fund, key, value)
    return fund


class TestSearchCompatibleFunds:
    """Tests pour search_compatible_funds."""

    @pytest.mark.asyncio
    @patch("app.modules.financing.service.get_fund_matches", new_callable=AsyncMock)
    @patch("app.modules.company.service.get_profile", new_callable=AsyncMock)
    async def test_search_with_matches(self, mock_profile, mock_matches, mock_config):
        """Recherche avec resultats retourne les fonds compatibles."""
        mock_profile.return_value = MagicMock(
            sector=MagicMock(value="agriculture"),
            annual_revenue_xof=50000000,
            country="Cote d'Ivoire",
            city="Abidjan",
        )
        mock_matches.return_value = [_make_fund_match(), _make_fund_match()]

        result = await search_compatible_funds.ainvoke({}, config=mock_config)

        assert "2" in result or "fonds" in result.lower()
        mock_matches.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.modules.financing.service.get_fund_matches", new_callable=AsyncMock)
    @patch("app.modules.company.service.get_profile", new_callable=AsyncMock)
    async def test_search_no_matches(self, mock_profile, mock_matches, mock_config):
        """Recherche sans resultat retourne un message."""
        mock_profile.return_value = MagicMock(
            sector=MagicMock(value="services"),
            annual_revenue_xof=None,
            country=None,
            city=None,
        )
        mock_matches.return_value = []

        result = await search_compatible_funds.ainvoke({}, config=mock_config)

        assert "Aucun" in result or "aucun" in result or "0" in result

    @pytest.mark.asyncio
    @patch(
        "app.modules.company.service.get_profile",
        new_callable=AsyncMock,
        side_effect=Exception("DB error"),
    )
    async def test_search_handles_error(self, mock_profile, mock_config):
        """Erreur retourne un message lisible."""
        result = await search_compatible_funds.ainvoke({}, config=mock_config)

        assert "Erreur" in result


class TestSaveFundInterest:
    """Tests pour save_fund_interest."""

    @pytest.mark.asyncio
    @patch("app.modules.financing.service.update_match_status", new_callable=AsyncMock)
    @patch("app.modules.financing.service.get_match_by_fund", new_callable=AsyncMock)
    async def test_save_interest_success(self, mock_get_match, mock_update, mock_config):
        """Sauvegarde d'interet retourne la confirmation."""
        match = _make_fund_match()
        mock_get_match.return_value = match
        mock_update.return_value = match

        result = await save_fund_interest.ainvoke(
            {"fund_id": str(uuid.uuid4())},
            config=mock_config,
        )

        assert "interet" in result.lower() or "enregistr" in result.lower() or "Fonds" in result

    @pytest.mark.asyncio
    @patch("app.modules.financing.service.get_match_by_fund", new_callable=AsyncMock)
    async def test_save_interest_no_match(self, mock_get_match, mock_config):
        """Fonds non matche retourne un message d'erreur."""
        mock_get_match.return_value = None

        result = await save_fund_interest.ainvoke(
            {"fund_id": str(uuid.uuid4())},
            config=mock_config,
        )

        assert "introuvable" in result.lower() or "Aucun" in result or "erreur" in result.lower()

    @pytest.mark.asyncio
    @patch(
        "app.modules.financing.service.get_match_by_fund",
        new_callable=AsyncMock,
        side_effect=Exception("DB error"),
    )
    async def test_save_handles_error(self, mock_get_match, mock_config):
        """Erreur retourne un message lisible."""
        result = await save_fund_interest.ainvoke(
            {"fund_id": str(uuid.uuid4())},
            config=mock_config,
        )

        assert "Erreur" in result


class TestGetFundDetails:
    """Tests pour get_fund_details."""

    @pytest.mark.asyncio
    @patch("app.modules.financing.service.get_fund_by_id", new_callable=AsyncMock)
    async def test_fund_found(self, mock_get_fund, mock_config):
        """Fonds trouve retourne les details."""
        fund = _make_fund()
        mock_get_fund.return_value = fund

        result = await get_fund_details.ainvoke(
            {"fund_id": str(fund.id)},
            config=mock_config,
        )

        assert "GCF" in result or "Fonds" in result
        mock_get_fund.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.modules.financing.service.get_fund_by_id", new_callable=AsyncMock)
    async def test_fund_not_found(self, mock_get_fund, mock_config):
        """Fonds introuvable retourne un message."""
        mock_get_fund.return_value = None

        result = await get_fund_details.ainvoke(
            {"fund_id": str(uuid.uuid4())},
            config=mock_config,
        )

        assert "introuvable" in result.lower() or "Aucun" in result


class TestCreateFundApplication:
    """Tests pour create_fund_application."""

    @pytest.mark.asyncio
    @patch("app.modules.applications.service.create_application", new_callable=AsyncMock)
    async def test_create_success(self, mock_create, mock_config):
        """Creation de candidature retourne la confirmation."""
        application = MagicMock()
        application.id = uuid.uuid4()
        application.status = "draft"
        mock_create.return_value = application

        result = await create_fund_application.ainvoke(
            {"fund_id": str(uuid.uuid4())},
            config=mock_config,
        )

        assert "cre" in result.lower() or str(application.id) in result
        mock_create.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(
        "app.modules.applications.service.create_application",
        new_callable=AsyncMock,
        side_effect=Exception("Fund not found"),
    )
    async def test_create_handles_error(self, mock_create, mock_config):
        """Erreur retourne un message lisible."""
        result = await create_fund_application.ainvoke(
            {"fund_id": str(uuid.uuid4())},
            config=mock_config,
        )

        assert "Erreur" in result


class TestFinancingToolsExport:
    """Tests pour l'export du module."""

    def test_tools_list_count(self):
        """FINANCING_TOOLS contient 6 tools (F15 BUG-003 : create_fund_application
        retiré du module financing au profit de application_tools)."""
        assert len(FINANCING_TOOLS) == 6

    def test_tool_names(self):
        """Les tools ont les bons noms (sans create_fund_application — F15 BUG-003)."""
        names = {t.name for t in FINANCING_TOOLS}
        assert names == {
            "search_compatible_funds",
            "save_fund_interest",
            "get_fund_details",
            # F07
            "list_offers",
            "get_offer",
            "compare_offers_for_fund",
        }

    def test_tools_have_french_descriptions(self):
        """Les descriptions des tools sont en francais."""
        for t in FINANCING_TOOLS:
            assert any(
                word in t.description.lower()
                for word in [
                    "financement", "fonds", "candidature", "rechercher",
                    "interet", "detail", "offre", "offres", "récupère",
                    "compare", "publi",
                ]
            ), f"Description manque de termes francais : {t.description}"
