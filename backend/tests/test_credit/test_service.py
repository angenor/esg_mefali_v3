"""Tests du service de scoring de credit vert."""

import uuid

import pytest

from app.modules.credit.service import (
    _clamp,
    calculate_combined_score,
    calculate_confidence,
    calculate_engagement_score,
    calculate_green_impact_score,
    calculate_solvability_score,
    generate_recommendations,
)


# --- Tests algorithme solvabilite (T007) ---


class TestSolvabilityScore:
    """Tests du calcul du score de solvabilite."""

    def test_all_factors_max(self):
        """T007-01 : Tous les facteurs a 100 → score 100."""
        data = {
            "activity_regularity": {"score": 100, "details": "test"},
            "information_coherence": {"score": 100, "details": "test"},
            "governance": {"score": 100, "details": "test"},
            "financial_transparency": {"score": 100, "details": "test"},
            "engagement_seriousness": {"score": 100, "details": "test"},
        }
        score, factors = calculate_solvability_score(data)
        assert score == 100.0
        assert len(factors) == 5

    def test_all_factors_zero(self):
        """T007-02 : Tous les facteurs a 0 → score 0."""
        data = {
            "activity_regularity": {"score": 0, "details": "test"},
            "information_coherence": {"score": 0, "details": "test"},
            "governance": {"score": 0, "details": "test"},
            "financial_transparency": {"score": 0, "details": "test"},
            "engagement_seriousness": {"score": 0, "details": "test"},
        }
        score, factors = calculate_solvability_score(data)
        assert score == 0.0

    def test_weighted_calculation(self):
        """T007-03 : Ponderation correcte (chaque facteur 20%)."""
        data = {
            "activity_regularity": {"score": 50, "details": "test"},
            "information_coherence": {"score": 50, "details": "test"},
            "governance": {"score": 50, "details": "test"},
            "financial_transparency": {"score": 50, "details": "test"},
            "engagement_seriousness": {"score": 50, "details": "test"},
        }
        score, _ = calculate_solvability_score(data)
        assert score == 50.0

    def test_missing_factors_default_zero(self):
        """T007-04 : Facteurs manquants → score 0 pour ces facteurs."""
        data = {
            "activity_regularity": {"score": 100, "details": "test"},
        }
        score, factors = calculate_solvability_score(data)
        assert score == 20.0  # 100 * 0.20 = 20
        assert factors["information_coherence"]["score"] == 0

    def test_intermediary_interactions_preserved(self):
        """T007-05 : Les interactions intermediaires sont dans le breakdown."""
        data = {
            "activity_regularity": {"score": 70, "details": "test"},
            "information_coherence": {"score": 60, "details": "test"},
            "governance": {"score": 55, "details": "test"},
            "financial_transparency": {"score": 75, "details": "test"},
            "engagement_seriousness": {
                "score": 80,
                "details": "test",
                "intermediary_interactions": {
                    "contacted": 2,
                    "appointments": 1,
                    "submitted": 1,
                    "intermediary_names": ["SUNREF BOAD"],
                },
            },
        }
        _, factors = calculate_solvability_score(data)
        assert "intermediary_interactions" in factors["engagement_seriousness"]
        assert factors["engagement_seriousness"]["intermediary_interactions"]["contacted"] == 2


