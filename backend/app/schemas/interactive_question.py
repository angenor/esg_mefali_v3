"""Schemas Pydantic pour la feature 018 (interactive chat widgets)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.interactive_question import (
    InteractiveQuestionState,
    InteractiveQuestionType,
)


class InteractiveOption(BaseModel):
    """Option clickable d'un widget interactif."""

    id: str = Field(..., min_length=1, max_length=32, pattern=r"^[a-z0-9_]+$")
    label: str = Field(..., min_length=1, max_length=120)
    emoji: str | None = Field(None, max_length=8)
    description: str | None = Field(None, max_length=200)


class InteractiveQuestionCreate(BaseModel):
    """Payload de creation d'une question interactive (cote tool LLM)."""

    model_config = ConfigDict(extra="forbid")

    question_type: InteractiveQuestionType
    prompt: str = Field(..., min_length=1, max_length=500)
    options: list[InteractiveOption] = Field(..., min_length=2, max_length=8)
    min_selections: int = Field(1, ge=1, le=8)
    max_selections: int = Field(1, ge=1, le=8)
    requires_justification: bool = False
    justification_prompt: str | None = Field(None, min_length=1, max_length=200)
    module: str = Field(..., max_length=32)

    @model_validator(mode="after")
    def _validate_consistency(self) -> "InteractiveQuestionCreate":
        # Unicite des option ids
        ids = [opt.id for opt in self.options]
        if len(set(ids)) != len(ids):
            raise ValueError("DUPLICATE_OPTION_ID")

        # Coherence type / cardinalite
        is_qcu = self.question_type in (
            InteractiveQuestionType.QCU,
            InteractiveQuestionType.QCU_JUSTIFICATION,
        )
        if is_qcu:
            if self.min_selections != 1 or self.max_selections != 1:
                raise ValueError(
                    "QCU requires min_selections=1 and max_selections=1",
                )

        if self.max_selections < self.min_selections:
            raise ValueError("max_selections must be >= min_selections")

        if self.max_selections > len(self.options):
            raise ValueError("max_selections must be <= number of options")

        # Coherence justification
        is_justif_type = self.question_type in (
            InteractiveQuestionType.QCU_JUSTIFICATION,
            InteractiveQuestionType.QCM_JUSTIFICATION,
        )
        if is_justif_type and not self.requires_justification:
            raise ValueError("INCONSISTENT_JUSTIFICATION")
        if not is_justif_type and self.requires_justification:
            raise ValueError("INCONSISTENT_JUSTIFICATION")
        if is_justif_type and not self.justification_prompt:
            raise ValueError("justification_prompt is required for _justification types")

        return self


class InteractiveQuestionResponse(BaseModel):
    """Reponse API representant une question interactive."""

    id: UUID
    conversation_id: UUID
    assistant_message_id: UUID | None
    response_message_id: UUID | None
    module: str
    question_type: InteractiveQuestionType
    prompt: str
    options: list[InteractiveOption]
    min_selections: int
    max_selections: int
    requires_justification: bool
    justification_prompt: str | None
    state: InteractiveQuestionState
    response_values: list[str] | None
    response_justification: str | None
    created_at: datetime
    answered_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class InteractiveQuestionAnswerInput(BaseModel):
    """Payload utilisateur de reponse a une question interactive."""

    question_id: UUID
    values: list[str] = Field(..., min_length=1, max_length=8)
    justification: str | None = Field(None, max_length=400)
