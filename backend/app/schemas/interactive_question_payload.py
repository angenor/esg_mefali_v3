"""Schémas Pydantic discriminés pour le payload des 9 widgets F10.

Chaque widget interactif (yes_no/select/number/date/date_range/rating/file_upload/form/summary_card)
embarque ses paramètres spécifiques dans la colonne ``payload jsonb`` de la
table ``interactive_questions``. Le typage est garanti par cette union
discriminée par ``question_type``.

Réf. :
- ``specs/031-widgets-bottom-sheet-complets/data-model.md``
- ``specs/031-widgets-bottom-sheet-complets/contracts/widget_payloads.md``
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

# ─── YesNo ───────────────────────────────────────────────────────────────


class YesNoPayload(BaseModel):
    """Payload du widget ``ask_yes_no`` (binaire, peut être destructif)."""

    model_config = ConfigDict(extra="forbid")

    question_type: Literal["yes_no"] = "yes_no"
    confirm_label: str = Field("Oui", min_length=1, max_length=50)
    deny_label: str = Field("Non", min_length=1, max_length=50)
    destructive: bool = False


# ─── Select ──────────────────────────────────────────────────────────────


class SelectOption(BaseModel):
    """Option cliquable d'un widget select."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=200)
    sublabel: str | None = Field(None, max_length=200)
    group: str | None = Field(None, max_length=100)


class SelectPayload(BaseModel):
    """Payload du widget ``ask_select`` (liste 1-200 options)."""

    model_config = ConfigDict(extra="forbid")

    question_type: Literal["select"] = "select"
    options: list[SelectOption] = Field(..., min_length=1, max_length=200)
    min_selections: int = Field(1, ge=1, le=200)
    max_selections: int = Field(1, ge=1, le=200)
    allow_other: bool = False


# ─── Number ──────────────────────────────────────────────────────────────


SupportedCurrency = Literal["XOF", "EUR", "USD", "CDF"]


class NumberPayload(BaseModel):
    """Payload du widget ``ask_number`` (numérique formaté avec devise optionnelle)."""

    model_config = ConfigDict(extra="forbid")

    question_type: Literal["number"] = "number"
    unit: str = Field(..., min_length=1, max_length=20)
    min: float | None = None
    max: float | None = None
    step: float = Field(1, gt=0)
    currency: SupportedCurrency | None = None
    default: float | None = None


# ─── Date / DateRange ────────────────────────────────────────────────────


class DatePayload(BaseModel):
    """Payload du widget ``ask_date`` (date unique)."""

    model_config = ConfigDict(extra="forbid")

    question_type: Literal["date"] = "date"
    min: date | None = None
    max: date | None = None
    default: date | None = None


class DateRangePayload(BaseModel):
    """Payload du widget ``ask_date_range`` (intervalle de dates)."""

    model_config = ConfigDict(extra="forbid")

    question_type: Literal["date_range"] = "date_range"
    min: date | None = None
    max: date | None = None


# ─── Rating ──────────────────────────────────────────────────────────────


class RatingPayload(BaseModel):
    """Payload du widget ``ask_rating`` (étoiles ou points)."""

    model_config = ConfigDict(extra="forbid")

    question_type: Literal["rating"] = "rating"
    scale: int = Field(5, ge=2, le=10)
    labels: list[str] | None = Field(None, max_length=10)

    @field_validator("labels")
    @classmethod
    def _check_labels_length(cls, v: list[str] | None, info) -> list[str] | None:
        if v is None:
            return v
        scale = info.data.get("scale", 5)
        if len(v) != scale:
            raise ValueError(
                f"len(labels)={len(v)} doit être égal à scale={scale}",
            )
        return v


# ─── FileUpload ─────────────────────────────────────────────────────────


class FileUploadPayload(BaseModel):
    """Payload du widget ``ask_file_upload`` (drag-and-drop avec validation MIME)."""

    model_config = ConfigDict(extra="forbid")

    question_type: Literal["file_upload"] = "file_upload"
    accept: list[str] = Field(
        default=[".pdf", ".docx", ".xlsx", ".png", ".jpg"],
        min_length=1,
        max_length=20,
    )
    max_size_mb: int = Field(10, ge=1, le=10)
    multi: bool = False
    doc_type_hint: str | None = Field(None, max_length=100)


# ─── Form ────────────────────────────────────────────────────────────────


class FormFieldType(str, Enum):
    """Types de champ supportés dans ``show_form``."""

    TEXT = "text"
    NUMBER = "number"
    SELECT = "select"
    DATE = "date"
    TEXTAREA = "textarea"
    MONEY = "money"


class FormFieldValidation(BaseModel):
    """Règles de validation client (zod côté frontend)."""

    model_config = ConfigDict(extra="forbid")

    min_length: int | None = None
    max_length: int | None = None
    min: float | None = None
    max: float | None = None
    pattern: str | None = None
    options: list[SelectOption] | None = None


class FormField(BaseModel):
    """Définition d'un champ d'un ``show_form`` (max 10 champs par formulaire)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(..., min_length=1, max_length=200)
    type: FormFieldType
    required: bool = True
    placeholder: str | None = Field(None, max_length=200)
    default: str | float | bool | None = None
    validation: FormFieldValidation | None = None


class FormPayload(BaseModel):
    """Payload du widget ``show_form`` (mini-formulaire 1-10 champs)."""

    model_config = ConfigDict(extra="forbid")

    question_type: Literal["form"] = "form"
    title: str = Field(..., min_length=1, max_length=200)
    fields: list[FormField] = Field(..., min_length=1, max_length=10)
    submit_label: str = Field("Enregistrer", min_length=1, max_length=50)


# ─── SummaryCard ────────────────────────────────────────────────────────


class SummaryCardItem(BaseModel):
    """Élément d'une carte récapitulative (extraction document)."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(..., min_length=1, max_length=200)
    value: str | float | bool | None
    editable: bool = False


class SummaryCardPayload(BaseModel):
    """Payload du widget ``show_summary_card`` (récap avec édition inline)."""

    model_config = ConfigDict(extra="forbid")

    question_type: Literal["summary_card"] = "summary_card"
    title: str = Field(..., min_length=1, max_length=200)
    items: list[SummaryCardItem] = Field(..., min_length=1, max_length=20)
    confirm_label: str = Field("Valider", min_length=1, max_length=50)
    correct_label: str = Field("Corriger", min_length=1, max_length=50)


# ─── Union discriminée ──────────────────────────────────────────────────


InteractiveQuestionPayload = Annotated[
    Union[
        YesNoPayload,
        SelectPayload,
        NumberPayload,
        DatePayload,
        DateRangePayload,
        RatingPayload,
        FileUploadPayload,
        FormPayload,
        SummaryCardPayload,
    ],
    Field(discriminator="question_type"),
]


_PAYLOAD_ADAPTER: TypeAdapter[Any] = TypeAdapter(InteractiveQuestionPayload)


def validate_payload(question_type: str, payload: dict[str, Any]) -> Any:
    """Valide le payload d'une question interactive selon son type.

    Lève ``ValidationError`` si le payload est non conforme.
    """
    payload_with_type = dict(payload)
    payload_with_type["question_type"] = question_type
    return _PAYLOAD_ADAPTER.validate_python(payload_with_type)
