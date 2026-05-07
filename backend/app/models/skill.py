"""Modèle SQLAlchemy ``Skill`` (F23 — Playbooks Métier).

Une Skill est un bundle métier réutilisable qui combine :
- ``prompt_expert`` (≤ 5000 tokens) : prompt focalisé domaine.
- ``procedure`` (≤ 3000 tokens) : pas-à-pas opératoire.
- ``tool_whitelist`` : sous-ensemble des tools LangChain autorisés.
- ``sources`` : UUIDs de Sources verified pré-résolues.
- ``activation_rules`` : règles de chargement contextuel (page_slugs,
  intent_keywords, active_module, offer_id, fund_id, intermediary_id).
- ``golden_examples`` : 5 à 15 cas de test pour le gating à la publication.

Workflow :
- ``draft`` : calibration en cours, golden_examples possiblement < 5.
- ``published`` : skill validée par eval gating (≥ 90 % de réussite),
  exposable au LLM via le loader contextuel.

Versioning F04 : édition d'une skill ``published`` → nouvelle ligne
``draft`` (semver patch+1) → eval gating → publication ; l'ancienne
ligne reçoit ``valid_to=today()`` + ``superseded_by=new_id``.

Catalogue global (pas d'``account_id``), édition admin only.
Le LLM ne peut PAS muter cette table (test conformity bloquant).
Référence : ``specs/033-skills-playbooks-metier/data-model.md``.
"""

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.source import JSONType
from app.models.versioning_mixin import VersioningMixin


class SkillDomain(str, Enum):
    """Domaine métier d'une Skill (7 valeurs)."""

    DIAGNOSTIC_ESG = "diagnostic_esg"
    SCORING_REFERENTIEL = "scoring_referentiel"
    CARBON_CALC = "carbon_calc"
    DOSSIER = "dossier"
    INTERMEDIAIRE = "intermediaire"
    ATTESTATION = "attestation"
    CREDIT_SCORE = "credit_score"


class SkillStatus(str, Enum):
    """Cycle de vie d'une Skill."""

    DRAFT = "draft"
    PUBLISHED = "published"


class Skill(UUIDMixin, TimestampMixin, VersioningMixin, Base):
    """Skill : playbook métier (prompt + procédure + tools + sources + golden)."""

    __tablename__ = "skills"

    # Override VersioningMixin default ("1.0") avec semver complet "1.0.0".
    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="1.0.0",
        server_default="1.0.0",
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    domain: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_expert: Mapped[str] = mapped_column(Text, nullable=False)
    procedure: Mapped[str] = mapped_column(Text, nullable=False)
    tool_whitelist: Mapped[list] = mapped_column(JSONType, nullable=False)
    sources: Mapped[list] = mapped_column(JSONType, nullable=False)
    activation_rules: Mapped[dict] = mapped_column(JSONType, nullable=False)
    golden_examples: Mapped[list] = mapped_column(JSONType, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SkillStatus.DRAFT.value,
        server_default=SkillStatus.DRAFT.value,
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
            "domain IN ('diagnostic_esg', 'scoring_referentiel', 'carbon_calc', "
            "'dossier', 'intermediaire', 'attestation', 'credit_score')",
            name="skills_domain_chk",
        ),
        CheckConstraint(
            "status IN ('draft', 'published')",
            name="skills_status_chk",
        ),
        CheckConstraint(
            "verified_by IS NULL OR verified_by != created_by",
            name="skills_four_eyes_chk",
        ),
        Index("ix_skills_domain_status_validto", "domain", "status", "valid_to"),
        Index("ix_skills_status", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Skill name={self.name!r} domain={self.domain!r} "
            f"version={self.version!r} status={self.status!r}>"
        )
