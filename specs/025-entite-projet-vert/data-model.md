# Phase 1 — Data Model: F06 Entité Projet Vert

**Feature** : F06 — Entité Projet Vert (Module 1.3)
**Date** : 2026-05-07
**Branch** : `feat/F06-entite-projet-vert`

## 1. Vue d'ensemble

Trois changements structurels :

1. **Nouvelle table `projects`** : entité métier principale (multi-tenant F02, Auditable F03, Money typed F04).
2. **Nouvelle table `project_documents`** : table de jointure projet ↔ document avec `doc_type`.
3. **Modification `fund_applications`** : ajout de `project_id` UUID FK NOT NULL (après backfill).

Aucune autre table n'est modifiée par F06.

## 2. Modèles SQLAlchemy

### 2.1 `Project` (`backend/app/models/project.py`)

```python
"""Modèle SQLAlchemy Project (F06 — Entité Projet Vert)."""

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
from app.models.source import JSONType  # JSONB() with_variant(JSON(), "sqlite")


# Whitelists applicatives (parallèles aux validators Pydantic)
PROJECT_OBJECTIVE_ENV_VALUES = frozenset({
    "mitigation",
    "adaptation",
    "biodiversity",
    "circular_economy",
    "water",
    "renewable_energy",
    "sustainable_agriculture",
    "mixed",
})

PROJECT_MATURITY_VALUES = frozenset({
    "ideation",
    "pre_feasibility",
    "pilot",
    "scale",
    "replication",
})

PROJECT_STATUS_VALUES = frozenset({
    "draft",
    "seeking_funding",
    "funded",
    "in_execution",
    "closed",
    "cancelled",
})

PROJECT_FINANCING_STRUCTURE_VALUES = frozenset({
    "subvention",
    "pret_concessionnel",
    "equity",
    "blending",
    "mixte",
})

# Enum supporté pour la devise Money (F04 cohérence)
PROJECT_CURRENCY_VALUES = frozenset({"XOF", "EUR", "USD", "GBP", "JPY"})


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

    maturity: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
    )
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
    expected_jobs_created: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
        # ISO 3166-1 alpha-2 : 2 lettres majuscules (validation côté Pydantic + CHECK)
        CheckConstraint(
            "location_country IS NULL OR length(location_country) = 2",
            name="projects_location_country_chk",
        ),
    )
```

### 2.2 `ProjectDocument` (`backend/app/models/project_document.py`)

```python
"""Modèle SQLAlchemy ProjectDocument (F06 — table de jointure)."""

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


PROJECT_DOC_TYPE_VALUES = frozenset({
    "feasibility_study",
    "business_plan",
    "impact_assessment",
    "support_letter",
    "other",
})


class ProjectDocument(UUIDMixin, TimestampMixin, Base):
    """Lien projet ↔ document avec qualification ``doc_type``.

    Pas hérité de ``Auditable`` (table de jointure pure ; la traçabilité
    est sur ``Project``). Listé dans ``EXEMPT_MODELS`` (cf. core/auditable.py).
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
        "Project", back_populates="project_documents"
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id", "document_id", name="project_documents_unique"
        ),
        Index("idx_project_documents_project_id", "project_id"),
        Index("idx_project_documents_document_id", "document_id"),
        CheckConstraint(
            "doc_type IN ('feasibility_study','business_plan',"
            "'impact_assessment','support_letter','other')",
            name="project_documents_doc_type_chk",
        ),
    )
```

### 2.3 Modification `FundApplication` (`backend/app/models/application.py`)

Ajout de la colonne `project_id` :

```python
class FundApplication(Auditable, UUIDMixin, TimestampMixin, Base):
    # ... champs existants ...

    # F06 — Lien vers Project
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,  # idx_fund_applications_project_id
    )

    # Relation
    project: Mapped["Project"] = relationship(
        "Project", lazy="selectin"
    )
```

NOTE : `nullable=False` est l'état post-migration. Pendant la migration, la colonne est temporairement `nullable=True`.

## 3. Migration Alembic `025_create_projects.py`

