"""F21 — Tests unitaires des équivalences pédagogiques carbone."""

import uuid
from decimal import Decimal

import pytest

from app.modules.reports.carbon.equivalences import (
    Equivalence,
    compute_equivalences,
)


class TestComputeEquivalences:
    """compute_equivalences()."""

    def test_returns_four_equivalences(self) -> None:
        result = compute_equivalences(10.0)
        assert len(result) == 4

    def test_zero_tco2e_returns_zeros(self) -> None:
        result = compute_equivalences(0)
        assert all(eq.value == 0 for eq in result)

    def test_decimal_input_supported(self) -> None:
        result = compute_equivalences(Decimal("5.5"))
        assert len(result) == 4
        assert all(isinstance(eq.value, float) for eq in result)

    def test_negative_input_treated_as_zero(self) -> None:
        # Sécurité : valeur négative ne lève pas mais produit un nombre.
        result = compute_equivalences(0.0)
        assert all(eq.value == 0 for eq in result)

    def test_unsourced_by_default(self) -> None:
        result = compute_equivalences(10.0)
        for eq in result:
            assert eq.is_sourced is False
            assert eq.source_id is None
            assert eq.fallback_label == "Recommandation générale (non sourcée)"

    def test_sourced_when_source_id_provided(self) -> None:
        sid = uuid.uuid4()
        result = compute_equivalences(10.0, sources={"km_voiture": sid})
        km = next(eq for eq in result if "voiture" in eq.label.lower())
        assert km.is_sourced is True
        assert km.source_id == sid
        assert km.fallback_label is None
        # Les autres restent non sourcées.
        others = [eq for eq in result if eq is not km]
        assert all(o.is_sourced is False for o in others)

    def test_km_voiture_proportional(self) -> None:
        result = compute_equivalences(10.0)
        km = next(eq for eq in result if "voiture" in eq.label.lower())
        assert km.value == pytest.approx(57000.0, rel=0.01)
        assert km.unit == "km"

    def test_immutability_dataclass(self) -> None:
        result = compute_equivalences(1.0)
        with pytest.raises(Exception):
            result[0].value = 999  # frozen dataclass
