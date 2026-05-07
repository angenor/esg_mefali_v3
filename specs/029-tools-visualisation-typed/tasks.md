# Tasks: F11 — Tools de Visualisation Typés (KPICard, MatchCard, Map, ComparisonTable)

**Input**: Design documents from `/specs/029-tools-visualisation-typed/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅
**Branch**: `feat/F11-tools-visualisation-typed`

**Tests**: Activés (TDD strict — Constitution Principle IV NON-NEGOTIABLE).

**Organization**: Tasks groupées par user story pour permettre l'implémentation incrémentale et le test indépendant.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : Parallélisable (fichiers différents, sans dépendance bloquante).
- **[Story]** : User story rattachée (US1, US2, US3, US4, US5).
- Chemins absolus relatifs au repo root `/Users/mac/Documents/projets/2025/esg_mefali_v3/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Préparer dépendances et structure de fichiers commune.

- [ ] T001 Vérifier que F01 (Source modal), F04 (Money), F06 (Project), F07 (Offer) sont mergés sur main et que les imports `app.core.money.Money`, `app.models.source.Source`, `app.models.project.Project`, `app.models.offer.Offer` fonctionnent (commande : `cd backend && source venv/bin/activate && python -c "from app.core.money import Money; from app.models.source import Source; from app.models.project import Project; from app.models.offer import Offer; print('OK')"`)
- [ ] T002 [P] Ajouter `leaflet@^1.9.4` aux `dependencies` et `@types/leaflet@^1.9.12` aux `devDependencies` de `frontend/package.json` puis lancer `cd frontend && npm install`
- [ ] T003 [P] Créer le répertoire `frontend/app/assets/geo/` (mkdir -p) et générer l'asset `frontend/app/assets/geo/uemoa-borders.geo.json` selon la procédure documentée dans `quickstart.md` (Natural Earth → ogr2ogr → mapshaper). Cible taille ≤ 35 KB. Si l'outil mapshaper n'est pas disponible, prévoir un asset minimal manuel (8 polygones simplifiés).
- [ ] T004 [P] Créer les répertoires de tests vides : `backend/tests/unit/` (existe), `backend/tests/integration/` (existe), `frontend/tests/unit/richblocks/` (mkdir -p), `frontend/tests/e2e/` (existe)

**Checkpoint**: Dépendances installées, structure prête.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schémas Pydantic partagés et infrastructure de validation. Bloquant pour US1, US2, US3, US4.

**⚠️ CRITICAL**: Aucune user story ne peut démarrer avant cette phase.

### Tests Foundational (TDD)

- [ ] T005 [P] Test Pydantic `KPICardArgs` (champs valides/invalides/extra/borne) dans `backend/tests/unit/test_visualization_schemas_kpi.py` — DOIT FAIL initialement
- [ ] T006 [P] Test Pydantic `MatchCardArgs` (champs valides/invalides/extra/borne/score 0-100) dans `backend/tests/unit/test_visualization_schemas_match.py` — DOIT FAIL initialement
- [ ] T007 [P] Test Pydantic `MapArgs` + `MapMarker` (lat/lon bornes, markers min 1 max 50, popup_content max 500) dans `backend/tests/unit/test_visualization_schemas_map.py` — DOIT FAIL initialement
- [ ] T008 [P] Test Pydantic `ComparisonTableArgs` + `ComparisonRow` + `ComparisonValue` + `ComparisonSubject` (subjects min 2 max 5, rows min 1 max 20, validateur cross-field values↔subjects) dans `backend/tests/unit/test_visualization_schemas_comparison.py` — DOIT FAIL initialement
- [ ] T009 [P] Test sérialisation Money + UUID dans payloads (model_dump JSON) dans `backend/tests/unit/test_visualization_serialization.py` — DOIT FAIL initialement

### Implementation Foundational

