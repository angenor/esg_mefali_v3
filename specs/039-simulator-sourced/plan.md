# Implementation Plan: F16 — Simulateur Financement Sourcé + Comparateur Multi-Offres

**Branch**: `feat/F16-simulateur-finance-source` (spec dir `specs/039-simulator-sourced`)
**Date**: 2026-05-08
**Spec**: [spec.md](./spec.md)

## Summary

Refondre le simulateur de financement existant pour rendre **traçables et sourcées** toutes les valeurs numériques produites (taux, durée, frais, garantie, marge FX, ratio d'impact, durée d'amortissement) et introduire un **comparateur multi-offres** (1 à 5 offres côte-à-côte) calculé à la demande, sans persistance MVP. Le module bascule vers Money typed (F04), s'appuie sur la table `simulation_factors` (F01), lit les délais réels d'offre (F07), utilise les ratios sectoriels (F17) pour l'impact carbone, et expose un tool LangChain rendant le composant `ComparisonTableBlock` (F11). Pas de nouvelle table, pas de migration Alembic.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy async, Pydantic v2, LangGraph, LangChain ; Nuxt 4, Vue Composition API, Pinia, TailwindCSS
**Storage**: PostgreSQL 16 + pgvector — lecture seule sur `simulation_factors`, `sources`, `offers`, `funds`, `intermediaries`, `projects`, `exchange_rates`. Aucune écriture métier. Pas de migration.
**Testing**: pytest + pytest-asyncio (backend, ≥ 80 % couverture sur `app/modules/applications/simulation.py` + nouveau `factor_service.py` + router `simulate-multi`) ; Vitest (frontend composants/composables) ; Playwright (E2E `simuler GCF/BOAD vs GCF/UNDP différents`).
**Target Platform**: API HTTP (FastAPI sous uvicorn) ; SPA Nuxt 4 SSR/SPA selon route ; navigateurs modernes desktop + mobile responsive.
**Project Type**: Web application (backend + frontend distincts).
**Performance Goals**: Comparaison côte-à-côte de 5 offres rendue en < 5 s côté API (SC-005), avec snapshot factors chargé une seule fois par appel (FR-017).
**Constraints**:
- Sourçage F01 invariant absolu (FR-002, FR-007, FR-010 ; SC-001 100 % chiffres cliquables).
- Money typed F04 partout (FR-004).
- Aucune constante numérique de calcul codée en dur dans `simulation.py` (FR-001 ; SC-002 ; garde-fou AST `test_no_magic_constants_in_simulation.py`).
- Pas de persistance des résultats (FR-012 ; SC-006).
- Multi-tenant F02 : projet et offres scopés au compte appelant via RLS PG + Depends(get_current_user) (FR-013).
- Borne dure 1..5 offres par appel (FR-014).
- Dark mode complet sur la page simulator + accessibilité clavier (FR-015).

**Scale/Scope**: Trafic faible MVP (quelques milliers de simulations/jour max). Pas de cache cross-request en MVP : chaque appel charge son propre snapshot de facteurs (acceptable au volume cible, simplifie la cohérence FR-017). Refactor concerne ~1 fichier backend simulation existant + nouveau service factor_service + 1 router + 1 tool LangChain + 1 page frontend + ~3 composants Vue + types/composables.

## Constitution Check

*GATE: doit passer avant Phase 0. Re-check après Phase 1.*

| Principe | Statut | Justification |
|----------|--------|---------------|
| I. Francophone-First & Contextualisation Africaine | PASS | UI 100 % FR (libellés "Moins chère" / "Plus rapide" / "calcul indisponible"), contexte UEMOA via F07/F17, Money typed F04 supporte FCFA-EUR peg. |
| II. Architecture Modulaire | PASS | Pas de couplage nouveau : F16 lit F01/F04/F06/F07/F11/F17 via leurs services existants ; aucun module métier ne dépendra rétroactivement de F16. |
| III. Conversation-Driven UX | PASS | Tool LangChain `compare_simulations` exposé via 2 nœuds (financing, application) — la PME peut comparer depuis le chat. |
| IV. Test-First (NON-NEGOTIABLE) | PASS | TDD obligatoire : tests unitaires (compute_*, factor_service, router), intégration (RLS + snapshot factors), E2E Playwright, garde-fou AST anti-constantes magiques. Couverture ≥ 80 %. |
| V. Sécurité & Protection des Données | PASS | Auth via Depends(get_current_user) sur tous endpoints simulate ; RLS PG via `set_rls_context` (F02) ; aucune fuite d'info sur offres/projets non-autorisés (FR-013). Pas de PII nouvelle stockée. |
| VI. Inclusivité | PASS | Mode dégradé explicite quand un facteur ou un délai manque (FR-007, FR-016) ; secteur informel pris en compte via F06 Project (objective_env, sector). |
| VII. Simplicité | PASS | Aucune nouvelle table, aucune migration, aucun cache distribué : 1 router REST + 1 tool LangChain + 1 page Vue. Snapshot factors par appel = simplicité MVP justifiée. |

