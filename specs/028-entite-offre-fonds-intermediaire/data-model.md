# Phase 1 — Data Model : F07 Entité Offre = Couple Fonds × Intermédiaire

**Date** : 2026-05-07
**Branch** : `feat/F07-entite-offre-fonds-intermediaire`
**Migration Alembic** : `028_offers_and_enrich_fund_intermediary.py` (down_revision = `027_consents_and_account_deletion`)

## Vue d'ensemble

Cette feature introduit **1 nouvelle table** (`offers`) et **enrichit 4 tables existantes** (`funds`, `intermediaries`, `fund_intermediaries`, `fund_applications`). Tous les changements sont **réversibles** via `alembic downgrade`. Les colonnes legacy (`min_amount_xof`, `typical_fees`) sont conservées en deprecated 2 sprints.

## Nouvelle entité : `Offer`

### Table `offers`

```sql
CREATE TABLE offers (
    -- Identité
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Couplage Fonds × Intermédiaire (les 2 NOT NULL)
    fund_id UUID NOT NULL REFERENCES funds(id) ON DELETE RESTRICT,
    intermediary_id UUID NOT NULL REFERENCES intermediaries(id) ON DELETE RESTRICT,

    -- Métadonnées
    name VARCHAR(200) NOT NULL,
    accepted_languages JSONB NOT NULL DEFAULT '["FR"]'::jsonb,
    target_sector JSONB,  -- nullable, optionnellement plus restrictif que fund.sectors_eligible
    notes TEXT,

    -- Champs effectifs calculés (cachés pour perf)
    effective_criteria JSONB NOT NULL DEFAULT '{}'::jsonb,
    effective_required_documents JSONB NOT NULL DEFAULT '[]'::jsonb,
    effective_fees JSONB NOT NULL DEFAULT '{}'::jsonb,
    effective_processing_time_days_min INT,
    effective_processing_time_days_max INT,
    effective_disbursement_time_days_min INT,
    effective_disbursement_time_days_max INT,

    -- Statut commercial
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    publication_status VARCHAR(20) NOT NULL DEFAULT 'draft',  -- 'draft' | 'published'

    -- F01 — Sourçage obligatoire
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,

    -- F04 — Versioning catalogue (via VersioningMixin)
    version VARCHAR(50) NOT NULL DEFAULT '1.0',
    valid_from DATE NOT NULL DEFAULT CURRENT_DATE,
    valid_to DATE,
    superseded_by UUID REFERENCES offers(id) ON DELETE SET NULL,

    -- Timestamps (TimestampMixin)
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Contraintes
    CONSTRAINT offers_publication_status_chk
        CHECK (publication_status IN ('draft', 'published')),
    CONSTRAINT offers_processing_time_consistency_chk
        CHECK (effective_processing_time_days_min IS NULL
               OR effective_processing_time_days_max IS NULL
               OR effective_processing_time_days_min <= effective_processing_time_days_max),
    CONSTRAINT offers_disbursement_time_consistency_chk
        CHECK (effective_disbursement_time_days_min IS NULL
               OR effective_disbursement_time_days_max IS NULL
               OR effective_disbursement_time_days_min <= effective_disbursement_time_days_max),
    CONSTRAINT offers_published_active_chk
        CHECK (publication_status = 'draft' OR is_active = TRUE)
);

-- Indexes
CREATE UNIQUE INDEX uq_offers_fund_intermediary_version
    ON offers (fund_id, intermediary_id, version);
CREATE INDEX idx_offers_publication_active
    ON offers (publication_status, is_active)
    WHERE publication_status = 'published' AND is_active = TRUE;
CREATE INDEX idx_offers_fund_intermediary_valid_to
    ON offers (fund_id, intermediary_id, valid_to);
CREATE INDEX idx_offers_theme_gin
    ON offers USING gin (effective_criteria jsonb_path_ops);  -- theme stocké dans effective_criteria.theme
CREATE INDEX idx_offers_name_fts
    ON offers USING gin (to_tsvector('french', name));
```

### Modèle SQLAlchemy `Offer`

