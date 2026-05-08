"""F15 — Modèle SQLAlchemy ``TemplateDossier``.

Catalogue admin-only : modèle officiel de dossier de candidature pour
une offre F07 ou un fallback générique par instrument. Lié à une Skill
F23 (prompt_expert + procedure + tool_whitelist) et à une Source F01
vérifiée. Versioning F04, workflow draft/published F09 avec 4-yeux.

Référence : ``specs/041-f15-dossiers-offre/data-model.md``.
"""

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.source import JSONType
from app.models.versioning_mixin import VersioningMixin


class TemplateLanguage(str, Enum):
    """Langues supportées en MVP."""

    FR = "fr"
    EN = "en"


class TemplateInstrumentType(str, Enum):
    """Type d'instrument financier ciblé (sert au fallback générique)."""

    SUBVENTION = "subvention"
    PRET_CONCESSIONNEL = "prêt_concessionnel"
    EQUITY = "equity"
    BLENDING = "blending"
    MIXTE = "mixte"


class TemplateStatus(str, Enum):
    """Cycle de vie d'un template (workflow F09)."""

    DRAFT = "draft"
    PUBLISHED = "published"


class TemplateDossier(UUIDMixin, TimestampMixin, VersioningMixin, Base):
    """Modèle officiel de dossier de candidature pour une offre F07."""

    __tablename__ = "templates_dossier"

    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)

    # Offre cible (NULL = fallback générique par instrument).
    offer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("offers.id", ondelete="RESTRICT"),
        nullable=True,
    )
    instrument_type: Mapped[str] = mapped_column(String(50), nullable=False)
    language: Mapped[str] = mapped_column(
        String(2), nullable=False, default=TemplateLanguage.FR.value,
        server_default=TemplateLanguage.FR.value,
    )

    # Contenu structuré
    sections: Mapped[list] = mapped_column(JSONType, nullable=False)
    required_documents: Mapped[list] = mapped_column(JSONType, nullable=False)
    tone: Mapped[str] = mapped_column(String(100), nullable=False)
    vocabulary_hints: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    anti_patterns: Mapped[list | None] = mapped_column(JSONType, nullable=True)

    # FK vers Skill F23 et Source F01 (NOT NULL — FR-001)
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Workflow F09
    status: Mapped[str] = mapped_column(
        String(20), nullable=False,
        default=TemplateStatus.DRAFT.value,
        server_default=TemplateStatus.DRAFT.value,
    )
    captured_by: Mapped[uuid.UUID] = mapped_column(
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
            "instrument_type IN ('subvention', 'prêt_concessionnel', 'equity', "
            "'blending', 'mixte')",
            name="templates_dossier_instrument_chk",
        ),
        CheckConstraint(
            "language IN ('fr', 'en')",
            name="templates_dossier_language_chk",
        ),
        CheckConstraint(
            "status IN ('draft', 'published')",
            name="templates_dossier_status_chk",
        ),
        CheckConstraint(
            "verified_by IS NULL OR verified_by != captured_by",
            name="templates_dossier_four_eyes_chk",
        ),
        CheckConstraint(
            "status = 'draft' OR verified_by IS NOT NULL",
            name="templates_dossier_published_requires_verifier_chk",
        ),
        Index(
            "idx_templates_offer_lang_status",
            "offer_id", "language", "status",
        ),
        Index(
            "idx_templates_instrument_lang_status",
            "instrument_type", "language", "status",
        ),
        Index("idx_templates_skill", "skill_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<TemplateDossier name={self.name!r} instrument={self.instrument_type!r} "
            f"language={self.language!r} status={self.status!r} version={self.version!r}>"
        )