Aucune violation. Pas de section Complexity Tracking nécessaire.

## Project Structure

### Documentation (this feature)

```text
specs/039-simulator-sourced/
├── plan.md              # Ce fichier
├── spec.md              # Specification (déjà écrite)
├── research.md          # Phase 0 — décisions techniques
├── data-model.md        # Phase 1 — entités volatiles + lectures
├── quickstart.md        # Phase 1 — checklist dev
├── contracts/           # Phase 1 — schémas API + tool
│   ├── api-simulate-multi.md
│   └── tool-compare-simulations.md
├── checklists/
│   └── requirements.md  # Spec quality checklist (déjà écrite)
└── tasks.md             # Phase 2 — généré par /speckit.tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/
│   │   ├── applications/
│   │   │   ├── simulation.py            # REFACTOR : 4 fonctions sourcées + agrégateur simulate_offer
│   │   │   ├── factor_service.py        # NEW : load_factors_snapshot(db) -> FactorSnapshot
│   │   │   ├── multi_simulate_service.py # NEW : compose simulate_offer pour N offres + ranking
│   │   │   ├── schemas.py               # EXTEND : MultiSimulateRequest/Response, SimulationResult, CostBreakdown, RoiBreakdown, CarbonImpact, TimelineStep
│   │   │   └── router.py                # EXTEND : POST /api/projects/{id}/simulate-multi
│   ├── graph/
│   │   ├── tools/
│   │   │   └── simulation_tools.py      # NEW : compare_simulations LangChain tool + CompareSimulationsArgs
│   │   ├── nodes.py                     # EXTEND : injection compare_simulations dans financing_node + application_node
│   │   └── tool_selector_config.py      # EXTEND : compare_simulations sur pages financing/applications
│   └── core/
│       └── (réutilise app/core/money.py F04, app/modules/currency F04, app/modules/sources F01)
└── tests/
    ├── unit/
    │   ├── test_factor_service.py
    │   ├── test_simulation_compute.py
    │   ├── test_multi_simulate_service.py
    │   └── test_no_magic_constants_in_simulation.py  # AST linter test
    ├── integration/
    │   ├── test_simulate_multi_router.py
    │   ├── test_simulate_multi_rls.py                # FR-013 isolation tenant
    │   └── test_compare_simulations_tool.py
    └── e2e/                                          # côté frontend Playwright

frontend/
├── app/
│   ├── pages/
│   │   └── financing/
│   │       └── simulator.vue            # REFACTOR complet
│   ├── components/
│   │   └── financing/
│   │       ├── ProjectSelector.vue              # NEW
│   │       ├── OffersMultiPicker.vue            # NEW (max 5, dedup)
│   │       ├── DetailedSimulationCard.vue       # NEW (rendu 1 offre)
│   │       └── (réutilise ComparisonTableBlock F11, MoneyDisplay F04, SourceLink F01, ReferentialBadge F04)
│   ├── composables/
│   │   └── useSimulator.ts              # NEW : simulateMulti + cache local éphémère
│   ├── stores/
│   │   └── simulator.ts                 # NEW : state Pinia volatile (selectedProject, selectedOfferIds, lastResult)
│   └── types/
│       └── simulator.ts                 # NEW : types TypeScript miroirs des schémas Pydantic
└── tests/
    └── e2e/
        └── F16-simulateur-finance-source.spec.ts    # NEW : scénario GCF/BOAD vs GCF/UNDP
```

**Structure Decision**: Web application existante (backend FastAPI + frontend Nuxt 4). F16 est un refactor + extension dans le module métier existant `applications` côté backend (les simulations restent dans ce module historique) et la sous-arborescence `financing/` côté frontend (cohérent avec la page actuelle `/financing/simulator`). Pas de nouveau module top-level — la fonctionnalité est une **vue** sur des données existantes.

## Phase 0 — Research outline

Cinq décisions techniques à instruire dans `research.md` :

1. **Mécanique de chargement des facteurs** : single SELECT par appel vs lazy par-facteur. Décision : single SELECT scoping `simulation_factors` par catégorie nécessaire + jointure `sources` (cohérence FR-017, perf SC-005).
2. **Mapping instrument → formule ROI** : table de dispatch en code Python (subvention/pret_concessionnel/equity/blending). Décision : `dict[InstrumentLiteral, Callable]` typé Pydantic v2, formules sourcées via facteurs nommés.
3. **Source des ratios sectoriels carbone** : F17 expose `emission_factors` avec colonne `sector`. Décision : lecture par `(project.sector, year)` avec fallback global, marquage `is_approximate` repris du pattern F17.
4. **Transport SSE du tool `compare_simulations`** : marker `<!--SSE:{"__sse_visualization_block__":true,...}-->` (pattern F11 ComparisonTable). Décision : réutilise sans extension protocole.
5. **Anti-régression constantes magiques** : test AST qui parse `simulation.py`, scanne les `Constant(value=Number)` ne servant pas à des libellés (whitelist : 0, 1, 12 pour mois/année). Décision : implémentation via `ast.NodeVisitor` + whitelist explicite.

