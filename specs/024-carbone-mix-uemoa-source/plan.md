# Implementation Plan: F17 — Carbone Mix UEMOA + Facteurs ADEME/IPCC Sourcés + Catégorie Achats

**Branch**: `feat/F17-carbone-mix-uemoa-source` (alias SpecKit `024-carbone-mix-uemoa-source`)
**Date**: 2026-05-07
**Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/024-carbone-mix-uemoa-source/spec.md`

## Summary

F17 migre les facteurs d'émission carbone codés en dur (`backend/app/modules/carbon/emission_factors.py`) vers la table BDD `emission_factors` créée par F01, peuplée via un seed admin idempotent (~50 lignes initiales). Mix électrique pays-spécifique pour les 8 pays UEMOA (CI/SN/BF/ML/NE/BJ/TG/GW) avec sources ADEME Base Carbone v23, IPCC AR6 WG3 et IEA Africa Energy Outlook 2024 (déjà seedées par F01). Refactor du modèle `CarbonEmissionEntry` : ajout de `source_id` + `factor_id` (UUID FK NOT NULL), conservation legacy `source_description` 2 sprints. Service `get_emission_factor(category, country, year)` avec priorité pays/année. Nouvelle catégorie « Achats » (`purchases_*`) intégrée au calcul. Plan de réduction sourcé (schéma JSON canonique avec `source_id` optionnel + flag `unsourced`). Composant Vue `<EmissionFactorBadge>` réutilisable avec `<SourceLink>` (F01) cliquable. Migration Alembic réversible avec backfill par matching `subcategory` ↔ `emission_factors.code`. Tests E2E Playwright avec backend mocké couvrant les 4 scénarios principaux.

## Technical Context

**Language/Version** : Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies** :
- Backend : FastAPI, SQLAlchemy async (asyncpg), Alembic, Pydantic v2, LangGraph (≥0.2.0), LangChain (≥0.3.0), langchain-openai
- Frontend : Nuxt 4, Vue 3 Composition API, Pinia, TailwindCSS 4, Chart.js, vue-chartjs, DOMPurify
**Storage** : PostgreSQL 16 + pgvector (extension), Alembic pour migrations
**Testing** :
- Backend : pytest, pytest-asyncio, pytest-cov (couverture ≥ 80 %)
- Frontend : Vitest + @vue/test-utils + @vitest/coverage-v8 + happy-dom
- E2E : Playwright (`@playwright/test`) avec backend mocké
**Target Platform** : Linux server (Docker) + navigateurs modernes (Chrome/Firefox/Safari)
**Project Type** : Web application (backend + frontend séparés)
**Performance Goals** :
- Lookup `get_emission_factor` en < 50 ms p95 (index composite sur `(category, country, year)`)
- Seed admin idempotent en < 5 s pour ~50 lignes
- Migration Alembic up/down/up en < 30 s sur base de dev
- Aucune régression sur le module carbone (temps de réponse `save_emission_entry` inchangé ± 20 %)
**Constraints** :
- Multi-tenant strict (F02) : facteurs `emission_factors.account_id = NULL` (catalogue commun lecture publique)
- Sourçage obligatoire (F01) : toute valeur affichée DOIT être liée à une `Source` `verified` via `cite_source`
- Migration backfill non destructive (entries historiques conservées)
- Conservation legacy `source_description` 2 sprints (réversibilité)
- Dark mode obligatoire sur composant `<EmissionFactorBadge>` et page `/carbon/results`
- Français avec accents dans tous les contenus utilisateur
**Scale/Scope** :
- 50 lignes seedées initiales dans `emission_factors`
- 8 pays UEMOA × 1 facteur électricité × 1 année = 8 lignes électricité minimum
- ~30 PME pilotes avec ~1-3 bilans carbone chacune (entries historiques à backfiller : < 1000)
- 1 nouveau composant Vue, 1 service backend, 1 migration Alembic, 1 spec E2E

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Statut | Justification |
|----------|--------|---------------|
| **I. Francophone-First & Contextualisation Africaine** | PASS | Mix électrique 8 pays UEMOA (CI/SN/BF/ML/NE/BJ/TG/GW) priorisé. Sources IEA Africa Energy Outlook 2024 préférées à ADEME pour électricité africaine. Tous les libellés UI et messages d'erreur en français avec accents. |
| **II. Architecture Modulaire** | PASS | Modifications cantonnées au module carbone (`backend/app/modules/carbon/`, `backend/app/graph/tools/carbon_tools.py`, `backend/app/prompts/carbon.py`, `frontend/app/pages/carbon/`). Aucun changement transversal hors `backend/app/models/carbon.py` et `backend/app/models/emission_factor.py` (table catalogue F01). Pas de touche aux zones interdites (graph.py, system.py, main.py, deps.py, etc.). |
| **III. Conversation-Driven UX** | PASS | Le LLM (carbon_node) reste le pilote ; refactor du tool `save_emission_entry` pour qu'il demande au LLM le pays via le profil entreprise et utilise le service `get_emission_factor`. Pas de nouveau formulaire UI, juste l'amélioration du badge dans la page résultats. |
| **IV. Test-First (NON-NEGOTIABLE)** | PASS | Plan TDD : tests pytest écrits AVANT le service `get_emission_factor`, le tool refactoré, le seed. Tests Vitest pour `<EmissionFactorBadge>`. Couverture ≥ 80 %. Test E2E Playwright `F17-carbone-mix-uemoa-source.spec.ts` avec backend mocké. |
| **V. Sécurité & Protection des Données** | PASS | Aucun secret hardcodé. Validation Pydantic stricte sur `EmissionFactorCreate` (categorie/pays/année/value/unit). Requêtes SQLAlchemy ORM (jamais de concaténation). RLS PostgreSQL F02 honorée (account_id NULL = catalogue lecture publique). Tool admin (seed) protégé par `Depends(get_current_admin)` (réutilise pattern F01). |
| **VI. Inclusivité & Accessibilité** | PASS | `<EmissionFactorBadge>` ARIA-conforme (rôle `region`, label descriptif), keyboard-navigable, dark mode obligatoire. Pas de dépendance JS lourde. |
| **VII. Simplicité** | PASS | Réutilise les modèles F01 existants (`Source`, `EmissionFactor`), juste ajoute la colonne `year` et étend `CarbonEmissionEntry`. Pas de nouvelle table métier. Pas d'introduction de Redis/Celery. |
| **Invariants projet n°1 (sourçage F01)** | PASS | Chaque facteur lié à `source_id` NOT NULL ; chaque `CarbonEmissionEntry` lié à `source_id` + `factor_id` NOT NULL ; LLM appelle `cite_source` post-tool. |
| **Invariants projet n°2 (multi-tenant F02)** | PASS | `emission_factors.account_id = NULL` (catalogue commun) ; `carbon_emission_entries.account_id` hérité de `assessment_id` (déjà multi-tenant). |
| **Invariants projet n°7 (admin only catalogue)** | PASS | Seed F17 protégé par `get_current_admin` (cohérent F01). Aucun tool LLM ne mute `emission_factors`. |
| **Invariants projet n°8 (dark mode)** | PASS | `<EmissionFactorBadge>` implémente toutes les variantes `dark:` (bg-white dark:bg-dark-card, text-surface-text dark:text-surface-dark-text, etc.). |
| **Invariants projet n°9 (réutilisabilité composants)** | PASS | Vérifié l'absence d'un composant équivalent dans `frontend/app/components/`. Le composant créé est lui-même réutilisable (props `factor`, `source`, `label`). Réutilise `<SourceLink>` F01. |

**Décision constitutionnelle** : ✅ TOUS LES GATES PASSENT. Aucune violation à justifier dans Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/024-carbone-mix-uemoa-source/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (interfaces backend)
│   └── carbon-emission-factor.md
├── checklists/
│   └── requirements.md  # Spec quality checklist
├── spec.md              # Feature specification
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
backend/
├── alembic/
│   └── versions/
│       └── 024_carbone_mix_uemoa.py    # NEW migration
├── app/
│   ├── models/
│   │   ├── emission_factor.py        # MODIFIED : ajoute colonne `year` + UNIQUE constraint
│   │   └── carbon.py                 # MODIFIED : ajoute source_id + factor_id sur CarbonEmissionEntry
│   ├── modules/
│   │   └── carbon/
│   │       ├── emission_factors.py   # MODIFIED : suppression EMISSION_FACTORS, helpers compute_emissions_tco2e/equivalences/applicable_categories conservés
│   │       ├── factor_service.py     # NEW : service get_emission_factor(category, country, year)
│   │       ├── service.py            # MODIFIED : add_entries valide source_id + factor_id
│   │       ├── schemas.py            # MODIFIED : EmissionEntryCreate ajoute source_id + factor_id
│   │       ├── seed_factors.py       # NEW : seed admin ~50 lignes (idempotent)
│   │       └── reduction_plan_schema.py  # NEW : Pydantic schema pour ReductionPlanAction
│   ├── graph/
│   │   └── tools/
│   │       └── carbon_tools.py       # MODIFIED : save_emission_entry refactoré (utilise factor_service)
│   ├── prompts/
│   │   └── carbon.py                 # MODIFIED : prompt enrichi pour utiliser country + cite_source
│   └── routers/
│       └── admin.py                  # MODIFIED : ajoute endpoint POST /admin/carbon/seed-factors
└── tests/
    ├── unit/
    │   ├── test_factor_service.py            # NEW
    │   ├── test_seed_factors.py              # NEW
    │   ├── test_carbon_tools_f17.py          # NEW
    │   └── test_reduction_plan_schema.py     # NEW
    ├── integration/
    │   └── test_carbon_pipeline_f17.py       # NEW : flux complet save → factor → backfill
    └── migrations/
        └── test_alembic_f17.py               # NEW : up/down/up + backfill

frontend/
├── app/
│   ├── components/
│   │   └── EmissionFactorBadge.vue   # NEW
│   └── pages/
│       └── carbon/
│           └── results.vue            # MODIFIED : intègre <EmissionFactorBadge>
└── tests/
    ├── unit/
    │   └── EmissionFactorBadge.spec.ts   # NEW
    └── e2e/
        └── F17-carbone-mix-uemoa-source.spec.ts   # NEW
```

