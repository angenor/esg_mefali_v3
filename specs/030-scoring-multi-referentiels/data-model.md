# Phase 1 — Data Model : F13 Scoring ESG Multi-Référentiels

**Date** : 2026-05-07
**Spec** : [spec.md](./spec.md)
**Plan** : [plan.md](./plan.md)
**Research** : [research.md](./research.md)

## Vue d'ensemble

F13 introduit **1 nouvelle table** (`referential_scores`) et étend le seed de la table existante `referentials` (F01) avec les 5 référentiels MVP. Aucune autre modification de schéma. Les colonnes legacy `esg_assessments.overall_score|environment_score|social_score|governance_score` sont **préservées** 2 sprints en deprecated.

## DDL — Table `referential_scores` (NEW)

```sql
-- Type ENUM
CREATE TYPE referential_score_computed_by_enum AS ENUM ('manual', 'llm', 'auto');

-- Table principale
CREATE TABLE referential_scores (
    -- Identifiants
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id              UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    assessment_id           UUID NOT NULL REFERENCES esg_assessments(id) ON DELETE CASCADE,
    referential_id          UUID NOT NULL REFERENCES referentials(id) ON DELETE RESTRICT,

    -- Versioning F04
    referential_version     VARCHAR(32) NOT NULL,  -- semver snapshot, ex: "1.2.0"
    superseded_by           UUID NULL REFERENCES referential_scores(id) ON DELETE SET NULL,

    -- Score
    overall_score           NUMERIC(5, 2) NULL,    -- 0..100, NULL si coverage_rate=0
    pillar_scores           JSONB NOT NULL DEFAULT '{}'::jsonb,
    coverage_rate           NUMERIC(4, 3) NOT NULL CHECK (coverage_rate >= 0 AND coverage_rate <= 1),
    covered_criteria        JSONB NOT NULL DEFAULT '[]'::jsonb,
    missing_criteria        JSONB NOT NULL DEFAULT '[]'::jsonb,
    gap_to_threshold        NUMERIC(5, 2) NULL,    -- positif si overall_score >= threshold, NULL si overall_score IS NULL
    eligibility             BOOLEAN NULL,          -- TRUE si overall_score >= referentials.threshold, NULL si overall_score IS NULL

    -- Provenance du calcul
    computed_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    computed_by             referential_score_computed_by_enum NOT NULL,
    computed_request_id     UUID NULL,             -- traçabilité du job background

    -- Audit timestamps
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index unique partiel : un seul score "courant" par couple (assessment_id, referential_id)
CREATE UNIQUE INDEX idx_referential_scores_current
    ON referential_scores (assessment_id, referential_id)
    WHERE superseded_by IS NULL;

-- Index pour tri chronologique
CREATE INDEX idx_referential_scores_assessment_computed_at
    ON referential_scores (assessment_id, computed_at DESC);

-- Index pour stats admin (PMEs avec score IFC > 60 cette semaine, etc.)
CREATE INDEX idx_referential_scores_referential_computed_at
    ON referential_scores (referential_id, computed_at DESC);

-- Index pour requêtes RLS
CREATE INDEX idx_referential_scores_account_id
    ON referential_scores (account_id);

-- RLS PostgreSQL (F02 invariant)
ALTER TABLE referential_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE referential_scores FORCE ROW LEVEL SECURITY;

CREATE POLICY referential_scores_account_isolation ON referential_scores
    FOR ALL
    USING (
        account_id = current_setting('app.current_account_id', true)::uuid
        OR current_setting('app.bypass_rls', true) = 'true'
    );

-- Trigger updated_at (réutilise la function utilitaire existante)
CREATE TRIGGER trigger_referential_scores_updated_at
    BEFORE UPDATE ON referential_scores
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Commentaires (documentation BDD)
COMMENT ON TABLE referential_scores IS
    'Résultat du calcul d''un référentiel pour une évaluation ESG donnée. Lie EsgAssessment et Referential avec snapshot de la version (F04). Pattern superseded_by pour historisation.';
COMMENT ON COLUMN referential_scores.referential_version IS
    'Snapshot semver de referentials.version au moment du calcul (F04 traçabilité).';
COMMENT ON COLUMN referential_scores.coverage_rate IS
    'Ratio indicateurs renseignés / indicateurs liés au référentiel (0..1). Si < 0.5, badge orange UI.';
COMMENT ON COLUMN referential_scores.superseded_by IS
    'FK self-référente : NULL = score courant, UUID = pointe vers la version qui remplace cet historique (F04 pattern).';
COMMENT ON COLUMN referential_scores.gap_to_threshold IS
    'overall_score - referentials.threshold ; positif = éligible, négatif = à améliorer.';
```