## Phase 1 — Design outline

### Entities (data-model.md)

Aucune entité persistée par F16. Le data-model décrira :

- **FactorSnapshot** (volatile, in-memory dataclass) : `dict[str, FactorEntry]` + `dict[UUID, SourceRef]` ; chargé par `load_factors_snapshot(db)` ; immuable (frozen dataclass).
- **SimulationResult** (Pydantic schema response) : `principal: Money`, `cost_breakdown: CostBreakdown`, `roi: RoiBreakdown`, `carbon_impact: CarbonImpact`, `timeline: list[TimelineStep]`, `sources_used: list[SourceRef]`.
- **CostBreakdown** : `principal: Money`, `doc_fee: Money`, `total_fees_over_duration: Money`, `guarantee_required: Money`, `fx_margin: Money`, `total_cost: Money`, chacun avec `source_id: UUID | None` et `degraded_reason: str | None`.
- **RoiBreakdown** : `instrument: Literal[...]`, `formula_id: str`, `gain_estimated: Money | None`, `payback_months: int | None`, `notes_fr: str`, `source_id: UUID | None`.
- **CarbonImpact** : `tco2e_per_year: Decimal | None`, `sector_factor: Decimal | None`, `factor_source_id: UUID | None`, `degraded_reason: str | None`.
- **TimelineStep** : `label_fr: str`, `weeks_min: int | None`, `weeks_max: int | None`, `source_id: UUID | None`, `degraded_reason: str | None`.
- **MultiSimulateRequest** : `offer_ids: list[UUID]` (1..5, validator dedup).
- **MultiSimulateResponse** : `per_offer: dict[UUID, SimulationResult | DegradedColumn]`, `comparison_metadata: ComparisonMetadata` (cheapest_offer_id, fastest_offer_id, generated_at).

Lectures BDD (read-only) : `simulation_factors`, `sources`, `projects`, `offers` (via F07 service), `funds`, `intermediaries`, `emission_factors` (F17), `exchange_rates` (F04).

### Contracts (contracts/)

1. **api-simulate-multi.md** — `POST /api/projects/{project_id}/simulate-multi`
   - Request : `MultiSimulateRequest`
   - Response 200 : `MultiSimulateResponse`
   - Errors : 401 (auth), 403 (RLS — projet ou offre non accessible), 404 (projet), 422 (validator dedup ou offer_ids hors borne), 503 (catalog corruption — facteurs critiques absents).
   - Auth : `Depends(get_current_user)` ; RLS automatique via `set_rls_context`.
   - Idempotence : oui (lecture seule).

2. **tool-compare-simulations.md** — Tool LangChain
   - `args_schema = CompareSimulationsArgs(project_id: UUID, offer_ids: list[UUID])` (Pydantic v2 strict, extra='forbid').
   - Visibilité : `MODULE_TOOL_MAPPING['financing']`, `MODULE_TOOL_MAPPING['application']`, `PAGE_TOOL_MAPPING['financing']`, `PAGE_TOOL_MAPPING['simulator']`.
   - Comportement : appelle `multi_simulate_service.simulate_multi()` ; émet marker SSE F11 `<!--SSE:{"__sse_visualization_block__":true,"block_type":"comparison_table",...}-->` ; retourne JSON résumé court au LLM.
   - Erreurs : `{ok: false, error: "..."}` si projet/offer hors-tenant ou >5.

### Quickstart (quickstart.md)

Checklist développeur : (1) lire spec + clarifications ; (2) écrire les tests unit AVANT implémentation (TDD) ; (3) implémenter `factor_service.load_factors_snapshot` ; (4) refactor `simulation.py` en 4 pure functions sourcées ; (5) implémenter `multi_simulate_service.simulate_multi` ; (6) router `/simulate-multi` ; (7) tool LangChain ; (8) refactor frontend `simulator.vue` ; (9) E2E ; (10) garde-fou AST `test_no_magic_constants` ; (11) coverage ≥ 80 % ; (12) commit + PR.

### Agent context update

À la fin de Phase 1, exécuter `.specify/scripts/bash/update-agent-context.sh claude` pour propager dans CLAUDE.md la mention F16 (technologies déjà couvertes — pas de nouveauté techno).

## Complexity Tracking

Aucune violation Constitution. Section vide intentionnellement.