- [ ] T010 [P] Créer `backend/app/schemas/__init__.py` (si inexistant) puis `backend/app/schemas/visualization.py` contenant les enums (`DeltaDirection`, `KPIColor`, `MarkerType`, `ComparisonValueType`) et les modèles Pydantic v2 strict (`KPICardArgs`, `MatchCardArgs`, `MapMarker`, `MapArgs`, `ComparisonValue`, `ComparisonRow`, `ComparisonSubject`, `ComparisonTableArgs`) selon `data-model.md` §2-6 (`extra="forbid"`, bornes, validateur cross-field). Faire passer T005-T009.
- [ ] T011 [P] Créer `backend/app/core/visualization_centroids.py` avec la constante `UEMOA_COUNTRY_CENTROIDS` (8 entrées dict[str, tuple[float, float]]), `UEMOA_REGION_CENTER`, `UEMOA_DEFAULT_ZOOM` selon `data-model.md` §5
- [ ] T012 Test backend `backend/tests/unit/test_visualization_centroids.py` (présence des 8 codes ISO3, valeurs lat/lon dans les bornes UEMOA) — TDD : écrire test, vérifier vert
- [ ] T013 [P] Créer le miroir TypeScript `frontend/app/types/richblocks.ts` (étendre, pas réécrire) avec `DeltaDirection`, `KPIColor`, `MarkerType`, `ComparisonValueType`, et les interfaces `KPICardBlockProps`, `MatchCardBlockProps`, `MapMarkerProps`, `MapBlockProps`, `ComparisonValueProps`, `ComparisonRowProps`, `ComparisonSubjectProps`, `ComparisonTableBlockProps` selon `data-model.md` §7 (camelCase)
- [ ] T014 [P] Créer le composable `frontend/app/composables/useMapTiles.ts` exportant `useMapTiles()` qui retourne `{ tileUrl: ComputedRef<string>, attribution: ComputedRef<string> }` en lisant le store `ui` (light → OSM standard, dark → CartoDB Dark Matter)
- [ ] T015 Tester `useMapTiles` dans `frontend/tests/unit/richblocks/useMapTiles.spec.ts` (toggle light/dark via mock store ui, vérifier tileUrl + attribution) — TDD
- [ ] T016 Étendre `backend/app/graph/validators/source_required.py` (ou créer `backend/app/graph/validators/payload_invalid.py`) pour intercepter les `ValidationError` Pydantic des nouveaux tools, retry max 1 avec message structuré au LLM, fallback texte sinon. Voir contracts/visualization-tools.md §"Politique d'erreurs LLM".
- [ ] T017 Test `backend/tests/unit/test_validator_payload_invalid.py` : payload invalide simulé → message d'erreur LLM structuré ; 2 retries → fallback texte — TDD

**Checkpoint**: Schémas Pydantic + types TS + composable tiles + validator d'erreurs prêts. Les 4 user stories peuvent démarrer en parallèle.

---

## Phase 3: User Story 1 — Carte KPI sourcée pour chiffre clé (Priority: P1) 🎯 MVP

**Goal**: L'assistant produit un `show_kpi_card` rendu inline dans le chat avec valeur, delta colorisé, picto Source cliquable, drill-down.

**Independent Test**: Demander à l'assistant "résume mon empreinte carbone 2026" → vérifier qu'une KPICard s'affiche avec tous les éléments requis et que le clic sur le picto Source ouvre la modale F01.

### Tests for User Story 1 (TDD strict)

> Écrire ces tests AVANT l'implémentation, vérifier qu'ils FAIL.

- [ ] T018 [P] [US1] Test backend `backend/tests/unit/test_visualization_tools_kpi.py` — invocation `show_kpi_card` valide retourne JSON string contenant les champs sérialisés ; payload invalide → ValidationError ; multi-tenant respecté (pas de filtrage car KPICard ne dépend pas de project_id/offer_id)
- [ ] T019 [P] [US1] Test frontend `frontend/tests/unit/richblocks/KPICardBlock.spec.ts` — props valides → rendu titre/value/delta avec couleur correcte selon `delta_is_good` ; click sur drilldown → emit navigate ; click sur picto Source → emit openSource ; ARIA label conforme
- [ ] T020 [P] [US1] Test frontend dark mode `frontend/tests/unit/richblocks/KPICardBlock.spec.ts` (suite) — toggle classe `dark` sur html → vérifier classes Tailwind dark: appliquées

### Implementation for User Story 1