```python
# backend/app/models/offer.py
import uuid
from datetime import date
from typing import Any

from sqlalchemy import (
    Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.source import JSONType, PublicationStatus
from app.models.versioning_mixin import VersioningMixin


class Offer(UUIDMixin, TimestampMixin, VersioningMixin, Base):
    """Offre = couple Fonds × Intermédiaire.
    
    F07 : entité commercialement actionnable côté PME.
    Catalogue global (pas d'account_id), édition admin only.
    """

    __tablename__ = "offers"

    fund_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("funds.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    intermediary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intermediaries.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    accepted_languages: Mapped[list[str]] = mapped_column(
        JSONType, nullable=False, server_default='["FR"]', default=lambda: ["FR"],
    )
    target_sector: Mapped[list[str] | None] = mapped_column(JSONType, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    effective_criteria: Mapped[dict[str, Any]] = mapped_column(
        JSONType, nullable=False, server_default="{}", default=dict,
    )
    effective_required_documents: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONType, nullable=False, server_default="[]", default=list,
    )
    effective_fees: Mapped[dict[str, Any]] = mapped_column(
        JSONType, nullable=False, server_default="{}", default=dict,
    )
    effective_processing_time_days_min: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    effective_processing_time_days_max: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    effective_disbursement_time_days_min: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    effective_disbursement_time_days_max: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true",
    )
    publication_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PublicationStatus.DRAFT.value,
        server_default=PublicationStatus.DRAFT.value,
        index=True,
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Relations
    fund: Mapped["Fund"] = relationship("Fund", lazy="selectin")
    intermediary: Mapped["Intermediary"] = relationship("Intermediary", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("fund_id", "intermediary_id", "version",
                         name="uq_offers_fund_intermediary_version"),
        CheckConstraint(
            "publication_status IN ('draft', 'published')",
            name="offers_publication_status_chk",
        ),
        CheckConstraint(
            "effective_processing_time_days_min IS NULL "
            "OR effective_processing_time_days_max IS NULL "
            "OR effective_processing_time_days_min <= effective_processing_time_days_max",
            name="offers_processing_time_consistency_chk",
        ),
        CheckConstraint(
            "effective_disbursement_time_days_min IS NULL "
            "OR effective_disbursement_time_days_max IS NULL "
            "OR effective_disbursement_time_days_min <= effective_disbursement_time_days_max",
            name="offers_disbursement_time_consistency_chk",
        ),
        CheckConstraint(
            "publication_status = 'draft' OR is_active = TRUE",
            name="offers_published_active_chk",
        ),
        Index("idx_offers_publication_active", "publication_status", "is_active",
              postgresql_where="publication_status = 'published' AND is_active = TRUE"),
        Index("idx_offers_fund_intermediary_valid_to",
              "fund_id", "intermediary_id", "valid_to"),
    )
```

## Enrichissement `Fund`

### Colonnes ajoutées

```sql
ALTER TABLE funds ADD COLUMN instruments JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE funds ADD COLUMN theme JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE funds ADD COLUMN submission_mode VARCHAR(30) NOT NULL DEFAULT 'rolling';
ALTER TABLE funds ADD COLUMN submission_calendar JSONB;
ALTER TABLE funds ADD COLUMN source_id UUID REFERENCES sources(id) ON DELETE RESTRICT;
ALTER TABLE funds ADD COLUMN publication_status VARCHAR(20) NOT NULL DEFAULT 'draft';

-- Contraintes
ALTER TABLE funds ADD CONSTRAINT funds_submission_mode_chk
    CHECK (submission_mode IN ('rolling', 'call_for_proposals'));
ALTER TABLE funds ADD CONSTRAINT funds_publication_status_chk
    CHECK (publication_status IN ('draft', 'published'));

-- Indexes
CREATE INDEX idx_funds_theme_gin ON funds USING gin (theme jsonb_path_ops);
CREATE INDEX idx_funds_instruments_gin ON funds USING gin (instruments jsonb_path_ops);
CREATE INDEX idx_funds_publication_status ON funds (publication_status);
```

### Renommage enum `fund_type`

```sql
-- 1. Création nouveau type
CREATE TYPE fund_type_v2_enum AS ENUM (
    'multilateral', 'bilateral', 'regional', 'national', 'private', 'carbon_marketplace'
);

-- 2. Migration des valeurs existantes
ALTER TABLE funds ALTER COLUMN fund_type TYPE fund_type_v2_enum
USING (
    CASE fund_type::text
        WHEN 'international' THEN 'multilateral'
        WHEN 'regional' THEN 'regional'
        WHEN 'national' THEN 'national'
        WHEN 'carbon_market' THEN 'carbon_marketplace'
        WHEN 'local_bank_green_line' THEN 'private'
        ELSE 'private'  -- safety fallback
    END::fund_type_v2_enum
);

-- 3. Drop ancien type
DROP TYPE fund_type_enum;

-- 4. Rename pour cohérence (optionnel)
ALTER TYPE fund_type_v2_enum RENAME TO fund_type_enum;
```

### Champs Fund post-migration

