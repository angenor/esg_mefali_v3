# Phase 1 — Data Model: F11 Tools de Visualisation Typés

**Date**: 2026-05-07
**Feature**: F11 — Tools de Visualisation Typés

## 1. Aperçu

Aucune nouvelle table BDD. Tous les modèles sont des **DTOs Pydantic v2** transitant LLM → backend → frontend. Persistance limitée au journal `tool_call_logs` (introduit en 012) qui enregistre déjà `tool_name`, `args`, `output`, `latency_ms`.

Tous les modèles utilisent `model_config = ConfigDict(extra="forbid")` pour rejeter strictement les champs inconnus (sécurité contre hallucinations LLM).

Tous les modèles sont définis dans `backend/app/schemas/visualization.py` et leur miroir TypeScript dans `frontend/app/types/richblocks.ts`.

## 2. Énumérations partagées

```python
# backend/app/schemas/visualization.py

from typing import Literal

DeltaDirection = Literal["up", "down", "neutral"]
KPIColor = Literal["emerald", "blue", "rose", "amber", "violet"]
MarkerType = Literal["project", "intermediary", "fund_office", "company_hq"]
ComparisonValueType = Literal["text", "money", "duration", "percentage", "rating", "boolean"]
```

```ts
// frontend/app/types/richblocks.ts

export type DeltaDirection = 'up' | 'down' | 'neutral'
export type KPIColor = 'emerald' | 'blue' | 'rose' | 'amber' | 'violet'
export type MarkerType = 'project' | 'intermediary' | 'fund_office' | 'company_hq'
export type ComparisonValueType = 'text' | 'money' | 'duration' | 'percentage' | 'rating' | 'boolean'
```

## 3. KPICardArgs

```python
class KPICardArgs(BaseModel):
    """Args strict pour show_kpi_card."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=120)
    value: str = Field(..., min_length=1, max_length=60)
    value_money: Money | None = Field(None)  # F04
    delta: float | None = Field(None, ge=-1e9, le=1e9)
    delta_label: str | None = Field(None, max_length=60)
    delta_direction: DeltaDirection | None = None
    delta_is_good: bool | None = None
    icon: str | None = Field(None, max_length=40)  # nom heroicon
    color: KPIColor = "emerald"
    source_id: UUID | None = None  # F01
    drilldown_url: str | None = Field(None, max_length=500)
```

**Règles métier** :
- Si `delta` fourni, `delta_direction` SHOULD être cohérent (`up` si > 0, `down` si < 0, `neutral` si == 0). Le frontend déduit visuellement si `delta_direction` est absent.
- Si `delta_is_good` est `True`, la couleur du delta sera verte (et inversement). Si absent, le frontend utilise une heuristique : `up` = vert, `down` = rouge.
- Si `value_money` fourni et `value` est une chaîne vide ou non formatée, le frontend doit formater à partir de `value_money` (ex: `"655 957 FCFA"`).
- `drilldown_url` SHOULD être une URL relative interne ; les URLs externes sont autorisées mais non encouragées.
- `source_id` doit être un `Source.id` existant et `verified` (vérifié côté frontend lors du clic via le composant modale source).

## 4. MatchCardArgs

```python
class MatchCardArgs(BaseModel):
    """Args strict pour show_match_card."""

    model_config = ConfigDict(extra="forbid")

    project_id: UUID  # F06
    offer_id: UUID  # F07
    fund_name: str = Field(..., min_length=1, max_length=120)
    fund_logo_url: str | None = Field(None, max_length=500)
    intermediary_name: str = Field(..., min_length=1, max_length=120)
    intermediary_logo_url: str | None = Field(None, max_length=500)
    compatibility_score: int = Field(..., ge=0, le=100)
    compatibility_breakdown: dict[str, int] | None = Field(
        None,
        description='ex: {"fund_score": 80, "intermediary_score": 65}',
    )
    amount_range: str = Field(..., min_length=1, max_length=80)
    timeline: str = Field(..., min_length=1, max_length=80)
    instruments: list[str] = Field(..., min_length=1, max_length=8)
    missing_criteria_count: int = Field(..., ge=0, le=99)
    cta_label: str = Field("Explorer", min_length=1, max_length=40)
    drilldown_url: str = Field(..., min_length=1, max_length=500)
```

