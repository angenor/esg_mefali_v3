"""F11 — Tests Pydantic stricts pour ComparisonTableArgs et entités imbriquées.

TDD strict : ces tests doivent FAIL initialement (avant T010).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.money import Money
from app.schemas.visualization import (
    ComparisonRow,
    ComparisonSubject,
    ComparisonTableArgs,
    ComparisonValue,
)


def _make_subject(sid: str = "boad", label: str = "GCF via BOAD") -> ComparisonSubject:
    return ComparisonSubject(id=sid, label=label)


def _make_value(subject_id: str, value="100", **kw) -> ComparisonValue:
    return ComparisonValue(subject_id=subject_id, value=value, **kw)


class TestComparisonValueValidation:
    def test_valid_minimal(self) -> None:
        v = ComparisonValue(subject_id="boad", value="500 000 FCFA")
        assert v.subject_id == "boad"
        assert v.source_id is None

    def test_valid_with_money(self) -> None:
        v = ComparisonValue(
            subject_id="boad",
            value="500000",
            money=Money(amount=Decimal("500000"), currency="XOF"),
        )
        assert v.money.currency == "XOF"

    def test_subject_id_min_length(self) -> None:
        with pytest.raises(ValidationError):
            ComparisonValue(subject_id="", value="x")

    def test_subject_id_max_length(self) -> None:
        with pytest.raises(ValidationError):
            ComparisonValue(subject_id="x" * 81, value="x")

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            ComparisonValue(  # type: ignore[call-arg]
                subject_id="boad", value="x", boom="y",
            )

    def test_value_can_be_int(self) -> None:
        v = ComparisonValue(subject_id="boad", value=42)
        assert v.value == 42

    def test_value_can_be_float(self) -> None:
        v = ComparisonValue(subject_id="boad", value=3.14)
        assert v.value == 3.14


class TestComparisonRowValidation:
    def test_valid(self) -> None:
        row = ComparisonRow(
            label="Frais d'instruction",
            type="money",
            values=[
                ComparisonValue(subject_id="a", value="100"),
                ComparisonValue(subject_id="b", value="200"),
            ],
        )
        assert row.higher_is_better is True  # défaut
        assert row.type == "money"

    def test_values_min_length(self) -> None:
        with pytest.raises(ValidationError):
            ComparisonRow(
                label="X",
                type="text",
                values=[ComparisonValue(subject_id="a", value="x")],
            )

    def test_values_max_length(self) -> None:
        values = [ComparisonValue(subject_id=f"s{i}", value=str(i)) for i in range(6)]
        with pytest.raises(ValidationError):
            ComparisonRow(label="X", type="text", values=values)

    def test_type_enum_strict(self) -> None:
        with pytest.raises(ValidationError):
            ComparisonRow(  # type: ignore[arg-type]
                label="X",
                type="not-a-type",
                values=[
                    ComparisonValue(subject_id="a", value="x"),
                    ComparisonValue(subject_id="b", value="y"),
                ],
            )

    def test_label_max_length(self) -> None:
        with pytest.raises(ValidationError):
            ComparisonRow(
                label="X" * 121,
                type="text",
                values=[
                    ComparisonValue(subject_id="a", value="x"),
                    ComparisonValue(subject_id="b", value="y"),
                ],
            )

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            ComparisonRow(  # type: ignore[call-arg]
                label="X",
                type="text",
                values=[
                    ComparisonValue(subject_id="a", value="x"),
                    ComparisonValue(subject_id="b", value="y"),
                ],
                hallu="z",
            )


class TestComparisonSubjectValidation:
    def test_valid(self) -> None:
        s = ComparisonSubject(id="boad", label="GCF via BOAD")
        assert s.sublabel is None

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            ComparisonSubject(id="x", label="X", boom="y")  # type: ignore[call-arg]

    def test_id_max_length(self) -> None:
        with pytest.raises(ValidationError):
            ComparisonSubject(id="x" * 81, label="X")


class TestComparisonTableArgsValidation:
    def _valid_args(self, **overrides):
        base = {
            "title": "Comparaison fonds GCF",
            "subjects": [_make_subject("a", "BOAD"), _make_subject("b", "UNDP")],
            "rows": [
                ComparisonRow(
                    label="Frais",
                    type="money",
                    values=[
                        _make_value("a", "100"),
                        _make_value("b", "200"),
                    ],
                ),
            ],
        }
        base.update(overrides)
        return base

    def test_valid_minimal(self) -> None:
        args = ComparisonTableArgs(**self._valid_args())
        assert args.highlight_winner is True
        assert len(args.subjects) == 2

    def test_subjects_min_length(self) -> None:
        with pytest.raises(ValidationError):
            ComparisonTableArgs(
                title="X",
                subjects=[_make_subject("a", "A")],
                rows=[],
            )

    def test_subjects_max_length(self) -> None:
        with pytest.raises(ValidationError):
            ComparisonTableArgs(**self._valid_args(
                subjects=[_make_subject(f"s{i}", f"S{i}") for i in range(6)],
            ))

    def test_rows_min_length(self) -> None:
        with pytest.raises(ValidationError):
            ComparisonTableArgs(**self._valid_args(rows=[]))

    def test_rows_max_length(self) -> None:
        many_rows = [
            ComparisonRow(
                label=f"R{i}",
                type="text",
                values=[
                    _make_value("a", f"v{i}a"),
                    _make_value("b", f"v{i}b"),
                ],
            )
            for i in range(21)
        ]
        with pytest.raises(ValidationError):
            ComparisonTableArgs(**self._valid_args(rows=many_rows))

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            ComparisonTableArgs(**self._valid_args(boom="x"))

    def test_cross_field_validator_subject_ids_match(self) -> None:
        """ComparisonRow.values doit couvrir exactement les subjects.id (validateur cross-field)."""
        with pytest.raises(ValidationError):
            ComparisonTableArgs(**self._valid_args(
                rows=[
                    ComparisonRow(
                        label="Frais",
                        type="money",
                        values=[
                            _make_value("a", "100"),
                            _make_value("c", "200"),  # 'c' pas dans subjects {a,b}
                        ],
                    ),
                ],
            ))

    def test_cross_field_validator_extra_value_subject(self) -> None:
        """value_ids strict superset des subjects → erreur (3 values pour 2 subjects)."""
        with pytest.raises(ValidationError):
            ComparisonTableArgs(**self._valid_args(
                rows=[
                    ComparisonRow(
                        label="Frais",
                        type="money",
                        values=[
                            _make_value("a", "100"),
                            _make_value("b", "200"),
                            _make_value("c", "300"),  # 'c' pas dans subjects
                        ],
                    ),
                ],
            ))

    def test_title_max_length(self) -> None:
        with pytest.raises(ValidationError):
            ComparisonTableArgs(**self._valid_args(title="X" * 201))