## DDL — Modifications de tables existantes

**Aucune.** Les tables `referentials`, `indicators`, `referential_indicators` (F01), `esg_assessments` (F05), `funds`/`intermediaries`/`offers` (F07), `accounts` (F02), `audit_log` (F03), `reminders` (F11), `tool_call_logs` (F12) restent inchangées.

Note : les colonnes legacy `esg_assessments.overall_score|environment_score|social_score|governance_score` sont **préservées** par F13 (cf. FR-024 et FR-065). Une migration ultérieure (post-F13) les supprimera.

## Seed — Référentiels MVP

```sql
-- Constante UUID stable pour Mefali (capturée dans backend/app/core/constants.py)
-- MEFALI_REFERENTIAL_UUID = '00000000-0000-0000-0000-000000000001'

-- Mefali (idempotent ; pré-condition pour le backfill)
INSERT INTO referentials (id, code, name, version, is_active, threshold, min_coverage_for_pdf, description, created_at, updated_at)
VALUES (
    '00000000-0000-0000-0000-000000000001'::uuid,
    'mefali',
    'ESG Mefali',
    '1.0.0',
    TRUE,
    50.00,
    0.500,
    'Référentiel synthétique Mefali (vue par défaut). 30 critères E/S/G adaptés au contexte africain UEMOA/CEDEAO.',
    NOW(),
    NOW()
)
ON CONFLICT (code) DO NOTHING;

-- 4 référentiels MVP supplémentaires (idempotent ; ne perturbe pas si F01 a déjà seedé)
INSERT INTO referentials (code, name, version, is_active, threshold, min_coverage_for_pdf, description, created_at, updated_at)
VALUES
    ('gcf', 'Green Climate Fund', '1.0.0', TRUE, 60.00, 0.500,
     'Référentiel GCF (Green Climate Fund) pour mitigation et adaptation climatique. Critères : impact paradigmatique, additionnalité financière, durabilité du développement, besoins du pays récipiendaire.', NOW(), NOW()),
    ('ifc_ps', 'IFC Performance Standards 2012', '1.0.0', TRUE, 60.00, 0.500,
     'Référentiel IFC Performance Standards 2012 (8 piliers PS1-PS8). Évaluation des risques environnementaux et sociaux pour les projets financés par la Banque Mondiale.', NOW(), NOW()),
    ('boad_ess', 'BOAD ESS', '1.0.0', TRUE, 55.00, 0.500,
     'Référentiel ESS (Environnement et Sustainable Standards) de la Banque Ouest-Africaine de Développement. Adapté aux PME UEMOA, intègre les taxonomies vertes BCEAO.', NOW(), NOW()),
    ('gri_2021', 'GRI 2021', '1.0.0', TRUE, 50.00, 0.500,
     'Référentiel Global Reporting Initiative 2021. Standards internationaux de reporting de durabilité (GRI 1-3 universels + topic-specific).', NOW(), NOW())
ON CONFLICT (code) DO NOTHING;
```

Note : les indicateurs et liaisons `referential_indicators` sont seedés par F01 (pas par F13). Si F01 ne les a pas livrés, les calculs retournent `coverage_rate=0` et l'UI cache la card.

## Backfill — Migration de l'historique vers `referential_scores`

