# Implementation Plan: F13 — Scoring ESG Multi-Référentiels

**Branch**: `feat/F13-scoring-multi-referentiels` (alias SpecKit `030-scoring-multi-referentiels`)
**Date**: 2026-05-07
**Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/030-scoring-multi-referentiels/spec.md`

## Summary

F13 introduit un **scoring ESG multi-référentiels** qui complète le score « ESG Mefali » mono-référentiel actuel par des scores détaillés par référentiel (GCF, IFC PS, BOAD ESS, GRI 2021, ODD post-MVP), tous calculés à partir du **même catalogue d'indicateurs** (F01) — une seule saisie d'indicateur PME alimente N scores sans duplication. Concrètement : (1) **création de la table `referential_scores`** (id, account_id RLS F02, assessment_id, referential_id, referential_version snapshot F04, overall_score, pillar_scores JSONB, coverage_rate, covered_criteria/missing_criteria avec `source_id` F01, gap_to_threshold, eligibility, computed_at, computed_by enum, computed_request_id, superseded_by self-ref pour pattern F04, created_at, updated_at) avec index unique partiel `(assessment_id, referential_id) WHERE superseded_by IS NULL` ; (2) **service `compute_all_referential_scores(assessment_id, only_referentials_using_indicators=None)`** qui calcule en parallèle (asyncio.gather) tous les référentiels actifs (UPSERT idempotent), et **`compute_referential_score_for_offer(assessment_id, offer_id)`** qui retourne `(score_fonds, score_intermediaire)` avec fallback Mefali si `fund.referential_id IS NULL` ; (3) **refactor du node LangGraph `esg_scoring_node`** pour appeler `compute_all_referential_scores` + maintenir les colonnes legacy `esg_assessments.overall_score|environment_score|social_score|governance_score` 2 sprints (cohérence F11 dashboard) ; (4) **3 tools LangChain** (`finalize_esg_assessment` refactorisé pour accepter `referentials_to_compute: list[str]`, **nouveaux** `recompute_score(entity_id, referentiel_id)` et `compare_referentials(assessment_id, referentials)`) avec instrumentation `tool_call_logs` (F12) ; (5) **endpoint `POST /api/reports/esg/{id}/generate` refactorisé** acceptant body `{referentials: list[str], include_appendix_sources: bool}` (defaults `["mefali"]`/`true` pour rétrocompatibilité F06), retournant `202 Accepted` avec génération PDF asynchrone via background task ; (6) **refactor du template Jinja2 `esg_report.html`** avec section dynamique par référentiel + tableau comparatif transverse + annexe « Sources et références » F01 + bannière coverage < 50 % ; (7) **frontend** : 4 nouveaux composants Vue (`ReferentialSelector`, `ReferentialScoreCard`, `DualReferentialView`, `MissingCriteriaList`) tous dark-mode + ARIA, refactor des pages `/esg/results.vue` (sélecteur + mode côte-à-côte) et `/financing/offers/[id].vue` (section dual view avec goulot d'étranglement), composable `useEsgMultiReferential.ts`, mise à jour store `esg.ts`, types TypeScript étendus ; (8) **migration Alembic 030_create_referential_scores** réversible avec `down_revision="028_offers_and_enrich"` (F11/029 sans migration), seed Mefali comme référentiel à part entière dans `referentials` + 4 référentiels MVP supplémentaires si non seedés par F01, backfill de toutes les `EsgAssessment` existantes vers `referential_scores` (Mefali) ; (9) **cron mensuel** `scripts/check_referential_versions_evolution.py` qui crée des reminders F11 `kind='referential_version_evolved'` pour les PMEs concernées par une évolution de version de référentiel ; (10) **tests** : couverture ≥ 80 % unit/integration backend + 80 % composants frontend + 3 scénarios E2E Playwright (`F13-scoring-multi-referentiels.spec.ts`) couvrant US1, US2, US3.

## Technical Context

**Language/Version** : Python 3.12 (backend), TypeScript 5.x strict (frontend)

**Primary Dependencies** :
- Backend : FastAPI, SQLAlchemy async (asyncpg), Alembic, Pydantic v2, LangGraph + LangChain (tools), `app.core.auditable` (mixin F03 pour journaliser les recalculs et fallbacks), `app.modules.currency` (non-utilisé directement F13 mais conservé pour Money typed des seuils si exprimés en montants), WeasyPrint + Jinja2 + matplotlib (refactor template PDF F06), `BackgroundTasks` FastAPI (in-memory MVP pour recalcul async)
- Frontend : Nuxt 4, Vue 3 Composition API, Pinia, TailwindCSS 4 (dark mode), Chart.js + vue-chartjs (radar par pilier, déjà en place), DOMPurify (rendu critères avec sources cliquables), `marked` (descriptions enrichies si Markdown dans définitions critères)

**Storage** : PostgreSQL 16 + pgvector, Alembic pour migrations. Pas de stockage fichiers nouveau (les PDF générés réutilisent `/uploads/reports/` existant F06).

**Testing** :
- Backend : pytest, pytest-asyncio, pytest-cov (couverture ≥ 80 % sur `app/modules/esg/multi_referential_service.py`, refactor `app/modules/esg/service.py`, refactor `app/graph/nodes.py:esg_scoring_node`, extension `app/graph/tools/esg_tools.py`, refactor endpoint `POST /api/reports/esg/{id}/generate`, refactor template `esg_report.html`, cron `check_referential_versions_evolution.py`)
- Frontend : Vitest + @vue/test-utils + @vitest/coverage-v8 + happy-dom (couverture ≥ 80 % sur les 4 nouveaux composants, le composable `useEsgMultiReferential.ts`, et les pages `/esg/results.vue` + `/financing/offers/[id].vue` refactorées)
- E2E : Playwright (`@playwright/test`) — fichier `frontend/tests/e2e/F13-scoring-multi-referentiels.spec.ts` avec 3 scénarios couvrant US1 (sélecteur multi-réf), US2 (dual view goulot), US3 (PDF [Mefali, IFC])

**Target Platform** : Linux server (Docker) + navigateurs modernes (Chrome/Firefox/Safari)

**Project Type** : Web application (backend FastAPI + frontend Nuxt 4 séparés)

**Performance Goals** :
- `compute_all_referential_scores` pour 5 référentiels et 35 indicateurs : < 5 s p95 (asyncio.gather parallèle, 1 SELECT par referential, en mémoire) (SC-002)
- `compute_referential_score_for_offer` : < 800 ms p95 (2 calculs ciblés en parallèle + lecture Offer + fallback éventuel Mefali)
- `GET /api/esg/assessments/{id}/referential-scores` : < 200 ms p95 (1 SELECT avec index `(assessment_id, computed_at DESC) WHERE superseded_by IS NULL`)
- Bascule UI sélecteur de référentiel sur `/esg/results` : < 500 ms (changement local Vue, pas de fetch ; les 5 scores sont préchargés au mount) (SC-001)
- PDF multi-référentiels (5 référentiels + annexe sources) : < 30 s (background task, WeasyPrint + matplotlib SVG) (SC-003)
- Latence saisie indicateur → score visible : < 10 s (recalcul async background task + polling 2 s frontend) (SC-006)
- Migration Alembic up/down/up sur base de dev avec ~50 EsgAssessment existantes : < 60 s

**Constraints** :
- Multi-tenant strict (F02 invariant n°2) : table `referential_scores` a `account_id NOT NULL` + RLS PostgreSQL `account_id = current_setting('app.current_account_id')` ; aucune fuite cross-tenant (SC-009).
- Sourçage F01 invariant n°1 : tous les `covered_criteria.*` et `missing_criteria.*` portent un `source_id` FK vers `sources.id` ; le frontend affiche les sources cliquables via `<SourceLink>` (SC-008).
- Audit log F03 invariant n°3 : table `referential_scores` exempte du mixin `Auditable` (les scores sont des artefacts calculés, pas des mutations métier au sens strict) ; mais les **événements de recalcul échec/partiel/fallback** sont journalisés explicitement via `audit_context.set_current_source_of_change('referential_score_recompute')` avec actions `referential_score_recompute_failed`, `referential_score_recompute_partial`, `dual_view_fallback_used`. Le cron `check_referential_versions_evolution.py` journalise via `audit_context.set_current_source_of_change('cron_referential_version_evolution')`.
- Versioning F04 invariant n°4 : `referential_version` snapshot semver `referentials.version` au moment du calcul ; pattern `superseded_by` self-référent pour historisation (cohérent avec Fund/Intermediary versioning F04). Pas de Money typed à introduire (les scores sont des Numeric pures, pas des montants).
- RGPD F05 invariant n°5 : non concerné directement (les scores agrégés ne contiennent pas de PII brute) — mais `account_id` lié reste protégé par RLS et la suppression de compte (F05 J+30) cascade ON DELETE via `esg_assessments`.
- Aucun secret hardcodé : codes de référentiels (`mefali`, `gcf`, `ifc_ps`, `boad_ess`, `gri_2021`) en constantes Python typées ; aucune URL/clé externe.
- Aucun tool LLM ne mute le catalogue (invariant n°7) : les 3 tools (`finalize_esg_assessment`, `recompute_score`, `compare_referentials`) sont en lecture/calcul seul ; ils mutent uniquement la table `referential_scores` (artefact calculé, pas catalogue).
- Dark mode obligatoire : 4 nouveaux composants Vue + 2 pages refactorées avec variantes `dark:` Tailwind sur tous les éléments visuels (cf. CLAUDE.md section dark mode).
- Réutilisabilité composants : avant création, vérifier `frontend/app/components/ui/` (Card, Badge, Modal, Select existants F11) ; `<ReferentialSelector>` réutilise `<UiSelect>` ; `<ReferentialScoreCard>` réutilise `<UiCard>` + composants Chart.js existants F05 ; `<MissingCriteriaList>` réutilise `<SourceLink>` F01.
- Français avec accents dans tout le contenu UI (titres, descriptions, badges, tooltips, messages d'erreur) ; libellés audit_log en anglais snake_case (cohérent F03).
- Tests E2E Playwright exécutables : `frontend/tests/e2e/F13-scoring-multi-referentiels.spec.ts` (3 scénarios), runnable via `cd frontend && npx playwright test tests/e2e/F13-scoring-multi-referentiels.spec.ts --reporter=html`.

**Scale/Scope** :
- 1 nouvelle table BDD (`referential_scores`)
- 1 migration Alembic réversible avec backfill (`030_create_referential_scores`) + seed Mefali + seed des 4 référentiels MVP supplémentaires (idempotent)
- 4 endpoints REST mis à jour ou nouveaux : `GET /api/esg/assessments/{id}/referential-scores`, `GET /api/esg/assessments/{id}/referential-scores/history`, `POST /api/esg/assessments/{id}/recompute-score?referentiel_id=X`, `POST /api/reports/esg/{id}/generate` (refactor body)
- 3 tools LangChain (1 refactorisé, 2 nouveaux)
- 1 module backend nouveau `app/modules/esg/multi_referential_service.py` + extensions sur `app/modules/esg/service.py`, `app/modules/reports/`, `app/graph/nodes.py`, `app/graph/tools/esg_tools.py`
- 1 cron Python (`backend/scripts/check_referential_versions_evolution.py`)
- 4 nouveaux composants Vue dans `frontend/app/components/esg/` + 1 composable + extension store + extension types TS
- 2 pages Vue refactorées (`/esg/results.vue`, `/financing/offers/[id].vue`)
- 1 spec E2E Playwright (3 scénarios)

## Constitution Check

Conformité avec `.specify/memory/constitution.md` (v1.0.0) et invariants ESG Mefali listés dans `.cc-orchestrator.md`.

| Principe / Invariant | Statut | Justification |
|---|---|---|
| I — Francophone-First & Contextualisation Africaine | ✓ Passe | UI en français avec accents corrects ; référentiels MVP couvrent BOAD ESS (UEMOA) en plus des standards internationaux ; dark mode + accessibilité ARIA. |
| II — Architecture Modulaire | ✓ Passe | Module `app/modules/esg/multi_referential_service.py` indépendant ; couplage faible avec `app/modules/reports/` (consommateur des scores) et `app/modules/esg/service.py` (qui expose `compute_score_for_referential` réutilisable). |
| III — Conversation-Driven UX | ✓ Passe | 3 tools LangChain permettent au chat de comparer, recalculer, finaliser ; le sélecteur UI est un complément, pas un remplacement. |
| IV — Test-First (NON-NÉGOCIABLE) | ✓ Passe | Tests écrits AVANT l'implémentation pour chaque tâche (TDD) ; couverture ≥ 80 % backend + frontend ; 3 scénarios E2E Playwright. |
| V — Sécurité & Protection des Données | ✓ Passe | RLS PostgreSQL stricte ; aucun secret hardcodé ; validation Pydantic v2 sur tous les inputs ; aucune fuite cross-tenant (SC-009 testé). |
| VI — Inclusivité & Accessibilité | ✓ Passe | Dark mode obligatoire ; rôles ARIA sur les composants ; messages d'erreur en français clair ; latence < 500 ms pour le sélecteur (connexions lentes OK). |
| VII — Simplicité & YAGNI | ✓ Passe | `BackgroundTasks` FastAPI in-memory plutôt que Redis+Celery (post-MVP) ; pattern `superseded_by` réutilise F04 plutôt qu'introduire une table d'historique séparée ; reuse des reminders F11 plutôt qu'une nouvelle table notifications. |
| 1 — Sourçage F01 obligatoire | ✓ Passe | `covered_criteria.*.source_id` + `missing_criteria.*.source_id` ; tous chiffres affichés liés à une `Source verified` ; annexe PDF auto-générée (FR-039). |
| 2 — Multi-tenant strict F02 | ✓ Passe | `account_id NOT NULL` + RLS PostgreSQL stricte sur `referential_scores` ; SC-009 vérifié par test E2E avec 2 comptes A et B. |
| 3 — Audit log append-only F03 | ✓ Passe | Mixin `Auditable` non appliqué (artefact calculé), mais événements `referential_score_recompute_failed`, `referential_score_recompute_partial`, `dual_view_fallback_used`, `cron_referential_version_evolution` journalisés via `audit_context`. |
| 4 — Versioning + Money typed F04 | ✓ Passe | Pattern `superseded_by` self-référent réutilisé ; `referential_version` semver snapshot ; pas de Money typed (scores Numeric purs). |
| 5 — RGPD F05 | ✓ Passe (N/A) | Pas de PII directe ; cascade ON DELETE via `esg_assessments` (suppression J+30 F05 propage). |
| 6 — Aucun secret hardcodé | ✓ Passe | Codes référentiels en constantes Python ; pas d'URL/clé externe nouvelle. |
| 7 — Aucun tool LLM ne mute le catalogue | ✓ Passe | 3 tools mutent uniquement `referential_scores` (artefact calculé) ; le catalogue (`referentials`, `indicators`, `sources`) reste réservé Admin F09 (FR-029). |
| 8 — Dark mode obligatoire | ✓ Passe | 4 composants Vue + 2 pages refactorées avec variantes `dark:` Tailwind systématiques. |
| 9 — Réutilisabilité composants | ✓ Passe | Audit `components/ui/` réalisé ; réutilisation `<UiSelect>`, `<UiCard>`, `<SourceLink>` (F01), `<MetricBadge>` ; pattern de radar Chart.js déjà extrait F05. |
| 10 — Français avec accents | ✓ Passe | Contenus UI en français (titres, descriptions, messages d'erreur, badges, tooltips). |
| 11 — Tests E2E Playwright | ✓ Passe | `frontend/tests/e2e/F13-scoring-multi-referentiels.spec.ts` avec 3 scénarios exécutables. |
| 12 — Couverture tests ≥ 80 % | ✓ Passe | Cibles fixées : 80%+ backend (multi_referential_service, refactor service, refactor node, tools, refactor endpoint+template, cron) + 80%+ frontend (4 composants + composable + 2 pages refactorées). |

**Conclusion** : Aucune violation. Pas de section « Complexity Tracking » nécessaire.

## Project Structure

### Documentation (this feature)

```text
specs/030-scoring-multi-referentiels/
├── spec.md              # /speckit.specify (created)
├── plan.md              # /speckit.plan (this file)
├── research.md          # Phase 0 (this command)
├── data-model.md        # Phase 1 (this command)
├── quickstart.md        # Phase 1 (this command)
├── contracts/           # Phase 1 (this command)
│   ├── openapi-referential-scores.yaml
│   ├── openapi-reports-multi-ref.yaml
│   └── tools-langchain.md
├── checklists/
│   └── requirements.md  # Quality checklist (created)
└── tasks.md             # /speckit.tasks (next command)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── models/
│   │   ├── esg.py                       # PRESERVED : EsgAssessment, IndicatorValue (legacy columns kept 2 sprints)
│   │   ├── referential.py               # EXISTING (F01) : Referential, Indicator, ReferentialIndicator (read-only catalog)
│   │   └── referential_score.py         # NEW : modèle SQLAlchemy ReferentialScore + enum ComputedBy + relations
│   ├── schemas/
│   │   └── referential_score.py         # NEW : Pydantic ReferentialScoreRead, ReferentialScoreCreate, PillarScore, CoveredCriterion, MissingCriterion, ComparisonResult, RecomputeRequestResponse
│   ├── modules/
│   │   ├── esg/
│   │   │   ├── service.py               # REFACTORED : extract compute_score_for_referential generic ; preserve compute_overall_score 2 sprints
│   │   │   ├── multi_referential_service.py  # NEW : compute_all_referential_scores + compute_referential_score_for_offer + recompute_score_async + helpers
│   │   │   ├── router.py                # EXTENDED : 3 nouveaux endpoints (GET referential-scores, GET history, POST recompute-score)
│   │   │   └── schemas.py               # PRESERVED : EsgAssessmentRead extended with referential_scores list
│   │   └── reports/
│   │       ├── router.py                # REFACTORED : POST /api/reports/esg/{id}/generate accepte body {referentials, include_appendix_sources}
│   │       ├── service.py               # REFACTORED : generate_multi_referential_pdf(...)
│   │       └── templates/
│   │           ├── esg_report.html      # REFACTORED : section dynamique par référentiel + tableau comparatif + annexe sources
│   │           └── _appendix_sources.html  # NEW : partial Jinja2 pour l'annexe sources F01
│   ├── graph/
│   │   ├── nodes.py                     # REFACTORED : esg_scoring_node appelle compute_all_referential_scores + maintient legacy columns
│   │   └── tools/
│   │       └── esg_tools.py             # REFACTORED + EXTENDED : finalize_esg_assessment refactored ; recompute_score nouveau ; compare_referentials nouveau ; instrumentation tool_call_logs F12
│   ├── core/
│   │   └── constants.py                 # EXTENDED : MEFALI_REFERENTIAL_CODE='mefali', GCF_REFERENTIAL_CODE='gcf', etc. + MEFALI_REFERENTIAL_UUID stable
│   └── main.py                          # PROTECTED ZONE : pas de modification
├── alembic/
│   └── versions/
│       └── 030_create_referential_scores.py  # NEW migration : table + indexes + RLS + seed Mefali + seed 4 réf MVP + backfill EsgAssessment → referential_scores
├── scripts/
│   └── check_referential_versions_evolution.py  # NEW : cron mensuel idempotent
└── tests/
    ├── unit/
    │   ├── test_multi_referential_service.py     # NEW : compute_all_referential_scores, compute_referential_score_for_offer, edge cases (coverage=0, fallback Mefali, parallèle)
    │   ├── test_referential_score_model.py        # NEW : invariants table referential_scores, contrainte unique partielle
    │   ├── test_compute_score_for_referential.py  # NEW : refactor service.py, pondération qui ignore non-renseignés
    │   ├── test_pydantic_schemas_referential_score.py  # NEW : validation Pydantic schemas (CoveredCriterion, MissingCriterion, ComparisonResult, etc.)
    │   ├── test_esg_tools_multi_ref.py             # NEW : finalize_esg_assessment refactor, recompute_score, compare_referentials
    │   └── test_check_referential_versions_evolution.py  # NEW : cron idempotent + reminder F11 created
    ├── integration/
    │   ├── test_referential_scores_router.py      # NEW : GET referential-scores, GET history, POST recompute-score (RLS + 404 cross-tenant)
    │   ├── test_reports_router_multi_ref.py        # NEW : POST /api/reports/esg/{id}/generate body {referentials, include_appendix_sources} ; rétrocompat ; 422 si réf invalide
    │   ├── test_esg_scoring_node_multi_ref.py     # NEW : esg_scoring_node refactor + maintenance legacy columns
    │   └── test_pdf_generation_multi_ref.py        # NEW : génération PDF avec 5 ref + annexe + bannière coverage
    ├── migrations/
    │   └── test_alembic_030.py                    # NEW : up/down/up + backfill (EsgAssessment count avant=après) + seed Mefali idempotent
    └── security/
        └── test_referential_scores_rls.py         # NEW : SC-009 (0 fuite cross-tenant via RLS)