### 3.1 Métadonnées

```python
"""F06 — Création tables projects et project_documents + lien fund_applications.project_id

Revision ID: 025_create_projects
Revises: 024_carbone_mix_uemoa
Create Date: 2026-05-07

Cette migration ajoute :
1. Table ``projects`` (multi-tenant F02, Auditable F03, Money typed F04).
2. Table de jointure ``project_documents``.
3. Colonne ``project_id`` UUID FK NOT NULL sur ``fund_applications``
   (en deux temps : NULL transitoire avec backfill, puis NOT NULL).

Backfill : pour chaque ``FundApplication`` orpheline, génère un ``Project``
auto-généré (``auto_generated=true``) afin de matérialiser le triangle
``Entreprise 1—N Projets 1—N Candidatures vers Offres``.

RLS PostgreSQL F02 héritée : ENABLE+FORCE + 2 policies sur les 2 nouvelles
tables.
"""

revision = "025_create_projects"
down_revision = "024_carbone_mix_uemoa"
branch_labels = None
depends_on = None
```

### 3.2 Étapes upgrade

```python
def upgrade() -> None:
    # 1. CREATE TABLE projects
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("objective_env", JSONType, nullable=False, server_default="[]"),
        sa.Column("maturity", sa.String(32), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("target_amount_amount", sa.Numeric(20, 2), nullable=True),
        sa.Column("target_amount_currency", sa.String(3), nullable=True),
        sa.Column("duration_months", sa.Integer(), nullable=True),
        sa.Column("financing_structure", sa.String(32), nullable=True),
        sa.Column("expected_impact_tco2e", sa.Numeric(20, 4), nullable=True),
        sa.Column("expected_jobs_created", sa.Integer(), nullable=True),
        sa.Column("expected_beneficiaries", sa.Integer(), nullable=True),
        sa.Column("expected_hectares_restored", sa.Numeric(10, 2), nullable=True),
        sa.Column("expected_other_impacts", JSONType, nullable=True),
        sa.Column("location_country", sa.String(2), nullable=True),
        sa.Column("location_region", sa.String(100), nullable=True),
        sa.Column(
            "auto_generated", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        # CHECK contraintes
        sa.CheckConstraint(
            "(target_amount_amount IS NULL AND target_amount_currency IS NULL) "
            "OR (target_amount_amount IS NOT NULL AND target_amount_currency IS NOT NULL)",
            name="projects_target_amount_pair_chk",
        ),
        # ... autres CHECK contraintes (cf. modèle SQLAlchemy) ...
    )
    op.create_index(
        "idx_projects_account_status", "projects", ["account_id", "status"]
    )
    op.create_index(
        "idx_projects_account_maturity", "projects", ["account_id", "maturity"]
    )

    # 2. CREATE TABLE project_documents
    op.create_table(
        "project_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doc_type", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "document_id", name="project_documents_unique"
        ),
        sa.CheckConstraint(
            "doc_type IN ('feasibility_study','business_plan',"
            "'impact_assessment','support_letter','other')",
            name="project_documents_doc_type_chk",
        ),
    )
    op.create_index(
        "idx_project_documents_project_id", "project_documents", ["project_id"]
    )
    op.create_index(
        "idx_project_documents_document_id", "project_documents", ["document_id"]
    )

    # 3. ALTER TABLE fund_applications ADD COLUMN project_id (NULLABLE)
    op.add_column(
        "fund_applications",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fund_applications_project_id_fkey",
        "fund_applications",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "idx_fund_applications_project_id",
        "fund_applications",
        ["project_id"],
    )

    # 4. Backfill : pour chaque fund_application avec project_id IS NULL,
    #    créer un projet auto-généré et le lier.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # CTE PostgreSQL : créer 1 projet par application orpheline
        bind.execute(sa.text("""
            WITH inserted_projects AS (
              INSERT INTO projects (
                id, account_id, name, description, objective_env,
                status, auto_generated, created_at, updated_at
              )
              SELECT
                gen_random_uuid(),
                fa.account_id,
                LEFT(
                  'Projet hérité — ' || COALESCE(f.name, '(fonds inconnu)') ||
                  ' (' || TO_CHAR(fa.created_at, 'YYYY-MM') || ')',
                  200
                ) AS name,
                COALESCE(
                  (fa.sections::jsonb ->> 'summary'),
                  'Projet créé automatiquement lors de la migration F06.'
                ) AS description,
                '[]'::jsonb AS objective_env,
                CASE
                  WHEN fa.status::text = 'accepted' THEN 'funded'
                  ELSE 'seeking_funding'
                END AS status,
                TRUE AS auto_generated,
                fa.created_at,
                fa.updated_at
              FROM fund_applications fa
              LEFT JOIN funds f ON f.id = fa.fund_id
              WHERE fa.project_id IS NULL
              RETURNING id, account_id, created_at
            )
            -- liaison fund_applications ↔ projets nouvellement créés
            UPDATE fund_applications fa
            SET project_id = ip.id
            FROM inserted_projects ip
            WHERE fa.project_id IS NULL
              AND fa.account_id = ip.account_id
              AND fa.created_at = ip.created_at;
        """))
        # Note : la jointure sur (account_id, created_at) suppose que
        # 2 applications du même compte ne sont pas créées au même millisecond.
        # En pratique, on peut renforcer en générant les projets et la liaison
        # dans un Python loop si la concurrence pose problème.

        # Pour les applications restantes (ex. account_id NULL — ne devrait pas
        # arriver post-F02, mais défense en profondeur), on log un warning sans bloquer.
        result = bind.execute(sa.text("""
            SELECT COUNT(*) FROM fund_applications WHERE project_id IS NULL
        """))
        remaining = result.scalar()
        if remaining > 0:
            print(
                f"[F06 migration] WARNING : {remaining} fund_applications "
                "n'ont pas pu être backfillées (account_id NULL ou autre)."
            )
    else:
        # SQLite (tests) : Python loop équivalent
        from sqlalchemy import select, insert, update
        from datetime import datetime

        # Tables réflectées
        meta = sa.MetaData()
        meta.reflect(bind=bind)
        applications_t = meta.tables["fund_applications"]
        funds_t = meta.tables["funds"]
        projects_t = meta.tables["projects"]

        orphans = bind.execute(
            sa.select(applications_t).where(applications_t.c.project_id.is_(None))
        ).fetchall()
        for app in orphans:
            fund = bind.execute(
                sa.select(funds_t).where(funds_t.c.id == app.fund_id)
            ).first()
            fund_name = fund.name if fund is not None else "(fonds inconnu)"
            project_id = uuid.uuid4()
            project_status = "funded" if str(app.status) == "accepted" else "seeking_funding"
            created_at = app.created_at
            label = (
                "Projet hérité — "
                f"{fund_name} ({created_at.strftime('%Y-%m') if created_at else '????-??'})"
            )[:200]
            description = "Projet créé automatiquement lors de la migration F06."
            bind.execute(
                sa.insert(projects_t).values(
                    id=project_id,
                    account_id=app.account_id,
                    name=label,
                    description=description,
                    objective_env=[],
                    status=project_status,
                    auto_generated=True,
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
            bind.execute(
                sa.update(applications_t)
                .where(applications_t.c.id == app.id)
                .values(project_id=project_id)
            )

    # 5. ALTER TABLE fund_applications ALTER COLUMN project_id SET NOT NULL
    op.alter_column("fund_applications", "project_id", nullable=False)

    # 6. RLS PostgreSQL (héritée F02) — ENABLE+FORCE + 2 policies par table
    if bind.dialect.name == "postgresql":
        for table in ("projects", "project_documents"):
            bind.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
            bind.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))

        # Policies sur projects
        bind.execute(sa.text("""
            CREATE POLICY pme_access_own_account ON projects
              FOR ALL
              USING (
                current_setting('app.current_account_id', true)::uuid = account_id
                AND current_setting('app.current_role', true) = 'PME'
              );
        """))
        bind.execute(sa.text("""
            CREATE POLICY admin_full_access ON projects
              FOR ALL
              USING (current_setting('app.current_role', true) = 'ADMIN');
        """))

        # Policies sur project_documents (filtrage via FK projects)
        bind.execute(sa.text("""
            CREATE POLICY pme_access_via_project ON project_documents
              FOR ALL
              USING (
                EXISTS (
                  SELECT 1 FROM projects p
                  WHERE p.id = project_documents.project_id
                    AND current_setting('app.current_account_id', true)::uuid = p.account_id
                    AND current_setting('app.current_role', true) = 'PME'
                )
              );
        """))
        bind.execute(sa.text("""
            CREATE POLICY admin_full_access ON project_documents
              FOR ALL
              USING (current_setting('app.current_role', true) = 'ADMIN');
        """))
```