| Champ | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `instruments` | JSONB | NOT NULL | `'[]'` | Liste : `subvention`, `pret_concessionnel`, `garantie`, `equity`, `blending` |
| `theme` | JSONB | NOT NULL | `'[]'` | Liste : `mitigation`, `adaptation`, `biodiversity`, `circular_economy`, `mixed` |
| `submission_mode` | VARCHAR(30) | NOT NULL | `'rolling'` | Enum : `rolling` \| `call_for_proposals` |
| `submission_calendar` | JSONB | NULL | — | Sessions datées si CFP : `[{name, opens_at, closes_at, status}]` |
| `source_id` | UUID FK | NOT NULL (post-backfill) | — | F01 |
| `publication_status` | VARCHAR(20) | NOT NULL | `'draft'` | F09 |
| `min_amount` (Money typed) | NUMERIC(20,2) + VARCHAR(3) | NULL | — | Existant F04 (cohabitation `_xof` legacy) |
| `max_amount` (Money typed) | NUMERIC(20,2) + VARCHAR(3) | NULL | — | Existant F04 |
| `version`, `valid_from`, `valid_to`, `superseded_by` | — | — | — | Existant F04 |

## Enrichissement `Intermediary`

### Colonnes ajoutées

```sql
ALTER TABLE intermediaries ADD COLUMN code VARCHAR(50);  -- pour singleton DIRECT
ALTER TABLE intermediaries ADD COLUMN required_documents JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE intermediaries ADD COLUMN fees_structured JSONB;
ALTER TABLE intermediaries ADD COLUMN processing_time_days_min INT;
ALTER TABLE intermediaries ADD COLUMN processing_time_days_max INT;
ALTER TABLE intermediaries ADD COLUMN disbursement_time_days_min INT;
ALTER TABLE intermediaries ADD COLUMN disbursement_time_days_max INT;
ALTER TABLE intermediaries ADD COLUMN submission_portal_url VARCHAR(500);
ALTER TABLE intermediaries ADD COLUMN success_rate NUMERIC(5, 4);
ALTER TABLE intermediaries ADD COLUMN total_funded_volume_amount NUMERIC(20, 2);
ALTER TABLE intermediaries ADD COLUMN total_funded_volume_currency VARCHAR(3);
ALTER TABLE intermediaries ADD COLUMN source_id UUID REFERENCES sources(id) ON DELETE RESTRICT;
ALTER TABLE intermediaries ADD COLUMN publication_status VARCHAR(20) NOT NULL DEFAULT 'draft';

-- Contraintes
ALTER TABLE intermediaries ADD CONSTRAINT intermediaries_processing_time_chk
    CHECK (processing_time_days_min IS NULL OR processing_time_days_max IS NULL
           OR processing_time_days_min <= processing_time_days_max);
ALTER TABLE intermediaries ADD CONSTRAINT intermediaries_disbursement_time_chk
    CHECK (disbursement_time_days_min IS NULL OR disbursement_time_days_max IS NULL
           OR disbursement_time_days_min <= disbursement_time_days_max);
ALTER TABLE intermediaries ADD CONSTRAINT intermediaries_success_rate_chk
    CHECK (success_rate IS NULL OR (success_rate >= 0 AND success_rate <= 1));
ALTER TABLE intermediaries ADD CONSTRAINT intermediaries_total_funded_volume_pair_chk
    CHECK ((total_funded_volume_amount IS NULL AND total_funded_volume_currency IS NULL)
           OR (total_funded_volume_amount IS NOT NULL AND total_funded_volume_currency IS NOT NULL));
ALTER TABLE intermediaries ADD CONSTRAINT intermediaries_publication_status_chk
    CHECK (publication_status IN ('draft', 'published'));

-- Index unique sur code (sparse, pour singleton DIRECT)
CREATE UNIQUE INDEX uq_intermediaries_code
    ON intermediaries (code) WHERE code IS NOT NULL;

-- Indexes complémentaires
CREATE INDEX idx_intermediaries_country ON intermediaries (country);
CREATE INDEX idx_intermediaries_publication_status ON intermediaries (publication_status);
```

### Schéma `fees_structured` JSONB

```json
{
  "doc_fee_amount": { "amount": "50000.00", "currency": "XOF" },
  "fee_rate_min": 0.02,
  "fee_rate_max": 0.05,
  "fx_margin": 0.01,
  "guarantee_required_pct": 0.10,
  "source_id": "uuid-here"
}
```

### Schéma `required_documents` JSONB (Intermediary et Fund)

