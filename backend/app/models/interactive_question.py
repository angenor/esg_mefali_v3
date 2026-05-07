"""Modele SQLAlchemy InteractiveQuestion (feature 018).

Materialise une question interactive (QCU/QCM avec ou sans justification)
posee par le LLM via le tool ask_interactive_question. Une question = une ligne.
Pas de tables satellites pour les options/reponses : tout en JSONB.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    Boolean,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class InteractiveQuestionType(str, Enum):
    """Type de widget interactif.

    Valeurs F18 (existantes) : qcu, qcm, qcu_justification, qcm_justification.
    Valeurs F10 (étendues, payload jsonb) : yes_no, select, number, date,
    date_range, rating, file_upload, form, summary_card.
    """

    # F18 — widgets QCU/QCM
    QCU = "qcu"
    QCM = "qcm"
    QCU_JUSTIFICATION = "qcu_justification"
    QCM_JUSTIFICATION = "qcm_justification"
    # F10 — 9 nouveaux widgets bottom sheet
    YES_NO = "yes_no"
    SELECT = "select"
    NUMBER = "number"
    DATE = "date"
    DATE_RANGE = "date_range"
    RATING = "rating"
    FILE_UPLOAD = "file_upload"
    FORM = "form"
    SUMMARY_CARD = "summary_card"


class InteractiveQuestionState(str, Enum):
    """Etat de la question dans son cycle de vie."""

    PENDING = "pending"
    ANSWERED = "answered"
    ABANDONED = "abandoned"
    EXPIRED = "expired"


# Type JSONB compatible PostgreSQL et SQLite (tests).
JSONType = JSONB().with_variant(JSON(), "sqlite")


class InteractiveQuestion(UUIDMixin, Base):
    """Question interactive posee par le LLM, materialisee en widget cote frontend."""

    __tablename__ = "interactive_questions"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # F02 — multi-tenant
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    assistant_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    response_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    module: Mapped[str] = mapped_column(String(32), nullable=False)
    question_type: Mapped[str] = mapped_column(String(24), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[dict]] = mapped_column(JSONType, nullable=False)
    min_selections: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1, server_default="1",
    )
    max_selections: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1, server_default="1",
    )
    requires_justification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    justification_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default=InteractiveQuestionState.PENDING.value,
        server_default="pending",
    )
    response_values: Mapped[list[str] | None] = mapped_column(JSONType, nullable=True)
    response_justification: Mapped[str | None] = mapped_column(String(400), nullable=True)
    # F10 — payload jsonb pour les paramètres spécifiques (yes_no/select/number/...)
    payload: Mapped[dict] = mapped_column(
        JSONType, nullable=False, default=dict, server_default="{}",
    )
    # F10 — réponse structurée variante-spécifique (au-delà de response_values)
    response_payload: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Relations
    conversation = relationship("Conversation")
    assistant_message = relationship("Message", foreign_keys=[assistant_message_id])
    response_message = relationship("Message", foreign_keys=[response_message_id])

    __table_args__ = (
        CheckConstraint("min_selections >= 1", name="ck_iq_min_selections"),
        CheckConstraint(
            "max_selections >= min_selections", name="ck_iq_max_ge_min",
        ),
        # F10 — contrainte étendue : permet max_selections > 8 pour 'select' et 'form'.
        CheckConstraint(
            "max_selections <= 8 OR question_type IN ('select', 'form')",
            name="ck_iq_max_le_8_or_select_form",
        ),
        # NB : la borne 500 caracteres sur prompt est verifiee cote Pydantic.
        # On evite un CHECK SQL avec char_length() qui n'est pas portable SQLite.
        Index(
            "ix_interactive_questions_conversation_pending",
            "conversation_id",
            "state",
        ),
        Index(
            "ix_interactive_questions_assistant_message",
            "assistant_message_id",
        ),
        Index(
            "ix_interactive_questions_module_state",
            "module",
            "state",
        ),
    )
