# Phase 1 — Data Model : F17 Carbone Mix UEMOA + Facteurs Sourcés

Date : 2026-05-07
Branche : `feat/F17-carbone-mix-uemoa-source` (alias SpecKit `024-carbone-mix-uemoa-source`)

## 1. Modèle `EmissionFactor` (existant F01, étendu F17)

Table : `emission_factors`. Modèle : `backend/app/models/emission_factor.py`.

### Colonnes (après migration F17)

| Colonne | Type SQL | Nullable | FK / Contrainte | Notes |
|---------|----------|----------|-----------------|-------|
| `id` | UUID | NO | PK | UUIDMixin (F01) |
| `code` | VARCHAR(100) | NO | UNIQUE (`emission_factors_code_uniq_idx`) | snake_case (ex. `electricity_ci_2024`) |
| `label` | VARCHAR(200) | NO |  | Libellé humain en français |
| `category` | VARCHAR(50) | NO | INDEX | `electricity`, `fuel_diesel`, `fuel_gasoline`, `fuel_butane`, `transport_personal`, `transport_freight`, `waste_landfill`, `waste_incineration`, `waste_compost`, `purchases_steel`, `purchases_cement`, `purchases_paper`, `purchases_food`, `purchases_plastic`, `purchases_other` |
| `country` | VARCHAR(50) | NO |  | Code ISO 2 lettres (CI, SN, BF, ML, NE, BJ, TG, GW) ou littéral `global` |
| **`year`** | INTEGER | **NO (après backfill)** | **NEW F17** | Année de référence du facteur (ex. 2024) |
| `value` | NUMERIC(10, 4) | NO |  | Valeur numérique du facteur |
| `unit` | VARCHAR(50) | NO |  | `kgCO2e/kWh`, `kgCO2e/L`, `kgCO2e/kg`, `kgCO2e/t`, etc. |
| `source_id` | UUID | NO | FK `sources(id)` ON DELETE RESTRICT | F01 |
| `publication_status` | VARCHAR(20) | NO | CHECK IN (`draft`, `published`) | Default `draft`, seedés F17 en `published` |
| `account_id` | UUID | YES | FK `accounts(id)` ON DELETE RESTRICT, INDEX | F02 ; NULL pour catalogue commun |
| `created_by_user_id` | UUID | NO | FK `users(id)` ON DELETE RESTRICT | Admin seedeur |
| `created_at` / `updated_at` | TIMESTAMP TZ | NO |  | TimestampMixin (F01) |

### Contraintes ajoutées par F17

- `UNIQUE (category, country, year)` — nom : `emission_factors_cat_country_year_uniq`
- INDEX composite `(category, country, year)` — nom : `idx_emission_factors_lookup`
- (existants F01 conservés : `emission_factors_code_uniq_idx`, `emission_factors_category_country_idx`, `emission_factors_publication_status_chk`)

### Règles de validation Pydantic (`EmissionFactorBase`)

- `code` : pattern `^[a-z0-9_]+$`, max 100 chars
- `category` : enum strict
- `country` : pattern `^[A-Z]{2}$|^global$`
- `year` : `int`, `2020 ≤ year ≤ 2100`
- `value` : `Decimal`, `value > 0`
- `unit` : enum strict (`kgCO2e/kWh`, `kgCO2e/L`, `kgCO2e/kg`, `kgCO2e/t`)

### Lifecycle

`draft` (créé par admin) → `published` (publié, lookup-able par les tools LLM). Pas de `outdated` au MVP (gestion via `valid_to` dans F04).

## 2. Modèle `CarbonEmissionEntry` (existant, étendu F17)

Table : `carbon_emission_entries`. Modèle : `backend/app/models/carbon.py`.

### Colonnes (après migration F17)

| Colonne | Type SQL | Nullable | FK / Contrainte | Notes |
|---------|----------|----------|-----------------|-------|
| `id` | UUID | NO | PK | UUIDMixin |
| `assessment_id` | UUID | NO | FK `carbon_assessments(id)` ON DELETE CASCADE |  |
| `category` | VARCHAR(30) | NO |  | `energy`, `transport`, `waste`, `industrial`, `agriculture`, **`purchases` (NEW F17)** |
| `subcategory` | VARCHAR(50) | NO |  | Match `emission_factors.code` (ex. `electricity_ci_2024`, `purchases_cement_global_2024`) |
| `quantity` | FLOAT | NO |  |  |
| `unit` | VARCHAR(20) | NO |  |  |
| `emission_factor` | FLOAT | NO |  | Snapshot de la valeur du facteur au moment du calcul |
| `emissions_tco2e` | FLOAT | NO |  | Calculé `quantity * factor / 1000` |
| `source_description` | VARCHAR(500) | YES | LEGACY | Conservée 2 sprints. Commentaire SQLAlchemy `# TODO(F17+1): drop after stabilisation` |
| **`source_id`** | UUID | **NO (après backfill)** | **NEW F17** FK `sources(id)` ON DELETE RESTRICT |  |
| **`factor_id`** | UUID | **NO (après backfill)** | **NEW F17** FK `emission_factors(id)` ON DELETE RESTRICT | Snapshot facteur utilisé |
| `created_at` | TIMESTAMP TZ | NO |  |  |
| `account_id` | UUID | YES | FK `accounts(id)` ON DELETE RESTRICT, INDEX | F02 |