### 3.3 Étapes downgrade (symétrique)

```python
def downgrade() -> None:
    bind = op.get_bind()

    # 1. Drop RLS policies
    if bind.dialect.name == "postgresql":
        for table in ("projects", "project_documents"):
            bind.execute(sa.text(
                f"DROP POLICY IF EXISTS pme_access_own_account ON {table}"
            ))
            bind.execute(sa.text(
                f"DROP POLICY IF EXISTS admin_full_access ON {table}"
            ))
        bind.execute(sa.text(
            "DROP POLICY IF EXISTS pme_access_via_project ON project_documents"
        ))

    # 2. ALTER TABLE fund_applications ALTER COLUMN project_id DROP NOT NULL
    op.alter_column("fund_applications", "project_id", nullable=True)

    # 3. DROP CONSTRAINT FK + INDEX
    op.drop_index("idx_fund_applications_project_id", "fund_applications")
    op.drop_constraint(
        "fund_applications_project_id_fkey", "fund_applications", type_="foreignkey"
    )

    # 4. DROP COLUMN
    op.drop_column("fund_applications", "project_id")

    # 5. DROP TABLE project_documents
    op.drop_index("idx_project_documents_document_id", "project_documents")
    op.drop_index("idx_project_documents_project_id", "project_documents")
    op.drop_table("project_documents")

    # 6. DROP TABLE projects
    op.drop_index("idx_projects_account_maturity", "projects")
    op.drop_index("idx_projects_account_status", "projects")
    op.drop_table("projects")
```