frontend/
├── app/
│   ├── pages/
│   │   ├── esg/
│   │   │   └── results.vue              # REFACTORED : intégration <ReferentialSelector> + <ReferentialScoreCard> + mode côte-à-côte
│   │   └── financing/
│   │       └── offers/
│   │           └── [id].vue             # REFACTORED : ajout section <DualReferentialView> avec goulot
│   ├── components/
│   │   └── esg/                         # EXTENDED DIRECTORY (existant F05)
│   │       ├── ReferentialSelector.vue       # NEW
│   │       ├── ReferentialScoreCard.vue      # NEW
│   │       ├── DualReferentialView.vue       # NEW
│   │       ├── MissingCriteriaList.vue       # NEW
│   │       └── BottleneckBanner.vue          # NEW (extracted helper component pour la bannière goulot)
│   ├── composables/
│   │   ├── useEsg.ts                    # PRESERVED : non modifié (legacy F05)
│   │   └── useEsgMultiReferential.ts    # NEW : getReferentialScores, recomputeScore, compareReferentials, generateMultiReferentialReport, pollRecomputeStatus
│   ├── stores/
│   │   └── esg.ts                       # EXTENDED : referentialScores, selectedReferential, isRecomputing, recomputeRequestId, getters
│   └── types/
│       └── esg.ts                       # EXTENDED : ReferentialScore, PillarScore, CoveredCriterion, MissingCriterion, ComparisonResult, RecomputeRequestResponse, BottleneckInfo
├── nuxt.config.ts                       # PROTECTED ZONE : pas de modification
└── tests/
    ├── components/
    │   ├── esg/
    │   │   ├── ReferentialSelector.spec.ts
    │   │   ├── ReferentialScoreCard.spec.ts
    │   │   ├── DualReferentialView.spec.ts
    │   │   ├── MissingCriteriaList.spec.ts
    │   │   └── BottleneckBanner.spec.ts
    └── e2e/
        └── F13-scoring-multi-referentiels.spec.ts  # NEW : 3 scénarios Playwright (US1, US2, US3 P1)
