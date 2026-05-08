"""Modèle SQLAlchemy ``Resource`` (F20 — Bibliothèque Ressources).

Une Resource regroupe 5 types de contenu pédagogique :

- ``guide`` : guide pratique en markdown.
- ``template_doc`` : modèle de document téléchargeable (.docx, .xlsx, .pdf).
- ``video`` : vidéo pédagogique (YouTube/Vimeo/local).
- ``faq`` : FAQ structurée (sections H2 par question).
- ``intermediary_guide`` : fiche pratique liée à un intermédiaire (BOAD, GCF...).

Workflow :
- ``draft`` : édition en cours.
- ``published`` : visible côté public, sourcée F01 vérifiée, 4-yeux.
- ``archived`` : retirée (soft-delete via valid_to + status archived).

Versioning F04 : édition d'une ressource ``published`` → nouvelle ligne
``draft`` (semver patch+1) ; publication de la nouvelle version supersède
l'ancienne.

Catalogue admin-only (pas d'``account_id``), édition admin only.
Le LLM ne peut PAS muter cette table (test conformity bloquant — F23 pattern).

Référence : ``specs/038-bibliotheque-ressources/data-model.md``.
"""

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.source import JSONType
from app.models.versioning_mixin import VersioningMixin


class ResourceType(str, Enum):
    """Type de ressource (5 valeurs)."""

    GUIDE = "guide"
    TEMPLATE_DOC = "template_doc"
    VIDEO = "video"
    FAQ = "faq"
    INTERMEDIARY_GUIDE = "intermediary_guide"


class ResourceLanguage(str, Enum):
    """Langue d'une ressource."""

    FR = "fr"
    EN = "en"


class ResourcePublicationStatus(str, Enum):
    """Cycle de vie de publication d'une Resource."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Resource(UUIDMixin, TimestampMixin, VersioningMixin, Base):
    """Resource : ressource pédagogique du catalogue F20."""

    __tablename__ = "resources"

    # Override VersioningMixin default ("1.0") avec semver complet "1.0.0".
    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="1.0.0",
        server_default="1.0.0",
    )

    type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    content_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    target_audience: Mapped[list] = mapped_column(
        JSONType, nullable=False, default=list
    )
    language: Mapped[str] = mapped_column(
        String(2), nullable=False, default="fr", server_default="fr"
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    intermediary_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intermediaries.id", ondelete="RESTRICT"),
        nullable=True,
    )
    publication_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ResourcePublicationStatus.DRAFT.value,
        server_default=ResourcePublicationStatus.DRAFT.value,
    )
    view_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "type IN ('guide','template_doc','video','faq','intermediary_guide')",
            name="resources_type_chk",
        ),
        CheckConstraint(
            "language IN ('fr','en')",
            name="resources_language_chk",
        ),
        CheckConstraint(
            "publication_status IN ('draft','published','archived')",
            name="resources_publication_status_chk",
        ),
        CheckConstraint(
            "verified_by IS NULL OR verified_by != created_by",
            name="resources_four_eyes_chk",
        ),
        CheckConstraint("view_count >= 0", name="resources_view_count_chk"),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="resources_duration_chk",
        ),
        Index(
            "ix_resources_lookup",
            "type",
            "publication_status",
            "valid_to",
        ),
        Index(
            "ix_resources_intermediary",
            "intermediary_id",
        ),
        Index(
            "ix_resources_views",
            "view_count",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Resource type={self.type!r} slug={self.slug!r} "
            f"version={self.version!r} status={self.publication_status!r}>"
        )
