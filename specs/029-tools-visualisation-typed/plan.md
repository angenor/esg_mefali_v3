# Implementation Plan: F11 — Tools de Visualisation Typés

**Branch**: `feat/F11-tools-visualisation-typed` | **Date**: 2026-05-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/029-tools-visualisation-typed/spec.md`

## Summary

Ajout d'un catalogue de **4 tools LangChain typés Pydantic strict** (`show_kpi_card`, `show_match_card`, `show_map`, `show_comparison_table`) consommés par l'assistant IA et rendus inline dans le chat via **4 nouveaux composants Vue** (`KPICardBlock`, `MatchCardBlock`, `MapBlock`, `ComparisonTableBlock`). Les blocs typés enrichissent les réponses LLM avec : KPI sourcés (F01) avec delta, cartes matching projet↔offre (F06×F07) cliquables, tables comparatives multi-sujets, et cartes Leaflet UEMOA. Aucune migration BDD : les tools sont **lecture/présentation uniquement**, persistance limitée au journal `tool_call_logs` existant (introduit en 012).

Approche technique : (1) backend — `app/graph/tools/visualization_tools.py` regroupant les 4 tools avec schémas Pydantic stricts (`extra="forbid"`, bornes, enums fermés, intégration Money F04 et `source_id` F01), filtrage par page via `tool_selector_config.py`, decision tree dans `app/prompts/system.py`, encouragements ciblés dans `app/prompts/financing.py` et `application.py` ; (2) frontend — Leaflet 1.9 ajouté en deps, composants Vue dans `frontend/app/components/richblocks/`, `MapBlock` chargé en lazy-load via `defineAsyncComponent`, composable `useMapTiles.ts` pour tile layer light/dark, asset GeoJSON UEMOA bundlé localement, types TypeScript et extension de `MessageParser.vue`/`useMessageParser.ts` pour rendre les tool calls structurés (transport SSE déjà existant via 012). Tests : Pytest unit (validation Pydantic, golden set tool selection mocké), Vitest unit (rendu composant, dark mode, accessibilité ARIA), Playwright E2E (4 scénarios chat).

## Technical Context

**Language/Version**: Python 3.12 (backend) ; TypeScript 5.x strict (frontend)
**Primary Dependencies**:
  - Backend (existant) : FastAPI, LangGraph ≥ 0.2, LangChain ≥ 0.3, langchain-openai, SQLAlchemy async, Pydantic v2.
  - Backend (à utiliser) : `app.core.money.Money` (F04), `app.models.source.Source` (F01), `app.models.project.Project` (F06), `app.models.offer.Offer` (F07).
  - Frontend (existant) : Nuxt 4, Vue 3 Composition API, Pinia, TailwindCSS 4, Chart.js, Mermaid, marked, DOMPurify.
  - Frontend (nouveau) : `leaflet@^1.9.4`, `@types/leaflet@^1.9.12` (devDependency).
**Storage**: PostgreSQL 16 + pgvector (lecture seule pour Source/Project/Offer). Aucune nouvelle table, aucune migration Alembic.
**Testing**: Backend pytest + pytest-asyncio + pytest-cov (cible 80 %) ; Frontend Vitest + @vue/test-utils + happy-dom + @vitest/coverage-v8 (cible 80 %) ; E2E Playwright `frontend/tests/e2e/F11-tools-visualisation-typed.spec.ts`.
**Target Platform**: Web (Nuxt SSR + SPA), backend FastAPI Linux. Mobile portrait responsive (≥ 320 px).
**Project Type**: Web application — monorepo `backend/` + `frontend/` (existant).
**Performance Goals**:
  - Bundle JS chat : delta ≤ +20 KB après ajout des composants typés (Leaflet exclu via lazy-load).
  - Validation Pydantic d'un payload : < 5 ms (p95).
  - Rendu d'un MatchCard : < 50 ms après réception SSE (sans network).
  - LLM tool selection accuracy : ≥ 90 % sur golden set (mocked).
**Constraints**:
  - Lazy-load Leaflet impératif (le composant `MapBlock` est wrappé dans `defineAsyncComponent`).
  - Tile layer libre uniquement (OpenStreetMap light, CartoDB Dark Matter dark — pas de clé API).
  - Multi-tenant strict (F02) : les `project_id` / `offer_id` référencés appartiennent à l'`account_id` courant ; à défaut, refus côté backend (service de récupération avant émission du tool).
  - Sources cliquables (F01) intégrées sur KPICard / MatchCard / ComparisonTable via composant modale source existant.
  - Money typé (F04) : tout champ monétaire utilise `Money` Pydantic ; jamais de `*_xof` simple.
  - Dark mode : toutes les variantes Tailwind `dark:` présentes (CLAUDE.md §"Dark Mode OBLIGATOIRE").
  - Aucun secret hardcodé.
  - Compatibilité ascendante avec les blocs richblocks markdown existants (chart/table/timeline/progress/gauge/mermaid).
**Scale/Scope**:
  - 4 tools backend, 4 composants Vue, 1 composable, 1 asset GeoJSON, ~10 fichiers de tests.
  - Estimation 1.5 sprint (orchestrateur F11).

## Constitution Check

*GATE: Doit passer avant Phase 0 research et après Phase 1 design.*

| Principe | Évaluation |
|----------|------------|
| **I. Francophone-First & Contextualisation Africaine** | ✅ Tous les contenus utilisateur en français avec accents. Map UEMOA, monnaie XOF par défaut, support `Money` multi-devises (F04), support secteur informel (les KPI/MatchCard/Comparaison sont neutres). |
| **II. Architecture Modulaire** | ✅ Module isolé `visualization_tools.py` ; couplage faible (tools = structures de données passées au frontend, pas de dépendance directe entre modules métier). Chaque composant Vue est autonome. |
| **III. Conversation-Driven UX** | ✅ Renforce l'approche conversationnelle : l'assistant produit des réponses graphiques structurées plutôt que du texte brut, sans formulaire. |
| **IV. Test-First (NON-NEGOTIABLE)** | ✅ Workflow TDD : tests Pydantic d'abord, puis implémentation tool ; tests Vitest composant d'abord, puis composant Vue ; tests Playwright E2E définis dans tasks.md avant implementation. Cible 80 %. |
| **V. Sécurité & Protection des Données** | ✅ Validation Pydantic stricte (`extra="forbid"`), `popup_content` Map sanitisé via DOMPurify côté frontend, multi-tenant respecté (`project_id`/`offer_id` filtrés par `account_id`), aucun secret. Tile layer public OSM/CartoDB sans clé. |
| **VI. Inclusivité & Accessibilité** | ✅ ARIA labels obligatoires (FR-005, FR-010, FR-022 implicite), navigation clavier, contraste WCAG AA en light/dark, lazy-load pour connexions lentes, fallback texte si payload invalide, mobile responsive (ComparisonTable replie en cartes ≤ 768 px). |
| **VII. Simplicité & YAGNI** | ✅ Pas de microservices, pas de Redis/Celery ajouté, pas de migration BDD, pas de table de centroïdes (constante Python), pas de clé Mapbox/MapTiler (OSM gratuit), réutilisation maximale des patterns existants (richblocks, modale source F01, composable `ui` dark mode). |

**Limites de taille respectées** : tous les nouveaux fichiers visent < 400 lignes. Le fichier `visualization_tools.py` est segmentable (un sous-module par tool) si dépassement.

**Gate verdict**: ✅ PASS — aucune dérogation requise.

## Project Structure

### Documentation (this feature)

```text
specs/029-tools-visualisation-typed/
├── plan.md              # This file
├── spec.md              # Feature specification (incl. Clarifications)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (modèles Pydantic + types TS)
├── quickstart.md        # Phase 1 output (procédure de validation manuelle)
├── contracts/
│   └── visualization-tools.md   # Contrats des 4 tools (signatures + exemples)
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── graph/
│   │   ├── tools/
│   │   │   ├── visualization_tools.py    # NEW — 4 tools typés (KPI/Match/Map/Comparison)
│   │   │   └── README.md                 # MODIF — ajouter section "Tools de visualisation"
│   │   ├── tool_selector_config.py       # MODIF — visibility par page (4 nouveaux tools)
│   │   └── nodes.py                      # MODIF — bind nouveaux tools dans noeuds chat/financing/application
│   ├── core/
│   │   └── visualization_centroids.py    # NEW — constante UEMOA_COUNTRY_CENTROIDS (8 pays)
│   ├── prompts/
│   │   ├── system.py                     # MODIF — ajout decision tree visualisation
│   │   ├── financing.py                  # MODIF — encourager show_match_card / show_comparison_table
│   │   └── application.py                # MODIF — encourager show_comparison_table pour multi-offres
│   └── schemas/
│       └── visualization.py              # NEW — schémas Pydantic exportables (réutilisables côté API/tests)
└── tests/
    ├── unit/
    │   ├── test_visualization_tools_kpi.py        # NEW
    │   ├── test_visualization_tools_match.py      # NEW
    │   ├── test_visualization_tools_map.py        # NEW
    │   ├── test_visualization_tools_comparison.py # NEW
    │   ├── test_visualization_centroids.py        # NEW
    │   └── test_tool_selector_visualization.py    # NEW (filtrage par page)
    └── integration/
        └── test_visualization_prompts.py          # NEW (golden set mock LLM)