```

**Structure Decision** : architecture web app monorepo (backend FastAPI Python 3.12 + frontend Nuxt 4 TypeScript), aligné avec la convention ESG Mefali existante. Le module `app/modules/esg/multi_referential_service.py` est isolé (helpers + 2 fonctions principales `compute_all_referential_scores` et `compute_referential_score_for_offer`) et n'introduit aucune dépendance circulaire. Le frontend respecte la convention `pages/` Nuxt 4 + `components/esg/` cohérent avec la structure existante (F05 a déjà créé `components/esg/`). Aucune zone interdite (`main.py`, `nuxt.config.ts`) n'est modifiée.

## Phase 0 — Research

Voir [research.md](./research.md) pour les décisions techniques détaillées sur :
- Stratégie de migration backfill (réversibilité, idempotence, perf, seed Mefali idempotent ON CONFLICT DO NOTHING)
- Algorithme `compute_score_for_referential` (pondération qui ignore les non-renseignés, formule pondérée, agrégation par pilier, gestion `coverage_rate`)
- Pattern d'historisation `superseded_by` (cohérence F04 ; index unique partiel PostgreSQL ; alternative considérée : table `referential_score_versions` séparée — rejetée pour simplicité)
- Stratégie de recalcul async via `BackgroundTasks` FastAPI (in-memory MVP) vs Redis+Celery (post-MVP)
- Stratégie de seed des 5 référentiels MVP (dans la migration F13 vs dépendance F01 vs F09 admin runtime)
- Stratégie d'inférence du fallback `fund.referential_id IS NULL` → ESG Mefali (helper service vs default DB column)
- Pattern API REST `/recompute-score` vs commande LangChain dédiée (réponse : les deux, l'endpoint sert l'UI directe et le tool sert le chat)
- Stratégie de tests JSONB `pillar_scores`/`covered_criteria`/`missing_criteria` (PostgreSQL `@>` containment vs in-memory dict deep_equal)

## Phase 1 — Design

### Data Model

Voir [data-model.md](./data-model.md) pour le schéma BDD complet :
- Table `referential_scores` (DDL complet : 17 colonnes + index unique partiel + 2 indexes secondaires + 1 contrainte CHECK sur `coverage_rate BETWEEN 0 AND 1`)
- ENUM PostgreSQL `referential_score_computed_by_enum` (`manual|llm|auto`)
- RLS PostgreSQL : policy `account_isolation` filtrant `account_id = current_setting('app.current_account_id')` (cohérent avec F02)
- Stratégie d'index : `(assessment_id, referential_id) WHERE superseded_by IS NULL` unique partiel ; `(assessment_id, computed_at DESC)` ; `(referential_id, computed_at DESC)` ; FK `superseded_by` → `referential_scores.id ON DELETE SET NULL`
- Seed migration : Mefali (idempotent), GCF, IFC PS, BOAD ESS, GRI 2021 dans `referentials` ; backfill `EsgAssessment` → `referential_scores` (Mefali) avec `ON CONFLICT DO NOTHING` pour idempotence
- Stratégie de cascade ON DELETE : `assessment_id` → CASCADE (supprimer les scores quand l'évaluation est supprimée par RGPD F05) ; `referential_id` → RESTRICT (empêcher la suppression d'un référentiel tant que des scores historiques existent)

### API Contracts

Voir [contracts/openapi-referential-scores.yaml](./contracts/openapi-referential-scores.yaml) (endpoints lecture + recalcul) et [contracts/openapi-reports-multi-ref.yaml](./contracts/openapi-reports-multi-ref.yaml) (endpoint refactor PDF) pour les schémas OpenAPI complets.

Endpoints publics (PME authentifiée, RLS multi-tenant) :
- `GET /api/esg/assessments/{id}/referential-scores` — liste des scores courants (filtre `superseded_by IS NULL`)
- `GET /api/esg/assessments/{id}/referential-scores/history?referential_id=X` — historique versions snapshot
- `POST /api/esg/assessments/{id}/recompute-score?referentiel_id=X` — déclenche recalcul ciblé async, réponse 202 + `recompute_request_id`
- `POST /api/reports/esg/{id}/generate` — refactorisé : body `{referentials: list[str], include_appendix_sources: bool}` (defaults `["mefali"]`/`true`) ; réponse 202 + `report_id`

Endpoints admin (rôle `admin` requis) :
- `POST /api/admin/recompute-referential-scores?account_id=X` — recalcul forcé global (pour QA / corrections)

### Tools LangChain

Voir [contracts/tools-langchain.md](./contracts/tools-langchain.md) pour les schémas Pydantic des 3 tools :
- `finalize_esg_assessment(assessment_id: UUID, referentials_to_compute: list[str] | None = None) → FinalizeAssessmentResult` — REFACTORÉ : ajoute `referentials_to_compute` ; retourne dict {ref_code: score} pour tous les ref calculés
- `recompute_score(entity_id: UUID, referentiel_id: UUID) → RecomputeRequestResponse` — NOUVEAU : enqueue background task, retourne `recompute_request_id`
- `compare_referentials(assessment_id: UUID, referentials: list[str]) → ComparisonResult` — NOUVEAU : retourne scores + gaps + critères divergents typés
- Instrumentation `tool_call_logs` F12 : chaque appel persiste arguments + réponse + durée + succès/erreur

### Quickstart

Voir [quickstart.md](./quickstart.md) pour le guide opérationnel :
- Comment lancer la migration `030_create_referential_scores` localement
- Comment vérifier le seed des 5 référentiels MVP (Mefali, GCF, IFC PS, BOAD ESS, GRI 2021)
- Comment tester le service `compute_all_referential_scores` via curl ou pytest
- Comment tester les 3 tools LangChain via le chat interactif local
- Comment générer un PDF multi-référentiels via curl
- Comment exécuter le cron `check_referential_versions_evolution.py` manuellement
- Comment tester les RLS multi-tenant (créer 2 comptes, vérifier 404 cross-tenant)

## Phase 2 — Tasks

Voir [tasks.md](./tasks.md) (généré par `/speckit.tasks`).

Note importante : `tasks.md` DOIT contenir des tests E2E **Playwright** exécutables dans `frontend/tests/e2e/F13-scoring-multi-referentiels.spec.ts` couvrant les 3 scénarios :
1. **US1** : PME ouvre `/esg/results` avec 35 indicateurs renseignés → bascule via `<ReferentialSelector>` entre Mefali (78/100) et IFC PS (52/100) → vérifie le radar par pilier IFC, le badge coverage, la liste des critères manquants avec sources cliquables.
2. **US2** : PME ouvre `/financing/offers/{id}` (offre GCF × BOAD) → vérifie l'affichage `<DualReferentialView>` avec score GCF (45/100, gauche) et score BOAD (68/100, droite) → vérifie la bannière goulot d'étranglement « GCF (45/100) » + bouton « Renseigner maintenant » qui redirige vers `/esg?focus=...`.
3. **US3** : PME clique « Générer rapport PDF » sur `/esg/results` → coche [Mefali, IFC PS] → POST `/api/reports/esg/{id}/generate` → polling jusqu'à PDF prêt → ouvre PDF → vérifie 2 sections référentiels + tableau comparatif + annexe sources F01 cliquables.

## Risks & Mitigations

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| F01 ne livre pas les 5 référentiels MVP avant F13 | Moyenne | Élevé | Seed direct dans la migration `030` pour Mefali (idempotent) ; les 4 autres référentiels sont seedés conditionnellement (`ON CONFLICT DO NOTHING`) si F01 n'a pas livré. Documentation explicite dans quickstart.md. |
| Les pondérations divergent significativement entre référentiels (PME à 80/Mefali et 30/IFC) | Élevée | Moyen | C'est exactement le but du feature (info actionnable) ; UI explique clairement les écarts via `<MissingCriteriaList>` et bannière coverage ; documentation pédagogique dans la modale détail critère. |
| Performance dégradée du `compute_all_referential_scores` (5-7 référentiels en parallèle) | Moyenne | Élevé | `asyncio.gather` natif ; chaque calcul est en mémoire (pas de I/O DB par critère, lecture en bulk) ; benchmark dans test_multi_referential_service.py vérifie SC-002 < 5s. |
| Le pattern `superseded_by` complexifie les requêtes API | Faible | Moyen | Index unique partiel `WHERE superseded_by IS NULL` rend les requêtes courantes triviales ; endpoint `/history` filtre `superseded_by IS NOT NULL` ; helper service `get_current_score` encapsule. |
| Background task FastAPI in-memory perd les jobs au redéploiement | Élevée (en prod) | Moyen | Documenté dans Assumptions ; UI affiche un toast « Recalcul perdu, réessayer » si polling timeout > 30s ; post-MVP migration vers Redis+Celery. |
| Migration backfill prend > 60s sur grosse base prod | Faible | Moyen | Backfill batch en chunks de 100 lignes via SQL stream ; `INSERT … ON CONFLICT DO NOTHING` idempotent en cas de retry ; documenté dans research.md. |
| Référentiel sans indicateurs liés (catalogue F01 vide) → score `null` puis crash UI | Moyenne | Moyen | Le service retourne `coverage_rate=0`, `overall_score=null` ; UI cache la card de ce référentiel (composant retourne `v-if="score.overall_score !== null"`) ; test `test_compute_score_for_referential_no_indicators`. |
| Refactor `esg_scoring_node` casse F11 dashboard / F06 reports | Élevée | Élevé | Maintenance des colonnes legacy `esg_assessments.overall_score|...` 2 sprints (FR-024) ; test d'intégration vérifie l'égalité `referential_scores[Mefali] == esg_assessments.overall_score` ; F11/F06 lisent les colonnes legacy en parallèle pendant la transition. |
| Cron `check_referential_versions_evolution.py` non lancé en prod | Élevée | Moyen | Documentation manuelle ou via orchestrateur externe ; F19 introduira un cron dispatcher dédié post-MVP ; le test E2E ne couvre pas le cron (test unitaire suffit pour MVP). |
| Tools LangChain renvoient des structures incohérentes au LLM | Faible | Élevé | Schemas Pydantic v2 stricts en sortie de chaque tool ; tests unitaires `test_esg_tools_multi_ref.py` vérifient la conformité ; instrumentation `tool_call_logs` permet l'audit en cas de divergence. |
| RLS PostgreSQL non appliquée à cause d'une session sans `app.current_account_id` | Faible | Critique | Helper FastAPI `get_db_session_with_rls` (existant F02) injecte systématiquement `SET LOCAL app.current_account_id = $1` au début de chaque transaction ; test sécurité `test_referential_scores_rls.py` vérifie SC-009. |

## Dependencies on other features

- **F01 (Sources + Indicators + Referentials catalogue)** : table `referentials` doit exister avec colonnes `code`, `version`, `is_active`, `threshold`, `min_coverage_for_pdf` ; table `indicators` et table de liaison `referential_indicators` doivent exister. **Statut au démarrage F13** : F01 livré (migration 020).
- **F02 (Multi-tenant + roles + RLS)** : helper `get_db_session_with_rls`, `is_admin`, table `accounts`. **Statut au démarrage F13** : F02 livré (migration 019).
- **F03 (Audit log append-only)** : `audit_context.set_current_source_of_change`, table `audit_log`. **Statut au démarrage F13** : F03 livré (migration 021).
- **F04 (Versioning + Money typed)** : pattern `superseded_by`, `VersioningMixin` ; colonne `referentials.version` semver. **Statut au démarrage F13** : F04 livré (migration 022).
- **F05 (ESG scoring assessment)** : table `esg_assessments` avec colonnes legacy `overall_score|environment_score|social_score|governance_score` et `IndicatorValues`. **Statut au démarrage F13** : F05 livré (migration 005).
- **F06 (ESG PDF reports)** : endpoint `POST /api/reports/esg/{id}/generate`, template `esg_report.html`, service WeasyPrint. **Statut au démarrage F13** : F06 livré (post-005).
- **F07 (Offer = Fonds × Intermédiaire)** : table `offers`, colonnes `funds.referential_id` et `intermediaries.referential_id`. **Statut au démarrage F13** : F07 livré (migration 028).
- **F11 (Dashboard + action plan)** : table `reminders` avec colonnes `kind`, `metadata`, `account_id` ; composable `useReminders.ts` ; lit les colonnes legacy `esg_assessments.overall_score`. **Statut au démarrage F13** : F11 livré (migration héritée 5b7f...).
- **F12 (Tool calling LangGraph)** : infrastructure tools LangChain, table `tool_call_logs`, instrumentation. **Statut au démarrage F13** : F12 livré (post-029).

Toutes les dépendances sont mergées sur main au moment du démarrage de F13. Aucun blocage.

## Out of scope (post-MVP)

- Référentiels custom par PME (auto-définis via le back-office PME)
- Calcul de scores composites pondérés (somme pondérée multi-référentiels)
- Recommandations IA priorisées par référentiel ciblé (« pour atteindre 60/IFC, renseigner ces 3 indicateurs en priorité »)
- Alertes automatiques si un nouvel indicateur change un score significativement (delta > 10 points)
- Cohort comparison sectorielle (« votre score IFC vs autres PME du même secteur en pgvector »)
- Migration vers Redis+Celery pour les background tasks (post-MVP, F19)
- Cron dispatcher dédié pour automatiser `check_referential_versions_evolution.py` (post-MVP, F19)
- Backend admin UI pour seed/édition de référentiels (F09, post-MVP) — pour MVP F13, l'admin utilise les endpoints REST directement (curl ou outil API) ou la migration seed F13.
- Suppression définitive des colonnes legacy `esg_assessments.overall_score|...` (planifié post-F13 dans une migration ultérieure, après 2 sprints de transition)

## Complexity Tracking

> Aucune violation des invariants ESG Mefali ni des principes de la constitution. Pas de justification nécessaire.