- [ ] T021 [US1] Implémenter le tool `show_kpi_card` dans `backend/app/graph/tools/visualization_tools.py` avec `@tool(args_schema=KPICardArgs)`, docstring 5 sections (use when / don't use when / exemple / anti) selon `contracts/visualization-tools.md` §"Tool 1", retour `args.model_dump_json()`. Faire passer T018.
- [ ] T022 [P] [US1] Créer le composant `frontend/app/components/richblocks/KPICardBlock.vue` selon `data-model.md` §3 et `spec.md` US1 : card avec gradient subtil selon color, icône heroicon à gauche, titre + value grande, delta colorisé selon `deltaIsGood`, picto Source en bas-droite (composant existant F01), navigation au clic vers `drilldownUrl`, dark mode complet, aria-label. Faire passer T019, T020.
- [ ] T023 [US1] Mettre à jour `frontend/app/components/chat/MessageParser.vue` et `frontend/app/composables/useMessageParser.ts` pour détecter les tool calls `show_kpi_card` dans `message.tool_calls` et instancier `KPICardBlock` avec props camelCase. Préserver l'ordre des blocs (texte/markdown/typed).
- [ ] T024 [US1] Mettre à jour `backend/app/graph/tool_selector_config.py` pour ajouter `show_kpi_card` aux pages `dashboard`, `esg`, `carbon`, `credit` et aux modules fallback `chat`, `esg_scoring`, `carbon`, `credit`, `action_plan`, `dashboard`. Vérifier que `MAX_TOOLS_PER_TURN=14` n'est pas dépassé sur ces pages.
- [ ] T025 [US1] Mettre à jour `backend/app/graph/nodes.py` pour binder le tool `show_kpi_card` dans les nœuds `chat_node`, `esg_scoring_node`, `carbon_node`, `credit_node`, `action_plan_node` (selon le pattern existant pour les autres tools).
- [ ] T026 [US1] Étendre `backend/app/prompts/system.py` avec la section "ARBRE DE DÉCISION VISUALISATION" mentionnant `show_kpi_card` comme choix par défaut pour les chiffres clés. Voir `spec.md` §FR-026.
- [ ] T027 [US1] Test d'intégration `backend/tests/integration/test_visualization_prompts_kpi.py` — golden set 5 questions KPI avec mock LLM → vérifier (a) que `show_kpi_card` est sélectionné dans ≥ 4/5 cas (cible SC-001 ≥ 90 %) ; (b) qu'une valeur quantitative sans `source_id` provoque l'invocation parallèle de `flag_unsourced` (FR-032 — vérification interaction prompt) ; (c) que la modale source F01 est bien la cible du clic (test contractuel sur l'event émis par le composant).

**Checkpoint US1**: KPICard fonctionnelle de bout en bout, testable en chat sur dashboard/esg/carbon/credit.

---

## Phase 4: User Story 2 — Cartes de matching projet↔offre cliquables (Priority: P1)

**Goal**: L'assistant produit 1 ou plusieurs `show_match_card` cliquables qui ouvrent `/financing/offers/{offer_id}?project_id={project_id}`.

**Independent Test**: Avec un projet test et 3 offres seedées, demander "quelles offres me correspondent ?" → 3 MatchCards affichées + clic Explorer ouvre la fiche offre.

### Tests for User Story 2 (TDD strict)

- [ ] T028 [P] [US2] Test backend `backend/tests/unit/test_visualization_tools_match.py` — invocation `show_match_card` valide ; project_id/offer_id appartenant à un autre account → erreur métier ; payload invalide rejeté
- [ ] T029 [P] [US2] Test frontend `frontend/tests/unit/richblocks/MatchCardBlock.spec.ts` — props valides → rendu logos (avec placeholder initiales si URL absente), score circulaire, range/timeline/instruments/missing_count ; click CTA → emit navigate vers drilldownUrl ; tooltip décomposition au survol
- [ ] T030 [P] [US2] Test frontend dark mode + ARIA `frontend/tests/unit/richblocks/MatchCardBlock.spec.ts` (suite)

### Implementation for User Story 2