frontend/
├── package.json                         # MODIF — +leaflet, +@types/leaflet (dev)
├── app/
│   ├── components/
│   │   ├── richblocks/
│   │   │   ├── KPICardBlock.vue          # NEW
│   │   │   ├── MatchCardBlock.vue        # NEW
│   │   │   ├── MapBlock.vue              # NEW (lazy-loaded usage)
│   │   │   └── ComparisonTableBlock.vue  # NEW
│   │   ├── chat/
│   │   │   └── MessageParser.vue         # MODIF — rendre les nouveaux tool blocks
│   │   └── ui/
│   │       └── SourceCitationIcon.vue    # REUSE — déjà introduit en F01 (à confirmer)
│   ├── composables/
│   │   ├── useMapTiles.ts                # NEW — sélection tile layer light/dark
│   │   └── useMessageParser.ts           # MODIF — détecter et router les nouveaux tool blocks
│   ├── types/
│   │   └── richblocks.ts                 # MODIF — types KPICard / MatchCard / Map / Comparison
│   └── assets/
│       └── geo/
│           └── uemoa-borders.geo.json    # NEW — overlay GeoJSON 8 pays UEMOA
└── tests/
    ├── unit/
    │   └── richblocks/
    │       ├── KPICardBlock.spec.ts            # NEW
    │       ├── MatchCardBlock.spec.ts          # NEW
    │       ├── MapBlock.spec.ts                # NEW (mock Leaflet)
    │       ├── ComparisonTableBlock.spec.ts    # NEW
    │       └── useMapTiles.spec.ts             # NEW
    └── e2e/
        └── F11-tools-visualisation-typed.spec.ts  # NEW (4 scénarios)
