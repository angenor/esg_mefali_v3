# Contract — F17 Carbone : Service `get_emission_factor`, Tool `save_emission_entry`, Endpoint Admin

Date : 2026-05-07
Branche : `feat/F17-carbone-mix-uemoa-source` (alias SpecKit `021-carbone-mix-uemoa-source`)

Ce document décrit les interfaces (services Python, tools LangChain, endpoints REST) introduites ou modifiées par F17.

## 1. Service Python `get_emission_factor`

### Localisation

`backend/app/modules/carbon/factor_service.py` (nouveau fichier).

### Signature

```python
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.emission_factor import EmissionFactor


@dataclass(frozen=True)
class EmissionFactorResolution:
    """Resultat d'une recherche de facteur d'emission."""
    factor: EmissionFactor
    is_approximate: bool         # True si match degrade (annee anterieure de >3 ans, ou pays global)
    fallback_reason: str | None  # "year_older", "country_global", None si match exact


class EmissionFactorNotFoundError(LookupError):
    """Levee quand aucun facteur n'est trouve, meme global."""


async def get_emission_factor(
    db: AsyncSession,
    category: str,
    country: str | None,
    year: int,
) -> EmissionFactorResolution:
    """Selectionne le facteur d'emission selon priorite pays/annee.

    Priorite :
        (1) country exact + year exact
        (2) country exact + year anterieure la plus recente
        (3) global + year exact
        (4) global + year anterieure la plus recente

    Si rien trouve : leve EmissionFactorNotFoundError.

    Le flag is_approximate vaut True si :
        - le pays est NULL (fallback global) OU
        - la difference d'annee est > 3 ans
    """
```

### Comportement attendu

| Scénario | Pays demandé | Année demandée | Match attendu | `is_approximate` | `fallback_reason` |
|----------|--------------|----------------|---------------|------------------|-------------------|
| Match exact CI 2024 | CI | 2024 | `electricity_ci_2024` | False | None |
| Pays exact, année antérieure | CI | 2026 | `electricity_ci_2024` | False (diff ≤ 3) | "year_older" |
| Pays exact, année très antérieure | CI | 2030 | `electricity_ci_2024` | True (diff > 3) | "year_older" |
| Pays non couvert | XX | 2024 | `electricity_global_2024` | True | "country_global" |
| Pays inexistant et année future inexistante | XX | 2030 | `electricity_global_2024` | True | "country_global" |
| Catégorie inconnue | `unknown` | 2024 | LookupError | n/a | n/a |

### Exception

- `EmissionFactorNotFoundError(category, country, year)` levée quand : aucun match (pas même global), ou catégorie inexistante.

### Tests unitaires (TDD obligatoire)

