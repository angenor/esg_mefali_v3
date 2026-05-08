# Quickstart — F16 Simulateur Financement Sourcé

**Public** : développeur·se reprenant l'implémentation de F16 après la phase de spec.

## Pré-requis

- Branche `feat/F16-simulateur-finance-source` checkout.
- Backend venv activé : `source backend/venv/bin/activate`.
- Postgres en marche avec migrations F01..F23 appliquées (`alembic upgrade head`).
- Frontend deps installées : `cd frontend && npm i`.

## Ordre d'implémentation (TDD obligatoire)

1. **Lire** : `spec.md` + `research.md` + `data-model.md` + les 2 contrats.
2. **Tests AVANT code** :
   - Créer `backend/tests/unit/test_factor_service.py` — cases : snapshot frozen, sources jointes, statut filtré.
   - Créer `backend/tests/unit/test_simulation_compute.py` — cases : `compute_total_cost` agrégation Money typed ; `compute_roi` 4 instruments ; `compute_carbon_impact` fallback ; `build_timeline` lit délais offre.
   - Créer `backend/tests/unit/test_no_magic_constants_in_simulation.py` — AST scan whitelist `{0, 1, 12}`.
   - Créer `backend/tests/unit/test_multi_simulate_service.py`.
   - Créer `backend/tests/integration/test_simulate_multi_router.py`.
   - Créer `backend/tests/integration/test_simulate_multi_rls.py`.
   - Créer `backend/tests/integration/test_compare_simulations_tool.py`.
   - Vitest : `frontend/tests/unit/components/financing/OffersMultiPicker.spec.ts`, `useSimulator.spec.ts`, `simulator-store.spec.ts`.
3. **Backend implémentation** (Red → Green) :
   - `backend/app/modules/applications/factor_service.py` : `load_factors_snapshot(db) -> FactorSnapshot`.
   - Refactor `backend/app/modules/applications/simulation.py` : supprimer toute constante magique, exposer `compute_total_cost`, `compute_roi`, `compute_carbon_impact`, `build_timeline`, `simulate_offer`. **Vérifier** que `test_no_magic_constants_in_simulation.py` passe.
   - `backend/app/modules/applications/multi_simulate_service.py` : `simulate_multi(db, project_id, offer_ids, account_id)`.
   - `backend/app/modules/applications/schemas.py` : ajout `MultiSimulateRequest`, `MultiSimulateResponse`, `SimulationResult`, `CostBreakdown`, `MonetaryFigure`, `RoiBreakdown`, `CarbonImpact`, `TimelineStep`, `DegradedColumn`, `ComparisonMetadata`.
   - `backend/app/modules/applications/router.py` : `POST /api/projects/{project_id}/simulate-multi`.
4. **Tool LangChain** :
   - `backend/app/graph/tools/simulation_tools.py` : `compare_simulations` + `CompareSimulationsArgs`.
   - Mise à jour `backend/app/graph/tool_selector_config.py` (page `simulator`, ajout pattern `^/financing/simulator`).
   - Injection dans `MODULE_TOOL_MAPPING['financing']` et `MODULE_TOOL_MAPPING['application']`.
   - `backend/app/graph/nodes.py` : `bind_tools` mis à jour pour les 2 nœuds concernés.
5. **Frontend** :
   - `frontend/app/types/simulator.ts` : types miroirs.
   - `frontend/app/composables/useSimulator.ts` : `simulateMulti(projectId, offerIds)`.
   - `frontend/app/stores/simulator.ts` : Pinia store volatile.
   - Composants `frontend/app/components/financing/{ProjectSelector,OffersMultiPicker,DetailedSimulationCard}.vue`.
   - Refactor `frontend/app/pages/financing/simulator.vue` : projet + offres + render `ComparisonTableBlock` (F11) ou `DetailedSimulationCard`.
6. **E2E** : `frontend/tests/e2e/F16-simulateur-finance-source.spec.ts` — scénario « simuler GCF/BOAD vs GCF/UNDP, vérifier coûts différents et sources cliquables ».
7. **Couverture** : `pytest --cov=app.modules.applications.simulation --cov=app.modules.applications.factor_service --cov=app.modules.applications.multi_simulate_service --cov=app.modules.applications.router --cov=app.graph.tools.simulation_tools --cov-fail-under=80`.

## Garde-fous critiques

- **Sourçage F01** : chaque `MonetaryFigure` non-dégradée doit avoir `source_id != None`. Test conformité dédié.
- **Anti-magic-constants** : test AST échoue → corriger en lisant le facteur depuis le snapshot.
- **Money typed F04** : aucun `Decimal` nu exposé en réponse, tout passe par `Money`.
- **RLS F02** : tests intégration multi-tenant obligatoires (deux comptes, vérifier 403/404).

## Commandes utiles

```bash
# Backend tests F16 ciblés
source backend/venv/bin/activate
pytest backend/tests/unit/test_factor_service.py backend/tests/unit/test_simulation_compute.py backend/tests/unit/test_no_magic_constants_in_simulation.py backend/tests/unit/test_multi_simulate_service.py -v

# Backend integration F16
pytest backend/tests/integration/test_simulate_multi_router.py backend/tests/integration/test_simulate_multi_rls.py backend/tests/integration/test_compare_simulations_tool.py -v

# Frontend Vitest
cd frontend && npx vitest run tests/unit/components/financing tests/unit/composables/useSimulator.spec.ts tests/unit/stores/simulator-store.spec.ts

# E2E
cd frontend && npx playwright test tests/e2e/F16-simulateur-finance-source.spec.ts
```

## Definition of Done

- [ ] Tous les tests F16 verts.
- [ ] Couverture ≥ 80 % sur les 5 modules listés.
- [ ] Test AST `test_no_magic_constants_in_simulation.py` vert.
- [ ] Test conformité sources vert (toute valeur non-dégradée a `source_id`).
- [ ] Aucune régression sur les tests baseline (`pytest backend/tests` complet).
- [ ] Round-trip Alembic `up/down/up` non requis (pas de migration F16).
- [ ] Page `/financing/simulator` en mode sombre + accessibilité clavier vérifiées manuellement.
- [ ] Spec.md, plan.md, research.md, data-model.md, contracts/, tasks.md committés sur la branche.