- [ ] T031 [US2] Implémenter le tool `show_match_card` dans `backend/app/graph/tools/visualization_tools.py` avec validation multi-tenant (charger `Project` et `Offer` par leurs IDs, vérifier `account_id`, retourner erreur si non accessible). Faire passer T028.
- [ ] T032 [P] [US2] Créer le composant `frontend/app/components/richblocks/MatchCardBlock.vue` selon `data-model.md` §4 et `spec.md` US2 : header 2 logos + score circulaire (réutiliser GaugeBlock ou inline SVG), body avec range/timeline/badges instruments, footer compteur critères + bouton CTA, hover effect, dark mode, aria-label. Faire passer T029, T030.
- [ ] T033 [US2] Étendre `frontend/app/components/chat/MessageParser.vue` et `frontend/app/composables/useMessageParser.ts` pour rendre `show_match_card` (cumul avec T023).
- [ ] T034 [US2] Mettre à jour `backend/app/graph/tool_selector_config.py` pour ajouter `show_match_card` aux pages `financing`, `candidatures` et aux modules fallback `chat`, `financing`, `application`. Vérifier `MAX_TOOLS_PER_TURN`.
- [ ] T035 [US2] Mettre à jour `backend/app/graph/nodes.py` pour binder `show_match_card` dans `chat_node`, `financing_node`, `application_node`.
- [ ] T036 [US2] Étendre `backend/app/prompts/financing.py` et `backend/app/prompts/application.py` pour encourager `show_match_card` lors de propositions de matching (cf. `spec.md` §FR-027). Note de coordination : T036 et T047 modifient les MÊMES fichiers ; les deux tâches DOIVENT s'exécuter en série (pas [P]). T036 ajoute la section "Match", T047 ajoute la section "Comparaison" sans réécrire.
- [ ] T037 [US2] Test d'intégration `backend/tests/integration/test_visualization_prompts_match.py` — golden set 5 questions financement avec mock LLM → `show_match_card` sélectionné dans ≥ 4/5 (SC-002 ≥ 90 %)

**Checkpoint US2**: MatchCard fonctionnelle, drill-down testable.

---

## Phase 5: User Story 3 — Tableau comparatif d'offres concurrentes (Priority: P1)

**Goal**: L'assistant produit `show_comparison_table` côte-à-côte avec highlight winner par row, formatage par type (money/duration/percentage), responsive mobile.

**Independent Test**: Demander "compare GCF via BOAD vs UNDP vs AFD" → table 3 colonnes, ≥ 4 lignes, highlight winner par row, fold en cartes ≤ 768 px.

### Tests for User Story 3 (TDD strict)

- [ ] T038 [P] [US3] Test backend `backend/tests/unit/test_visualization_tools_comparison.py` — invocation valide ; > 5 subjects rejeté ; values_subject_ids ≠ subjects.id rejeté (validateur cross-field)
- [ ] T039 [P] [US3] Test frontend `frontend/tests/unit/richblocks/ComparisonTableBlock.spec.ts` — props valides → rendu headers cliquables, cellules formatées par type (money via useCurrency F04, percentage "80 %", duration "12 mois", boolean coche/croix), highlight winner par row selon `higherIsBetter`
- [ ] T040 [P] [US3] Test responsive `frontend/tests/unit/richblocks/ComparisonTableBlock.spec.ts` (suite) — viewport ≤ 768 px → fold en cartes verticales
- [ ] T041 [P] [US3] Test dark mode + ARIA + sources cliquables `frontend/tests/unit/richblocks/ComparisonTableBlock.spec.ts` (suite)

### Implementation for User Story 3

- [ ] T042 [US3] Implémenter le tool `show_comparison_table` dans `backend/app/graph/tools/visualization_tools.py`. Faire passer T038.
- [ ] T043 [P] [US3] Créer le composant `frontend/app/components/richblocks/ComparisonTableBlock.vue` selon `data-model.md` §6 et `spec.md` US3 : headers cliquables, cellules formatées par type (importer composable `useCurrency` F04 pour money), highlight cellule gagnante (vert subtil) selon `higherIsBetter`, picto Source par cellule (réutiliser composant F01), responsive (collapse cards ≤ 768 px), dark mode, aria-label + `caption` + `scope="col"`. Faire passer T039, T040, T041.
- [ ] T044 [US3] Étendre `MessageParser.vue` et `useMessageParser.ts` pour rendre `show_comparison_table`.
- [ ] T045 [US3] Mettre à jour `backend/app/graph/tool_selector_config.py` (pages `financing`, `candidatures` ; modules `chat`, `financing`, `application`).
- [ ] T046 [US3] Mettre à jour `backend/app/graph/nodes.py` pour binder `show_comparison_table` dans `chat_node`, `financing_node`, `application_node`.
- [ ] T047 [US3] Étendre `backend/app/prompts/financing.py` et `application.py` pour encourager `show_comparison_table` lors de comparaison ≥ 2 offres (FR-027).
- [ ] T048 [US3] Test d'intégration `backend/tests/integration/test_visualization_prompts_comparison.py` — golden set 3 questions comparaison → `show_comparison_table` ≥ 90 % (SC-003)