```json
[
  {
    "title": "Statuts juridiques de l'entreprise",
    "source_id": "uuid-here",
    "mandatory": true,
    "format_spec": "PDF, max 10 MB"
  },
  {
    "title": "Plan d'affaires détaillé",
    "source_id": "uuid-here",
    "mandatory": true,
    "format_spec": "PDF ou DOCX"
  }
]
```

## Enrichissement `FundIntermediary`

### Colonnes ajoutées

```sql
ALTER TABLE fund_intermediaries ADD COLUMN accredited_from DATE;
ALTER TABLE fund_intermediaries ADD COLUMN accredited_to DATE;
ALTER TABLE fund_intermediaries ADD COLUMN max_amount_per_fund_amount NUMERIC(20, 2);
ALTER TABLE fund_intermediaries ADD COLUMN max_amount_per_fund_currency VARCHAR(3);
ALTER TABLE fund_intermediaries ADD COLUMN accreditation_source_id UUID REFERENCES sources(id) ON DELETE RESTRICT;

-- Backfill : accredited_from = created_at::date pour les paires existantes
UPDATE fund_intermediaries SET accredited_from = CURRENT_DATE WHERE accredited_from IS NULL;

-- NOT NULL post-backfill
ALTER TABLE fund_intermediaries ALTER COLUMN accredited_from SET NOT NULL;

-- Contraintes
ALTER TABLE fund_intermediaries ADD CONSTRAINT fund_intermediaries_accreditation_dates_chk
    CHECK (accredited_to IS NULL OR accredited_to > accredited_from);
ALTER TABLE fund_intermediaries ADD CONSTRAINT fund_intermediaries_max_amount_pair_chk
    CHECK ((max_amount_per_fund_amount IS NULL AND max_amount_per_fund_currency IS NULL)
           OR (max_amount_per_fund_amount IS NOT NULL AND max_amount_per_fund_currency IS NOT NULL));

-- Indexes
CREATE INDEX idx_fund_intermediaries_accredited_to
    ON fund_intermediaries (accredited_to)
    WHERE accredited_to IS NOT NULL;  -- pour cron expiration
```

## Enrichissement `FundApplication`

### Colonnes ajoutées

```sql
ALTER TABLE fund_applications ADD COLUMN offer_id UUID REFERENCES offers(id) ON DELETE RESTRICT;
CREATE INDEX idx_fund_applications_offer_id ON fund_applications (offer_id);
```

### Backfill (étape post-création offers)

```sql
-- Pour chaque application avec intermediary_id renseigné
UPDATE fund_applications fa
SET offer_id = (
    SELECT o.id FROM offers o
    WHERE o.fund_id = fa.fund_id
      AND o.intermediary_id = fa.intermediary_id
    LIMIT 1
)
WHERE fa.intermediary_id IS NOT NULL AND fa.offer_id IS NULL;

-- Pour chaque application sans intermediary_id (cas direct)
UPDATE fund_applications fa
SET offer_id = (
    SELECT o.id FROM offers o
    JOIN intermediaries i ON o.intermediary_id = i.id
    WHERE o.fund_id = fa.fund_id AND i.code = 'DIRECT'
    LIMIT 1
)
WHERE fa.intermediary_id IS NULL AND fa.offer_id IS NULL;

-- NOT NULL post-backfill
ALTER TABLE fund_applications ALTER COLUMN offer_id SET NOT NULL;
```

## Seed de l'intermédiaire singleton DIRECT

```sql
-- Inséré idempotent dans la migration 028
INSERT INTO intermediaries (
    id, code, name, intermediary_type, organization_type, country, city,
    description, accreditations, services_offered, eligibility_for_sme,
    typical_fees, is_active, source_id, version, valid_from, publication_status,
    required_documents, created_at, updated_at
)
SELECT
    gen_random_uuid(), 'DIRECT', 'Direct (sans intermédiaire)',
    'accredited_entity'::intermediary_type_enum,
    'un_agency'::organization_type_enum,
    'ALL', 'N/A',
    'Représente la soumission directe à un fonds (pas d''intermédiaire requis).',
    '[]'::jsonb, '{}'::jsonb, '{}'::jsonb,
    NULL, true, (SELECT id FROM sources WHERE url = 'system://mefali/direct-singleton' LIMIT 1),
    '1.0', CURRENT_DATE, 'published',
    '[]'::jsonb, now(), now()
WHERE NOT EXISTS (SELECT 1 FROM intermediaries WHERE code = 'DIRECT');

-- Note : la source `system://mefali/direct-singleton` doit être créée AU PRÉALABLE
-- dans la même migration via INSERT ... ON CONFLICT DO NOTHING.
```

## OfferDraft Pydantic (non persisté)

```python
# backend/app/modules/offers/schemas.py
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field

