# Phase 1 — Data Model : F21

**Feature** : F21 — Dashboard par Offre + Rapport Carbone PDF
**Date** : 2026-05-08
**Migration requise** : **NON** (`alembic_or_migration = false`)

Aucune nouvelle table, aucune nouvelle colonne. F21 ne fait que **lire** les tables existantes et **écrire** dans la table `Report` (déjà présente, F06).

## Entités existantes consommées

### `reports` (existante — F06)

Réutilisée à l'identique. Valeurs nouvelles (sans changement de schéma) :
- `report_type='carbon'` (la colonne accepte déjà des chaînes).
- `assessment_id` pointe vers une `carbon_assessments.id` quand `report_type='carbon'`.

| Champ | Type | Notes F21 |
|---|---|---|
| `id` | UUID | inchangé |
| `account_id` | UUID FK accounts | RLS F02 inchangée |
| `assessment_id` | UUID FK polymorphique | renvoie vers `carbon_assessments.id` quand `report_type='carbon'` |
| `report_type` | str | nouvelle valeur autorisée `'carbon'` (pas de CHECK BDD : conservation flexibilité F06) |
| `status` | str | `pending` → `generating` → `ready` ou `failed` |
| `file_path` | str nullable | rempli quand `status='ready'` |
| `error_message` | str nullable | rempli quand `status='failed'` |
| `created_at` / `updated_at` | timestamptz | inchangés |

**Invariant applicatif F21** : à un instant T, au plus un `Report(assessment_id=X, report_type='carbon', status IN ('pending','generating'))`. Vérifié par sélection préalable dans le service (FR-018), pas de contrainte SQL.

### `carbon_assessments` (existante)

Lecture seule pour la génération du rapport.
- `is_finalized: bool` — précondition (FR-017).
- Relation `entries` → `carbon_emission_entries`.

### `carbon_emission_entries` (existante — F17)

Lecture seule. Champs exploités :
- `category` (energy / transport / waste / industrial / agriculture / purchases)
- `scope` (1 / 2 / 3)
- `factor_id` → FK `emission_factors.id` (F17) → permet de remonter à `Source` (F01).
- `source_id` → FK direct vers `Source` quand renseigné.
- `total_emissions_tco2e: Decimal`.

### `emission_factors` (existante — F17)

Lecture seule. Sert à constituer la section Méthodologie.

### `fund_applications` (existante)

Lecture seule pour les cards par offre.
- `offer_id` → FK Offer (F07).
- `status` → mappé en libellé d'étape (cf research R2).
- `updated_at` → tri `last_activity_at`.

### `offers` (existante — F07)

Lecture seule. Composition `Offer = Fund × Intermediary`. Relations chargées :
- `Offer.fund` → `Fund` (name, logo_url).
- `Offer.intermediary` → `Intermediary` ou null (DIRECT) ; champs `name`, `country`, `logo_url`, `lat`, `lon`, `type`.

### `intermediaries` (existante)

Lecture seule. Champs exploités pour la carte :
- `lat`, `lon` — peuvent être NULL.
- `country` (ISO-3166 alpha-2 ou alpha-3) → fallback capitale UEMOA.
- `type` (gov_agency / dfi / commercial_bank / mfi / ngo / consulting).

### `projects` (existante)

Lecture seule. Source supplémentaire pour identifier les intermédiaires actifs (`status NOT IN ('cancelled','closed')`).

### `sources` (existante — F01)

Lecture seule. Référencée dans le PDF carbone (annexe) et dans les ScoreCards.

### `audit_log` (existante — F03)

Lecture seule pour la section « Activité récente » du dashboard. Limit 5.

### `tool_call_logs` (existante)

Lecture seule. Filtre `tool_name='cite_source' AND assessment_id=X` pour collecter les sources mobilisées dans le résumé conversationnel du bilan.

## DTO / schémas Pydantic backend (nouveaux)

### `ApplicationCard` (DTO sortant)

Dans `app/modules/dashboard/schemas.py` (étendu).

```python
class ApplicationCard(BaseModel):
    application_id: UUID
    offer_id: UUID | None
    fund_name: str
    intermediary_name: str   # "Accès direct" si null
    fund_logo_url: str | None = None
    intermediary_logo_url: str | None = None
    status: str              # status BDD brut
    current_step: str        # libellé FR mappé
    next_deadline: date | None = None
    next_reminder: str | None = None
    last_activity_at: datetime
```

### `ActiveIntermediary` (DTO sortant)

```python
class ActiveIntermediary(BaseModel):
    intermediary_id: UUID
    name: str
    type: str                # gov_agency / dfi / commercial_bank / ...
    country: str
    lat: float
    lon: float
    is_fallback_capital: bool = False  # true si lat/lon issus de UEMOA_CAPITAL_COORDINATES
    accreditations: list[str]          # noms de fonds
    applications_count: int
```

### `ScoreSourceRef` (DTO sortant — pour ScoreCards cliquables)

```python
class ScoreSourceRef(BaseModel):
    source_id: UUID
    label: str
    publisher: str
    version: str | None
    url: str | None
```