**Checkpoint US3**: ComparisonTable fonctionnelle, responsive, dark mode.

---

## Phase 6: User Story 4 — Carte géographique UEMOA (Priority: P2)

**Goal**: L'assistant produit `show_map` avec markers SVG et overlay UEMOA optionnel ; lazy-load Leaflet ; dark mode tile layer.

**Independent Test**: Avec un projet à Bouaké et un intermédiaire BOAD à Lomé, demander "où sont mes interlocuteurs ?" → carte Leaflet avec 2 markers, popups, overlay UEMOA, plein écran.

### Tests for User Story 4 (TDD strict)

- [ ] T049 [P] [US4] Test backend `backend/tests/unit/test_visualization_tools_map.py` — invocation valide ; markers vide rejeté ; lat/lon hors bornes rejeté ; popup_content trop long rejeté
- [ ] T050 [P] [US4] Test frontend `frontend/tests/unit/richblocks/MapBlock.spec.ts` (mock Leaflet via vi.mock) — markers passés au composant, color codes par type, overlay UEMOA chargé si `showUemoaOverlay=true`, popup au clic
- [ ] T051 [P] [US4] Test lazy-load `frontend/tests/unit/richblocks/MapBlock.spec.ts` (suite) — vérifier que `import('leaflet')` est appelé en `onMounted` et pas au top-level
- [ ] T052 [P] [US4] Test dark mode tiles `frontend/tests/unit/richblocks/MapBlock.spec.ts` (suite) — toggle dark via store ui → composable `useMapTiles` retourne URL CartoDB Dark Matter

### Implementation for User Story 4

- [ ] T053 [US4] Implémenter le tool `show_map` dans `backend/app/graph/tools/visualization_tools.py` avec helpers fallback centroïdes (importer `UEMOA_COUNTRY_CENTROIDS`). Faire passer T049.
- [ ] T054 [P] [US4] Créer le composant `frontend/app/components/richblocks/MapBlock.vue` selon `data-model.md` §5 et `spec.md` US4 : import dynamique Leaflet en `onMounted` (`L = await import('leaflet'); await import('leaflet/dist/leaflet.css')`), instanciation map + tile layer via `useMapTiles`, markers SVG colorés selon `type` (emerald/blue/violet/amber), popups DOMPurify-sanitisés, overlay GeoJSON via fetch `/_nuxt/assets/geo/uemoa-borders.geo.json` si `showUemoaOverlay=true`, bouton plein écran. Faire passer T050, T051, T052.
- [ ] T055 [US4] Wrapper le rendu dans `MessageParser.vue` via `defineAsyncComponent(() => import('~/components/richblocks/MapBlock.vue'))` pour assurer lazy-load à l'usage.
- [ ] T056 [US4] Mettre à jour `backend/app/graph/tool_selector_config.py` (pages `profile`, `profile_projects`, `financing` ; modules `chat`, `profiling`, `financing`).
- [ ] T057 [US4] Mettre à jour `backend/app/graph/nodes.py` pour binder `show_map` dans `chat_node`, `profiling_node`, `financing_node`.
- [ ] T058 [US4] Étendre `backend/app/prompts/system.py` (ou `financing.py`) avec recommandation `show_map` si géolocalisation pertinente (FR-026).

**Checkpoint US4**: Map Leaflet fonctionnelle avec lazy-load, overlay UEMOA, dark mode.

---

## Phase 7: User Story 5 — Sélection du bon tool (Priority: P2)

**Goal**: Le system prompt contient l'arbre de décision visualisation, le LLM choisit correctement entre KPI/Match/Comparison/Map/fences/texte.

**Independent Test**: Lancer le golden set complet (10 KPI + 5 match + 3 comparison + 1 map = 19 questions) avec mock LLM → ≥ 90 % de tool selection correct.

### Tests for User Story 5 (TDD strict)