### 3.4 Mapping `application.status` → `project.status` (backfill)

| Application status | Project status auto-généré |
|---|---|
| `draft`, `preparing_documents`, `in_progress`, `review` | `seeking_funding` |
| `ready_for_intermediary`, `ready_for_fund`, `submitted_to_intermediary`, `submitted_to_fund`, `under_review` | `seeking_funding` |
| `accepted` | `funded` |
| `rejected` | `seeking_funding` (la PME peut retenter) |

Le SQL utilise un `CASE WHEN fa.status::text = 'accepted' THEN 'funded' ELSE 'seeking_funding' END` pour simplifier.

## 4. Schémas Pydantic v2 strict (`backend/app/modules/projects/schemas.py`)

```python
"""Schémas Pydantic strict pour le module Projects (F06)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.money import Money

# Whitelists (parallèles aux enums du modèle)
OBJECTIVE_ENV_VALUES = {
    "mitigation", "adaptation", "biodiversity", "circular_economy",
    "water", "renewable_energy", "sustainable_agriculture", "mixed",
}
MATURITY_VALUES = {
    "ideation", "pre_feasibility", "pilot", "scale", "replication",
}
STATUS_VALUES = {
    "draft", "seeking_funding", "funded", "in_execution", "closed", "cancelled",
}
FINANCING_STRUCTURE_VALUES = {
    "subvention", "pret_concessionnel", "equity", "blending", "mixte",
}
DOC_TYPE_VALUES = {
    "feasibility_study", "business_plan", "impact_assessment",
    "support_letter", "other",
}


class ProjectBase(BaseModel):
    """Base partagée par Create / Update / Read."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=200)]
    description: str | None = None
    objective_env: list[str] = Field(default_factory=list)
    maturity: str | None = None
    status: str = "draft"
    target_amount: Money | None = None  # Money typed F04
    duration_months: Annotated[int | None, Field(default=None, gt=0)] = None
    financing_structure: str | None = None
    expected_impact_tco2e: Annotated[Decimal | None, Field(default=None, ge=0)] = None
    expected_jobs_created: Annotated[int | None, Field(default=None, ge=0)] = None
    expected_beneficiaries: Annotated[int | None, Field(default=None, ge=0)] = None
    expected_hectares_restored: Annotated[Decimal | None, Field(default=None, ge=0)] = None
    expected_other_impacts: dict[str, Any] | None = None
    location_country: Annotated[str | None, Field(default=None, min_length=2, max_length=2)] = None
    location_region: Annotated[str | None, Field(default=None, max_length=100)] = None

    @field_validator("objective_env")
    @classmethod
    def validate_objective_env(cls, v: list[str]) -> list[str]:
        for o in v:
            if o not in OBJECTIVE_ENV_VALUES:
                raise ValueError(
                    f"objective_env value '{o}' not in {OBJECTIVE_ENV_VALUES}"
                )
        return v

    @field_validator("maturity")
    @classmethod
    def validate_maturity(cls, v: str | None) -> str | None:
        if v is not None and v not in MATURITY_VALUES:
            raise ValueError(f"maturity must be in {MATURITY_VALUES}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in STATUS_VALUES:
            raise ValueError(f"status must be in {STATUS_VALUES}")
        return v

    @field_validator("financing_structure")
    @classmethod
    def validate_financing_structure(cls, v: str | None) -> str | None:
        if v is not None and v not in FINANCING_STRUCTURE_VALUES:
            raise ValueError(
                f"financing_structure must be in {FINANCING_STRUCTURE_VALUES}"
            )
        return v

    @field_validator("location_country")
    @classmethod
    def validate_country(cls, v: str | None) -> str | None:
        if v is not None and not v.isalpha():
            raise ValueError("location_country must be 2 ISO alpha letters")
        if v is not None:
            return v.upper()
        return v


class ProjectCreate(ProjectBase):
    """Payload de création."""

    pass  # hérite de ProjectBase ; status défaut 'draft'


class ProjectUpdate(BaseModel):
    """Payload de mise à jour partielle. Aucun champ obligatoire."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: Annotated[str | None, Field(default=None, min_length=1, max_length=200)] = None
    description: str | None = None
    objective_env: list[str] | None = None
    maturity: str | None = None
    status: str | None = None
    target_amount: Money | None = None
    duration_months: Annotated[int | None, Field(default=None, gt=0)] = None
    financing_structure: str | None = None
    expected_impact_tco2e: Annotated[Decimal | None, Field(default=None, ge=0)] = None
    expected_jobs_created: Annotated[int | None, Field(default=None, ge=0)] = None
    expected_beneficiaries: Annotated[int | None, Field(default=None, ge=0)] = None
    expected_hectares_restored: Annotated[Decimal | None, Field(default=None, ge=0)] = None
    expected_other_impacts: dict[str, Any] | None = None
    location_country: Annotated[str | None, Field(default=None, min_length=2, max_length=2)] = None
    location_region: Annotated[str | None, Field(default=None, max_length=100)] = None

    # Validators identiques à ProjectBase pour les champs concernés.
    # (omis ici pour brièveté ; même implémentation)


class ProjectSummary(BaseModel):
    """Réponse résumée pour les listes (cards)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: str
    maturity: str | None
    objective_env: list[str]
    target_amount: Money | None
    expected_impact_tco2e: Decimal | None
    auto_generated: bool
    applications_count: int = 0  # calculé par le service
    created_at: datetime


class ProjectDetail(ProjectBase):
    """Réponse détaillée."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    auto_generated: bool
    created_at: datetime
    updated_at: datetime
    project_documents: list["ProjectDocumentRead"] = Field(default_factory=list)
    applications_count: int = 0


class ProjectDocumentRead(BaseModel):
    """Lien projet ↔ document."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    document_id: uuid.UUID
    doc_type: str
    created_at: datetime


class DeleteResult(BaseModel):
    """Résultat de DELETE /api/projects/{id}."""

    ok: bool
    blocked_by: list["BlockedApplication"] = Field(default_factory=list)
    hint: str | None = None


class BlockedApplication(BaseModel):
    """Application bloquante pour la suppression."""

    application_id: uuid.UUID
    fund_name: str
    status: str


class DuplicateProjectRequest(BaseModel):
    """Payload de POST /api/projects/{id}/duplicate."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    new_name: Annotated[str | None, Field(default=None, min_length=1, max_length=200)] = None


class ProjectFilters(BaseModel):
    """Query params de GET /api/projects."""

    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    maturity: str | None = None
    objective_env: str | None = None  # filtre exact sur 1 valeur
    auto_generated: bool | None = None
    page: Annotated[int, Field(default=1, ge=1)] = 1
    limit: Annotated[int, Field(default=25, ge=1, le=100)] = 25


class ProjectListResponse(BaseModel):
    """Liste paginée de projets."""

    items: list[ProjectSummary]
    total: int
    page: int
    limit: int


# Forward refs
ProjectDetail.model_rebuild()
DeleteResult.model_rebuild()
```