```sql
-- Pour chaque EsgAssessment existante, créer une ligne referential_scores Mefali
-- (idempotent via ON CONFLICT)
INSERT INTO referential_scores (
    account_id, assessment_id, referential_id, referential_version,
    overall_score, pillar_scores, coverage_rate, covered_criteria, missing_criteria,
    gap_to_threshold, eligibility, computed_at, computed_by, superseded_by
)
SELECT
    a.account_id,
    a.id AS assessment_id,
    '00000000-0000-0000-0000-000000000001'::uuid AS referential_id,  -- MEFALI_REFERENTIAL_UUID
    '1.0.0' AS referential_version,
    a.overall_score,
    jsonb_build_object(
        'environment', jsonb_build_object('score', COALESCE(a.environment_score, 0), 'weight', 0.33, 'criteria_count', 0, 'criteria_renseignés', 0),
        'social', jsonb_build_object('score', COALESCE(a.social_score, 0), 'weight', 0.33, 'criteria_count', 0, 'criteria_renseignés', 0),
        'governance', jsonb_build_object('score', COALESCE(a.governance_score, 0), 'weight', 0.34, 'criteria_count', 0, 'criteria_renseignés', 0)
    ) AS pillar_scores,
    COALESCE(0.000, 0)::numeric(4,3) AS coverage_rate,  -- legacy, pas de tracking pré-F13
    '[]'::jsonb AS covered_criteria,
    '[]'::jsonb AS missing_criteria,
    CASE WHEN a.overall_score IS NOT NULL THEN a.overall_score - 50 ELSE NULL END AS gap_to_threshold,
    CASE WHEN a.overall_score IS NOT NULL THEN a.overall_score >= 50 ELSE NULL END AS eligibility,
    COALESCE(a.completed_at, a.created_at) AS computed_at,
    'auto'::referential_score_computed_by_enum AS computed_by,
    NULL AS superseded_by
FROM esg_assessments a
WHERE a.overall_score IS NOT NULL
ON CONFLICT (assessment_id, referential_id) WHERE superseded_by IS NULL DO NOTHING;
```

Note : le ON CONFLICT cible l'index unique partiel `idx_referential_scores_current`. Si la migration est rejouée (idempotence), aucune duplication.

## Modèle SQLAlchemy

`backend/app/models/referential_score.py` :

```python
"""Modèle SQLAlchemy pour ReferentialScore (F13)."""
from __future__ import annotations
import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint, DateTime, Enum, ForeignKey, Index, Numeric, String, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.esg import EsgAssessment
    from app.models.referential import Referential


class ComputedByEnum(str, enum.Enum):
    """Source du calcul du score."""
    MANUAL = "manual"
    LLM = "llm"
    AUTO = "auto"


class ReferentialScore(Base):
    """Score d'un référentiel pour une évaluation ESG."""
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
        index=True,
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
    referential_version: Mapped[str] = mapped_column(String(32), nullable=False)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("referential_scores.id", ondelete="SET NULL"),
        nullable=True,
    )

    overall_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    pillar_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    coverage_rate: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    covered_criteria: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    missing_criteria: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    gap_to_threshold: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    eligibility: Mapped[bool | None] = mapped_column(nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    computed_by: Mapped[ComputedByEnum] = mapped_column(
        Enum(ComputedByEnum, name="referential_score_computed_by_enum"),
        nullable=False,
    )
    computed_request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

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
    account: Mapped["Account"] = relationship("Account", back_populates="referential_scores")
    assessment: Mapped["EsgAssessment"] = relationship("EsgAssessment", back_populates="referential_scores")
    referential: Mapped["Referential"] = relationship("Referential")
    superseded_by_rel: Mapped["ReferentialScore | None"] = relationship(
        "ReferentialScore",
        remote_side="ReferentialScore.id",
        foreign_keys=[superseded_by],
    )

    __table_args__ = (
        # Index unique partiel pour le score courant
        Index(
            "idx_referential_scores_current",
            "assessment_id", "referential_id",
            unique=True,
            postgresql_where="superseded_by IS NULL",
        ),
        Index("idx_referential_scores_assessment_computed_at", "assessment_id", "computed_at"),
        Index("idx_referential_scores_referential_computed_at", "referential_id", "computed_at"),
        CheckConstraint("coverage_rate >= 0 AND coverage_rate <= 1", name="ck_referential_scores_coverage_rate_range"),
    )

    def __repr__(self) -> str:
        return (
            f"<ReferentialScore id={self.id} assessment={self.assessment_id} "
            f"referential={self.referential_id} score={self.overall_score} "
            f"coverage={self.coverage_rate} version={self.referential_version}>"
        )
```