from app.core.money import Money


class OfferDraft(BaseModel):
    """Résultat de compute_effective_offer (pas persisté)."""
    fund_id: UUID
    intermediary_id: UUID
    name: str
    target_sector: list[str] | None = None
    effective_criteria: dict[str, Any] = Field(default_factory=dict)
    effective_required_documents: list[dict[str, Any]] = Field(default_factory=list)
    effective_fees: dict[str, Any] = Field(default_factory=dict)
    effective_processing_time_days_min: int | None = None
    effective_processing_time_days_max: int | None = None
    effective_disbursement_time_days_min: int | None = None
    effective_disbursement_time_days_max: int | None = None
    accepted_languages_hint: list[str] = Field(default_factory=lambda: ["FR"])
    notes: str | None = None
    suggested_source_id: UUID | None = None  # = fund_intermediary.accreditation_source_id si présent


class OfferRead(BaseModel):
    """Lecture publique d'une offre (PME + admin)."""
    id: UUID
    fund: dict  # FundSummary
    intermediary: dict  # IntermediarySummary
    name: str
    accepted_languages: list[str]
    target_sector: list[str] | None = None
    effective_criteria: dict[str, Any]
    effective_required_documents: list[dict[str, Any]]
    effective_fees: dict[str, Any]
    effective_processing_time_days_min: int | None = None
    effective_processing_time_days_max: int | None = None
    effective_disbursement_time_days_min: int | None = None
    effective_disbursement_time_days_max: int | None = None
    notes: str | None = None
    is_active: bool
    publication_status: str
    source_id: UUID
    version: str
    valid_from: str
    valid_to: str | None = None


class OfferCreate(BaseModel):
    """Payload de création depuis draft édité (admin only)."""
    fund_id: UUID
    intermediary_id: UUID
    name: str = Field(min_length=1, max_length=200)
    accepted_languages: list[str] = Field(default_factory=lambda: ["FR"])
    target_sector: list[str] | None = None
    effective_criteria: dict[str, Any] = Field(default_factory=dict)
    effective_required_documents: list[dict[str, Any]] = Field(default_factory=list)
    effective_fees: dict[str, Any] = Field(default_factory=dict)
    effective_processing_time_days_min: int | None = None
    effective_processing_time_days_max: int | None = None
    effective_disbursement_time_days_min: int | None = None
    effective_disbursement_time_days_max: int | None = None
    notes: str | None = None
    source_id: UUID
    publication_status: str = "draft"


class OfferComparison(BaseModel):
    """Élément du comparateur multi-offres pour un fonds."""
    offer_id: UUID
    name: str
    intermediary_name: str
    intermediary_country: str
    accepted_languages: list[str]
    effective_fees_total_min: Money | None
    effective_fees_total_max: Money | None
    effective_processing_time_days_min: int | None
    effective_processing_time_days_max: int | None
    effective_disbursement_time_days_min: int | None
    effective_disbursement_time_days_max: int | None
    success_rate: float | None
    documents_count: int
    publication_status: str
    is_active: bool
```

## Récapitulatif des changements de schéma

| Table | Colonnes ajoutées | Nouveaux indexes | Nouvelles contraintes |
|---|---|---|---|
| `funds` | 6 (instruments, theme, submission_mode, submission_calendar, source_id, publication_status) + renommage enum fund_type | 3 (theme_gin, instruments_gin, publication_status) | 2 (submission_mode_chk, publication_status_chk) |
| `intermediaries` | 13 (code, required_documents, fees_structured, 4 timing, submission_portal_url, success_rate, total_funded_volume_amount/currency, source_id, publication_status) | 3 (code uniq sparse, country, publication_status) | 5 (processing_time_chk, disbursement_time_chk, success_rate_chk, total_funded_volume_pair_chk, publication_status_chk) |
| `fund_intermediaries` | 5 (accredited_from, accredited_to, max_amount_per_fund_amount/currency, accreditation_source_id) | 1 (accredited_to partiel) | 2 (accreditation_dates_chk, max_amount_pair_chk) |
| `fund_applications` | 1 (offer_id) | 1 (offer_id) | 1 (NOT NULL post-backfill) |
| `offers` (NOUVELLE) | 16 colonnes business + 4 versioning + 2 timestamps | 5 (uniq fund_intermed_version, publication_active partiel, fund_intermed_valid_to, theme_gin, name_fts) | 4 CHECK |

**Total** : ~25 colonnes ajoutées sur 4 tables existantes + 1 nouvelle table avec 22 colonnes + 13 indexes nouveaux + 14 contraintes CHECK.