**Règles métier** :
- `project_id` et `offer_id` DOIVENT appartenir à l'`account_id` courant (vérifié côté backend par le service récupérant les données avant émission du tool ; le multi-tenant est géré au niveau de la couche service).
- `compatibility_breakdown` quand fourni doit avoir des valeurs entières 0-100. Le frontend affiche un tooltip avec ces valeurs au survol du score.
- `instruments` : valeurs libres (ex: "subvention", "blending", "garantie", "prêt concessionnel"). Les badges sont rendus sans validation lexicale stricte.
- `drilldown_url` cible attendue (convention) : `/financing/offers/{offer_id}?project_id={project_id}` (le tool peut produire une URL légèrement différente).
- Pas de `source_id` direct sur MatchCardArgs (les chiffres sourcés sont dans la fiche offre, pas dans la carte de match elle-même).

## 5. MapMarker + MapArgs

```python
class MapMarker(BaseModel):
    """Marker individuel pour show_map."""

    model_config = ConfigDict(extra="forbid")

    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    label: str = Field(..., min_length=1, max_length=120)
    type: MarkerType
    icon: str | None = Field(None, max_length=40)  # nom heroicon optionnel
    popup_content: str | None = Field(None, max_length=500)  # HTML court (sanitisé front)
    drilldown_url: str | None = Field(None, max_length=500)


class MapArgs(BaseModel):
    """Args strict pour show_map."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, max_length=120)
    center: tuple[float, float] | None = None  # (lat, lon) ; défaut centre UEMOA
    zoom: int = Field(6, ge=1, le=18)
    markers: list[MapMarker] = Field(..., min_length=1, max_length=50)
    show_uemoa_overlay: bool = False
```

**Règles métier** :
- `markers` ne peut PAS être vide (au minimum 1 marker — sinon l'utilisateur n'a rien à voir, le LLM doit basculer sur du texte).
- `center` quand absent : le frontend calcule automatiquement le centre en fonction des markers (ou utilise le centroïde de la zone UEMOA si tous les markers sont en UEMOA).
- `popup_content` est HTML court (gras, italique, lien) sanitisé via DOMPurify côté frontend avant rendu.
- `show_uemoa_overlay=true` charge l'asset GeoJSON local et l'affiche en couche par-dessus le tile layer.

### Constante `UEMOA_COUNTRY_CENTROIDS` (backend)

```python
# backend/app/core/visualization_centroids.py

UEMOA_COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "BEN": (9.30769, 2.31583),    # Bénin
    "BFA": (12.23833, -1.56167),  # Burkina Faso
    "CIV": (7.53980, -5.54712),   # Côte d'Ivoire
    "GNB": (11.80372, -15.18041), # Guinée-Bissau
    "MLI": (17.57046, -3.99617),  # Mali
    "NER": (17.60782, 8.08183),   # Niger
    "SEN": (14.49709, -14.45239), # Sénégal
    "TGO": (8.61961, 0.82482),    # Togo
}

UEMOA_REGION_CENTER: tuple[float, float] = (12.0, -2.0)
UEMOA_DEFAULT_ZOOM: int = 5
```

Ces valeurs sont les centroïdes officiels Natural Earth pour chaque pays (Public Domain).

## 6. ComparisonTable (4 entités imbriquées)

```python
class ComparisonValue(BaseModel):
    """Cellule individuelle d'une row de ComparisonTable."""

    model_config = ConfigDict(extra="forbid")

    subject_id: str = Field(..., min_length=1, max_length=80)
    value: str | int | float = Field(...)
    money: Money | None = None  # utilisé si row.type == "money"
    annotation: str | None = Field(None, max_length=120)
    source_id: UUID | None = None  # F01


class ComparisonRow(BaseModel):
    """Ligne (un critère) de ComparisonTable."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(..., min_length=1, max_length=120)
    values: list[ComparisonValue] = Field(..., min_length=2, max_length=5)
    type: ComparisonValueType
    higher_is_better: bool = True


class ComparisonSubject(BaseModel):
    """Colonne (une entité comparée) de ComparisonTable."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, max_length=80)
    label: str = Field(..., min_length=1, max_length=120)
    sublabel: str | None = Field(None, max_length=120)
    drilldown_url: str | None = Field(None, max_length=500)


class ComparisonTableArgs(BaseModel):
    """Args strict pour show_comparison_table."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=200)
    subjects: list[ComparisonSubject] = Field(..., min_length=2, max_length=5)
    rows: list[ComparisonRow] = Field(..., min_length=1, max_length=20)
    highlight_winner: bool = True

    @field_validator("rows", mode="after")
    @classmethod
    def _check_values_match_subjects(cls, rows, info):
        subjects = info.data.get("subjects")
        if not subjects:
            return rows
        subject_ids = {s.id for s in subjects}
        for r_index, r in enumerate(rows):
            value_ids = {v.subject_id for v in r.values}
            if value_ids != subject_ids:
                raise ValueError(
                    f"Row {r_index} ('{r.label}') : les subject_id des values "
                    f"({value_ids}) ne correspondent pas aux subjects "
                    f"({subject_ids})."
                )
        return rows
```