## Schémas Pydantic

`backend/app/schemas/referential_score.py` :

```python
"""Schémas Pydantic pour ReferentialScore (F13)."""
from __future__ import annotations
import enum
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ComputedBy(str, enum.Enum):
    MANUAL = "manual"
    LLM = "llm"
    AUTO = "auto"


class PillarScore(BaseModel):
    """Score d'un pilier (E/S/G ou autre selon référentiel)."""
    score: Decimal = Field(ge=0, le=100)
    weight: Decimal = Field(ge=0, le=1)
    criteria_count: int = Field(ge=0)
    criteria_renseignés: int = Field(ge=0)


class CoveredCriterion(BaseModel):
    """Critère couvert (indicateur renseigné)."""
    indicator_id: uuid.UUID
    indicator_code: str
    score: Decimal = Field(ge=0, le=100)
    weight: Decimal = Field(ge=0, le=1)
    source_id: uuid.UUID  # F01 traçabilité


class MissingReason(str, enum.Enum):
    NON_RENSEIGNE = "non_renseigne"
    INVALIDE = "invalide"
    HORS_SCOPE = "hors_scope"


class MissingCriterion(BaseModel):
    """Critère manquant (indicateur non renseigné ou invalide)."""
    indicator_id: uuid.UUID
    indicator_code: str
    reason: MissingReason
    source_id: uuid.UUID  # F01 traçabilité
    suggestion: str | None = None


class ReferentialScoreRead(BaseModel):
    """ReferentialScore exposé en lecture API."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assessment_id: uuid.UUID
    referential_id: uuid.UUID
    referential_code: str  # via jointure
    referential_name: str  # via jointure
    referential_version: str

    overall_score: Decimal | None
    pillar_scores: dict[str, PillarScore]
    coverage_rate: Decimal
    covered_criteria: list[CoveredCriterion]
    missing_criteria: list[MissingCriterion]
    gap_to_threshold: Decimal | None
    eligibility: bool | None

    computed_at: datetime
    computed_by: ComputedBy
    computed_request_id: uuid.UUID | None

    is_fallback: bool = False  # exposé seulement pour compute_referential_score_for_offer


class ReferentialScoreCreate(BaseModel):
    """Création interne (pour le service, pas exposé en API)."""
    account_id: uuid.UUID
    assessment_id: uuid.UUID
    referential_id: uuid.UUID
    referential_version: str
    overall_score: Decimal | None
    pillar_scores: dict[str, PillarScore]
    coverage_rate: Decimal
    covered_criteria: list[CoveredCriterion]
    missing_criteria: list[MissingCriterion]
    gap_to_threshold: Decimal | None
    eligibility: bool | None
    computed_by: ComputedBy
    computed_request_id: uuid.UUID | None = None


class ComparisonResult(BaseModel):
    """Résultat du tool compare_referentials."""
    scores: list[ReferentialScoreRead]
    gaps: dict[str, Decimal]  # ex: {"mefali_vs_ifc_ps": 26.0}
    divergent_criteria: dict[str, list[CoveredCriterion]]  # critères couverts par un ref mais pas l'autre


class RecomputeRequestResponse(BaseModel):
    """Réponse 202 Accepted lors d'un recalcul async."""
    status: str = "accepted"
    recompute_request_id: uuid.UUID
    referentials_to_recompute: list[str]  # codes des référentiels concernés
    estimated_duration_seconds: int = 5


class FinalizeAssessmentResult(BaseModel):
    """Résultat du tool finalize_esg_assessment."""
    assessment_id: uuid.UUID
    finalized_at: datetime
    referential_scores: list[ReferentialScoreRead]
    failures: list[dict]  # éventuels référentiels qui ont échoué (atomicité par référentiel)


class BottleneckInfo(BaseModel):
    """Information sur le goulot d'étranglement entre 2 référentiels (offer)."""
    bottleneck_referential_code: str
    bottleneck_referential_name: str
    bottleneck_score: Decimal
    other_referential_code: str
    other_referential_score: Decimal
    gap: Decimal
    eligibility_min: bool
    top_3_critical_indicators: list[str]  # codes des indicateurs prioritaires à renseigner


class DualReferentialResponse(BaseModel):
    """Réponse de compute_referential_score_for_offer."""
    fund_score: ReferentialScoreRead
    intermediary_score: ReferentialScoreRead | None
    bottleneck: BottleneckInfo | None
    is_dual_view: bool  # FALSE si fund.referential == intermediary.referential
```