### Élargissement `VALID_CATEGORIES`

Avant F17 : `("energy", "transport", "waste", "industrial", "agriculture")`
Après F17 : `("energy", "transport", "waste", "industrial", "agriculture", "purchases")`

### Règles métier

- `source_id` et `factor_id` NOT NULL après backfill (contraintes ajoutées en deuxième temps de la migration)
- `emission_factor` reste un snapshot float (rétro-compatibilité, audit) ; le `factor_id` permet de remonter à la définition exacte
- `subcategory` doit matcher `emission_factors.code` au moment de la création (validation côté service `add_entries`)

## 3. Modèle `CarbonAssessment` (existant, schéma JSON enrichi F17)

Table : `carbon_assessments` — pas de modification SQL. Le champ `reduction_plan: JSON` voit son schéma logique enrichi.

### Schéma logique de `reduction_plan`

```json
{
  "actions": [
    {
      "title": "Passer au solaire",
      "description": "Installation de 5 kWc de panneaux photovoltaïques sur la toiture du bureau principal pour réduire la consommation réseau de 70 %.",
      "estimated_reduction_tco2e": 1.2,
      "cost_estimate_fcfa": 4500000,
      "timeline": "6-12 mois",
      "source_id": "550e8400-e29b-41d4-a716-446655440000",
      "unsourced": false
    },
    {
      "title": "Optimiser les trajets de livraison",
      "description": "Réorganiser les tournées pour réduire les kilomètres à vide.",
      "estimated_reduction_tco2e": 0.5,
      "cost_estimate_fcfa": null,
      "timeline": "0-3 mois",
      "source_id": null,
      "unsourced": true
    }
  ]
}
```

### Validation Pydantic (`ReductionPlanAction`)

- `title` : `str`, `1 ≤ len ≤ 200`
- `description` : `str`, `1 ≤ len ≤ 1000`
- `estimated_reduction_tco2e` : `float ≥ 0`
- `cost_estimate_fcfa` : `int ≥ 0 | None`
- `timeline` : `str`, enum suggéré `("0-3 mois", "3-12 mois", "12-24 mois")` (validation soft, juste pattern non vide)
- `source_id` : `UUID string | None`
- `unsourced` : `bool` ; règle de cohérence : `(source_id is None) <=> (unsourced is True)` (validateur Pydantic `model_validator`)

## 4. Source `EmissionFactor` ↔ `Source` ↔ `CarbonEmissionEntry`

### Relations

- `EmissionFactor.source_id` → `Source.id` (1 facteur = 1 source obligatoire)
- `CarbonEmissionEntry.source_id` → `Source.id` (snapshot de la source du facteur au moment du calcul)
- `CarbonEmissionEntry.factor_id` → `EmissionFactor.id` (snapshot du facteur utilisé)

### Cohérence

Au moment de la création d'une entry, le service garantit `entry.source_id == factor.source_id`. Cette redondance est volontaire :
- Permet de retrouver la source d'une entry sans JOIN sur `emission_factors` (perf).
- Si dans le futur la source d'un facteur change (admin met à jour), les entries historiques conservent la source originale (audit).

## 5. Volumétrie initiale (seed F17)

| Catégorie | Pays | Année | Lignes |
|-----------|------|-------|--------|
| `electricity` | CI, SN, BF, ML, NE, BJ, TG, GW | 2024 | 8 |
| `fuel_diesel` | global | 2024 | 1 |
| `fuel_gasoline` | global | 2024 | 1 |
| `fuel_butane` | global | 2024 | 1 |
| `transport_personal` | global | 2024 | 4 (essence, diesel, hybride, électrique) |
| `transport_freight` | global | 2024 | 3 (camion léger, camion lourd, fluvial) |
| `waste_landfill` | global | 2024 | 1 |
| `waste_incineration` | global | 2024 | 1 |
| `waste_compost` | global | 2024 | 1 |
| `purchases_steel` | global | 2024 | 1 |
| `purchases_cement` | global | 2024 | 1 |
| `purchases_paper` | global | 2024 | 1 |
| `purchases_food` | global | 2024 | 1 |
| `purchases_plastic` | global | 2024 | 1 |
| `purchases_other` | global | 2024 | 1 |
| **TOTAL** |  |  | **~27 lignes minimum, ~50 avec variantes/transport élargi** |

