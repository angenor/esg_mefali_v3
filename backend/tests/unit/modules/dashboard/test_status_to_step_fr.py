"""F21 — Tests unitaires du mapping statut → libellé d'étape français."""

import pytest

from app.modules.dashboard.service import _status_to_step_fr


class TestStatusToStepFr:
    """Mapping `_status_to_step_fr`."""

    @pytest.mark.parametrize(
        "status,expected",
        [
            ("draft", "Brouillon"),
            ("preparing_documents", "Préparation des documents"),
            ("in_progress", "Rédaction en cours"),
            ("review", "Relecture interne"),
            ("ready_for_intermediary", "Prêt à soumettre à l'intermédiaire"),
            ("ready_for_fund", "Prêt à soumettre au fonds"),
            ("submitted_to_fund", "Dossier déposé auprès du fonds"),
            ("under_review", "En cours d'évaluation"),
            ("accepted", "Accepté"),
            ("rejected", "Rejeté"),
        ],
    )
    def test_known_statuses(self, status: str, expected: str) -> None:
        assert _status_to_step_fr(status) == expected

    def test_submitted_to_intermediary_with_name(self) -> None:
        result = _status_to_step_fr("submitted_to_intermediary", intermediary_name="BOAD")
        assert result == "Instruction par BOAD"

    def test_submitted_to_intermediary_without_name(self) -> None:
        result = _status_to_step_fr("submitted_to_intermediary")
        # Fallback : libellé générique sans suffixe.
        assert "Instruction" in result

    def test_unknown_status_passes_through(self) -> None:
        assert _status_to_step_fr("xyz_unknown") == "xyz_unknown"