**Structure Decision** : Web application (backend FastAPI + frontend Nuxt 4 séparés). Tous les nouveaux fichiers backend dans `backend/app/modules/carbon/` ou `backend/tests/` ; côté frontend, un nouveau composant `EmissionFactorBadge.vue` et la mise à jour de `pages/carbon/results.vue`. Migration Alembic dans `backend/alembic/versions/` (numéro à définir au moment de l'implémentation selon l'ordre de merge des autres features). Le backend conserve un seul module `carbon` ; pas de nouveau sous-module créé.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Aucune violation. Tous les gates passent. Cette section reste vide.

## Phase 0 — Outline & Research

Voir [research.md](./research.md). Synthèse :

- **Décision** : Ajout colonne `year: Integer NOT NULL` à `emission_factors` (clarification Q1 du spec). Justification : index composite `(category, country, year)` performant, pas de parsing fragile de chaîne. Alternative rejetée : encodage dans `code` (parsing coûteux + fragile).
- **Décision** : Conversion FCFA → tonnes via `simulation_factors` (clarification Q2). Justification : table déjà prévue par F01 pour conversions économiques. Alternative rejetée : entrées `prices_*` dans `emission_factors` (mélange dimensions physiques et monétaires).
- **Décision** : Backfill matching strict `subcategory` ↔ `emission_factors.code` puis fallback générique global (clarification Q3). Justification : minimise les surprises sémantiques.
- **Décision** : Schéma JSON canonique pour `reduction_plan` (clarification Q4). Justification : permet validation Pydantic et type TS frontend.
- **Décision** : Conservation legacy `source_description` 2 sprints (clarification Q5). Justification : décision orchestrateur par défaut, réversibilité de migration.
- **Décision** : Pour le seed des facteurs ciment/acier/papier/etc., reprendre les valeurs ADEME Base Carbone v23 publiées (chapitres « Matériaux »). Pour le mix électrique UEMOA, reprendre les facteurs IEA Africa Energy Outlook 2024 (Sub-Saharan Africa Power Mix Tables) et les chiffres BCEAO/CIE pour la CI. Documenter chaque valeur avec page de référence.
- **Décision** : Pas de cache LRU sur `get_emission_factor` au MVP (volume faible : 50 lignes, lookup simple). Re-évaluer post-MVP si besoin.
- **Décision** : Le backfill se fait dans la migration Alembic elle-même (op.execute SQL ou requête SQLAlchemy via `op.get_bind()`), pas dans un script séparé. Avantage : cohérence transactionnelle, rollback possible.

