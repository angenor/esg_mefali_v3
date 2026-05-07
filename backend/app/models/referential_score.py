"""Modèle SQLAlchemy ReferentialScore (F13 — scoring multi-référentiels).

Une ligne représente le résultat du calcul d'UN référentiel pour UNE
évaluation ESG donnée. Pattern superseded_by self-référent pour
historisation des versions (F04). Index unique partiel garantit qu'un
seul score « courant » existe par couple (assessment_id, referential_id).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.source import JSONType

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.esg import ESGAssessment
    from app.models.referential import Referential


class ComputedByEnum(str, enum.Enum):
    """Source du calcul du score d'un référentiel."""

    MANUAL = "manual"
    LLM = "llm"
    AUTO = "auto"


class ReferentialScore(Base):
    """Score d'un référentiel pour une évaluation ESG (F13).

    Pattern d'historisation cohérent avec F04 ``superseded_by`` self-référent
    nullable : ``WHERE superseded_by IS NULL`` filtre le score courant ;
    ``WHERE superseded_by IS NOT NULL`` filtre l'historique antérieur.
    """

    __tablename__ = "referential_scores"

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
        ForeignKey("esg_assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    referential_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("referentials.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Versioning F04 : snapshot semver au moment du calcul + chaîne d'historique
    referential_version: Mapped[str] = mapped_column(String(32), nullable=False)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("referential_scores.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Score
    overall_score: Mapped[float | None] = mapped_column(
        Numeric(5, 2), nullable=True,
    )
    pillar_scores: Mapped[dict] = mapped_column(
        JSONType, nullable=False, default=dict, server_default="{}",
    )
    coverage_rate: Mapped[float] = mapped_column(
        Numeric(4, 3), nullable=False, default=0.000, server_default="0.000",
    )
    covered_criteria: Mapped[list] = mapped_column(
        JSONType, nullable=False, default=list, server_default="[]",
    )
    missing_criteria: Mapped[list] = mapped_column(
        JSONType, nullable=False, default=list, server_default="[]",
    )
    gap_to_threshold: Mapped[float | None] = mapped_column(
        Numeric(5, 2), nullable=True,
    )
    eligibility: Mapped[bool | None] = mapped_column(nullable=True)

    # Provenance
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    computed_by: Mapped[ComputedByEnum] = mapped_column(
        SAEnum(
            ComputedByEnum,
            name="referential_score_computed_by_enum",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    computed_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relations
    account: Mapped["Account"] = relationship(
        "Account", foreign_keys=[account_id],
    )
    assessment: Mapped["ESGAssessment"] = relationship(
        "ESGAssessment",
        foreign_keys=[assessment_id],
        back_populates="referential_scores",
    )
    referential: Mapped["Referential"] = relationship(
        "Referential", foreign_keys=[referential_id],
    )
    superseded_by_rel: Mapped["ReferentialScore | None"] = relationship(
        "ReferentialScore",
        remote_side="ReferentialScore.id",
        foreign_keys=[superseded_by],
    )

    __table_args__ = (
        Index(
            "idx_referential_scores_current",
            "assessment_id",
            "referential_id",
            unique=True,
            postgresql_where=text("superseded_by IS NULL"),
            sqlite_where=text("superseded_by IS NULL"),
        ),
        Index(
            "idx_referential_scores_assessment_computed_at",
            "assessment_id",
            "computed_at",
        ),
        Index(
            "idx_referential_scores_referential_computed_at",
            "referential_id",
            "computed_at",
        ),
        Index("idx_referential_scores_account_id", "account_id"),
        CheckConstraint(
            "coverage_rate >= 0 AND coverage_rate <= 1",
            name="ck_referential_scores_coverage_rate_range",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<ReferentialScore id={self.id} assessment={self.assessment_id} "
            f"referential={self.referential_id} score={self.overall_score} "
            f"coverage={self.coverage_rate} version={self.referential_version}>"
        )
