"""Modèles SQLAlchemy pour le module documents."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None


class DocumentStatus(str, enum.Enum):
    """Statuts de traitement d'un document."""

    uploaded = "uploaded"
    processing = "processing"
    analyzed = "analyzed"
    error = "error"


class DocumentType(str, enum.Enum):
    """Types de documents identifiés par l'analyse."""

    statuts_juridiques = "statuts_juridiques"
    rapport_activite = "rapport_activite"
    facture = "facture"
    contrat = "contrat"
    politique_interne = "politique_interne"
    bilan_financier = "bilan_financier"
    autre = "autre"


class Document(UUIDMixin, TimestampMixin, Base):
    """Fichier uploadé par un utilisateur."""

    __tablename__ = "documents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
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
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", create_constraint=True),
        nullable=False,
        default=DocumentStatus.uploaded,
        index=True,
    )
    document_type: Mapped[DocumentType | None] = mapped_column(
        Enum(DocumentType, name="document_type_enum", create_constraint=True),
        nullable=True,
    )

    # Relations
    analysis: Mapped["DocumentAnalysis | None"] = relationship(
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class DocumentAnalysis(UUIDMixin, TimestampMixin, Base):
    """Résultat de l'analyse IA d'un document."""

    __tablename__ = "document_analyses"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_findings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    esg_relevant_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analyzed_at: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
    )

    # Relation
    document: Mapped["Document"] = relationship(back_populates="analysis")


class DocumentChunk(UUIDMixin, Base):
    """Segment de texte avec embedding vectoriel pour le RAG."""

    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(
        Vector(1536) if Vector is not None else Text,
        nullable=True,
    )
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relation
    document: Mapped["Document"] = relationship(back_populates="chunks")


# Index HNSW pour la recherche vectorielle sur les embeddings
if Vector is not None:
    hnsw_index = Index(
        "ix_document_chunks_embedding_hnsw",
        DocumentChunk.embedding,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