- [ ] T059 [US5] Créer le fichier de golden set `backend/tests/integration/fixtures/visualization_golden_set.json` listant les 19 questions (10 KPI + 5 match + 3 comparison + 1 map) avec : `id`, `user_message`, `expected_tool` (ex: `"show_kpi_card"`), `context_page` (ex: `"carbon"`), `expected_min_args` (champs obligatoires attendus dans le tool call). Format JSON facilement extensible.
- [ ] T060 [US5] Test d'intégration consolidé `backend/tests/integration/test_visualization_prompts_full.py` — charge `visualization_golden_set.json` (T059), itère sur les 19 questions avec mock LLM, vérifie accuracy ≥ 90 % de sélection du bon tool typed selon contexte
- [ ] T060B [US5] Test "fallback texte" `backend/tests/integration/test_visualization_prompts_fallback.py` — questions floues (ex: "aide-moi à choisir") → LLM préfère texte au lieu de mauvais tool

### Implementation for User Story 5

- [ ] T061 [US5] Compléter l'arbre de décision visualisation dans `backend/app/prompts/system.py` avec 7 cas explicites (KPI / comparison / match / map / line_chart / pie_chart / mermaid / texte) selon spec.md §"Decision tree dans le prompt"
- [ ] T062 [US5] Documenter dans `backend/app/graph/tools/README.md` la section "Tools de visualisation" : règle "Si tool typé existe, l'utiliser" + exemples concrets

**Checkpoint US5**: Tool selection accuracy mesurée, prompts arbitrent correctement.

---

## Phase 8: E2E Playwright (USR1+USR2+USR3+USR4)

**Purpose**: Tests E2E exécutables couvrant les 4 scénarios principaux (un par user story P1/P2). Branche live de bout en bout.

- [ ] T063 Créer le fichier `frontend/tests/e2e/F11-tools-visualisation-typed.spec.ts` avec les 4 scénarios suivants (squelette ci-dessous) ; chaque scénario seed les données nécessaires via fixtures Playwright (helpers existants `frontend/tests/e2e/helpers/` ou API REST de seeding existants), puis pilote l'UI via le LLM ou via stub SSE selon disponibilité.

### Scénarios attendus dans T063

```typescript
import { test, expect } from '@playwright/test'

test.describe('F11 - Tools de visualisation typés', () => {
  test.beforeEach(async ({ page }) => {
    // login + navigation /chat
  })

  // Scénario A — KPICard pour empreinte carbone
  test('KPICard empreinte carbone rendu inline', async ({ page }) => {
    // Préparer un bilan carbone 2026 finalisé (45 tCO2e) + bilan 2024 (51 tCO2e)
    // Envoyer "résume mon empreinte carbone 2026"
    // Attendre l'event SSE tool_call_end pour show_kpi_card
    // Assertions :
    //   - Une .kpi-card-block est visible
    //   - Titre = "Empreinte carbone 2026"
    //   - Valeur contient "45"
    //   - Delta visible avec couleur verte (down + delta_is_good=true)
    //   - Picto Source visible et cliquable
    //   - Click sur picto → modale source visible
    //   - Click sur drilldown → URL contient "/carbon/results"
  })

  // Scénario B — 3 MatchCards cliquables
  test('3 MatchCards proposées avec drill-down', async ({ page }) => {
    // Préparer 1 projet test + 3 offres compatibles (data-tagged "GCF/BOAD/AFD")
    // Envoyer "quelles offres me correspondent ?"
    // Attendre 3 events tool_call_end show_match_card
    // Assertions :
    //   - 3 .match-card-block visibles
    //   - Chaque carte a logo (ou placeholder), score circulaire, badges instruments
    //   - Click sur "Explorer" de la 1re carte → URL contient "/financing/offers/" et "?project_id="
  })

  // Scénario C — ComparisonTable avec highlight winner
  test('ComparisonTable 3 offres avec highlight winner par row', async ({ page }) => {
    // Préparer 3 offres GCF (BOAD/UNDP/AFD)
    // Envoyer "compare GCF via BOAD vs GCF via UNDP vs GCF via AFD"
    // Attendre event tool_call_end show_comparison_table
    // Assertions :
    //   - 1 .comparison-table-block visible
    //   - 3 colonnes sujets, ≥ 4 rows critères
    //   - Au moins 1 cellule a la classe .winner (highlight vert)
    //   - Resize viewport à 600px → fold en cartes verticales (.comparison-cards-mobile visible)
  })

  // Scénario D — Map UEMOA avec markers + overlay
  test('Map UEMOA avec markers projet + intermédiaire et overlay', async ({ page }) => {
    // Préparer projet à Bouaké (lat 7.6906, lon -5.0307) + intermédiaire BOAD à Lomé (lat 6.1319, lon 1.2228)
    // Envoyer "où sont mes interlocuteurs en UEMOA ?"
    // Attendre event tool_call_end show_map (après lazy-load Leaflet)
    // Assertions :
    //   - 1 .map-block visible
    //   - 2 .leaflet-marker-icon présents
    //   - Path GeoJSON UEMOA visible (.leaflet-overlay-pane svg path)
    //   - Click sur 1 marker → popup visible avec label
    //   - Toggle dark mode → tile URL contient "cartocdn.com/dark_all"
  })
})
```