**Règles métier** :
- 2 ≤ nombre de sujets ≤ 5 (lisibilité chat).
- 1 ≤ nombre de rows ≤ 20.
- Chaque `ComparisonRow.values` DOIT contenir exactement une `ComparisonValue` par sujet (validation cross-field via `field_validator`).
- `value` typé `str | int | float` ; le formatage final dépend de `row.type` (ex: `type="money"` → utiliser `value.money` plutôt que `value.value`).
- `highlight_winner=true` met en surbrillance la meilleure cellule par row : pour `type=money/percentage/rating/duration` numérique, comparaison directe (selon `higher_is_better`) ; pour `type=text/boolean`, pas de highlight (skip silencieux).
- Pour `type=duration`, `value` est en jours ou en mois (texte libre, ex: `"12 mois"` ou `"45 jours"`). Le frontend tente un parsing best-effort pour le highlight ; si non parsable, skip highlight.

## 7. Mapping TypeScript miroir

```ts
// frontend/app/types/richblocks.ts (extension)

import type { Money } from './currency'

export interface KPICardBlockProps {
  title: string
  value: string
  valueMoney?: Money | null
  delta?: number | null
  deltaLabel?: string | null
  deltaDirection?: DeltaDirection | null
  deltaIsGood?: boolean | null
  icon?: string | null
  color: KPIColor
  sourceId?: string | null  // UUID en string côté front
  drilldownUrl?: string | null
}

export interface MatchCardBlockProps {
  projectId: string
  offerId: string
  fundName: string
  fundLogoUrl?: string | null
  intermediaryName: string
  intermediaryLogoUrl?: string | null
  compatibilityScore: number
  compatibilityBreakdown?: Record<string, number> | null
  amountRange: string
  timeline: string
  instruments: string[]
  missingCriteriaCount: number
  ctaLabel: string
  drilldownUrl: string
}

export interface MapMarkerProps {
  lat: number
  lon: number
  label: string
  type: MarkerType
  icon?: string | null
  popupContent?: string | null
  drilldownUrl?: string | null
}

export interface MapBlockProps {
  title?: string | null
  center?: [number, number] | null
  zoom: number
  markers: MapMarkerProps[]
  showUemoaOverlay: boolean
}

export interface ComparisonValueProps {
  subjectId: string
  value: string | number
  money?: Money | null
  annotation?: string | null
  sourceId?: string | null
}

export interface ComparisonRowProps {
  label: string
  values: ComparisonValueProps[]
  type: ComparisonValueType
  higherIsBetter: boolean
}

export interface ComparisonSubjectProps {
  id: string
  label: string
  sublabel?: string | null
  drilldownUrl?: string | null
}

export interface ComparisonTableBlockProps {
  title: string
  subjects: ComparisonSubjectProps[]
  rows: ComparisonRowProps[]
  highlightWinner: boolean
}
```

**Convention nommage** : Pydantic snake_case côté backend → TypeScript camelCase côté frontend. Mapping appliqué à la sérialisation par `model_dump(by_alias=True)` (alias générés par Pydantic) ou conversion explicite dans `useMessageParser.ts`.

## 8. Diagramme relations

```text
ConversationMessage (existant 012)
  └── tool_calls: list[ToolCall]
        └── ToolCall
              ├── name: "show_kpi_card" | "show_match_card" | "show_map" | "show_comparison_table"
              └── args: KPICardArgs | MatchCardArgs | MapArgs | ComparisonTableArgs

ComparisonTableArgs
  ├── subjects: list[ComparisonSubject]
  └── rows: list[ComparisonRow]
        └── values: list[ComparisonValue]
              └── money: Money | None  (réutilise F04)

KPICardArgs / MatchCardArgs / ComparisonValue
  └── source_id: UUID | None  → ref Source (F01)

MatchCardArgs
  ├── project_id: UUID  → ref Project (F06)
  └── offer_id: UUID    → ref Offer (F07)

MapArgs
  └── markers: list[MapMarker]
```

## 9. Persistance & journalisation

- **`tool_call_logs`** (existant 012) : enregistre automatiquement `tool_name`, `args` (JSON), `output`, `duration_ms` pour chaque invocation des nouveaux tools. Aucune extension nécessaire.
- **Aucune nouvelle table** : les blocs typés sont éphémères (réponse LLM rendue inline puis sérialisée dans `messages.content` standard).

## 10. Migration & versioning

- **Aucune migration Alembic.**
- Pas de risque sur les données existantes.
- L'ajout de tools dans `tool_selector_config.py` est rétrocompatible (les tools sont opt-in côté noeud).