class TestGreenImpactScore:
    """Tests du calcul du score d'impact vert."""

    def test_all_factors_max(self):
        """T007-06 : Tous les facteurs impact vert a 100."""
        data = {
            "esg_global_score": {"score": 100, "details": "test"},
            "esg_trend": {"score": 100, "details": "test"},
            "carbon_engagement": {"score": 100, "details": "test"},
            "green_projects": {"score": 100, "details": "test"},
        }
        score, factors = calculate_green_impact_score(data)
        assert score == 100.0
        assert len(factors) == 4

    def test_weighted_esg_dominant(self):
        """T007-07 : ESG global pese 40%, les autres 20%."""
        data = {
            "esg_global_score": {"score": 100, "details": "test"},
            "esg_trend": {"score": 0, "details": "test"},
            "carbon_engagement": {"score": 0, "details": "test"},
            "green_projects": {"score": 0, "details": "test"},
        }
        score, _ = calculate_green_impact_score(data)
        assert score == 40.0

    def test_application_statuses_preserved(self):
        """T007-08 : Les statuts candidatures sont dans le breakdown."""
        data = {
            "esg_global_score": {"score": 72, "details": "test"},
            "esg_trend": {"score": 60, "details": "test"},
            "carbon_engagement": {"score": 80, "details": "test"},
            "green_projects": {
                "score": 70,
                "details": "test",
                "application_statuses": {
                    "interested": 1,
                    "submitted_via_intermediary": 2,
                    "accepted": 0,
                },
            },
        }
        _, factors = calculate_green_impact_score(data)
        assert "application_statuses" in factors["green_projects"]


class TestCombinedScore:
    """Tests du calcul du score combine."""

    def test_equal_scores_full_confidence(self):
        """T007-09 : Scores egaux avec confiance 1.0."""
        score = calculate_combined_score(80.0, 80.0, 1.0)
        assert score == 80.0

    def test_confidence_reduces_score(self):
        """T007-10 : La confiance reduit le score proportionnellement."""
        score = calculate_combined_score(80.0, 80.0, 0.5)
        assert score == 40.0

    def test_different_axes(self):
        """T007-11 : Poids 50/50 entre solvabilite et impact vert."""
        score = calculate_combined_score(100.0, 0.0, 1.0)
        assert score == 50.0

    def test_clamped_to_100(self):
        """T007-12 : Score borne a 100 maximum."""
        score = calculate_combined_score(100.0, 100.0, 1.0)
        assert score <= 100.0


class TestConfidence:
    """Tests du calcul de confiance."""

    def test_no_sources(self):
        """T007-13 : Aucune source → confiance minimale 0.5."""
        confidence, label = calculate_confidence({})
        assert confidence == 0.5
        assert label == "very_low"

    def test_all_sources_available(self):
        """T007-14 : Toutes les sources disponibles → confiance elevee."""
        sources = {
            name: {"available": True, "completeness": 1.0, "last_updated": "2026-03-31"}
            for name in [
                "Profil entreprise",
                "Evaluation ESG",
                "Bilan carbone",
                "Documents fournis",
                "Candidatures fonds",
                "Interactions intermediaires",
            ]
        }
        confidence, label = calculate_confidence(sources)
        assert confidence >= 0.8
        assert label in ("good", "excellent")

    def test_confidence_between_bounds(self):
        """T007-15 : Confiance toujours entre 0.5 et 1.0."""
        confidence, _ = calculate_confidence({"test": {"available": True}})
        assert 0.5 <= confidence <= 1.0

    def test_confidence_labels_correct(self):
        """T007-16 : Labels de confiance corrects selon les seuils."""
        # Tres faible
        c1, l1 = calculate_confidence({})
        assert l1 == "very_low"

        # Avec quelques sources
        partial = {
            "Profil entreprise": {"available": True, "completeness": 0.5},
            "Evaluation ESG": {"available": True, "completeness": 0.8},
        }
        c2, l2 = calculate_confidence(partial)
        assert c2 > c1