## Phase 1 — Design & Contracts

Voir [data-model.md](./data-model.md), [contracts/carbon-emission-factor.md](./contracts/carbon-emission-factor.md), [quickstart.md](./quickstart.md). Synthèse :

### Modèles BDD modifiés

- `EmissionFactor` (extension F17) : ajout colonne `year: Integer NOT NULL`, contrainte `UNIQUE (category, country, year)`, index composite `idx_emission_factors_lookup (category, country, year)`.
- `CarbonEmissionEntry` (extension F17) : ajout `source_id: UUID NOT NULL FK sources.id`, `factor_id: UUID NOT NULL FK emission_factors.id`. Conservation legacy `source_description: String(500) | NULL`.

### Service backend nouveau

- `app/modules/carbon/factor_service.py::get_emission_factor(db, category, country, year) -> EmissionFactorWithFlags` : retourne le facteur + flag `is_approximate` (booléen) selon priorité de fallback (pays exact + année exacte > pays + année antérieure > global + année exacte > global + antérieure).

### Tools LangChain modifiés

- `save_emission_entry` (refactor) : signature inchangée côté LLM mais lit le `country` du profil entreprise via `get_db_and_user(config)`, appelle `get_emission_factor`, stocke `source_id` + `factor_id` dans l'entrée, retourne `factor_used` + `source_id` dans le JSON résultat pour que le LLM puisse appeler `cite_source(source_id)`.

