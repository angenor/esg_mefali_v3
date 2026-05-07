"""Modèle SQLAlchemy ProjectDocument (F06 — table de jointure projet ↔ document)."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


PROJECT_DOC_TYPE_VALUES: frozenset[str] = frozenset({
    "feasibility_study",
    "business_plan",
    "impact_assessment",
    "support_letter",
    "other",
})


class ProjectDocument(UUIDMixin, TimestampMixin, Base):
    """Lien projet ↔ document avec qualification ``doc_type``.

    Pas hérité de :class:`Auditable` (table de jointure pure ; la traçabilité
    est sur :class:`Project`). Listé dans ``EXEMPT_MODELS``.
    """

    __tablename__ = "project_documents"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)

    project: Mapped["Project"] = relationship(
        "Project", back_populates="project_documents",
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id", "document_id", name="project_documents_unique",
        ),
        Index("idx_project_documents_project_id", "project_id"),
        Index("idx_project_documents_document_id", "document_id"),
        CheckConstraint(
            "doc_type IN ('feasibility_study','business_plan',"
            "'impact_assessment','support_letter','other')",
            name="project_documents_doc_type_chk",
        ),
    )