`DashboardSummary.esg.sources: list[ScoreSourceRef]`, idem `carbon`, `credit`.

### `CarbonReportRequest` (entrée)

Aucun corps requis (path param `assessment_id`). Optionnellement :

```python
class CarbonReportRequest(BaseModel):
    include_methodology_appendix: bool = True   # always True MVP
    language: Literal['fr'] = 'fr'              # MVP fr only
```

### `CarbonReportResponse` (sortie 202)

```python
class CarbonReportResponse(BaseModel):
    report_id: UUID
    status: Literal['pending','generating','ready','failed']
    message: str  # ex: "Rapport en cours de génération"
```

### `CarbonReportListItem` (DTO sortant pour /reports)

```python
class CarbonReportListItem(BaseModel):
    report_id: UUID
    assessment_id: UUID
    assessment_year: int
    status: Literal['pending','generating','ready','failed']
    created_at: datetime
    download_url: str | None  # si status='ready'
    error_message: str | None
```

## Types TypeScript (frontend)

Dans `frontend/app/types/dashboard.ts` (extension) :

```typescript
export interface ApplicationCard {
  applicationId: string;
  offerId: string | null;
  fundName: string;
  intermediaryName: string;
  fundLogoUrl: string | null;
  intermediaryLogoUrl: string | null;
  status: ApplicationStatus;
  currentStep: string;
  nextDeadline: string | null;     // ISO 8601
  nextReminder: string | null;
  lastActivityAt: string;          // ISO 8601
}

export interface ActiveIntermediary {
  intermediaryId: string;
  name: string;
  type: IntermediaryType;
  country: string;
  lat: number;
  lon: number;
  isFallbackCapital: boolean;
  accreditations: string[];
  applicationsCount: number;
}

export interface ScoreSourceRef {
  sourceId: string;
  label: string;
  publisher: string;
  version: string | null;
  url: string | null;
}
```

Dans `frontend/app/types/carbon-report.ts` (nouveau) :

```typescript
export type CarbonReportStatus = 'pending' | 'generating' | 'ready' | 'failed';

export interface CarbonReportListItem {
  reportId: string;
  assessmentId: string;
  assessmentYear: number;
  status: CarbonReportStatus;
  createdAt: string;
  downloadUrl: string | null;
  errorMessage: string | null;
}
```

## State transitions — `Report.status` (carbon)

```
       POST /generate
             │
             ▼
        ┌────────┐    BackgroundTasks.start    ┌──────────────┐
        │pending │ ───────────────────────────▶│  generating  │
        └────────┘                             └──────┬───────┘
                                                      │
                                          PDF rendu OK│       PDF erreur
                                                      ▼
                                                ┌─────────┐    ┌─────────┐
                                                │  ready  │    │ failed  │
                                                └─────────┘    └─────────┘
                                                                    │
                                          POST /generate (retry) ◀──┘
```

Aucune transition non listée n'est autorisée.

## Constantes nouvelles

### `UEMOA_CAPITAL_COORDINATES` (`backend/app/core/uemoa_capitals.py`)

```python
UEMOA_CAPITAL_COORDINATES: dict[str, tuple[float, float]] = {
    "BEN": (6.3703, 2.3912),    # Cotonou (capitale économique) ; alt: Porto-Novo (6.4969, 2.6283)
    "BFA": (12.3714, -1.5197),  # Ouagadougou
    "CIV": (5.3600, -4.0083),   # Abidjan
    "GNB": (11.8638, -15.5982), # Bissau
    "MLI": (12.6392, -8.0029),  # Bamako
    "NER": (13.5117, 2.1251),   # Niamey
    "SEN": (14.7167, -17.4677), # Dakar
    "TGO": (6.1725, 1.2314),    # Lomé
}
```

Compatible avec `UEMOA_COUNTRY_CENTROIDS` (F11) pour la cohérence d'affichage.

## Validation rules (récapitulatif)

| Champ / DTO | Règle | Source |
|---|---|---|
| `applications_by_offer.length` | ≤ 5 | FR-002 |
| `next_deadline` | ISO date ou null | FR-001 |
| `intermediary_name` | "Accès direct" si offer.intermediary is null | FR-004 |
| `lat`, `lon` | Float ; fallback capitale si null en BDD | FR-006 |
| `Report.assessment_id` | doit pointer vers un `CarbonAssessment.is_finalized=True` | FR-017 |
| Concurrence | un seul `Report(carbon, pending|generating)` par assessment | FR-018 |
| Date PDF | format `DD/MM/YYYY` | FR-015 |
| Chiffres PDF | référence `[n]` ou « Recommandation générale (non sourcée) » | FR-016 |
| Multi-tenant | RLS PostgreSQL ENABLE+FORCE | FR-025 |

## Hors-modèle (confirmation)

- Pas de nouvelle table.
- Pas de nouvelle colonne.
- Pas de nouvelle contrainte SQL.
- Pas de nouvelle policy RLS.
- Pas de nouveau ENUM PostgreSQL.

Fin du data-model.
