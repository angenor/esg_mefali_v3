---
description: "Task list for F16 Simulateur Financement Sourcé + Comparateur Multi-Offres"
---

# Tasks: F16 — Simulateur Financement Sourcé + Comparateur Multi-Offres

**Input**: Design documents from `/specs/039-simulator-sourced/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api-simulate-multi.md, contracts/tool-compare-simulations.md, quickstart.md

**Tests**: TDD obligatoire (Constitution principe IV — NON-NEGOTIABLE). Tests AVANT implémentation, couverture ≥ 80 %.

**Organization** : Tâches groupées par user story (US1..US5) après une phase Setup et une phase Foundational. Suit l'ordre P1 → P1 → P1 → P2 → P2 du spec.

## Format

`- [ ] [TaskID] [P?] [Story?] Description avec chemin absolu`

## Path Conventions

- Backend : `backend/app/...`, `backend/tests/...`
- Frontend : `frontend/app/...`, `frontend/tests/...`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose** : Vérifications préalables, aucune création de fichier de code (NO MIGRATION).

- [ ] T001 Vérifier que la branche `feat/F16-simulateur-finance-source` est checkout et à jour avec `main` (rebase si besoin).
- [ ] T002 [P] Vérifier en BDD locale que la table `simulation_factors` (F01) existe et contient au moins les facteurs critiques `default_loan_rate`, `default_doc_fee_rate`, `default_guarantee_rate`, `default_fx_margin_rate`, `default_payback_months`, `gain_rate_default` (sinon créer un script de seed `backend/app/scripts/seed_simulation_factors_f16.py` idempotent qui les insère en statut `pending` avec FK source vers `system://mefali/simulation-factors-f16`).
- [ ] T003 [P] Lire `specs/039-simulator-sourced/spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/api-simulate-multi.md`, `contracts/tool-compare-simulations.md`, `quickstart.md`.
- [ ] T004 [P] Confirmer en relisant `backend/alembic/versions/` qu'aucune migration F16 n'est nécessaire (les tables sont toutes pré-existantes via F01..F23).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose** : Schémas Pydantic et garde-fous transversaux nécessaires à toutes les user stories.

**⚠️ CRITICAL** : aucune US ne peut démarrer avant la fin de cette phase.

- [ ] T005 [P] Écrire le test garde-fou `backend/tests/unit/test_no_magic_constants_in_simulation.py` : parse AST de `backend/app/modules/applications/simulation.py`, fail si numérique ∉ whitelist `{0, 1, 12}`. Doit passer ROUGE pour l'instant (le fichier contient encore `_SAVINGS_RATE = 0.15`).
- [ ] T006 [P] Écrire les tests unitaires pour `factor_service` dans `backend/tests/unit/test_factor_service.py` : (a) `load_factors_snapshot` retourne un FactorSnapshot frozen (immuable), (b) sources jointes en un seul SELECT, (c) facteurs `outdated` exclus, (d) `verified` et `pending` inclus avec `factor_status` correct, (e) snapshot `loaded_at` UTC.
- [ ] T007 Implémenter `backend/app/modules/applications/factor_service.py` avec `FactorEntry`, `SourceRef`, `FactorSnapshot` (frozen dataclass), fonction `async load_factors_snapshot(db: AsyncSession) -> FactorSnapshot`. T006 doit passer VERT.
- [ ] T008 [P] Étendre `backend/app/modules/applications/schemas.py` : ajouter `MonetaryFigure`, `CostBreakdown`, `RoiBreakdown`, `CarbonImpact`, `TimelineStep`, `SimulationResult`, `DegradedColumn`, `ComparisonMetadata`, `MultiSimulateRequest`, `MultiSimulateResponse` (Pydantic v2 strict, `model_config = ConfigDict(extra='forbid')`, validators dedup et borne 1..5). Tests inline pour chaque schéma dans `backend/tests/unit/test_simulation_schemas.py`.

**Checkpoint** : factor_service + schémas validés. Implémentation des US peut démarrer.

---

## Phase 3: User Story 1 — Coût total réel sourcé (Priority: P1) 🎯 MVP

**Goal** : La PME voit la décomposition complète du coût total (principal + doc_fee + total_fees_over_duration + guarantee + fx_margin) en Money typed, chaque ligne avec une source cliquable.

