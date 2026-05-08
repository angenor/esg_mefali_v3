"""Modele SQLAlchemy Report pour les rapports ESG PDF."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class ReportTypeEnum(str, enum.Enum):
    """Type de rapport genere."""

    esg_compliance = "esg_compliance"
    # F21 — Rapport carbone PDF. La valeur est ajoutée à l'enum Python ;
    # une migration ALTER TYPE PostgreSQL devra être exécutée hors-spec F21
    # pour le déploiement production (les tests SQLite ne sont pas concernés).
    carbon = "carbon"


class ReportStatusEnum(str, enum.Enum):
    """Statut de generation d'un rapport."""

    generating = "generating"
    completed = "completed"
    failed = "failed"


class Report(UUIDMixin, TimestampMixin, Base):
    """Rapport PDF genere a partir d'une evaluation ESG."""

    __tablename__ = "reports"

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
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("esg_assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_type: Mapped[ReportTypeEnum] = mapped_column(
        Enum(ReportTypeEnum, name="report_type_enum", create_constraint=True),
        nullable=False,
        default=ReportTypeEnum.esg_compliance,
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[ReportStatusEnum] = mapped_column(
        Enum(ReportStatusEnum, name="report_status_enum", create_constraint=True),
        nullable=False,
        default=ReportStatusEnum.generating,
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Contrainte d'unicite partielle geree dans la migration Alembic :
    # CREATE UNIQUE INDEX uq_one_generating_per_assessment
    # ON reports (assessment_id) WHERE status = 'generating'