### Frontend

- `EmissionFactorBadge.vue` : composant atomique (~80 lignes) prenant 3 props (`factor: { value, unit, label }`, `source: SourceLite`, `isApproximate?: boolean`), affichant `<span>label</span> <span>{value} {unit}</span> <SourceLink :source="source"/>`. Variant `is-approximate` ajoute un picto warning + tooltip « facteur approximatif ». Dark mode complet.
- `pages/carbon/results.vue` : intègre `<EmissionFactorBadge>` dans la liste des entrées et dans le bloc plan de réduction.

### Migration Alembic

- Up : (1) ALTER TABLE `emission_factors` ADD COLUMN `year` INTEGER avec valeur par défaut 2024 ; (2) UPDATE `emission_factors` SET `year` = 2024 (rétro-compatibilité avec entrées F01 existantes) ; (3) ALTER COLUMN `year` SET NOT NULL ; (4) DROP DEFAULT ; (5) CREATE UNIQUE INDEX + CREATE INDEX composite ; (6) seed `~50 lignes` via `op.bulk_insert` ; (7) ALTER TABLE `carbon_emission_entries` ADD COLUMN `source_id` UUID NULL + `factor_id` UUID NULL ; (8) backfill via SQL/Python (matching subcategory→code, fallback générique) ; (9) ALTER COLUMN `source_id` SET NOT NULL + `factor_id` SET NOT NULL ; (10) ADD FOREIGN KEY constraints.
- Down : symétrique inversé. Suppression des FK, NULL des colonnes, DROP COLUMN `source_id` + `factor_id`, suppression des seedés F17 (UPDATE par `created_by_user_id = system_admin_id`), DROP INDEX, DROP COLUMN `year`.

### Endpoints API

- Aucun nouvel endpoint REST côté utilisateur PME (le tool LangChain `save_emission_entry` reste le point d'entrée).
- Nouvel endpoint admin : `POST /api/admin/carbon/seed-factors` (idempotent, protégé par `get_current_admin`, retourne le nombre de lignes ajoutées/ignorées).

### Update agent context

- Lancer `.specify/scripts/bash/update-agent-context.sh claude` après finalisation de Phase 1 pour mettre à jour CLAUDE.md avec les nouvelles entrées (Active Technologies, Recent Changes).

## Re-évaluation Constitution Check (post-design Phase 1)

| Gate | Statut | Notes |
|------|--------|-------|
| I. Francophone-First | PASS | Inchangé. |
| II. Architecture Modulaire | PASS | Inchangé. |
| III. Conversation-Driven | PASS | Aucun nouveau formulaire UI ; juste enrichissement du badge. |
| IV. Test-First | PASS | Phase 1 confirme la suite de tests TDD planifiée. |
| V. Sécurité | PASS | Inchangé. Endpoint seed protégé. |
| VI. Inclusivité | PASS | Composant ARIA + dark mode confirmés. |
| Invariants 1, 2, 7, 8, 9 | PASS | Inchangés. |

**Décision finale Constitution** : ✅ Plan validé pour génération des tasks (Phase 2 via `/speckit.tasks`).