- `test_get_emission_factor_exact_match_country_year` (CI 2024)
- `test_get_emission_factor_exact_country_older_year` (CI 2026 → CI 2024, `is_approximate=False`)
- `test_get_emission_factor_exact_country_very_old_year` (CI 2030 → CI 2024, `is_approximate=True`)
- `test_get_emission_factor_global_fallback` (XX 2024 → global 2024, `is_approximate=True`, `fallback_reason="country_global"`)
- `test_get_emission_factor_no_country_provided` (None 2024 → global 2024)
- `test_get_emission_factor_not_found` (catégorie inconnue → LookupError)
- `test_get_emission_factor_filter_published_only` (vérifie qu'on ignore les `draft`)

## 2. Tool LangChain `save_emission_entry` (refactoré)

### Localisation

`backend/app/graph/tools/carbon_tools.py` (modification).

### Signature LangChain (inchangée côté LLM)

```python
@tool
async def save_emission_entry(
    assessment_id: str,
    category: str,
    quantity: float,
    unit: str,
    source_description: str,
    subcategory: str | None = None,
    config: RunnableConfig = None,
) -> str:
    """Enregistrer une entree d'emission dans le bilan carbone.

    Le facteur d'emission est selectionne automatiquement selon la categorie,
    le pays du profil entreprise et l'annee du bilan. Le facteur est cite
    via la table sources (F01) ; le LLM doit appeler cite_source(source_id)
    apres ce tool.

    Args:
        assessment_id: UUID du bilan carbone.
        category: Categorie d'emission (energy, transport, waste, industrial,
                  agriculture, purchases).
        quantity: Quantite consommee (ex: 500 kWh, 200 litres).
        unit: Unite de la quantite (kWh, L, kg, t, etc.).
        source_description: Texte libre legacy (sera deprecie).
        subcategory: Sous-categorie / cle du facteur d'emission (ex: electricity,
                     diesel_generator, purchases_cement). Si fournie, utilise
                     pour matcher le facteur dans emission_factors.

    Returns: JSON string avec status, entry, total_emissions_tco2e, factor_used,
             source_id (a citer via cite_source), is_approximate, fallback_reason.
    """
```

### Comportement attendu (nouveau)

1. Charge le bilan via `get_assessment(db, uuid.UUID(assessment_id), user_id)`.
2. Charge le profil entreprise pour récupérer `country` (via `get_profile(db, user_id)`).
3. Détermine l'année à partir du bilan : `assessment.year`.
4. Calcule la `category_for_lookup` :
   - Si `subcategory` fournie et matche un `emission_factors.code` → utilise tel quel.
   - Sinon, on cherche par `(category, country, year)` ⇒ appelle `get_emission_factor(db, category, country, assessment.year)`.
5. Calcule `emissions_tco2e = quantity * factor.value / 1000`.
6. Crée `CarbonEmissionEntry` avec `source_id=factor.source_id`, `factor_id=factor.id`, `subcategory=factor.code`, `emission_factor=factor.value` (snapshot).
7. Retourne JSON :

```json
{
  "status": "success",
  "entry": {
    "category": "energy",
    "subcategory": "electricity_ci_2024",
    "quantity": 1000,
    "unit": "kWh",
    "emission_factor_kgco2e": 0.456,
    "emissions_tco2e": 0.456,
    "source_description": "Electricite siege"
  },
  "factor_used": {
    "code": "electricity_ci_2024",
    "label": "Electricite reseau Cote d'Ivoire 2024",
    "country": "CI",
    "year": 2024
  },
  "source_id": "550e8400-e29b-41d4-a716-446655440000",
  "is_approximate": false,
  "fallback_reason": null,
  "total_emissions_tco2e": 12.3,
  "message": "Entree enregistree : 1000 kWh d'Electricite reseau Cote d'Ivoire 2024 = 0.456 tCO2e."
}
```

### Cas d'erreur

```json
{
  "status": "error",
  "message": "Aucun facteur d'emission trouve pour la categorie 'unknown' (pays=CI, annee=2026).",
  "error_code": "factor_not_found"
}
```

### Tests unitaires

- `test_save_emission_entry_uses_country_from_profile` (CI → electricity_ci)
- `test_save_emission_entry_falls_back_to_global` (pays non couvert)
- `test_save_emission_entry_returns_source_id_for_cite_source`
- `test_save_emission_entry_purchases_category` (catégorie achats reconnue)
- `test_save_emission_entry_returns_is_approximate_flag`
- `test_save_emission_entry_no_country_in_profile` (profil sans country → global)
- `test_save_emission_entry_invalid_category` (factor_not_found)

## 3. Endpoint REST Admin `POST /api/admin/carbon/seed-factors`

### Localisation

`backend/app/routers/admin.py` (extension).

### Signature OpenAPI

```yaml
POST /api/admin/carbon/seed-factors
Tags: [admin, carbon]
Security: BearerAuth (role=ADMIN, via get_current_admin)
Request:
  - body: aucun (le seed est defini en code)
Response 200:
  - body: SeedResult
Response 401: Unauthorized
Response 403: Forbidden (PME role)
```

### Schéma `SeedResult`

```python
class SeedResult(BaseModel):
    """Resultat du seed des facteurs d'emission."""
    inserted: int                 # Nombre de facteurs nouvellement inseres
    skipped: int                  # Nombre de facteurs ignores (deja presents, conflit code)
    total_in_db: int              # Total apres seed
    sources_used: list[SourceLite]  # Sources F01 referencees
```

### Comportement

1. Vérifie que le user est ADMIN (via `Depends(get_current_admin)`).
2. Charge la liste de seed depuis `app/modules/carbon/seed_factors.py::SEED_DATA`.
3. Pour chaque entrée : `INSERT ... ON CONFLICT (code) DO NOTHING`.
4. Compte les inserted vs skipped.
5. Renvoie `SeedResult`.

### Tests d'intégration

- `test_admin_seed_factors_first_run` (db vide → 50 inserted, 0 skipped)
- `test_admin_seed_factors_idempotent` (re-run → 0 inserted, 50 skipped)
- `test_admin_seed_factors_unauthorized_pme` (403)
- `test_admin_seed_factors_unauthenticated` (401)

## 4. Composant Vue `<EmissionFactorBadge>`

### Localisation

`frontend/app/components/EmissionFactorBadge.vue` (nouveau).

### Props (TypeScript)

```typescript
interface EmissionFactorBadgeProps {
  factor: {
    code: string;          // ex. "electricity_ci_2024"
    label: string;         // ex. "Electricite reseau Cote d'Ivoire 2024"
    value: number;         // ex. 0.456
    unit: string;          // ex. "kgCO2e/kWh"
    country?: string;      // ex. "CI"
    year?: number;         // ex. 2024
  };
  source: {
    id: string;
    publisher: string;
    title: string;
    url?: string;
    page?: number;
  };
  isApproximate?: boolean;  // affiche un picto warning + tooltip
  fallbackReason?: 'year_older' | 'country_global' | null;
}
```

### Slots / Émits

- Aucun slot (composant atomique).
- Aucun émit.

### Structure DOM (simplifiée)

```html
<div class="emission-factor-badge inline-flex items-center gap-2 px-2 py-1 rounded-md bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border">
  <span class="text-sm text-surface-text dark:text-surface-dark-text">
    {{ factor.label }}
  </span>
  <span class="font-mono text-xs text-gray-600 dark:text-gray-400">
    {{ factor.value }} {{ factor.unit }}
  </span>
  <SourceLink :source="source" />
  <Icon v-if="isApproximate" name="warning" class="text-amber-500 dark:text-amber-400" :title="approximateTooltip" />
</div>
```

### Tests Vitest

- `EmissionFactorBadge.spec.ts` :
  - `renders factor label and value`
  - `forwards source prop to SourceLink`
  - `shows warning icon when isApproximate=true`
  - `does not show warning when isApproximate=false`
  - `respects dark mode classes`
  - `tooltip uses correct fallbackReason`

## 5. Schéma JSON `reduction_plan` (validation Pydantic)

### Localisation

`backend/app/modules/carbon/reduction_plan_schema.py` (nouveau).

### Schéma

```python
from pydantic import BaseModel, Field, model_validator
from typing import Literal


class ReductionPlanAction(BaseModel):
    """Action recommandee dans le plan de reduction carbone."""
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)
    estimated_reduction_tco2e: float = Field(ge=0)
    cost_estimate_fcfa: int | None = Field(default=None, ge=0)
    timeline: str = Field(min_length=1, max_length=100)  # ex. "0-3 mois"
    source_id: str | None = None  # UUID string
    unsourced: bool = False

    @model_validator(mode='after')
    def check_source_unsourced_consistency(self):
        if self.source_id is None and not self.unsourced:
            raise ValueError("source_id is None but unsourced is False (incoherent)")
        if self.source_id is not None and self.unsourced:
            raise ValueError("source_id is provided but unsourced is True (incoherent)")
        return self


class ReductionPlan(BaseModel):
    """Plan de reduction stocke dans CarbonAssessment.reduction_plan (JSON)."""
    actions: list[ReductionPlanAction] = Field(default_factory=list)
```

### Tests unitaires

- `test_reduction_plan_action_valid_with_source`
- `test_reduction_plan_action_valid_unsourced`
- `test_reduction_plan_action_inconsistency_source_and_unsourced`
- `test_reduction_plan_action_inconsistency_no_source_and_not_unsourced`
- `test_reduction_plan_empty_actions`

## 6. Garantie d'invariants projet

| Invariant | Garantie F17 |
|-----------|--------------|
| 1. Sourçage F01 | `EmissionFactor.source_id NOT NULL` ; `CarbonEmissionEntry.source_id NOT NULL` ; LLM appelle `cite_source(source_id)` post-tool ; validator `source_required` valide |
| 2. Multi-tenant F02 | `emission_factors.account_id = NULL` (catalogue commun lecture publique) ; entries héritent de `account_id` du bilan |
| 7. Admin only catalogue | Endpoint seed `Depends(get_current_admin)` ; aucun tool LLM ne mute `emission_factors` |
| 8. Dark mode | `<EmissionFactorBadge>` implémente toutes variantes `dark:` |
| 9. Réutilisabilité composants | `<EmissionFactorBadge>` paramétrable via props ; réutilise `<SourceLink>` |
| 10. Français accents | Libellés seed en français (ex. « Électricité réseau Côte d'Ivoire ») |
