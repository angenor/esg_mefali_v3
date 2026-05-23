"""Modèles SQLAlchemy pour l'évaluation ESG-projet (F047).

Deux tables :

- :class:`ProjectEsgAssessment` — évaluation d'un projet contre un référentiel
  F13 (IFC PS / GCF ESS / BOAD ESS). Cycle de vie ``draft → finalized``
  (immuable). Snapshot F04 versionné (``referential_version`` + ``snapshot_data``).
- :class:`ProjectEsgCriterionResponse` — une réponse par critère pour une
  évaluation donnée. XOR strict ``source_id`` / ``unsourced`` (F01).

Les deux modèles héritent du mixin :class:`Auditable` (F03) pour la capture
automatique du diff field-level via le listener ``before_flush``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.auditable import Auditable
from app.models.base import Base
from app.models.source import JSONType


class ProjectEsgAssessment(Auditable, Base):
    """Évaluation ESG d'un projet vert contre un référentiel F13."""

    __tablename__ = "project_esg_assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    referential_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("referentials.id", ondelete="RESTRICT"),
        nullable=False,
    )
    referential_version: Mapped[str] = mapped_column(String(16), nullable=False)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft", server_default="draft",
    )
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pillar_scores: Mapped[dict] = mapped_column(
        JSONType, nullable=False, default=dict,
    )
    covered_criteria: Mapped[list] = mapped_column(
        JSONType, nullable=False, default=list,
    )
    missing_criteria: Mapped[list] = mapped_column(
        JSONType, nullable=False, default=list,
    )
    coverage_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 3), nullable=True,
    )
    snapshot_data: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "state IN ('draft','finalized')",
            name="pea_state_chk",
        ),
        CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="pea_score_range_chk",
        ),
        CheckConstraint(
            "coverage_rate IS NULL OR (coverage_rate >= 0 AND coverage_rate <= 1)",
            name="pea_coverage_range_chk",
        ),
        CheckConstraint(
            "(state = 'finalized' AND score IS NOT NULL AND finalized_at IS NOT NULL)"
            " OR state = 'draft'",
            name="pea_finalized_score_present_chk",
        ),
    )


class ProjectEsgCriterionResponse(Auditable, Base):
    """Réponse à un critère F13 pour une évaluation ESG-projet."""

    __tablename__ = "project_esg_criterion_responses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_esg_assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    criterion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("criteria.id", ondelete="RESTRICT"),
        nullable=False,
    )
    response_type: Mapped[str] = mapped_column(String(32), nullable=False)
    response_value: Mapped[dict] = mapped_column(JSONType, nullable=False)
    normalized_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=True,
    )
    unsourced: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "assessment_id",
            "criterion_id",
            name="uq_one_response_per_criterion_per_assessment",
        ),
        CheckConstraint(
            "response_type IN ('qcu','qcm','qcu_justification','qcm_justification',"
            "'numeric','money','free_text')",
            name="pecr_response_type_chk",
        ),
        CheckConstraint(
            "normalized_score >= 0 AND normalized_score <= 1",
            name="pecr_normalized_score_range_chk",
        ),
        CheckConstraint(
            "(source_id IS NOT NULL AND unsourced = false) "
            "OR (source_id IS NULL AND unsourced = true)",
            name="pecr_source_or_unsourced_chk",
        ),
    )