```

**Structure Decision**: Web application monorepo (Option 2 du template). Backend Python FastAPI sous `backend/`, frontend Nuxt 4 sous `frontend/`. Aucun nouveau projet/répertoire racine.

## Phase 0 — Outline & Research

Voir [research.md](./research.md). Les sujets traités :

1. **Choix Leaflet vs alternatives** (MapLibre, OpenLayers, Vue-Leaflet) — décision : Leaflet 1.9 vanilla, intégré via composable Vue, pas de wrapper Vue dédié.
2. **Tile layer dark mode gratuit** — décision : CartoDB Dark Matter (OSM-based, sans clé), confirmé compatible attribution OSM.
3. **Stratégie de lazy-load Leaflet dans Nuxt 4** — décision : `defineAsyncComponent` côté composant + import dynamique du package dans `onMounted` (Leaflet manipule `window`/`document`).
4. **Source GeoJSON UEMOA** — décision : extraction depuis Natural Earth (Public Domain) → simplification via mapshaper (~30 KB) → asset bundlé `frontend/app/assets/geo/uemoa-borders.geo.json`.
5. **Mécanisme de transport des tool calls structurés vers le frontend** — décision : SSE déjà existant (012), événements `tool_call_end` avec `tool_name` ∈ {show_kpi_card, ...} et `output` JSON de l'args ; le frontend rend le composant correspondant.
6. **Pattern de rendu d'un tool typed comme bulle inline dans le chat** — décision : `MessageParser.vue` détecte les blocs typés via la liste des `tool_calls` du message (ajoutée à `MessageBlock`), instancie le composant correspondant avec les args validés.
7. **Validation Pydantic asymétrique entre LLM args et payload SSE** — décision : la validation Pydantic est appliquée au moment de l'invocation par LangChain (auto via `args_schema`) ; la sortie SSE est sérialisée à partir d'un `model_dump(mode="json")` pour cohérence Money/UUID/Decimal.
8. **Stratégie golden set de tests** — décision : mock LLM via `unittest.mock.AsyncMock` qui retourne des `AIMessage` avec `tool_calls` synthétiques ; le test vérifie que le routeur a bien sélectionné le tool attendu et que le payload est conforme.
9. **Réutilisation du composant modale source F01** — décision : importer le composant existant (à confirmer dans le code F01) ; le `source_id` est passé en prop au composant qui ouvre la modale au clic.
10. **Strategy de fallback texte si Pydantic invalid** — décision : LangGraph existant (validators/source_required.py) est étendu pour traiter aussi `payload_invalid` ; retry max 1 puis fallback texte LLM.

**Output**: `research.md` consolidant les 10 décisions ci-dessus.

## Phase 1 — Design & Contracts

Voir :

- [data-model.md](./data-model.md) — entités Pydantic et types TypeScript détaillés
- [contracts/visualization-tools.md](./contracts/visualization-tools.md) — signatures des 4 tools
- [quickstart.md](./quickstart.md) — procédure de validation manuelle

### Entités principales (résumé)

| Entité | Type | Source de vérité | Localisation |
|--------|------|------------------|--------------|
| `KPICardArgs` | Pydantic v2 BaseModel | Backend | `backend/app/schemas/visualization.py` |
| `MatchCardArgs` | Pydantic v2 BaseModel | Backend | `backend/app/schemas/visualization.py` |
| `MapArgs` + `MapMarker` | Pydantic v2 BaseModel | Backend | `backend/app/schemas/visualization.py` |
| `ComparisonTableArgs` + `ComparisonSubject` + `ComparisonRow` + `ComparisonValue` | Pydantic v2 BaseModel | Backend | `backend/app/schemas/visualization.py` |
| `KPICardBlockProps` / etc. | TypeScript interface | Frontend (généré ou maintenu en miroir) | `frontend/app/types/richblocks.ts` |
| `UEMOA_COUNTRY_CENTROIDS` | Dict[str, tuple[float, float]] | Backend | `backend/app/core/visualization_centroids.py` |

### Tools LangChain (résumé)

| Tool | Args Schema | Visibility (page) | Visibility (node fallback) |
|------|-------------|-------------------|----------------------------|
| `show_kpi_card` | `KPICardArgs` | dashboard, esg, carbon, credit | chat, esg_scoring, carbon, credit, action_plan, dashboard |
| `show_match_card` | `MatchCardArgs` | financing, candidatures | chat, financing, application |
| `show_map` | `MapArgs` | profile, profile_projects, financing | chat, profiling, financing |
| `show_comparison_table` | `ComparisonTableArgs` | financing, candidatures | chat, financing, application |

### Endpoints / interfaces externes

Aucun nouvel endpoint REST. Le transport reste l'événement SSE `tool_call_end` (existant, 012). Aucune mutation BDD, aucun service applicatif transversal.

### Mise à jour du contexte agent

Sera exécutée via `.specify/scripts/bash/update-agent-context.sh claude` à la fin de Phase 1, ajoutant `Leaflet 1.9` au stack frontend et `visualization_tools` au stack backend dans `CLAUDE.md`.

## Phase 2 (anticipé — sera produit par /speckit.tasks)

`tasks.md` listera : (a) tâches backend TDD (1 par tool : test args invalides → test args valides → implémentation tool), (b) tâche `tool_selector_config.py` (visibility), (c) tâche prompts (system + financing + application), (d) tâche centroïdes UEMOA, (e) tâches frontend TDD (1 par composant), (f) tâche composable `useMapTiles`, (g) tâche extension `MessageParser`/`useMessageParser`, (h) tâches Playwright E2E (4 scénarios), (i) audit dark mode + accessibilité, (j) mise à jour CLAUDE.md via script.

## Complexity Tracking

> Aucun écart constitutionnel. Section laissée vide intentionnellement.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _N/A_ | _N/A_ | _N/A_ |
