"""Modèle SQLAlchemy pour la journalisation des tool calls LangGraph."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ToolCallLog(Base):
    """Journal des appels de tools LangChain dans les nœuds LangGraph.

    Chaque exécution de tool (succès, erreur, retry) est enregistrée
    pour le suivi, le débogage et l'audit (FR-022).
    """

    __tablename__ = "tool_call_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id"),
        nullable=True,
    )
    node_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    tool_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    tool_args: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    tool_result: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="success",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    # Story 10.2 : liste des tools effectivement exposes au LLM lors de ce tour.
    # Permet d'auditer le filtrage par contexte de page.
    tools_offered: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    # Story 10.4 : statut de la boucle de validation Pydantic.
    # Valeurs canoniques : "valid", "valid_after_retry", "failed_after_retry".
    # NULL pour les logs runtime non-Pydantic (couche with_retry).
    validation_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )
    # Story 10.4 : erreurs Pydantic filtrees (loc, msg, type) — sans `input`
    # qui peut contenir des secrets.
    pydantic_errors: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_tool_call_logs_user_created", "user_id", created_at.desc()),
        Index("ix_tool_call_logs_conversation", "conversation_id"),
        Index("ix_tool_call_logs_tool_status", "tool_name", "status"),
        Index("ix_tool_call_logs_validation_status", "validation_status"),
    )