Le ciblage de ~50 lignes est atteint en ajoutant les variantes suivantes (par exemple : `electricity_ci_2024` et `electricity_ci_2023` pour permettre la priorité année antérieure ; transport découpé par carburant et catégorie de véhicule). La liste exhaustive est définie dans `app/modules/carbon/seed_factors.py`.

### Mapping source → facteur

| Source (F01) | Facteurs alimentés |
|--------------|---------------------|
| ADEME Base Carbone v23 | `fuel_*`, `transport_*`, `waste_*`, `purchases_*` |
| IPCC AR6 WG3 chap. 10 | `waste_landfill` (cohérence méthane) |
| IEA Africa Energy Outlook 2024 | `electricity_<8 pays UEMOA>` |

## 6. Migration Alembic — pseudo-code

```python
# Fichier : backend/alembic/versions/024_carbone_mix_uemoa.py

def upgrade():
    # 1. Ajouter colonne `year` nullable + valeur par défaut 2024 pour les entries F01 existantes
    op.add_column('emission_factors', sa.Column('year', sa.Integer(), nullable=True))
    op.execute("UPDATE emission_factors SET year = 2024 WHERE year IS NULL")
    op.alter_column('emission_factors', 'year', nullable=False)
    op.create_index('idx_emission_factors_lookup', 'emission_factors', ['category', 'country', 'year'])
    op.create_unique_constraint('emission_factors_cat_country_year_uniq',
                                'emission_factors', ['category', 'country', 'year'])

    # 2. Seeder les ~50 lignes de facteurs (idempotent via ON CONFLICT)
    op.execute(SEED_INSERT_SQL_WITH_ON_CONFLICT_DO_NOTHING)

    # 3. Étendre carbon_emission_entries
    op.add_column('carbon_emission_entries', sa.Column('source_id', UUID(as_uuid=True), nullable=True))
    op.add_column('carbon_emission_entries', sa.Column('factor_id', UUID(as_uuid=True), nullable=True))

    # 4. Backfill via Python (matching subcategory ↔ code, fallback générique global)
    backfill_carbon_entries(op.get_bind())

    # 5. NOT NULL + FK
    op.alter_column('carbon_emission_entries', 'source_id', nullable=False)
    op.alter_column('carbon_emission_entries', 'factor_id', nullable=False)
    op.create_foreign_key('fk_carbon_entries_source', 'carbon_emission_entries', 'sources',
                          ['source_id'], ['id'], ondelete='RESTRICT')
    op.create_foreign_key('fk_carbon_entries_factor', 'carbon_emission_entries', 'emission_factors',
                          ['factor_id'], ['id'], ondelete='RESTRICT')


def downgrade():
    op.drop_constraint('fk_carbon_entries_factor', 'carbon_emission_entries', type_='foreignkey')
    op.drop_constraint('fk_carbon_entries_source', 'carbon_emission_entries', type_='foreignkey')
    op.drop_column('carbon_emission_entries', 'factor_id')
    op.drop_column('carbon_emission_entries', 'source_id')
    # On ne supprime PAS source_description (legacy conservée 2 sprints, voir Décision 5)

    op.execute("DELETE FROM emission_factors WHERE code LIKE 'electricity_%_2024' OR ...")  # rollback seed F17
    op.drop_constraint('emission_factors_cat_country_year_uniq', 'emission_factors')
    op.drop_index('idx_emission_factors_lookup', 'emission_factors')
    op.drop_column('emission_factors', 'year')
```

## 7. Considérations multi-tenant (F02) et RLS

- `emission_factors.account_id = NULL` pour le catalogue commun ⇒ visible par toutes les PME via la policy F02 (lecture publique sur `account_id IS NULL`).
- `carbon_emission_entries.account_id` est hérité de `assessment.account_id` (déjà multi-tenant en F02). Pas de modification nécessaire.

## 8. Considérations sourçage (F01) et validator

- Le validator `source_required` (F01) est déjà actif sur le `carbon_node`.
- Après F17 : tous les chiffres carbone affichés ont un `source_id` ⇒ le LLM peut citer via `cite_source(source_id)` ⇒ le validator passe.
- Le seed F17 réutilise les `Source` existantes (ADEME v23, IPCC AR6, IEA Africa) seedées par F01 ; pas de nouvelle source nécessaire au MVP.
