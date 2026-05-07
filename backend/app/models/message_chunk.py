"""Modèle SQLAlchemy MessageChunk (F12 — mémoire contextuelle pgvector).

Représente un fragment d'un message conversationnel indexé pour la recherche
sémantique. Un message court (≤ 6 000 caractères) produit exactement un chunk
(``chunk_index = 0``). Un message long est découpé en N chunks avec recouvrement
de 200 caractères entre chunks consécutifs.

Tables liées :
- ``messages.id`` (FK CASCADE) — message d'origine.
- ``conversations.id`` (FK CASCADE) — conversation d'origine.
- ``accounts.id`` (FK RESTRICT) — tenant propriétaire (RLS active).

Voir ``specs/023-memoire-contextuelle-pgvector/data-model.md``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - SQLite fallback in tests
    Vector = None  # type: ignore[assignment]


class MessageChunk(UUIDMixin, Base):
    """Fragment d'un message conversationnel indexé pour la recherche sémantique."""

    __tablename__ = "message_chunks"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Le type Vector est uniquement disponible sous PostgreSQL+pgvector. En
    # tests SQLite, on retombe sur Text (la sémantique des recherches HNSW
    # n'est pas testée sur SQLite — les tests pertinents sont marqués
    # ``@pytest.mark.postgres`` ou utilisent un fallback explicite).
    embedding = mapped_column(
        Vector(1536) if Vector is not None else Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="message_chunks_role_chk",
        ),
        CheckConstraint(
            "chunk_index >= 0",
            name="message_chunks_chunk_index_chk",
        ),
        Index(
            "idx_message_chunks_account_conv_created",
            "account_id",
            "conversation_id",
            "created_at",
        ),
    )


# Index HNSW (PostgreSQL only — créé directement par la migration Alembic 023).
# On ne déclare pas l'index ici via Index() pour éviter qu'Alembic autogenerate
# ne tente de le recréer dans une autre migration. La création est explicite
# dans backend/alembic/versions/023_create_message_chunks.py.