- [ ] T064 Configurer les fixtures de seeding nécessaires (utilisateur test, projet, offres GCF, bilan carbone) dans un helper `frontend/tests/e2e/helpers/F11-fixtures.ts` ; réutiliser les helpers existants si disponibles (vérifier `frontend/tests/e2e/helpers/`)
- [ ] T065 Lancer les E2E localement : `cd frontend && npx playwright test tests/e2e/F11-tools-visualisation-typed.spec.ts --reporter=html` et corriger les flakies éventuels

**Checkpoint Phase 8**: 4/4 scénarios E2E verts.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Audit qualité (couverture, accessibilité, dark mode, bundle), documentation, mise à jour CLAUDE.md.

- [ ] T066 [P] Audit couverture backend ≥ 80 % : `cd backend && source venv/bin/activate && pytest tests/ -v --cov=app.graph.tools.visualization_tools --cov=app.schemas.visualization --cov=app.core.visualization_centroids --cov-report=term-missing`. Compléter les tests manquants si < 80 %.
- [ ] T067 [P] Audit couverture frontend ≥ 80 % : `cd frontend && npm run test -- --coverage tests/unit/richblocks/`. Compléter les tests manquants si < 80 %.
- [ ] T068 [P] Audit dark mode visuel manuel sur les 4 composants (toggle store ui, vérifier contrastes, gradients, picto sources visibles)
- [ ] T069 [P] Audit accessibilité : lancer un check axe-core ou vérifier manuellement les aria-label, navigation clavier (Tab/Enter), contraste WCAG AA
- [ ] T070 Audit bundle frontend : capturer la baseline `cd frontend && npm run build` AVANT modifications F11 (taille `.output/public/_nuxt/_payload.js` + chunks main), puis recompiler après merge. Outils : `du -h .output/public/_nuxt/*.js | sort -h` et inspection manuelle du manifest. Vérifier (a) que le chunk Leaflet n'est pas dans le bundle initial — il doit apparaître comme un chunk asynchrone séparé, (b) que le delta du bundle initial chat ≤ +20 KB (cible SC-004). Si l'outil `nuxi analyze` est disponible, l'utiliser : `cd frontend && npx nuxi analyze`.
- [ ] T071 [P] Mettre à jour `CLAUDE.md` (section "Recent Changes") avec un résumé F11 (ajouté manuellement entre marqueurs `<!-- AGENT_CONTEXT_START -->` si présents)
- [ ] T072 [P] Compléter `backend/app/graph/tools/README.md` section "Tools de visualisation" (référence à T062 si pas encore fait)
- [ ] T073 Vérifier le constitution check post-implémentation (cf. plan.md) : francophone-first, modulaire, conversation-driven, TDD ≥ 80 %, sécurité, accessibilité, simplicité — tout doit rester PASS
- [ ] T073B Audit régression compatibilité ascendante (FR-031) : créer une assertion E2E ou unit test garantissant que le rendu d'un message contenant un fence ` ```chart` continue de produire un `ChartBlock` (idem `table`, `timeline`, `progress`, `gauge`, `mermaid`). Localisation : `frontend/tests/unit/richblocks/MessageParser.markdown-compat.spec.ts`
- [ ] T073C Validation manuelle SC-007 (test usage 30 s) : à conduire post-merge sur l'environnement preview avec 1-2 utilisateurs PME volontaires. Documenter dans une section "Validation utilisateur" du PR.
- [ ] T074 Créer un commit final (en plus du commit intermédiaire SpecKit) si la phase B-E2E ajoute du code : `feat(F11): tools visualisation typés (KPICard, MatchCard, Map, ComparisonTable)`