## 5. Modèle conceptuel post-F06

```text
Account (F02)
  │
  └──< User (F02)
  │
  └──< CompanyProfile (existant)
  │
  └──< Project (F06)               ← NOUVEAU
            │
            ├──< ProjectDocument >── Document (existant)
            │
            └──< FundApplication (refactor)
                       │
                       ├── Fund (existant)
                       └── Intermediary (existant, optionnel)
```

## 6. Indexes complets

| Table | Index | Type | Colonnes |
|-------|-------|------|----------|
| projects | idx_projects_account_status | btree | (account_id, status) |
| projects | idx_projects_account_maturity | btree | (account_id, maturity) |
| projects | (FK auto) | btree | (account_id) — FK accounts |
| project_documents | idx_project_documents_project_id | btree | (project_id) |
| project_documents | idx_project_documents_document_id | btree | (document_id) |
| project_documents | project_documents_unique | btree UNIQUE | (project_id, document_id) |
| fund_applications | idx_fund_applications_project_id | btree | (project_id) — NEW F06 |

## 7. Audit log F03

### Modèles audités
- `Project` → ajouté à `AUDITABLE_MODELS` dans `app/core/auditable.py`.
- `ProjectDocument` → ajouté à `EXEMPT_MODELS` (table de jointure pure).