class TestEngagementScore:
    """Tests du calcul du score d'engagement intermediaire."""

    def test_no_interactions(self):
        """T007-17 : Aucune interaction → score 0."""
        score, details = calculate_engagement_score({
            "contacted": 0,
            "appointments": 0,
            "submitted": 0,
            "accepted": 0,
            "intermediary_names": [],
        })
        assert score == 0

    def test_one_contact(self):
        """T007-18 : Un intermediaire contacte → +15 points."""
        score, _ = calculate_engagement_score({
            "contacted": 1,
            "appointments": 0,
            "submitted": 0,
            "accepted": 0,
            "intermediary_names": ["SUNREF BOAD"],
        })
        assert score == 15

    def test_full_engagement(self):
        """T007-19 : Engagement complet → score eleve."""
        score, _ = calculate_engagement_score({
            "contacted": 2,
            "appointments": 1,
            "submitted": 1,
            "accepted": 1,
            "intermediary_names": ["SUNREF BOAD", "FDE BNDA"],
        })
        # 2*15 + 1*20 + 1*30 + 1*20 = 100
        assert score == 100

    def test_contacts_capped_at_two(self):
        """T007-20 : Contacts plafonnes a 2 (max 30 points)."""
        score, _ = calculate_engagement_score({
            "contacted": 5,
            "appointments": 0,
            "submitted": 0,
            "accepted": 0,
            "intermediary_names": [],
        })
        assert score == 30  # 2 * 15


class TestRecommendations:
    """Tests de la generation de recommandations."""

    def test_low_score_generates_recommendations(self):
        """T007-21 : Scores bas → recommandations high."""
        solv = {
            "activity_regularity": {"score": 30, "weight": 0.2, "details": "test"},
            "information_coherence": {"score": 80, "weight": 0.2, "details": "test"},
            "governance": {"score": 80, "weight": 0.2, "details": "test"},
            "financial_transparency": {"score": 80, "weight": 0.2, "details": "test"},
            "engagement_seriousness": {"score": 80, "weight": 0.2, "details": "test"},
        }
        green = {
            "esg_global_score": {"score": 90, "weight": 0.4, "details": "test"},
            "esg_trend": {"score": 90, "weight": 0.2, "details": "test"},
            "carbon_engagement": {"score": 90, "weight": 0.2, "details": "test"},
            "green_projects": {"score": 90, "weight": 0.2, "details": "test"},
        }
        recs = generate_recommendations(solv, green, {})
        assert len(recs) > 0
        assert recs[0]["impact"] == "high"

    def test_high_scores_no_recommendations(self):
        """T007-22 : Scores eleves → pas de recommandations facteurs."""
        solv = {k: {"score": 90, "weight": 0.2, "details": "ok"} for k in [
            "activity_regularity", "information_coherence", "governance",
            "financial_transparency", "engagement_seriousness",
        ]}
        green = {k: {"score": 90, "weight": v, "details": "ok"} for k, v in {
            "esg_global_score": 0.4, "esg_trend": 0.2,
            "carbon_engagement": 0.2, "green_projects": 0.2,
        }.items()}
        recs = generate_recommendations(solv, green, {
            name: {"available": True} for name in [
                "Profil entreprise", "Evaluation ESG", "Bilan carbone",
                "Documents fournis", "Candidatures fonds", "Interactions intermediaires",
            ]
        })
        # Pas de recommandations de facteurs (tout > 70)
        factor_recs = [r for r in recs if r["category"] in ("solvability", "green_impact")]
        assert len(factor_recs) == 0

    def test_no_intermediary_generates_suggestion(self):
        """T007-23 : Aucune interaction intermediaire → suggestion contact."""
        solv = {k: {"score": 80, "weight": 0.2, "details": "ok"} for k in [
            "activity_regularity", "information_coherence", "governance",
            "financial_transparency", "engagement_seriousness",
        ]}
        green = {k: {"score": 80, "weight": v, "details": "ok"} for k, v in {
            "esg_global_score": 0.4, "esg_trend": 0.2,
            "carbon_engagement": 0.2, "green_projects": 0.2,
        }.items()}
        recs = generate_recommendations(
            solv, green, {}, {"contacted": 0, "submitted": 0}
        )
        engagement_recs = [r for r in recs if r["category"] == "engagement"]
        assert len(engagement_recs) == 1

    def test_sorted_by_impact(self):
        """T007-24 : Recommandations triees par impact decroissant."""
        solv = {
            "activity_regularity": {"score": 30, "weight": 0.2, "details": "test"},
            "information_coherence": {"score": 60, "weight": 0.2, "details": "test"},
            "governance": {"score": 80, "weight": 0.2, "details": "test"},
            "financial_transparency": {"score": 80, "weight": 0.2, "details": "test"},
            "engagement_seriousness": {"score": 80, "weight": 0.2, "details": "test"},
        }
        green = {k: {"score": 80, "weight": v, "details": "ok"} for k, v in {
            "esg_global_score": 0.4, "esg_trend": 0.2,
            "carbon_engagement": 0.2, "green_projects": 0.2,
        }.items()}
        recs = generate_recommendations(solv, green, {})
        if len(recs) >= 2:
            priorities = {"high": 0, "medium": 1, "low": 2}
            for i in range(len(recs) - 1):
                assert priorities[recs[i]["impact"]] <= priorities[recs[i + 1]["impact"]]


