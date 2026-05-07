"""Modèle SQLAlchemy Project (F06 — Entité Projet Vert).

Représente un projet vert d'une PME. Multi-tenant via ``account_id`` (F02),
Auditable (F03), Money typed (F04) sur ``target_amount``.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.auditable import Auditable
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.source import JSONType


# --- Whitelists applicatives (parallèles aux validators Pydantic) ---

PROJECT_OBJECTIVE_ENV_VALUES: frozenset[str] = frozenset({
    "mitigation",
    "adaptation",
    "biodiversity",
    "circular_economy",
    "water",
    "renewable_energy",
    "sustainable_agriculture",
    "mixed",
})

PROJECT_MATURITY_VALUES: frozenset[str] = frozenset({
    "ideation",
    "pre_feasibility",
    "pilot",
    "scale",
    "replication",
})

PROJECT_STATUS_VALUES: frozenset[str] = frozenset({
    "draft",
    "seeking_funding",
    "funded",
    "in_execution",
    "closed",
    "cancelled",
})

PROJECT_FINANCING_STRUCTURE_VALUES: frozenset[str] = frozenset({
    "subvention",
    "pret_concessionnel",
    "equity",
    "blending",
    "mixte",
})

PROJECT_CURRENCY_VALUES: frozenset[str] = frozenset({
    "XOF",
    "EUR",
    "USD",
    "GBP",
    "JPY",
})


class Project(Auditable, UUIDMixin, TimestampMixin, Base):
    """Projet vert d'une PME.

    Multi-tenant via ``account_id`` (F02), Auditable (F03) — toutes les
    mutations sont tracées par le listener global ``before_flush``.

    Money typed (F04) : ``target_amount`` est une paire ``target_amount_amount``
    (Numeric(20,2)) + ``target_amount_currency`` (Char(3)).
    """

    __tablename__ = "projects"

    # Multi-tenant F02
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSONB array de strings ; whitelist appliquée au niveau Pydantic + CHECK applicatif.
    objective_env: Mapped[list[str]] = mapped_column(
        JSONType, nullable=False, server_default="[]", default=list,
    )

    maturity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", server_default="draft",
    )

    # Money typed F04 (les 2 colonnes nullables, mais les deux NULL ou les 2 non-NULL)
    target_amount_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True,
    )
    target_amount_currency: Mapped[str | None] = mapped_column(
        String(3), nullable=True,
    )

    duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    financing_structure: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
    )

    # Impacts attendus
    expected_impact_tco2e: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 4), nullable=True,
    )
    expected_jobs_created: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    expected_beneficiaries: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    expected_hectares_restored: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True,
    )
    expected_other_impacts: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType, nullable=True,
    )

    # Localisation (PostGIS différé F11)
    location_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    location_region: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Flag migration backfill F06
    auto_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    # Relations
    project_documents: Mapped[list["ProjectDocument"]] = relationship(
        "ProjectDocument",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        # Indexes composites (perf FR-004)
        Index("idx_projects_account_status", "account_id", "status"),
        Index("idx_projects_account_maturity", "account_id", "maturity"),
        # Money typed F04 : les 2 colonnes ensemble
        CheckConstraint(
            "(target_amount_amount IS NULL AND target_amount_currency IS NULL) "
            "OR (target_amount_amount IS NOT NULL AND target_amount_currency IS NOT NULL)",
            name="projects_target_amount_pair_chk",
        ),
        CheckConstraint(
            "target_amount_amount IS NULL OR target_amount_amount >= 0",
            name="projects_target_amount_positive_chk",
        ),
        CheckConstraint(
            "target_amount_currency IS NULL OR target_amount_currency IN "
            "('XOF','EUR','USD','GBP','JPY')",
            name="projects_target_amount_currency_chk",
        ),
        CheckConstraint(
            "duration_months IS NULL OR duration_months > 0",
            name="projects_duration_months_positive_chk",
        ),
        CheckConstraint(
            "expected_jobs_created IS NULL OR expected_jobs_created >= 0",
            name="projects_expected_jobs_positive_chk",
        ),
        CheckConstraint(
            "expected_beneficiaries IS NULL OR expected_beneficiaries >= 0",
            name="projects_expected_beneficiaries_positive_chk",
        ),
        CheckConstraint(
            "expected_hectares_restored IS NULL OR expected_hectares_restored >= 0",
            name="projects_expected_hectares_positive_chk",
        ),
        CheckConstraint(
            "expected_impact_tco2e IS NULL OR expected_impact_tco2e >= 0",
            name="projects_expected_impact_tco2e_positive_chk",
        ),
        CheckConstraint(
            "status IN ('draft','seeking_funding','funded','in_execution',"
            "'closed','cancelled')",
            name="projects_status_chk",
        ),
        CheckConstraint(
            "maturity IS NULL OR maturity IN "
            "('ideation','pre_feasibility','pilot','scale','replication')",
            name="projects_maturity_chk",
        ),
        CheckConstraint(
            "financing_structure IS NULL OR financing_structure IN "
            "('subvention','pret_concessionnel','equity','blending','mixte')",
            name="projects_financing_structure_chk",
        ),
        # ISO 3166-1 alpha-2 : 2 lettres majuscules
        CheckConstraint(
            "location_country IS NULL OR length(location_country) = 2",
            name="projects_location_country_chk",
        ),
    )