---

## Dependencies & Execution Order

```text
Phase 1 (Setup) — T001..T004
       │
       ▼
Phase 2 (Foundational) — T005..T017  [BLOCKING]
       │
       ├──────────────┬──────────────┬──────────────┐
       ▼              ▼              ▼              ▼
   Phase 3 (US1)   Phase 4 (US2)   Phase 5 (US3)   Phase 6 (US4)
   T018..T027     T028..T037     T038..T048     T049..T058
       │              │              │              │
       └──────┬───────┴──────────────┴──────────────┘
              ▼
       Phase 7 (US5) — T059..T062  [dépend de Phase 2 + au moins 1 story P1]
              │
              ▼
       Phase 8 (E2E) — T063..T065  [dépend de toutes les User Stories implémentées]
              │
              ▼
       Phase 9 (Polish) — T066..T074  [dépend de Phase 8 vert]
```

**Notes** :
- Les Phases 3, 4, 5, 6 peuvent s'exécuter **en parallèle** une fois la Phase 2 terminée (User Stories indépendantes, fichiers distincts modulo `MessageParser.vue` et `tool_selector_config.py` à sérialiser).
- `MessageParser.vue` et `useMessageParser.ts` sont mis à jour cumulativement par US1 → US2 → US3 → US4 (un seul écrivain à la fois ; sérialiser).
- `tool_selector_config.py` même contrainte (sérialiser US1 → US2 → US3 → US4).
- `nodes.py` même contrainte.
- L'agent Phase B implémentera ces tâches en suivant TDD strict (Red → Green → Refactor).

## MVP Scope

**MVP = Phase 1 + Phase 2 + Phase 3 (US1)** : un assistant capable de produire des KPICards sourcées sur dashboard/esg/carbon/credit avec dark mode et drill-down. Cela délivre déjà 80 % de la valeur pour les utilisateurs (cas d'usage le plus fréquent).

**Increments suivants** : ajouter US2, US3, US4 selon priorité métier.

## Parallel Execution Examples

### Au sein de Phase 2 (Foundational)

```text
# Lancer en // (différents fichiers) :
T005 (test KPI schema) — T006 (test Match schema) — T007 (test Map schema) — T008 (test Comparison schema) — T009 (test serialization)
T010 (impl schemas)
T011 (centroïdes) — T013 (types TS) — T014 (composable useMapTiles)
```

### Phases 3, 4, 5, 6 en // (User Stories indépendantes)

```text
# Une fois Phase 2 verte, démarrer en // :
[Agent A] Phase 3 (US1 KPICard)
[Agent B] Phase 4 (US2 MatchCard)
[Agent C] Phase 5 (US3 ComparisonTable)
[Agent D] Phase 6 (US4 Map)
```

Sérialiser uniquement les modifications de `MessageParser.vue`, `useMessageParser.ts`, `tool_selector_config.py`, `nodes.py`.

## Format Validation Checklist

- [x] Tous les tasks suivent le format `- [ ] T### [P?] [Story?] description avec chemin fichier`
- [x] Numéros séquentiels T001..T074
- [x] Marqueurs [P] uniquement sur tâches parallélisables
- [x] Marqueurs [USx] uniquement sur les phases user stories (Phase 3-7)
- [x] Tests E2E Playwright dans `frontend/tests/e2e/F11-tools-visualisation-typed.spec.ts` — 4 scénarios définis (T063)
- [x] TDD strict : tests écrits AVANT implémentation à chaque user story
- [x] Couverture cible 80 % vérifiée (T066, T067)
- [x] Pas de migration Alembic (vérifié dans plan.md)
- [x] Pas de nouvel endpoint REST (vérifié dans contracts/)
- [x] Sources cliquables F01 + Money typed F04 + Project F06 + Offer F07 intégrés
- [x] Dark mode obligatoire (audit T068)
- [x] Accessibilité ARIA (audit T069)
- [x] Lazy-load Leaflet (audit T070)
