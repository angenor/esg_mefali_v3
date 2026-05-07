"""Tests unitaires pour les tools credit vert."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.graph.tools.credit_tools import (
    CREDIT_TOOLS,
    generate_credit_certificate,
    generate_credit_score,
    get_credit_score,
)


def _make_credit_score(**overrides):
    """Creer un mock de CreditScore."""
    score = MagicMock()
    defaults = {
        "id": uuid.uuid4(),
        "user_id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
        "combined_score": 72,
        "solvability_score": 68,
        "green_impact_score": 76,
        "risk_level": "moyen",
        "version": 1,
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        setattr(score, key, value)
    return score


class TestGenerateCreditScore:
    """Tests pour generate_credit_score."""

    @pytest.mark.asyncio
    @patch("app.modules.credit.service.generate_credit_score", new_callable=AsyncMock)
    async def test_generate_success(self, mock_generate, mock_config):
        """Generation du score retourne le resultat."""
        score = _make_credit_score()
        mock_generate.return_value = score

        result = await generate_credit_score.ainvoke({}, config=mock_config)

        assert "72" in result
        mock_generate.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(
        "app.modules.credit.service.generate_credit_score",
        new_callable=AsyncMock,
        side_effect=Exception("Insufficient data"),
    )
    async def test_generate_handles_error(self, mock_generate, mock_config):
        """Erreur retourne un message lisible."""
        result = await generate_credit_score.ainvoke({}, config=mock_config)

        assert "Erreur" in result


class TestGetCreditScore:
    """Tests pour get_credit_score."""

    @pytest.mark.asyncio
    @patch("app.modules.credit.service.get_latest_score", new_callable=AsyncMock)
    async def test_score_found(self, mock_get, mock_config):
        """Score existant retourne les details."""
        score = _make_credit_score()
        mock_get.return_value = score

        result = await get_credit_score.ainvoke({}, config=mock_config)

        assert "72" in result
        mock_get.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.modules.credit.service.get_latest_score", new_callable=AsyncMock)
    async def test_no_score(self, mock_get, mock_config):
        """Pas de score retourne un message."""
        mock_get.return_value = None

        result = await get_credit_score.ainvoke({}, config=mock_config)

        assert "Aucun" in result or "aucun" in result

    @pytest.mark.asyncio
    @patch(
        "app.modules.credit.service.get_latest_score",
        new_callable=AsyncMock,
        side_effect=Exception("DB error"),
    )
    async def test_get_handles_error(self, mock_get, mock_config):
        """Erreur retourne un message lisible."""
        result = await get_credit_score.ainvoke({}, config=mock_config)

        assert "Erreur" in result


class TestGenerateCreditCertificate:
    """Tests pour generate_credit_certificate (F08 — refactor → service réel)."""

    @pytest.mark.asyncio
    @patch(
        "app.graph.tools.credit_tools._resolve_account_id",
        new_callable=AsyncMock,
    )
    @patch(
        "app.modules.attestations.service.generate_attestation",
        new_callable=AsyncMock,
    )
    async def test_certificate_success(
        self, mock_generate, mock_resolve_acct, mock_config,
    ):
        """Génération du certificat retourne l'URL de vérification publique."""
        mock_resolve_acct.return_value = uuid.uuid4()
        a = MagicMock()
        a.display_id = "ATT-2026-00042"
        a.verification_url = "https://esg-mefali.com/verify/abc-1234"
        a.pdf_hash_sha256 = "a" * 64
        mock_generate.return_value = a

        result = await generate_credit_certificate.ainvoke({}, config=mock_config)

        assert "ATT-2026-00042" in result
        assert "verify" in result
        assert "vérification" in result.lower() or "verification" in result.lower()
        mock_generate.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(
        "app.graph.tools.credit_tools._resolve_account_id",
        new_callable=AsyncMock,
    )
    async def test_certificate_no_account_returns_error_message(
        self, mock_resolve_acct, mock_config,
    ):
        """Sans account_id, retourne un message d'erreur explicite."""
        mock_resolve_acct.return_value = None

        result = await generate_credit_certificate.ainvoke({}, config=mock_config)

        assert "tenant" in result.lower() or "support" in result.lower()

    @pytest.mark.asyncio
    @patch(
        "app.graph.tools.credit_tools._resolve_account_id",
        new_callable=AsyncMock,
    )
    @patch(
        "app.modules.attestations.service.generate_attestation",
        new_callable=AsyncMock,
    )
    async def test_certificate_no_credit_score_friendly(
        self, mock_generate, mock_resolve_acct, mock_config,
    ):
        """CreditScoreMissingError → message clair en français."""
        from app.modules.attestations.service import CreditScoreMissingError

        mock_resolve_acct.return_value = uuid.uuid4()
        mock_generate.side_effect = CreditScoreMissingError("absent")

        result = await generate_credit_certificate.ainvoke({}, config=mock_config)

        assert "score" in result.lower()
        assert "crédit" in result.lower() or "credit" in result.lower()

    @pytest.mark.asyncio
    @patch(
        "app.graph.tools.credit_tools._resolve_account_id",
        new_callable=AsyncMock,
        side_effect=Exception("DB error"),
    )
    async def test_certificate_handles_error(self, mock_resolve, mock_config):
        """Erreur inattendue retourne un message lisible."""
        result = await generate_credit_certificate.ainvoke({}, config=mock_config)

        assert "Erreur" in result


class TestCreditToolsExport:
    """Tests pour l'export du module."""

    def test_tools_list_count(self):
        """CREDIT_TOOLS contient 3 tools."""
        assert len(CREDIT_TOOLS) == 3

    def test_tool_names(self):
        """Les tools ont les bons noms."""
        names = {t.name for t in CREDIT_TOOLS}
        assert names == {"generate_credit_score", "get_credit_score", "generate_credit_certificate"}

    def test_tools_have_french_descriptions(self):
        """Les descriptions des tools sont en francais."""
        for t in CREDIT_TOOLS:
            assert any(
                word in t.description.lower()
                for word in ["credit", "score", "attestation", "certificat", "calculer", "generer", "consulter"]
            ), f"Description manque de termes francais : {t.description}"