class TestIntegrationScoring:
    """Tests d'integration du flux complet de scoring (T013-T015)."""

    def test_full_scoring_with_complete_data(self):
        """T013 : Generer un score avec donnees completes → scores eleves."""
        solvability_data = {
            "activity_regularity": {"score": 80, "details": "12 mois d'activite"},
            "information_coherence": {"score": 75, "details": "7/7 champs"},
            "governance": {"score": 70, "details": "Structure partielle"},
            "financial_transparency": {"score": 85, "details": "5 documents"},
            "engagement_seriousness": {
                "score": 65,
                "details": "2 intermediaires contactes",
                "intermediary_interactions": {
                    "contacted": 2,
                    "appointments": 1,
                    "submitted": 1,
                    "intermediary_names": ["SUNREF BOAD", "FDE BNDA"],
                },
            },
        }
        green_data = {
            "esg_global_score": {"score": 72, "details": "Score ESG 72/100"},
            "esg_trend": {"score": 60, "details": "Amelioration de +12 points"},
            "carbon_engagement": {"score": 80, "details": "Bilan carbone realise"},
            "green_projects": {
                "score": 70,
                "details": "2 candidatures",
                "application_statuses": {
                    "interested": 1,
                    "submitted_via_intermediary": 2,
                    "accepted": 0,
                },
            },
        }
        source_coverage = {
            name: {"available": True, "completeness": 0.8, "last_updated": "2026-03-15"}
            for name in [
                "Profil entreprise", "Evaluation ESG", "Bilan carbone",
                "Documents fournis", "Candidatures fonds", "Interactions intermediaires",
            ]
        }

        solv_score, solv_factors = calculate_solvability_score(solvability_data)
        green_score, green_factors = calculate_green_impact_score(green_data)
        confidence, conf_label = calculate_confidence(source_coverage)
        combined = calculate_combined_score(solv_score, green_score, confidence)

        assert 0 < solv_score <= 100
        assert 0 < green_score <= 100
        assert 0.5 <= confidence <= 1.0
        assert 0 < combined <= 100
        assert conf_label in ("good", "excellent")

    def test_scoring_with_partial_data(self):
        """T014 : Donnees partielles → confiance faible."""
        solvability_data = {
            "activity_regularity": {"score": 50, "details": "Profil partiel"},
        }
        green_data = {
            "esg_global_score": {"score": 60, "details": "Score ESG basic"},
        }
        source_coverage = {
            "Profil entreprise": {"available": True, "completeness": 0.3},
            "Evaluation ESG": {"available": True, "completeness": 0.5},
        }

        _, _ = calculate_solvability_score(solvability_data)
        _, _ = calculate_green_impact_score(green_data)
        confidence, conf_label = calculate_confidence(source_coverage)

        # Confiance faible car seulement 2/6 sources
        assert confidence < 0.8
        assert conf_label in ("very_low", "low", "medium")

    def test_intermediary_boost_engagement(self):
        """T015 : Un utilisateur avec intermediaires a un meilleur score engagement."""
        # Sans intermediaires
        data_no_inter = {
            "activity_regularity": {"score": 70, "details": "test"},
            "information_coherence": {"score": 70, "details": "test"},
            "governance": {"score": 70, "details": "test"},
            "financial_transparency": {"score": 70, "details": "test"},
            "engagement_seriousness": {"score": 0, "details": "Aucune interaction"},
        }
        score_no_inter, _ = calculate_solvability_score(data_no_inter)

        # Avec intermediaires
        data_with_inter = {
            "activity_regularity": {"score": 70, "details": "test"},
            "information_coherence": {"score": 70, "details": "test"},
            "governance": {"score": 70, "details": "test"},
            "financial_transparency": {"score": 70, "details": "test"},
            "engagement_seriousness": {"score": 65, "details": "2 intermediaires contactes"},
        }
        score_with_inter, _ = calculate_solvability_score(data_with_inter)

        assert score_with_inter > score_no_inter