**Independent Test** : Appeler `POST /api/projects/{id}/simulate-multi` avec une seule offre prêt concessionnel et vérifier que la réponse contient un `cost_breakdown` complet avec un `source_id` non-null sur chaque `MonetaryFigure` non-dégradée.

### Tests-First (US1)

- [ ] T009 [P] [US1] Écrire `backend/tests/unit/test_compute_total_cost.py` : (a) agrégation Money typed XOF, (b) doc_fee lu depuis snapshot factors, (c) total_fees calculé sur durée du projet (months/12), (d) fx_margin = 0 si devise fonds == devise PME, (e) fx_margin > 0 sinon avec source du facteur `default_fx_margin_rate`, (f) `source_id` rempli sur chaque MonetaryFigure, (g) total_cost == principal + doc_fee + total_fees + fx_margin (la garantie n'entre pas).
- [ ] T010 [P] [US1] Écrire `backend/tests/unit/test_compute_total_cost_degraded.py` : (a) facteur introuvable → `MonetaryFigure.degraded_reason='facteur_introuvable'` et `amount=Money(0, ...)`, (b) statut `pending` → `factor_status='pending'` propagé, (c) statut `outdated` → propagé.
- [ ] T011 [P] [US1] Écrire `backend/tests/integration/test_simulate_multi_router_us1.py` : 200 OK pour 1 offre prêt concessionnel sur projet 5M XOF, vérifie cost_breakdown complet et SourceLink sur chaque ligne, vérifie absence de `cheapest_offer_id`/`fastest_offer_id` (1 seule offre).

### Implementation (US1)

- [ ] T012 [US1] Refactor `backend/app/modules/applications/simulation.py` : SUPPRIMER `_SAVINGS_RATE`, `_CARBON_IMPACT_PER_MXOF`, `_DEFAULT_FEE_RATE` et toute autre constante magique. Implémenter `async compute_total_cost(project, offer, snapshot, currency_service) -> CostBreakdown` lisant doc_fee/fee_rate/guarantee_rate/fx_margin_rate uniquement depuis `snapshot.factors`. Vérifier que T005 (anti-magic) passe VERT.
- [ ] T013 [US1] Implémenter dans `simulation.py` la fonction `_to_monetary_figure(amount, source_id, factor_name, factor_status, currency_service)` qui convertit Money → MonetaryFigure avec equivalent PME (lecture `currency_service.convert` F04).
- [ ] T014 [US1] Créer `backend/app/modules/applications/multi_simulate_service.py` avec `async simulate_multi(db, project_id, offer_ids, account_id) -> MultiSimulateResponse` (squelette : dedup, charge snapshot via `load_factors_snapshot`, charge project + offers, boucle `simulate_offer` pour chaque offre, agrège metadata). Pour cette US : ne calcule que `cost_breakdown` (les autres champs sont laissés vides, complétés US2/US3/US4).
- [ ] T015 [US1] Étendre `backend/app/modules/applications/router.py` : ajouter `POST /api/projects/{project_id}/simulate-multi` avec `Depends(get_current_user)`, signature `(project_id: UUID, body: MultiSimulateRequest, db, user)`, gestion erreurs 401/403/404/422/503, retourne `MultiSimulateResponse`.
- [ ] T016 [US1] Vérifier T009/T010/T011 VERTS. Coverage `simulation.compute_total_cost` ≥ 80 %.

**Checkpoint US1** : on peut simuler une offre seule, voir le coût total décomposé, chaque chiffre source-cliquable. MVP livrable.

---

## Phase 4: User Story 2 — Comparateur multi-offres côte-à-côte (Priority: P1)

**Goal** : Comparer 2 à 5 offres pour un même projet, voir un tableau côte-à-côte avec highlight « moins chère » + « plus rapide ».

**Independent Test** : Appeler `simulate-multi` avec 3 offres distinctes, vérifier `comparison_metadata.cheapest_offer_id` et `comparison_metadata.fastest_offer_id` non-nuls et cohérents avec les coûts/timelines retournés.

### Tests-First (US2)

- [ ] T017 [P] [US2] Écrire `backend/tests/unit/test_multi_simulate_service_ranking.py` : (a) 1 offre = pas de winner, (b) 2 offres = cheapest/fastest désignés, (c) offre dégradée exclue du ranking, (d) tie-break déterministe (UUID lexicographique) si égalité.
- [ ] T018 [P] [US2] Écrire `backend/tests/unit/test_multi_simulate_service_dedup.py` : (a) `[uuid_a, uuid_a, uuid_b]` → calcule 2 offres uniquement, (b) ordre préservé.
- [ ] T019 [P] [US2] Écrire `backend/tests/integration/test_simulate_multi_router_us2.py` : 200 OK pour 3 offres, valide highlights, valide 422 si 6 offres, valide 422 si liste vide après dedup.
- [ ] T020 [P] [US2] Écrire `backend/tests/integration/test_simulate_multi_rls.py` : crée 2 comptes, vérifie que compte A ne peut pas simuler avec offer du compte B (403) et avec project du compte B (404), aucune fuite d'info.
- [ ] T021 [P] [US2] Écrire `backend/tests/integration/test_simulate_multi_sources.py` : conformité — toute valeur Money non-dégradée a `source_id IS NOT NULL`. Test scan récursif du JSON de réponse.

### Implementation (US2)

- [ ] T022 [US2] Compléter `multi_simulate_service.simulate_multi` : calcul `cheapest_offer_id` (min total_cost converti devise PME pour comparabilité, exclut dégradés), `fastest_offer_id` (min sum(weeks_max), exclut dégradés/timeline incomplète).
- [ ] T023 [US2] Ajouter dans `simulate_multi` la logique `DegradedColumn` : try/except autour de `simulate_offer` par offre, capture `FactorMissingError` ou `OfferDataMissingError` → renvoie `DegradedColumn(offer_id, degraded=True, reason=...)`. Le calcul des autres offres continue.
- [ ] T024 [US2] Ajouter validation FR-013 dans router : 404 si projet hors tenant (avant 403 sur offres pour ne pas révéler), 403 si au moins une offer hors tenant (vérification post-RLS).
- [ ] T025 [US2] Vérifier T017-T021 VERTS.

**Checkpoint US2** : comparaison multi-offres opérationnelle backend.

---

## Phase 5: User Story 3 — Impact carbone et timeline non inventés (Priority: P1)

**Goal** : `CarbonImpact` calculé depuis project.expected_impact_tco2e × ratio sectoriel sourcé F17 ; `TimelineStep[]` lu depuis offer.intermediary + offer.fund + sources F07.

### Tests-First (US3)

- [ ] T026 [P] [US3] Écrire `backend/tests/unit/test_compute_carbon_impact.py` : (a) project avec `expected_impact_tco2e=12.4` + sector_factor 1.0 verified → tco2e_per_year=12.4 + source_id, (b) facteur `is_approximate=True` (fallback année antérieure) propagé, (c) fallback global si pays absent, (d) project sans estimate → tco2e_per_year=None + degraded_reason='aucune_estimation_projet', (e) facteur sectoriel introuvable → degraded_reason='aucun_facteur_sectoriel_disponible'.
- [ ] T027 [P] [US3] Écrire `backend/tests/unit/test_build_timeline.py` : (a) 4 étapes labelées en français, (b) `weeks_min/max` calculés depuis `intermediary.processing_time_days_min/max // 7`, (c) `source_id` propagé pour chaque étape, (d) étape sans données → degraded_reason='delai_intermediaire_non_renseigne' avec weeks_min=weeks_max=None, (e) deux offres avec intermédiaires différents → timelines différentes (régression FR-007).
- [ ] T028 [P] [US3] Écrire `backend/tests/integration/test_simulate_multi_carbon_timeline.py` : appel multi-simulate avec 2 offres (intermédiaires distincts), vérifie timelines distinctes et carbon_impact non-nul si project a expected_impact.

### Implementation (US3)

- [ ] T029 [US3] Implémenter `compute_carbon_impact(project, offer, snapshot, emission_factor_lookup)` dans `simulation.py` : appelle un helper qui interroge `emission_factors` par `(category='sector_carbon_intensity', country=project.country, year=now.year)` avec fallback ascendant (R3 du research). PAS de constante numérique.
- [ ] T030 [US3] Implémenter `build_timeline(offer)` dans `simulation.py` : 4 TimelineStep (preparation/instruction/validation/decaissement) lisant offer.intermediary.processing_time_days_*, offer.fund.typical_timeline_months × 4, offer.intermediary.disbursement_time_days_*, joints à leurs source_id F01.
- [ ] T031 [US3] Brancher `compute_carbon_impact` et `build_timeline` dans `simulate_offer` (composition dans `simulation.py`) puis dans `multi_simulate_service`.
- [ ] T032 [US3] Vérifier T026-T028 VERTS. Coverage `compute_carbon_impact` + `build_timeline` ≥ 80 %.

**Checkpoint US3** : aucune valeur inventée pour le carbone ou la timeline.

---

## Phase 6: User Story 4 — ROI différencié par instrument (Priority: P2)

**Goal** : `RoiBreakdown` calculé via dispatch `dict[InstrumentLiteral, RoiCalculator]` ; subvention/pret_concessionnel/equity/blending ont des formules distinctes.

### Tests-First (US4)

- [ ] T033 [P] [US4] Écrire `backend/tests/unit/test_compute_roi.py` : (a) subvention → `payback_months=None`, `notes_fr` contient « pas de remboursement », (b) pret_concessionnel → `ratio` calculé, `payback_months` dérivé, (c) equity → ratio dilution + IRR, (d) blending → combinaison pondérée, (e) chaque RoiBreakdown porte `sources` non-vide.
- [ ] T034 [P] [US4] Écrire `backend/tests/integration/test_simulate_multi_roi_differenciated.py` : 2 offres (subvention vs prêt concessionnel) sur même projet → ROI distincts (régression FR-005).

### Implementation (US4)

- [ ] T035 [US4] Implémenter dans `simulation.py` la table de dispatch `_ROI_DISPATCH: dict[InstrumentLiteral, Callable]` et 4 fonctions pures `_roi_subvention`, `_roi_pret_concessionnel`, `_roi_equity`, `_roi_blending` (R2 du research). Toutes lisent les paramètres depuis `snapshot.factors`.
- [ ] T036 [US4] Implémenter `compute_roi(project, offer, snapshot) -> RoiBreakdown` qui détermine l'instrument depuis `offer.fund.instruments` (JSONB) et appelle la fonction dispatch correspondante. Edge case blending : prend la combinaison majoritaire ou applique `_roi_blending`.
- [ ] T037 [US4] Brancher `compute_roi` dans `simulate_offer`. Vérifier T033/T034 VERTS.

**Checkpoint US4** : ROI différencié.

---

## Phase 7: User Story 5 — Tool LangChain `compare_simulations` (Priority: P2)

**Goal** : la PME peut depuis le chat dire « compare GCF/BOAD et SUNREF pour mon projet » et voir un `ComparisonTableBlock` (F11) rendu dans la conversation.

### Tests-First (US5)

- [ ] T038 [P] [US5] Écrire `backend/tests/unit/test_compare_simulations_tool_args.py` : valide `CompareSimulationsArgs` (Pydantic strict, extra='forbid', borne 1..5, dedup logique).
- [ ] T039 [P] [US5] Écrire `backend/tests/integration/test_compare_simulations_tool.py` : appel du tool avec `(project_id, [offer_a, offer_b, offer_c])` → marker SSE F11 émis dans le contenu, payload conforme `ComparisonTableArgs` (subjects, rows, winner_indices), résumé JSON `{ok:true, compared:3, cheapest_offer_id, fastest_offer_id, ...}`.
- [ ] T040 [P] [US5] Écrire `backend/tests/integration/test_compare_simulations_tool_errors.py` : (a) > 5 offres → `{ok:false, error:'max_5_offres'}`, (b) project hors tenant → `{ok:false, error:'access_denied'}`, (c) project_id absent → `{ok:false, error:'project_required'}`.

### Implementation (US5)

- [ ] T041 [US5] Créer `backend/app/graph/tools/simulation_tools.py` : `CompareSimulationsArgs` Pydantic strict, fonction `@tool compare_simulations(project_id: UUID, offer_ids: list[UUID])` qui appelle `multi_simulate_service.simulate_multi`, formate le payload `ComparisonTableArgs` F11, émet le marker SSE `<!--SSE:{"__sse_visualization_block__":true,"block_type":"comparison_table","payload":{...}}-->`, retourne le résumé JSON court.
- [ ] T042 [US5] Étendre `backend/app/graph/tool_selector_config.py` : ajouter le pattern URL `^/financing/simulator(?:/|$)` AVANT `^/financing` dans `_PATH_TO_SLUG_PATTERNS` ; injecter `compare_simulations` dans `MODULE_TOOL_MAPPING['financing']`, `MODULE_TOOL_MAPPING['application']`, `PAGE_TOOL_MAPPING['financing']`, `PAGE_TOOL_MAPPING['simulator']`.
- [ ] T043 [US5] Étendre `backend/app/graph/nodes.py` : `bind_tools` du `financing_node` et `application_node` inclut `compare_simulations`. Vérifier `MAX_TOOLS_PER_TURN` toujours respecté.
- [ ] T044 [US5] Étendre les prompts `app/graph/prompts/financing.py` et `app/graph/prompts/application.py` avec une section « TOOL COMPARE_SIMULATIONS » : cas d'usage, contrainte `project_id` obligatoire, fallback question interactive si projet inconnu.
- [ ] T045 [US5] Vérifier T038-T040 VERTS. Coverage `simulation_tools.py` ≥ 80 %.

**Checkpoint US5** : tool conversationnel disponible.

---

## Phase 8: Frontend (transverse US1..US5)

**Purpose** : refactor de la page simulator + composants Vue.

### Tests-First (Frontend)

- [ ] T046 [P] Écrire `frontend/tests/unit/composables/useSimulator.spec.ts` (Vitest) : `simulateMulti(projectId, offerIds)` appelle l'API, gère 200/403/404/422, ne persiste rien hors store volatile.
- [ ] T047 [P] Écrire `frontend/tests/unit/stores/simulator-store.spec.ts` : state Pinia volatile, `setSelectedProject`, `toggleOffer` (max 5), reset après navigation.
- [ ] T048 [P] Écrire `frontend/tests/unit/components/financing/OffersMultiPicker.spec.ts` : props, dedup visuel, max 5 hard-cap, dark mode, ARIA `role='listbox'` + `aria-multiselectable='true'`.
- [ ] T049 [P] Écrire `frontend/tests/unit/components/financing/DetailedSimulationCard.spec.ts` : rend cost_breakdown, ROI, carbon, timeline, MoneyDisplay, SourceLink, badges `factor_status='pending'/'outdated'`.

### Implementation (Frontend)

- [ ] T050 Créer `frontend/app/types/simulator.ts` : interfaces TypeScript miroirs strictes des schémas Pydantic v2 (`SimulationResult`, `CostBreakdown`, `MonetaryFigure`, `RoiBreakdown`, `CarbonImpact`, `TimelineStep`, `MultiSimulateRequest`, `MultiSimulateResponse`, `DegradedColumn`, `ComparisonMetadata`).
- [ ] T051 [P] Créer `frontend/app/composables/useSimulator.ts` : `simulateMulti`, `useFetchAuth` Bearer, gestion erreurs 401/403/404/422.
- [ ] T052 [P] Créer `frontend/app/stores/simulator.ts` (Pinia) : state volatile + actions, reset on logout.
- [ ] T053 [P] Créer `frontend/app/components/financing/ProjectSelector.vue` : sélecteur projet (lit `useProjects` F06), dark mode, ARIA combobox.
- [ ] T054 [P] Créer `frontend/app/components/financing/OffersMultiPicker.vue` : multi-sélection chips, max 5, dedup, dark mode, ARIA listbox.
- [ ] T055 [P] Créer `frontend/app/components/financing/DetailedSimulationCard.vue` : rend `SimulationResult` (1 offre) avec MoneyDisplay (F04), SourceLink (F01), ReferentialBadge (F04), bandeaux d'avertissement pour `factor_status='pending'/'outdated'`. Dark mode complet.
- [ ] T056 Refactor `frontend/app/pages/financing/simulator.vue` : assemble ProjectSelector + OffersMultiPicker + bouton « Simuler ». Pour 1 offre : DetailedSimulationCard. Pour 2..5 offres : ComparisonTableBlock (F11) avec payload construit côté backend ou mappé client. Dark mode + accessibilité clavier.
- [ ] T057 Vérifier T046-T049 VERTS.

---

## Phase 9: E2E

- [ ] T058 Écrire `frontend/tests/e2e/F16-simulateur-finance-source.spec.ts` (Playwright) : 4 scénarios :
  - **SC1 (US1)** : créer projet 5M XOF, sélectionner 1 offre prêt concessionnel, lancer simulation, vérifier cost_breakdown rendu + clic sur taux ouvre la fiche source.
  - **SC2 (US2)** : sélectionner 3 offres distinctes (mock GCF/BOAD vs GCF/UNDP vs SUNREF Ecobank), lancer comparaison, vérifier coûts différents et badges « Moins chère » + « Plus rapide ».
  - **SC3 (US3)** : 2 offres avec intermédiaires distincts → timelines visibles distinctes dans le tableau.
  - **SC4 (US5)** : depuis la page chat, taper « compare GCF/BOAD et SUNREF pour mon projet » → ComparisonTableBlock rendu inline dans le fil.
- [ ] T059 Lancer la spec E2E, ajuster les helpers de mock backend si nécessaire dans `frontend/tests/e2e/helpers/F16-helpers.ts`.

---

## Phase 10: Polish & Cross-Cutting

- [ ] T060 Lancer `pytest --cov=app.modules.applications.simulation --cov=app.modules.applications.factor_service --cov=app.modules.applications.multi_simulate_service --cov=app.modules.applications.router --cov=app.graph.tools.simulation_tools --cov-fail-under=80 backend/tests/` ; corriger les zones < 80 %.
- [ ] T061 Lancer `pytest backend/tests/` complet ; vérifier 0 régression sur la baseline pré-F16.
- [ ] T062 Lancer `npx vitest run` côté frontend ; vérifier 0 régression hors préexistants connus.
- [ ] T063 [P] Vérifier accessibilité clavier sur `pages/financing/simulator.vue` (Tab order, Enter sur ProjectSelector et OffersMultiPicker, Escape sur dialogs si présents). Documenter dans le commit.
- [ ] T064 [P] Vérifier dark mode complet : toggler `dark` sur `<html>` et inspecter contrastes sur tous les nouveaux composants. Pas de hardcode `bg-white` sans `dark:bg-dark-card`.
- [ ] T065 Mettre à jour `CLAUDE.md` (section "Recent Changes") avec un paragraphe résumant F16 (suivre le format des features précédentes : migration, modèles, tests, frontend).
- [ ] T066 Commit final avec message conventionnel `feat(F16): simulateur financement sourcé + comparateur multi-offres`. Inclure mention « no migration » et « zero regression » dans le corps.

---

## Dependencies

```
Phase 1 (Setup) → Phase 2 (Foundational)
Phase 2 → Phase 3 (US1)
Phase 3 → Phase 4 (US2)         [US2 réutilise simulate_offer + cost_breakdown US1]
Phase 4 → Phase 5 (US3)         [US3 ajoute carbon + timeline à simulate_offer]
Phase 5 → Phase 6 (US4)         [US4 ajoute ROI à simulate_offer]
Phase 6 → Phase 7 (US5)         [US5 réutilise simulate_multi déjà complet]
Phase 7 → Phase 8 (Frontend)    [Frontend consomme l'API stable]
Phase 8 → Phase 9 (E2E)
Phase 9 → Phase 10 (Polish)
```

US1 = MVP livrable seul (1 offre, cost_breakdown). US2 ajoute le comparateur. US3+US4 enrichissent les colonnes. US5 ajoute le canal conversationnel. Frontend transverse à toutes les US.

## Parallel Execution Examples

- **Phase 2** : T005, T006, T008 en parallèle (fichiers distincts), T007 séquentiel après T006.
- **Phase 3 (US1) tests** : T009, T010, T011 en parallèle.
- **Phase 4 (US2) tests** : T017, T018, T019, T020, T021 en parallèle.
- **Phase 5 (US3) tests** : T026, T027, T028 en parallèle.
- **Phase 7 (US5) tests** : T038, T039, T040 en parallèle.
- **Phase 8 (Frontend) tests** : T046, T047, T048, T049 en parallèle.
- **Phase 8 (Frontend) impl** : T051, T052, T053, T054, T055 en parallèle après T050.
- **Phase 10 polish** : T063, T064 en parallèle.

## Implementation Strategy

1. **MVP (sprint 1)** : Setup + Foundational + US1. Livrable : simulation 1 offre avec cost_breakdown sourcé.
2. **Sprint 1 fin** : US2. Livrable : comparateur multi-offres backend opérationnel.
3. **Sprint 2 début** : US3 + US4. Livrable : carbon + ROI + timeline complets.
4. **Sprint 2 milieu** : US5 + Frontend. Livrable : tool chat + page simulator refactor.
5. **Sprint 2 fin** : E2E + Polish + couverture ≥ 80 % + commit.

Total : **66 tâches**.
