"""Schémas Pydantic discriminés pour le response_payload des 9 widgets F10.

Stocke la réponse structurée de l'utilisateur (au-delà de ``response_values``
hérité F18) dans la colonne ``response_payload jsonb`` de la table
``interactive_questions``.

Réf. :
- ``specs/031-widgets-bottom-sheet-complets/data-model.md``
- ``specs/031-widgets-bottom-sheet-complets/contracts/widget_responses.md``
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.schemas.interactive_question_payload import SelectOption, SupportedCurrency

# ─── YesNo ───────────────────────────────────────────────────────────────


class YesNoResponse(BaseModel):
    """Réponse à un widget ``ask_yes_no`` (boolean + label affiché)."""

    model_config = ConfigDict(extra="forbid")

    question_type: Literal["yes_no"] = "yes_no"
    value: bool
    label: str = Field(..., min_length=1, max_length=50)


# ─── Select ──────────────────────────────────────────────────────────────


class SelectResponse(BaseModel):
    """Réponse à un widget ``ask_select`` (1 ou plusieurs options + autre)."""

    model_config = ConfigDict(extra="forbid")

    question_type: Literal["select"] = "select"
    selected: list[SelectOption] = Field(..., min_length=1)
    other_value: str | None = Field(None, max_length=200)


# ─── Number ──────────────────────────────────────────────────────────────


class NumberResponse(BaseModel):
    """Réponse à un widget ``ask_number`` (valeur + devise + format affiché)."""

    model_config = ConfigDict(extra="forbid")

    question_type: Literal["number"] = "number"
    value: float
    currency: SupportedCurrency | None = None
    formatted: str = Field(..., min_length=1, max_length=100)


# ─── Date / DateRange ────────────────────────────────────────────────────


class DateResponse(BaseModel):
    """Réponse à un widget ``ask_date`` (ISO 8601 + label fr)."""

    model_config = ConfigDict(extra="forbid")

    question_type: Literal["date"] = "date"
    value: date
    label: str = Field(..., min_length=1, max_length=100)


class DateRangeResponse(BaseModel):
    """Réponse à un widget ``ask_date_range`` (intervalle + label fr)."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    question_type: Literal["date_range"] = "date_range"
    from_date: date = Field(..., alias="from")
    to_date: date = Field(..., alias="to")
    label: str = Field(..., min_length=1, max_length=200)


# ─── Rating ──────────────────────────────────────────────────────────────


class RatingResponse(BaseModel):
    """Réponse à un widget ``ask_rating`` (note + scale + label optionnel)."""

    model_config = ConfigDict(extra="forbid")

    question_type: Literal["rating"] = "rating"
    value: int = Field(..., ge=1, le=10)
    scale: int = Field(..., ge=2, le=10)
    label: str | None = Field(None, max_length=100)


# ─── FileUpload ─────────────────────────────────────────────────────────


class UploadedDocument(BaseModel):
    """Document uploadé via ``ask_file_upload``."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    filename: str = Field(..., min_length=1, max_length=300)
    size: int = Field(..., ge=0)
    mime_type: str = Field(..., min_length=1, max_length=200)


class FileUploadResponse(BaseModel):
    """Réponse à un widget ``ask_file_upload`` (1 ou N documents)."""

    model_config = ConfigDict(extra="forbid")

    question_type: Literal["file_upload"] = "file_upload"
    documents: list[UploadedDocument] = Field(..., min_length=1, max_length=20)


# ─── Form ────────────────────────────────────────────────────────────────


class FormResponse(BaseModel):
    """Réponse à un widget ``show_form`` (dict name→value + label synthétique)."""

    model_config = ConfigDict(extra="forbid")

    question_type: Literal["form"] = "form"
    values: dict[str, str | float | bool | None]
    summary_label: str = Field(..., min_length=1, max_length=300)


# ─── SummaryCard ────────────────────────────────────────────────────────


class SummaryCardModification(BaseModel):
    """Modification appliquée à un item de summary_card en mode édition inline."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(..., min_length=1, max_length=200)
    before: str | float | bool | None
    after: str | float | bool | None


class SummaryCardResponse(BaseModel):
    """Réponse à un widget ``show_summary_card`` (validé + corrections optionnelles)."""

    model_config = ConfigDict(extra="forbid")

    question_type: Literal["summary_card"] = "summary_card"
    validated: bool
    modifications: list[SummaryCardModification] = Field(default_factory=list)


# ─── Union discriminée ──────────────────────────────────────────────────


InteractiveQuestionResponse = Annotated[
    Union[
        YesNoResponse,
        SelectResponse,
        NumberResponse,
        DateResponse,
        DateRangeResponse,
        RatingResponse,
        FileUploadResponse,
        FormResponse,
        SummaryCardResponse,
    ],
    Field(discriminator="question_type"),
]


_RESPONSE_ADAPTER: TypeAdapter[Any] = TypeAdapter(InteractiveQuestionResponse)


def validate_response(question_type: str, response: dict[str, Any]) -> Any:
    """Valide la réponse structurée d'une question interactive selon son type.

    Lève ``ValidationError`` si la réponse est non conforme.
    """
    response_with_type = dict(response)
    response_with_type["question_type"] = question_type
    return _RESPONSE_ADAPTER.validate_python(response_with_type)