class TestBuildEngagementDetails:
    """Tests de la fonction _build_engagement_details."""

    def test_no_interactions(self):
        """Aucune interaction → message par defaut."""
        from app.modules.credit.service import _build_engagement_details

        result = _build_engagement_details({
            "contacted": 0,
            "appointments": 0,
            "submitted": 0,
            "accepted": 0,
        })
        assert result == "Aucune interaction avec les intermediaires"

    def test_full_interactions(self):
        """Interactions completes → description detaillee."""
        from app.modules.credit.service import _build_engagement_details

        result = _build_engagement_details({
            "contacted": 2,
            "appointments": 1,
            "submitted": 1,
            "accepted": 1,
        })
        assert "2 intermediaire(s) contacte(s)" in result
        assert "1 rendez-vous" in result
        assert "1 dossier(s) soumis" in result
        assert "1 accepte(s)" in result

    def test_partial_interactions(self):
        """Interactions partielles → description partielle."""
        from app.modules.credit.service import _build_engagement_details

        result = _build_engagement_details({
            "contacted": 1,
            "appointments": 0,
            "submitted": 0,
            "accepted": 0,
        })
        assert "1 intermediaire(s) contacte(s)" in result
        assert "rendez-vous" not in result


class TestAsyncGetLatestScore:
    """Tests de get_latest_score."""

    @pytest.mark.asyncio
    async def test_returns_none_when_empty(self):
        """Aucun score → None."""
        from unittest.mock import AsyncMock, MagicMock

        from app.modules.credit.service import get_latest_score

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await get_latest_score(mock_db, uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_score(self):
        """Score existant → retourne le score."""
        from unittest.mock import AsyncMock, MagicMock

        from app.modules.credit.service import get_latest_score

        mock_db = AsyncMock()
        mock_score = MagicMock()
        mock_score.combined_score = 75.0
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_score
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await get_latest_score(mock_db, uuid.uuid4())
        assert result is not None
        assert result.combined_score == 75.0


class TestAsyncGetNextVersion:
    """Tests de get_next_version."""

    @pytest.mark.asyncio
    async def test_first_version(self):
        """Aucun score existant → version 1."""
        from unittest.mock import AsyncMock, MagicMock

        from app.modules.credit.service import get_next_version

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        version = await get_next_version(mock_db, uuid.uuid4())
        assert version == 1

    @pytest.mark.asyncio
    async def test_increments_version(self):
        """Version existante → incremente de 1."""
        from unittest.mock import AsyncMock, MagicMock

        from app.modules.credit.service import get_next_version

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 3
        mock_db.execute = AsyncMock(return_value=mock_result)

        version = await get_next_version(mock_db, uuid.uuid4())
        assert version == 4


class TestAsyncGetScoreHistory:
    """Tests de get_score_history."""

    @pytest.mark.asyncio
    async def test_empty_history(self):
        """Historique vide → liste vide et total 0."""
        from unittest.mock import AsyncMock, MagicMock

        from app.modules.credit.service import get_score_history

        mock_db = AsyncMock()

        # Premier appel pour count, deuxieme pour resultats
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_scores_result = MagicMock()
        mock_scores_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_scores_result])

        scores, total = await get_score_history(mock_db, uuid.uuid4())
        assert total == 0
        assert scores == []

    @pytest.mark.asyncio
    async def test_history_with_scores(self):
        """Historique avec scores → liste et total corrects."""
        from unittest.mock import AsyncMock, MagicMock

        from app.modules.credit.service import get_score_history

        mock_db = AsyncMock()
        mock_score1 = MagicMock(combined_score=80.0)
        mock_score2 = MagicMock(combined_score=75.0)

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2
        mock_scores_result = MagicMock()
        mock_scores_result.scalars.return_value.all.return_value = [mock_score1, mock_score2]

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_scores_result])

        scores, total = await get_score_history(mock_db, uuid.uuid4())
        assert total == 2
        assert len(scores) == 2


