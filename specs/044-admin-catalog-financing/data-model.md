# Phase 1 — Data Model (lecture seule)

**Feature**: 044-admin-catalog-financing
**Date**: 2026-05-21

> **Aucune nouvelle table, aucune migration.** Cette feature consomme exclusivement des entités existantes (fondations F06/F07/F01/F04). Le tableau ci-dessous synthétise les attributs lus et les transformations effectuées en mémoire pour produire les DTO exposés.

## Entités lues

### `Fund` (table `funds`, F07)
- **Identité** : `id UUID PK`
- **Attributs exposés** : `name`, `code`, `fund_type` (enum multilateral/bilateral/regional/national/private/carbon_marketplace), `description`, `publication_status` (draft/published/deprecated), `version`, `valid_from`, `valid_to`, `superseded_by` (FK self), `submission_mode`, `instruments JSONB`, `theme JSONB`, `min_amount_money`, `max_amount_money`, `source_id`, `created_at`, `updated_at`
- **Lecture** : `SELECT … FROM funds WHERE (filtres dynamiques)`
- **Tri par défaut** : `updated_at DESC`

### `Intermediary` (table `intermediaries`, F07)
- **Identité** : `id UUID PK`
- **Attributs exposés** : `name`, `code` (sparse unique), `description`, `publication_status`, `version`, `valid_from`, `valid_to`, `superseded_by`, `fees_structured JSONB`, `processing_time_days_min/max`, `disbursement_time_days_min/max`, `success_rate`, `total_funded_volume_money`, `source_id`, `created_at`, `updated_at`
- **Tri par défaut** : `updated_at DESC`

### `Offer` (table `offers`, F07)
- **Identité** : `id UUID PK`
- **Attributs exposés** : `fund_id`, `intermediary_id`, `publication_status`, `version`, `valid_from`, `valid_to`, `superseded_by`, agrégats effectifs `effective_min_money`, `effective_max_money`, `effective_documents JSONB`, `created_at`, `updated_at`
- **Tri par défaut** : `updated_at DESC`

### `FundIntermediary` (table `fund_intermediaries`, F07)
- **Identité** : PK composite `(fund_id, intermediary_id)` — exposée sous forme `id = "{fund_id}:{intermediary_id}"` côté API et URL
- **Attributs exposés** : `fund_id`, `intermediary_id`, `accredited_from NOT NULL`, `accredited_to`, `max_amount_per_fund_money`, `accreditation_source_id`, `created_at`, `updated_at`
- **État dérivé** : `is_active = (accredited_to IS NULL OR accredited_to >= today)`, `is_expired = NOT is_active`
- **Tri par défaut** : `accredited_from DESC`

### `Source` (table `sources`, F01) — référence
- Lecture jointe pour exposer `source.id`, `source.title`, `source.url`, `source.status` quand demandé par la fiche détail.

---

## DTO exposés (Pydantic v2, schemas dans `backend/app/schemas/admin_catalog.py`)

### `CatalogSummary`
```python
class CatalogTabCounts(BaseModel):
    total: int
    by_status: dict[str, int]  # {"draft": 3, "published": 42, "deprecated": 1}

class CatalogFundIntermediariesCounts(BaseModel):
    total: int
    active: int
    expired: int

class CatalogSummary(BaseModel):
    funds: CatalogTabCounts
    intermediaries: CatalogTabCounts
    offers: CatalogTabCounts
    fund_intermediaries: CatalogFundIntermediariesCounts
```

### `CatalogRow` (générique, un type par onglet)
Chaque ligne de liste expose au minimum :
```python
class CatalogRowBase(BaseModel):
    id: str              # UUID stringifié ou clé composite pour les liaisons
    name: str            # nom court affiché
    publication_status: Literal["draft", "published", "deprecated"] | None
    version: str | None
    updated_at: datetime
    has_incoherence: bool  # cf. D5 research.md
```

### `FundIntermediaryRow` & `FundIntermediaryDetail`
```python
class FundIntermediaryRow(BaseModel):
    id: str                  # "{fund_id}:{intermediary_id}"
    fund_id: UUID
    fund_name: str
    intermediary_id: UUID
    intermediary_name: str
    accredited_from: date
    accredited_to: date | None
    is_active: bool
    max_amount_per_fund_money: Money | None
    has_source: bool
    updated_at: datetime

class FundIntermediaryDetail(FundIntermediaryRow):
    accreditation_source: SourceRef | None  # {id, title, url, status}
    fund_link: str           # "/admin/catalog/funds/{fund_id}"
    intermediary_link: str   # "/admin/catalog/intermediaries/{intermediary_id}"
    created_at: datetime
```

### `PaginatedListResponse[T]`
```python
class PaginatedListResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int                # 1 si mode liste complète
    page_size: int           # = total si mode liste complète
    paginated: bool          # False tant que total < 2000
```

---

## Transitions d'état (lecture seule — aucune mutation déclenchée)

La page consulte les états existants ; elle ne modifie aucun état. Les transitions `draft → published → deprecated` (workflow 4-yeux F01) restent gérées par les routers admin existants hors-scope de cette feature.

## Volumes attendus

| Onglet | Volume actuel | Cible 2 ans | Seuil pagination |
|---|---|---|---|
| Fonds | ~12 | ~200 | 2 000 |
| Intermédiaires | ~14 | ~150 | 2 000 |
| Offres | ~50 | ~1 500 | 2 000 |
| Liaisons | ~50 | ~1 500 | 2 000 |

Sous ces volumes, la liste complète est servie en une seule requête JSON < 500 KB par onglet.
