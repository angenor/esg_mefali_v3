"""Tests unitaires F10 — schémas Pydantic discriminés des 9 widgets payload/response.

Tests T005 (TDD strict) :
- Validation ``extra='forbid'``
- Bornes (max options, max fields, max items, hard limits)
- Validation discriminée par ``question_type``
- Round-trip dict→model→dict pour persistance JSONB

Couvre FR-002, FR-003, contracts/widget_payloads.md, contracts/widget_responses.md.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.interactive_question_payload import (
    DatePayload,
    DateRangePayload,
    FileUploadPayload,
    FormField,
    FormPayload,
    NumberPayload,
    RatingPayload,
    SelectOption,
    SelectPayload,
    SummaryCardItem,
    SummaryCardPayload,
    YesNoPayload,
    validate_payload,
)
from app.schemas.interactive_question_response import (
    DateRangeResponse,
    DateResponse,
    FileUploadResponse,
    FormResponse,
    NumberResponse,
    RatingResponse,
    SelectResponse,
    SummaryCardModification,
    SummaryCardResponse,
    UploadedDocument,
    YesNoResponse,
    validate_response,
)


# ─── YesNoPayload / YesNoResponse ────────────────────────────────────────


class TestYesNoPayload:
    def test_default_labels(self) -> None:
        p = YesNoPayload(question_type="yes_no")
        assert p.confirm_label == "Oui"
        assert p.deny_label == "Non"
        assert p.destructive is False

    def test_destructive_with_custom_labels(self) -> None:
        p = YesNoPayload(
            question_type="yes_no",
            confirm_label="Oui, supprimer",
            deny_label="Non, annuler",
            destructive=True,
        )
        assert p.destructive is True
        assert p.confirm_label == "Oui, supprimer"

    def test_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            YesNoPayload(question_type="yes_no", extra_field="forbidden")  # type: ignore[call-arg]

    def test_label_max_length(self) -> None:
        with pytest.raises(ValidationError):
            YesNoPayload(question_type="yes_no", confirm_label="x" * 51)


class TestYesNoResponse:
    def test_true_value(self) -> None:
        r = YesNoResponse(question_type="yes_no", value=True, label="Oui")
        assert r.value is True
        assert r.label == "Oui"

    def test_false_value(self) -> None:
        r = YesNoResponse(question_type="yes_no", value=False, label="Non")
        assert r.value is False


# ─── SelectPayload / SelectResponse ──────────────────────────────────────


class TestSelectPayload:
    def test_minimal(self) -> None:
        p = SelectPayload(
            question_type="select",
            options=[SelectOption(id="ci", label="Côte d'Ivoire")],
        )
        assert p.min_selections == 1
        assert p.max_selections == 1

    def test_max_200_options(self) -> None:
        opts = [SelectOption(id=f"id_{i}", label=f"Label {i}") for i in range(200)]
        p = SelectPayload(question_type="select", options=opts)
        assert len(p.options) == 200

    def test_refuse_201_options(self) -> None:
        opts = [SelectOption(id=f"id_{i}", label=f"Label {i}") for i in range(201)]
        with pytest.raises(ValidationError):
            SelectPayload(question_type="select", options=opts)

    def test_grouped_options(self) -> None:
        p = SelectPayload(
            question_type="select",
            options=[
                SelectOption(id="ci", label="Côte d'Ivoire", group="UEMOA"),
                SelectOption(id="ml", label="Mali", group="UEMOA"),
            ],
        )
        assert p.options[0].group == "UEMOA"

    def test_allow_other(self) -> None:
        p = SelectPayload(
            question_type="select",
            options=[SelectOption(id="ci", label="Côte d'Ivoire")],
            allow_other=True,
        )
        assert p.allow_other is True


class TestSelectResponse:
    def test_mono_selection(self) -> None:
        r = SelectResponse(
            question_type="select",
            selected=[SelectOption(id="ci", label="Côte d'Ivoire")],
        )
        assert len(r.selected) == 1

    def test_multi_selection(self) -> None:
        r = SelectResponse(
            question_type="select",
            selected=[
                SelectOption(id="ci", label="Côte d'Ivoire"),
                SelectOption(id="sn", label="Sénégal"),
            ],
        )
        assert len(r.selected) == 2

    def test_other_value(self) -> None:
        r = SelectResponse(
            question_type="select",
            selected=[SelectOption(id="other", label="Autre")],
            other_value="Tchad",
        )
        assert r.other_value == "Tchad"


# ─── NumberPayload / NumberResponse ──────────────────────────────────────


class TestNumberPayload:
    def test_minimal(self) -> None:
        p = NumberPayload(question_type="number", unit="FCFA")
        assert p.unit == "FCFA"
        assert p.step == 1

    def test_with_currency(self) -> None:
        p = NumberPayload(
            question_type="number",
            unit="FCFA",
            min=0,
            max=1_000_000_000,
            currency="XOF",
        )
        assert p.currency == "XOF"

    def test_invalid_step(self) -> None:
        with pytest.raises(ValidationError):
            NumberPayload(question_type="number", unit="FCFA", step=0)

    def test_invalid_currency(self) -> None:
        with pytest.raises(ValidationError):
            NumberPayload(question_type="number", unit="FCFA", currency="YEN")  # type: ignore[arg-type]


class TestNumberResponse:
    def test_with_currency(self) -> None:
        r = NumberResponse(
            question_type="number",
            value=1_200_000.0,
            currency="XOF",
            formatted="1 200 000 FCFA",
        )
        assert r.currency == "XOF"
        assert "1 200 000" in r.formatted


# ─── DatePayload / DateRangePayload / DateResponse ──────────────────────


class TestDatePayload:
    def test_with_bounds(self) -> None:
        p = DatePayload(
            question_type="date",
            min=date(2026, 1, 1),
            max=date(2026, 12, 31),
        )
        assert p.min == date(2026, 1, 1)


class TestDateResponse:
    def test_basic(self) -> None:
        r = DateResponse(
            question_type="date",
            value=date(2026, 3, 15),
            label="15 mars 2026",
        )
        assert r.value == date(2026, 3, 15)
        assert r.label == "15 mars 2026"


class TestDateRangeResponse:
    def test_alias_from_to(self) -> None:
        r = DateRangeResponse(
            question_type="date_range",
            from_date=date(2026, 1, 1),
            to_date=date(2026, 12, 31),
            label="Du 1 janvier au 31 décembre 2026",
        )
        # Sérialisation sous "from"/"to" via alias
        dumped = r.model_dump(by_alias=True)
        assert dumped["from"] == date(2026, 1, 1)
        assert dumped["to"] == date(2026, 12, 31)


# ─── RatingPayload / RatingResponse ──────────────────────────────────────


class TestRatingPayload:
    def test_default_scale_5(self) -> None:
        p = RatingPayload(question_type="rating")
        assert p.scale == 5

    def test_scale_10(self) -> None:
        p = RatingPayload(question_type="rating", scale=10)
        assert p.scale == 10

    def test_invalid_scale_below_2(self) -> None:
        with pytest.raises(ValidationError):
            RatingPayload(question_type="rating", scale=1)

    def test_invalid_scale_above_10(self) -> None:
        with pytest.raises(ValidationError):
            RatingPayload(question_type="rating", scale=11)

    def test_labels_match_scale(self) -> None:
        p = RatingPayload(
            question_type="rating",
            scale=5,
            labels=["Très mauvais", "Mauvais", "Moyen", "Très bien", "Excellent"],
        )
        assert len(p.labels or []) == 5

    def test_labels_must_match_scale(self) -> None:
        with pytest.raises(ValidationError):
            RatingPayload(
                question_type="rating", scale=5,
                labels=["Très mauvais", "Mauvais"],
            )


# ─── FileUploadPayload / FileUploadResponse ─────────────────────────────


class TestFileUploadPayload:
    def test_default_accept(self) -> None:
        p = FileUploadPayload(question_type="file_upload")
        assert ".pdf" in p.accept
        assert p.max_size_mb == 10

    def test_max_size_capped_at_10(self) -> None:
        with pytest.raises(ValidationError):
            FileUploadPayload(question_type="file_upload", max_size_mb=20)

    def test_max_size_min_1(self) -> None:
        with pytest.raises(ValidationError):
            FileUploadPayload(question_type="file_upload", max_size_mb=0)


class TestFileUploadResponse:
    def test_with_documents(self) -> None:
        r = FileUploadResponse(
            question_type="file_upload",
            documents=[
                UploadedDocument(
                    document_id=uuid4(),
                    filename="business_plan.pdf",
                    size=524288,
                    mime_type="application/pdf",
                ),
            ],
        )
        assert len(r.documents) == 1
        assert r.documents[0].filename == "business_plan.pdf"


# ─── FormPayload / FormResponse ─────────────────────────────────────────


class TestFormPayload:
    def test_minimal_form(self) -> None:
        p = FormPayload(
            question_type="form",
            title="Création de projet",
            fields=[
                FormField(name="project_name", label="Nom du projet", type="text"),
            ],
        )
        assert len(p.fields) == 1
        assert p.submit_label == "Enregistrer"

    def test_max_10_fields(self) -> None:
        fields = [
            FormField(name=f"field_{i}", label=f"Champ {i}", type="text")
            for i in range(10)
        ]
        p = FormPayload(question_type="form", title="Formulaire", fields=fields)
        assert len(p.fields) == 10

    def test_refuse_11_fields(self) -> None:
        fields = [
            FormField(name=f"field_{i}", label=f"Champ {i}", type="text")
            for i in range(11)
        ]
        with pytest.raises(ValidationError):
            FormPayload(question_type="form", title="Formulaire", fields=fields)

    def test_field_name_pattern(self) -> None:
        with pytest.raises(ValidationError):
            FormField(name="Project_Name", label="Nom", type="text")  # majuscule pas autorisée

    def test_field_type_whitelist(self) -> None:
        with pytest.raises(ValidationError):
            FormField(name="x", label="X", type="array")  # type: ignore[arg-type]


class TestFormResponse:
    def test_with_values(self) -> None:
        r = FormResponse(
            question_type="form",
            values={"project_name": "Panneaux", "amount": 5000000.0},
            summary_label="Projet créé : Panneaux, 5M FCFA",
        )
        assert r.values["project_name"] == "Panneaux"


# ─── SummaryCardPayload / SummaryCardResponse ──────────────────────────


class TestSummaryCardPayload:
    def test_minimal(self) -> None:
        p = SummaryCardPayload(
            question_type="summary_card",
            title="Voici l'extraction",
            items=[
                SummaryCardItem(label="Forme", value="SARL", editable=True),
            ],
        )
        assert len(p.items) == 1

    def test_max_20_items(self) -> None:
        items = [
            SummaryCardItem(label=f"Item {i}", value=str(i)) for i in range(20)
        ]
        p = SummaryCardPayload(
            question_type="summary_card", title="X", items=items,
        )
        assert len(p.items) == 20

    def test_refuse_21_items(self) -> None:
        items = [
            SummaryCardItem(label=f"Item {i}", value=str(i)) for i in range(21)
        ]
        with pytest.raises(ValidationError):
            SummaryCardPayload(
                question_type="summary_card", title="X", items=items,
            )


class TestSummaryCardResponse:
    def test_validated_no_modifications(self) -> None:
        r = SummaryCardResponse(
            question_type="summary_card", validated=True, modifications=[],
        )
        assert r.modifications == []

    def test_validated_with_modifications(self) -> None:
        r = SummaryCardResponse(
            question_type="summary_card",
            validated=True,
            modifications=[
                SummaryCardModification(
                    field="capital",
                    before="5M",
                    after="6M",
                ),
            ],
        )
        assert len(r.modifications) == 1


# ─── Validation discriminée par question_type ───────────────────────────


class TestDiscriminatedValidation:
    def test_validate_payload_yes_no(self) -> None:
        result = validate_payload(
            "yes_no",
            {"confirm_label": "Oui", "deny_label": "Non", "destructive": False},
        )
        assert isinstance(result, YesNoPayload)

    def test_validate_payload_select(self) -> None:
        result = validate_payload(
            "select",
            {"options": [{"id": "a", "label": "A"}], "min_selections": 1, "max_selections": 1, "allow_other": False},
        )
        assert isinstance(result, SelectPayload)

    def test_validate_response_yes_no(self) -> None:
        result = validate_response("yes_no", {"value": True, "label": "Oui"})
        assert isinstance(result, YesNoResponse)

    def test_validate_response_number(self) -> None:
        result = validate_response(
            "number",
            {"value": 1200000.0, "currency": "XOF", "formatted": "1 200 000 FCFA"},
        )
        assert isinstance(result, NumberResponse)

    def test_validate_payload_invalid_type(self) -> None:
        with pytest.raises(ValidationError):
            validate_payload("not_a_real_type", {})

    def test_validate_payload_form_max_10(self) -> None:
        fields = [
            {"name": f"f_{i}", "label": f"F{i}", "type": "text", "required": True}
            for i in range(11)
        ]
        with pytest.raises(ValidationError):
            validate_payload("form", {"title": "T", "fields": fields})