class TestAsyncIsGenerationInProgress:
    """Tests de is_generation_in_progress."""

    @pytest.mark.asyncio
    async def test_no_generation_in_progress(self):
        """Aucune generation en cours → False."""
        from unittest.mock import AsyncMock, MagicMock

        from app.modules.credit.service import is_generation_in_progress

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await is_generation_in_progress(mock_db, uuid.uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_generation_in_progress(self):
        """Generation en cours → True."""
        from unittest.mock import AsyncMock, MagicMock

        from app.modules.credit.service import is_generation_in_progress

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await is_generation_in_progress(mock_db, uuid.uuid4())
        assert result is True


class TestAsyncGenerateCreditScore:
    """Tests de generate_credit_score."""

    @pytest.mark.asyncio
    async def test_raises_if_generation_in_progress(self):
        """Leve ValueError si generation en cours."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from app.modules.credit.service import generate_credit_score

        mock_db = AsyncMock()
        user_id = uuid.uuid4()

        with patch(
            "app.modules.credit.service.is_generation_in_progress",
            new_callable=AsyncMock,
            return_value=True,
        ):
            with pytest.raises(ValueError, match="deja en cours"):
                await generate_credit_score(mock_db, user_id)

    @pytest.mark.asyncio
    async def test_generates_score_successfully(self):
        """Generation complete retourne un CreditScore."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from app.modules.credit.service import generate_credit_score

        mock_db = AsyncMock()
        user_id = uuid.uuid4()
        account_id = uuid.uuid4()

        # Mock les dependances
        empty_points = {
            k: {"score": 50, "details": "test"}
            for k in ["activity_regularity", "information_coherence",
                       "governance", "financial_transparency",
                       "engagement_seriousness"]
        }
        empty_green = {
            k: {"score": 60, "details": "test"}
            for k in ["esg_global_score", "esg_trend",
                       "carbon_engagement", "green_projects"]
        }
        source_cov = {
            "Profil entreprise": {"available": True, "completeness": 0.5},
        }

        with patch(
            "app.modules.credit.service.is_generation_in_progress",
            new_callable=AsyncMock,
            return_value=False,
        ), patch(
            "app.modules.credit.service.collect_data_points",
            new_callable=AsyncMock,
            return_value=(empty_points, empty_green, source_cov, {"contacted": 0}),
        ), patch(
            "app.modules.credit.service.get_next_version",
            new_callable=AsyncMock,
            return_value=1,
        ):
            result = await generate_credit_score(mock_db, user_id, account_id=account_id)

            # Verifie que l'objet CreditScore a ete cree
            assert result.combined_score > 0
            assert result.version == 1
            assert result.user_id == user_id
            # F02 — account_id propage pour satisfaire la RLS
            assert result.account_id == account_id
            mock_db.add.assert_called_once()
            mock_db.flush.assert_awaited_once()


class TestAsyncCollectDataPoints:
    """Tests de collect_data_points."""

    @pytest.mark.asyncio
    async def test_collect_with_no_data(self):
        """Aucune donnee en BDD → facteurs par defaut a 0."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from app.modules.credit.service import collect_data_points

        mock_db = AsyncMock()
        user_id = uuid.uuid4()

        # Chaque query retourne None/0 (pas de profil, pas d'ESG, etc.)
        mock_empty_result = MagicMock()
        mock_empty_result.scalar_one_or_none.return_value = None
        mock_empty_result.scalar.return_value = 0
        mock_empty_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_empty_result)

        solv, green, coverage, interactions = await collect_data_points(mock_db, user_id)

        # Tous les facteurs doivent etre remplis (valeurs par defaut)
        assert "activity_regularity" in solv
        assert "esg_global_score" in green
        assert coverage.get("Profil entreprise", {}).get("available") is False

    @pytest.mark.asyncio
    async def test_collect_with_profile(self):
        """Profil entreprise present → facteurs solvabilite renseignes."""
        from unittest.mock import AsyncMock, MagicMock

        from app.modules.credit.service import collect_data_points

        mock_db = AsyncMock()
        user_id = uuid.uuid4()

        # Creer un mock profil avec des champs remplis
        mock_profile = MagicMock()
        mock_profile.company_name = "EcoVert SA"
        mock_profile.sector = "agriculture"
        mock_profile.city = "Abidjan"
        mock_profile.employee_count = 25
        mock_profile.annual_revenue_xof = 50_000_000
        mock_profile.governance_structure = "SA"
        mock_profile.year_founded = 2018
        mock_profile.updated_at = None

        # Resultat pour profil (1er appel)
        mock_profile_result = MagicMock()
        mock_profile_result.scalar_one_or_none.return_value = mock_profile

        # Resultats vides pour les autres queries
        mock_empty_result = MagicMock()
        mock_empty_result.scalar_one_or_none.return_value = None
        mock_empty_result.scalar.return_value = 0
        mock_empty_result.scalars.return_value.all.return_value = []

        # Sequencer les retours : profil, puis ESG, puis carbone, documents, candidatures
        mock_db.execute = AsyncMock(side_effect=[
            mock_profile_result,  # CompanyProfile
            mock_empty_result,    # ESGAssessment (latest)
            mock_empty_result,    # CarbonAssessment
            mock_empty_result,    # Document count
            mock_empty_result,    # FundMatch
        ])

        solv, green, coverage, interactions = await collect_data_points(mock_db, user_id)

        # Le profil est complet (7/7 champs) → score activity_regularity = 100
        assert solv["activity_regularity"]["score"] == 100.0
        assert coverage["Profil entreprise"]["available"] is True

    @pytest.mark.asyncio
    async def test_collect_with_esg(self):
        """Evaluation ESG presente → facteurs impact vert renseignes."""
        from unittest.mock import AsyncMock, MagicMock

        from app.modules.credit.service import collect_data_points

        mock_db = AsyncMock()
        user_id = uuid.uuid4()

        # Profil vide
        mock_empty_result = MagicMock()
        mock_empty_result.scalar_one_or_none.return_value = None
        mock_empty_result.scalar.return_value = 0
        mock_empty_result.scalars.return_value.all.return_value = []

        # ESG avec score
        mock_esg = MagicMock()
        mock_esg.overall_score = 72
        mock_esg.created_at = MagicMock()
        mock_esg.created_at.isoformat.return_value = "2026-03-20T10:00:00+00:00"

        mock_esg_result = MagicMock()
        mock_esg_result.scalar_one_or_none.return_value = mock_esg

        # Pas de prev ESG
        mock_no_prev = MagicMock()
        mock_no_prev.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(side_effect=[
            mock_empty_result,    # CompanyProfile
            mock_esg_result,      # ESGAssessment (latest)
            mock_no_prev,         # ESGAssessment (previous)
            mock_empty_result,    # CarbonAssessment
            mock_empty_result,    # Document count
            mock_empty_result,    # FundMatch
        ])

        solv, green, coverage, interactions = await collect_data_points(mock_db, user_id)

        assert green["esg_global_score"]["score"] == 72
        assert green["esg_trend"]["score"] == 50  # Premiere evaluation
        assert coverage["Evaluation ESG"]["available"] is True

    @pytest.mark.asyncio
    async def test_collect_with_documents(self):
        """Documents fournis → facteur financial_transparency renseigne."""
        from unittest.mock import AsyncMock, MagicMock

        from app.modules.credit.service import collect_data_points

        mock_db = AsyncMock()
        user_id = uuid.uuid4()

        mock_empty = MagicMock()
        mock_empty.scalar_one_or_none.return_value = None
        mock_empty.scalar.return_value = 0
        mock_empty.scalars.return_value.all.return_value = []

        # 3 documents
        mock_doc_result = MagicMock()
        mock_doc_result.scalar.return_value = 3

        mock_db.execute = AsyncMock(side_effect=[
            mock_empty,       # CompanyProfile
            mock_empty,       # ESGAssessment
            mock_empty,       # CarbonAssessment
            mock_doc_result,  # Document count = 3
            mock_empty,       # FundMatch
        ])

        solv, green, coverage, interactions = await collect_data_points(mock_db, user_id)

        assert solv["financial_transparency"]["score"] == 60.0  # 3/5 * 100 = 60
        assert coverage["Documents fournis"]["available"] is True

    @pytest.mark.asyncio
    async def test_collect_with_carbon(self):
        """Bilan carbone present → facteur carbon_engagement renseigne."""
        from unittest.mock import AsyncMock, MagicMock

        from app.modules.credit.service import collect_data_points

        mock_db = AsyncMock()
        user_id = uuid.uuid4()

        mock_empty = MagicMock()
        mock_empty.scalar_one_or_none.return_value = None
        mock_empty.scalar.return_value = 0
        mock_empty.scalars.return_value.all.return_value = []

        # Bilan carbone avec plan de reduction
        mock_carbon = MagicMock()
        mock_carbon.reduction_plan = {"actions": ["reduire transport"]}
        mock_carbon.created_at = MagicMock()
        mock_carbon.created_at.isoformat.return_value = "2026-02-15T10:00:00+00:00"

        mock_carbon_result = MagicMock()
        mock_carbon_result.scalar_one_or_none.return_value = mock_carbon

        mock_db.execute = AsyncMock(side_effect=[
            mock_empty,          # CompanyProfile
            mock_empty,          # ESGAssessment
            mock_carbon_result,  # CarbonAssessment
            mock_empty,          # Document count
            mock_empty,          # FundMatch
        ])

        solv, green, coverage, interactions = await collect_data_points(mock_db, user_id)

        assert green["carbon_engagement"]["score"] == 85
        assert "plan de reduction actif" in green["carbon_engagement"]["details"]
        assert coverage["Bilan carbone"]["available"] is True

    @pytest.mark.asyncio
    async def test_collect_handles_import_errors(self):
        """Erreurs d'import de modeles → facteurs par defaut gracieux."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from app.modules.credit.service import collect_data_points

        mock_db = AsyncMock()
        user_id = uuid.uuid4()

        # Simuler une erreur sur chaque execute
        mock_db.execute = AsyncMock(side_effect=Exception("Module not found"))

        solv, green, coverage, interactions = await collect_data_points(mock_db, user_id)

        # Les facteurs par defaut doivent etre remplis
        assert "activity_regularity" in solv
        assert solv["activity_regularity"]["score"] == 0
        assert "esg_global_score" in green


class TestHelpers:
    """Tests des fonctions utilitaires."""

    def test_clamp_within_range(self):
        """Valeurs dans la plage ne changent pas."""
        assert _clamp(50) == 50

    def test_clamp_below_min(self):
        """Valeurs sous le minimum sont bornees."""
        assert _clamp(-10) == 0.0

    def test_clamp_above_max(self):
        """Valeurs au-dessus du maximum sont bornees."""
        assert _clamp(150) == 100.0
