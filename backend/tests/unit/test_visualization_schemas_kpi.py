"""F11 — Tests Pydantic stricts pour KPICardArgs.

TDD strict : ces tests doivent FAIL initialement (avant T010).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.money import Money
from app.schemas.visualization import KPICardArgs


class TestKPICardArgsValidation:
    """Validation des champs et bornes Pydantic."""

    def test_valid_minimal(self) -> None:
        """KPICardArgs avec champs minimaux requis."""
        args = KPICardArgs(title="Empreinte carbone 2026", value="45 tCO2e")
        assert args.title == "Empreinte carbone 2026"
        assert args.value == "45 tCO2e"
        assert args.color == "emerald"  # défaut
        assert args.delta is None
        assert args.source_id is None

    def test_valid_full(self) -> None:
        """KPICardArgs avec tous les champs."""
        sid = uuid.uuid4()
        args = KPICardArgs(
            title="Empreinte carbone 2026",
            value="45 tCO2e",
            value_money=Money(amount=Decimal("655957"), currency="XOF"),
            delta=-12.0,
            delta_label="vs 2024",
            delta_direction="down",
            delta_is_good=True,
            icon="chart-bar",
            color="emerald",
            source_id=sid,
            drilldown_url="/carbon/results",
        )
        assert args.delta == -12.0
        assert args.delta_direction == "down"
        assert args.delta_is_good is True
        assert args.source_id == sid
        assert args.value_money.currency == "XOF"

    def test_extra_field_forbidden(self) -> None:
        """extra="forbid" rejette les champs inconnus (anti-hallucination LLM)."""
        with pytest.raises(ValidationError):
            KPICardArgs(  # type: ignore[call-arg]
                title="X",
                value="1",
                hallucinated_field="boom",
            )

    def test_title_min_length(self) -> None:
        """title vide rejeté (min_length=1)."""
        with pytest.raises(ValidationError):
            KPICardArgs(title="", value="1")

    def test_title_max_length(self) -> None:
        """title > 120 caractères rejeté."""
        with pytest.raises(ValidationError):
            KPICardArgs(title="X" * 121, value="1")

    def test_value_min_length(self) -> None:
        """value vide rejetée (min_length=1)."""
        with pytest.raises(ValidationError):
            KPICardArgs(title="X", value="")

    def test_value_max_length(self) -> None:
        """value > 60 caractères rejetée."""
        with pytest.raises(ValidationError):
            KPICardArgs(title="X", value="V" * 61)

    def test_color_enum_strict(self) -> None:
        """color non-enum rejetée."""
        with pytest.raises(ValidationError):
            KPICardArgs(title="X", value="1", color="orange")  # type: ignore[arg-type]

    def test_delta_direction_enum_strict(self) -> None:
        """delta_direction hors enum rejeté."""
        with pytest.raises(ValidationError):
            KPICardArgs(  # type: ignore[arg-type]
                title="X", value="1", delta_direction="sideways",
            )

    def test_delta_borne(self) -> None:
        """delta hors bornes ±1e9 rejeté."""
        with pytest.raises(ValidationError):
            KPICardArgs(title="X", value="1", delta=1e10)

    def test_drilldown_url_max_length(self) -> None:
        """drilldown_url > 500 caractères rejetée."""
        with pytest.raises(ValidationError):
            KPICardArgs(title="X", value="1", drilldown_url="/x" + "y" * 500)

    def test_color_default(self) -> None:
        """color non fournie → 'emerald' par défaut."""
        args = KPICardArgs(title="X", value="1")
        assert args.color == "emerald"

    def test_color_all_values(self) -> None:
        """Tous les enums acceptés."""
        for c in ("emerald", "blue", "rose", "amber", "violet"):
            args = KPICardArgs(title="X", value="1", color=c)  # type: ignore[arg-type]
            assert args.color == c