### Métadonnées tool LangChain (FR-035)
Lors d'une mutation via tool `create_project`, l'helper `actor_metadata` est enrichi avec :
```python
actor_metadata = {
    "tool_name": "create_project",
    "conversation_id": str(conversation_id) if conversation_id else None,
    "request_id": request_id,
}
```
Cohérent avec le pattern existant `app/api/audit_context_middleware.py` (F03).

## 8. Compatibilité tests SQLite

### Stratégies
- `JSONType = JSONB().with_variant(JSON(), "sqlite")` : bascule automatique.
- VARCHAR + CHECK applicatif : pas d'ENUM PG natif.
- RLS : skip via `if bind.dialect.name == "postgresql":` dans la migration.
- Backfill SQL CTE : remplacé par Python loop sur SQLite (cf. § 3.2).

### Tests SQLite garantis
- `test_project_model.py` (modèle SQLAlchemy + contraintes Pydantic) : SQLite OK.
- `test_project_schemas.py` (Pydantic strict) : pas de DB.
- `test_project_crud.py` (CRUD via service) : SQLite in-memory OK.
- `test_alembic_f06.py` (round-trip) : exécuté sur PostgreSQL local en CI.

### Tests PostgreSQL uniquement
- `test_project_rls_cross_tenant.py` (RLS PG only).
- `test_alembic_f06_postgres.py` (CTE backfill PG only).