## Relations

```
accounts (F02)
   ↑ ON DELETE CASCADE
   |
   referential_scores  ◄────────► referentials (F01) [ON DELETE RESTRICT]
   ↑ ON DELETE CASCADE
   |
   esg_assessments (F05)

referential_scores ◄────self-référence (superseded_by) ON DELETE SET NULL

referentials ◄────► referential_indicators (F01) ◄────► indicators (F01)

audit_log (F03) ← événements 'referential_score_recompute_failed', 'referential_score_recompute_partial', 'dual_view_fallback_used', 'cron_referential_version_evolution'

reminders (F11) ← reminders kind='referential_version_evolved' (créés par cron F13)

tool_call_logs (F12) ← logs des 3 tools LangChain F13
```

## Constantes Backend

`backend/app/core/constants.py` (extension) :

```python
import uuid

# F13 — Codes des référentiels MVP
MEFALI_REFERENTIAL_CODE = "mefali"
GCF_REFERENTIAL_CODE = "gcf"
IFC_PS_REFERENTIAL_CODE = "ifc_ps"
BOAD_ESS_REFERENTIAL_CODE = "boad_ess"
GRI_2021_REFERENTIAL_CODE = "gri_2021"

REFERENTIAL_CODES_MVP = [
    MEFALI_REFERENTIAL_CODE,
    GCF_REFERENTIAL_CODE,
    IFC_PS_REFERENTIAL_CODE,
    BOAD_ESS_REFERENTIAL_CODE,
    GRI_2021_REFERENTIAL_CODE,
]

# UUID stable de Mefali (pour le backfill et le fallback)
MEFALI_REFERENTIAL_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# Seuils par défaut
DEFAULT_MIN_COVERAGE_FOR_PDF = 0.5
DEFAULT_REFERENTIAL_THRESHOLD = 50.0
```

## Cardinalités

- 1 `EsgAssessment` (F05) → N `ReferentialScore` (1 par référentiel actif au moment du calcul ; ~5-7 en MVP).
- 1 `Account` (F02) → N `ReferentialScore` (via cascade `EsgAssessment` → `ReferentialScore`).
- 1 `Referential` (F01) → N `ReferentialScore` (toutes les PMEs ayant calculé ce référentiel).
- 1 `ReferentialScore` ↔ 0..1 `ReferentialScore` via `superseded_by` (chaîne d'historique).

## Invariants techniques (vérifiés par tests)

1. **Un seul score courant par couple** : `COUNT(*) FROM referential_scores WHERE assessment_id=X AND referential_id=Y AND superseded_by IS NULL ≤ 1` (garanti par index unique partiel).
2. **Cascade RGPD** : suppression d'`EsgAssessment` → suppression CASCADE de tous ses `ReferentialScore`.
3. **Pas de suppression de référentiel** : `referential_id` ON DELETE RESTRICT empêche la suppression d'un référentiel qui a des scores historiques (admin doit soft-delete via `is_active=false`).
4. **Cohérence Mefali ↔ legacy 2 sprints** : `referential_scores[Mefali].overall_score == esg_assessments.overall_score` après chaque calcul (vérifié par `test_legacy_columns_equality.py`).
5. **RLS multi-tenant** : aucune fuite cross-account (vérifié par `test_referential_scores_rls.py`).
6. **Coverage rate borné** : CHECK constraint `coverage_rate BETWEEN 0 AND 1`.
7. **Versioning F04** : le `referential_version` est un snapshot ; il ne change jamais après création ; les évolutions de version créent une nouvelle ligne avec `superseded_by` pointant vers la version remplacée.
