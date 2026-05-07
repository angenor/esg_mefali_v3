---

description: "Task list — F17 Carbone Mix UEMOA + Facteurs ADEME/IPCC Sourcés + Catégorie Achats"
---

# Tasks: F17 — Carbone Mix UEMOA + Facteurs ADEME/IPCC Sourcés + Catégorie Achats

**Input** : Design documents from `/specs/024-carbone-mix-uemoa-source/`
**Prerequisites** : plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Branch** : `feat/F17-carbone-mix-uemoa-source` (alias SpecKit `024-carbone-mix-uemoa-source`)

**Tests** : Tests TDD obligatoires (cycle Red-Green-Refactor enforce, couverture ≥ 80 %).

**Organization** : Tasks groupées par user story (US1, US2, US3, US4) pour livraison incrémentale.

## Format : `[ID] [P?] [Story] Description`

- **[P]** : Peut s'exécuter en parallèle (fichiers différents, pas de dépendance bloquante)
- **[Story]** : Rattachement user story (US1, US2, US3, US4) ; absent pour Setup/Foundational/Polish
- Chemins absolus depuis racine repo

## Path Conventions

- **Backend** : `backend/app/`, `backend/tests/`, `backend/alembic/versions/`
- **Frontend** : `frontend/app/`, `frontend/tests/`
- **Specs** : `specs/024-carbone-mix-uemoa-source/`

---

## Phase 1 : Setup (Shared Infrastructure)

**Purpose** : Préparer l'environnement de développement et vérifier les prérequis.

- [ ] T001 Vérifier l'activation du venv backend (`source backend/venv/bin/activate`) et des dépendances installées (`pip install -r backend/requirements.txt`) ; vérifier `which python` pointe vers `backend/venv/bin/python`.
- [ ] T002 Vérifier que la migration F01 (`020_create_sources_catalog`) est appliquée localement (`cd backend && alembic current` doit afficher au moins `020_*`) et que les sources ADEME Base Carbone v23 / IPCC AR6 WG3 / IEA Africa Energy Outlook 2024 sont seedées (`SELECT COUNT(*) FROM sources WHERE verification_status='verified'` ≥ 3).
- [ ] T003 [P] Vérifier que les dépendances frontend sont à jour (`cd frontend && npm install`) et que Playwright est installé (`npx playwright install`).

---

## Phase 2 : Foundational (Blocking Prerequisites)

**Purpose** : Mise en place de la migration Alembic, du module `factor_service`, du seed et des schémas Pydantic — prérequis bloquants pour toutes les user stories.

**⚠️ CRITICAL** : Aucune user story ne peut commencer avant la fin de cette phase.

### Tests Foundational (TDD — écrire AVANT implémentation, vérifier qu'ils ÉCHOUENT)

- [ ] T004 [P] Écrire test unitaire `backend/tests/unit/test_reduction_plan_schema.py` : `ReductionPlanAction` (validation `source_id`/`unsourced` cohérence, bornes title/description/timeline, contradiction levée).
- [ ] T005 [P] Écrire test unitaire `backend/tests/unit/test_factor_service.py` : `get_emission_factor` (7 cas : match exact, pays + année antérieure récente, pays + année très antérieure, fallback global, no country, no found, ignore draft).
- [ ] T006 [P] Écrire test unitaire `backend/tests/unit/test_seed_factors.py` : seed idempotent (premier run → 50 inserted ; deuxième run → 0 inserted/50 skipped ; mapping source corrigé sur ADEME/IEA/IPCC ; comptage par catégorie correct).
- [ ] T007 [P] Écrire test migration `backend/tests/migrations/test_alembic_f17.py` : up/down/up sans erreur ; backfill (entries historiques avec subcategory `electricity_ci` → liées au factor `electricity_ci_2024` correct ; entries non matchables → fallback générique global) ; contraintes NOT NULL appliquées en deuxième temps.

### Implementation Foundational

- [ ] T008 Créer `backend/app/modules/carbon/reduction_plan_schema.py` avec `ReductionPlanAction` et `ReductionPlan` Pydantic conformément au contrat `contracts/carbon-emission-factor.md` § 5 (validateur `model_validator` sur cohérence source_id/unsourced).
- [ ] T009 Créer `backend/app/modules/carbon/factor_service.py` avec dataclass `EmissionFactorResolution`, exception `EmissionFactorNotFoundError`, fonction async `get_emission_factor(db, category, country, year)` selon l'algorithme priorité pays/année du contrat § 1.
- [ ] T010 Créer `backend/app/modules/carbon/seed_factors.py` avec constante `SEED_DATA` (~50 lignes : 8 électricité UEMOA + combustibles + transport + déchets + 6 achats + variantes années antérieures pour priorité fallback) et fonction async `seed_emission_factors(db, admin_user_id) -> SeedResult` utilisant `INSERT ON CONFLICT (code) DO NOTHING` ; intègre les valeurs documentées dans `research.md` § 6.
- [ ] T011 Créer la migration Alembic `backend/alembic/versions/024_carbone_mix_uemoa.py` (revision=`024_carbone_mix_uemoa`, down_revision=`023_create_message_chunks`) — voir `data-model.md` § 6 : (1) ajout colonne `year` Integer NOT NULL avec backfill 2024, (2) index composite + UNIQUE constraint, (3) appel `seed_emission_factors`, (4) ajout `source_id` + `factor_id` nullable sur `carbon_emission_entries`, (5) backfill matching subcategory→code + fallback générique global, (6) NOT NULL + FK ; downgrade symétrique sans suppression de `source_description` (legacy 2 sprints).
- [ ] T012 Étendre `backend/app/models/emission_factor.py` avec `year: Mapped[int] = mapped_column(Integer, nullable=False)` + ajouter UNIQUE constraint `(category, country, year)` + index composite `idx_emission_factors_lookup` (synchronisé avec la migration T011).
- [ ] T013 Étendre `backend/app/models/carbon.py` (`CarbonEmissionEntry`) avec `source_id: Mapped[uuid.UUID]` (FK `sources.id`, NOT NULL après backfill) et `factor_id: Mapped[uuid.UUID]` (FK `emission_factors.id`, NOT NULL après backfill) ; conserver `source_description` Mapped[str | None] avec commentaire `# TODO(F17+1): drop after stabilisation` ; élargir `VALID_CATEGORIES` pour inclure `"purchases"`.
- [ ] T014 Étendre `backend/app/modules/carbon/schemas.py` (`EmissionEntryCreate`) avec `source_id: uuid.UUID` et `factor_id: uuid.UUID` obligatoires ; mettre à jour `EmissionEntryResponse` ; ajouter `EmissionFactorResolutionResponse` Pydantic pour exposer `is_approximate`, `fallback_reason`, `factor_used`.
- [ ] T015 Faire passer les tests T004 à T007 au vert ; mesurer la couverture (`pytest tests/unit/test_factor_service.py tests/unit/test_seed_factors.py tests/unit/test_reduction_plan_schema.py tests/migrations/test_alembic_f17.py --cov=app.modules.carbon --cov-report=term-missing`) et vérifier ≥ 80 %.
- [ ] T016 Vérifier la migration up/down/up : `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head` ; aucune perte de données ; aucune erreur Alembic.

**Checkpoint** : Foundation prête — les user stories peuvent maintenant être implémentées en parallèle.

---

## Phase 3 : User Story 1 — Mix électrique pays-spécifique pour le calcul carbone (Priority: P1) 🎯 MVP

**Goal** : Le facteur d'émission utilisé pour la consommation électrique d'une PME dépend de son pays (CI, SN, BF, ML, NE, BJ, TG, GW). Aujourd'hui une seule valeur (CI) est utilisée pour toutes les PME UEMOA — F17 corrige ce biais critique.

**Independent Test** : Créer 2 profils PME (un en CI, un en SN), saisir 1000 kWh dans chaque bilan, vérifier que les tCO2e calculés sont distincts (~0.456 t pour CI vs ~0.540 t pour SN), et que `<EmissionFactorBadge>` affiche bien la source pays-spécifique cliquable.

### Tests pour User Story 1 (TDD — écrire AVANT implémentation, vérifier qu'ils ÉCHOUENT)

- [ ] T017 [P] [US1] Écrire test unitaire `backend/tests/unit/test_carbon_tools_f17.py::TestSaveEmissionEntryWithCountry` : `save_emission_entry` (1) lit le `country` du profil entreprise via `get_profile`, (2) appelle `get_emission_factor(db, category, country, year)`, (3) stocke `source_id` + `factor_id` dans l'entrée, (4) retourne `factor_used`, `source_id`, `is_approximate`, `fallback_reason` dans le JSON.
- [ ] T018 [P] [US1] Écrire test d'intégration `backend/tests/integration/test_carbon_pipeline_f17.py::test_pipeline_ci_electricity_factor` : profil PME CI → save_emission_entry(category=energy, quantity=1000, unit=kWh, subcategory=electricity) → entry stocké avec factor.code=`electricity_ci_2024`, factor.value≈0.456, source.publisher in {ADEME, IEA}.
- [ ] T019 [P] [US1] Écrire test d'intégration `backend/tests/integration/test_carbon_pipeline_f17.py::test_pipeline_sn_electricity_different_from_ci` : profil PME SN → save_emission_entry idem → factor.code=`electricity_sn_2024`, factor.value ≠ valeur CI.
- [ ] T020 [P] [US1] Écrire test d'intégration `backend/tests/integration/test_carbon_pipeline_f17.py::test_pipeline_no_country_falls_back_to_global` : profil PME sans country → factor.country='global', is_approximate=True, fallback_reason='country_global'.
- [ ] T020bis [P] [US1] Écrire test paramétré `backend/tests/integration/test_carbon_pipeline_f17.py::test_pipeline_all_uemoa_countries_use_correct_factor` (couvre SC-004) : `@pytest.mark.parametrize("country_code", ["CI", "SN", "BF", "ML", "NE", "BJ", "TG", "GW"])` → pour chaque pays UEMOA, save_emission_entry(category='energy', subcategory='electricity', quantity=1000, unit='kWh') → factor.code commence par `electricity_<lowercase(country_code)>_` ; les 8 facteurs retournés ont des `factor.id` distincts.

### Implementation pour User Story 1

- [ ] T021 [US1] Refactorer `backend/app/graph/tools/carbon_tools.py::save_emission_entry` selon le contrat § 2 : (1) charger profil via `get_profile`, (2) extraire `country` (défaut None si absent), (3) appeler `get_emission_factor(db, category=mapped_category, country=country, year=assessment.year)`, (4) calculer `emissions_tco2e = quantity * factor.value / 1000`, (5) créer entry avec `source_id=factor.source_id`, `factor_id=factor.id`, `subcategory=factor.code`, `emission_factor=factor.value` ; (6) retourner JSON enrichi avec `factor_used`, `source_id`, `is_approximate`, `fallback_reason`.
- [ ] T022 [US1] Mettre à jour `backend/app/modules/carbon/service.py::add_entries` pour valider la présence de `source_id` + `factor_id` dans `entries_data` (validation Pydantic via `EmissionEntryCreate`) et lever une `ValueError` explicite si manquants.
- [ ] T023 [US1] Mettre à jour `backend/app/modules/carbon/emission_factors.py` : supprimer la constante Python `EMISSION_FACTORS` (déplacée vers seed BDD) et adapter `get_emission_factor(subcategory)` pour qu'elle devienne synchrone optionnelle (fallback de transition) ou être supprimée en faveur du nouveau service `factor_service.get_emission_factor` ; conserver les helpers `compute_emissions_tco2e`, `compute_equivalences`, `get_applicable_categories`, `EMISSION_CATEGORIES` (élargi avec entry `purchases`).
- [ ] T024 [US1] Faire passer les tests T017-T020 au vert ; mesurer la couverture sur `app/graph/tools/carbon_tools.py` et `app/modules/carbon/factor_service.py` ≥ 80 %.

**Checkpoint** : User Story 1 fonctionnelle — la PME CI obtient un facteur électricité distinct de la PME SN ; tests verts.

---

## Phase 4 : User Story 2 — Sourçage cliquable sur chaque facteur dans le chat et l'UI carbone (Priority: P1)

**Goal** : Chaque facteur d'émission affiché dans le chat ou sur `/carbon/results` est accompagné d'un picto Source cliquable (`<SourceLink>` F01) qui ouvre une modale avec publisher/page/date/URL. L'invariant projet n°1 (sourçage obligatoire) est respecté pour le module carbone.

**Independent Test** : Lancer une conversation où l'utilisateur déclare une consommation, observer dans le chat que chaque facteur a un picto Source cliquable, vérifier que la modale s'ouvre avec les bonnes données ADEME/IEA.

### Tests pour User Story 2 (TDD)

- [ ] T025 [P] [US2] Écrire test unitaire frontend `frontend/tests/unit/EmissionFactorBadge.spec.ts` : (1) rend le label et la valeur, (2) forward la prop source à `<SourceLink>`, (3) affiche picto warning quand `isApproximate=true`, (4) tooltip cohérent avec `fallbackReason` (« Facteur d'année antérieure » pour `year_older`, « Facteur générique régional » pour `country_global`), (5) classes dark mode présentes (`bg-white`, `dark:bg-dark-card`, `text-surface-text`, `dark:text-surface-dark-text`, `border-gray-200`, `dark:border-dark-border`), (6) attributs ARIA exacts : `role="region"`, `aria-label="Facteur d'émission : <factor.label>"` ; le picto warning a `role="img"` + `aria-label="Facteur approximatif"`.
- [ ] T026 [P] [US2] Écrire test unitaire `backend/tests/unit/test_carbon_tools_f17.py::TestSaveEmissionEntryReturnsSourceForCiteSource` : la réponse JSON de `save_emission_entry` inclut `source_id` UUID valide → permet au LLM d'appeler `cite_source(source_id)`.
- [ ] T027 [P] [US2] Écrire test golden_set/integration `backend/tests/integration/test_carbon_node_source_validator.py::test_carbon_response_passes_source_required_validator` : message LLM simulé contenant un chiffre carbone + `cite_source(source_id)` valide → validator `source_required` (F01) passe sans retry.

### Implementation pour User Story 2

- [ ] T028 [P] [US2] Créer composant `frontend/app/components/EmissionFactorBadge.vue` selon contrat § 4 : props `factor`, `source`, `isApproximate`, `fallbackReason` ; structure DOM décrite (inline-flex avec label + valeur + `<SourceLink>` + picto warning conditionnel) ; dark mode complet ; tooltip ARIA.
- [ ] T029 [US2] Mettre à jour `backend/app/prompts/carbon.py` : enrichir `CARBON_PROMPT` pour couvrir **FR-016 (1), (2) et (4)** : (1) instruire le LLM à utiliser `country` du `company_context`, (2) instruire à appeler `cite_source(source_id)` après chaque facteur affiché en texte, (4) demander confirmation utilisateur si `is_approximate=True` est retourné. Le sous-point (3) reconnaissance catégorie Achats est traité par T039 (US3).
- [ ] T030 [US2] Mettre à jour `frontend/app/pages/carbon/results.vue` pour intégrer `<EmissionFactorBadge>` sur chaque entrée détaillée (par catégorie et par sous-catégorie) avec récupération de `factor` + `source` depuis l'API `/api/carbon/assessments/{id}/summary` (étendre la réponse pour inclure source_id si pas déjà fait).
- [ ] T031 [US2] Étendre l'API `backend/app/modules/carbon/router.py` (endpoint `GET /api/carbon/assessments/{id}/summary`) pour inclure dans chaque entry du breakdown : `factor: {code, label, value, unit, country, year}`, `source: {id, publisher, title, url, page}` (jointure SQLAlchemy `selectinload` sur `emission_factor` et `source`).
- [ ] T032 [US2] Faire passer les tests T025-T027 au vert ; mesurer la couverture frontend (`cd frontend && npm run test -- --coverage --reporter=verbose`) ≥ 80 % sur `EmissionFactorBadge.vue` et backend ≥ 80 % sur les fichiers modifiés.

**Checkpoint** : User Stories 1 ET 2 fonctionnelles — chaque facteur affiché a une source cliquable.

---

## Phase 5 : User Story 3 — Catégorie Achats (matières premières) intégrée au bilan (Priority: P2)

**Goal** : L'utilisateur peut déclarer des achats de matières premières (ciment, acier, papier, alimentaire, plastique) et le calculateur applique les facteurs ADEME correspondants. La catégorie « Achats » apparaît dans la ventilation `/carbon/results`.

**Independent Test** : Démarrer un bilan, saisir « j'ai acheté 50 tonnes de ciment cette année », vérifier qu'une entrée `category=purchases`, `subcategory=purchases_cement_global_2024` est stockée avec `source_id`/`factor_id` non null, et que `/carbon/results` affiche la catégorie Achats dans la ventilation.

### Tests pour User Story 3 (TDD)

- [ ] T033 [P] [US3] Écrire test d'intégration `backend/tests/integration/test_carbon_pipeline_f17.py::test_pipeline_purchases_cement_recognized` : save_emission_entry(category='purchases', quantity=50, unit='t', subcategory='purchases_cement') → factor.code=`purchases_cement_global_2024`, emissions_tco2e ≈ 45 (50000kg × 0.9 / 1000), entry.category='purchases'.
- [ ] T034 [P] [US3] Écrire test unitaire `backend/tests/unit/test_carbon_tools_f17.py::TestSaveEmissionEntryFcfaConversion` : si l'utilisateur fournit un montant FCFA pour ciment via `simulation_factors`, le tool convertit en tonnes via le ratio sourcé puis applique le facteur (intégration `simulation_factors` F01).
- [ ] T035 [P] [US3] Écrire test d'intégration `backend/tests/integration/test_carbon_pipeline_f17.py::test_assessment_summary_includes_purchases_category` : un bilan avec entrées Achats → `get_assessment_summary` retourne `by_category` incluant clé `purchases` avec emissions/percentage/entries_count corrects.

### Implementation pour User Story 3

- [ ] T036 [US3] Étendre `backend/app/modules/carbon/emission_factors.py::EMISSION_CATEGORIES` pour inclure une entrée `purchases` (key='purchases', label='Achats', required=False, applicable_sectors=['manufacturing', 'construction', 'commerce', 'mining']) ; mettre à jour `get_applicable_categories` pour inclure 'purchases' selon le secteur de la PME. Ajouter un test unitaire `test_get_applicable_categories_purchases_for_industrial_sector` (manufacturing → inclut purchases) et `test_get_applicable_categories_purchases_optional_for_services` (services → n'inclut PAS purchases ; couvre US3 scénario 4).
- [ ] T037 [US3] Étendre `backend/app/graph/tools/carbon_tools.py::save_emission_entry` pour reconnaître la catégorie `purchases` et son routing vers le service `get_emission_factor(category='purchases_cement'|...)` (la catégorie utilisateur est `purchases`, la subcategory finale est `purchases_<material>_global_<year>`).
- [ ] T038 [US3] Implémenter dans `save_emission_entry` la conversion FCFA → tonnes pour les achats : si `unit='FCFA'`, interroger `simulation_factors` (table F01) pour `<material>_price_fcfa_per_tonne`, calculer `quantity_tonnes = montant_fcfa / price_fcfa_per_tonne`, appliquer le facteur d'émission, marquer dans le JSON résultat `converted_from_fcfa=True` + source du ratio de conversion.
- [ ] T039 [US3] Mettre à jour `backend/app/prompts/carbon.py` (`CARBON_PROMPT`) pour couvrir **FR-016 (3)** : ajouter une section « Achats » dans l'ordre de collecte : « 5. Achats (matières premières — ciment, acier, papier, alimentaire, plastique) » et instruire le LLM à demander volumes en tonnes ou montants FCFA, à utiliser `subcategory='purchases_<material>'` lors de l'appel à `save_emission_entry`.
- [ ] T040 [US3] Mettre à jour `frontend/app/pages/carbon/results.vue` pour ajouter le label « Achats » dans la ventilation par catégorie quand des entrées `purchases_*` existent (mapping `purchases` → « Achats »).
- [ ] T041 [US3] Faire passer les tests T033-T035 au vert ; couverture ≥ 80 % sur les fichiers modifiés.

**Checkpoint** : User Stories 1, 2 ET 3 fonctionnelles — la catégorie Achats est opérationnelle avec sourçage et UI.

---

## Phase 6 : User Story 4 — Plan de réduction sourcé (Priority: P3)

**Goal** : Le `reduction_plan` généré à la finalisation d'un bilan contient des actions avec `source_id` (UUID string) référençant ADEME guides / IEA roadmaps / BOAD policies, ou `unsourced=true` si pas de source. Affichage UI avec `<SourceLink>` cliquable sur chaque action.

**Independent Test** : Finaliser un bilan via le chat, observer le `reduction_plan` généré, vérifier que chaque action a soit `source_id` non null + `unsourced=false`, soit `source_id=null` + `unsourced=true`. Sur `/carbon/results`, chaque action a un `<SourceLink>` cliquable (sauf si unsourced).

### Tests pour User Story 4 (TDD)

- [ ] T042 [P] [US4] Écrire test unitaire `backend/tests/unit/test_reduction_plan_schema.py::test_reduction_plan_action_with_source_validates` : action `{title, description, estimated_reduction_tco2e, cost_estimate_fcfa, timeline, source_id="<uuid>", unsourced=false}` valide.
- [ ] T043 [P] [US4] Écrire test unitaire `backend/tests/unit/test_reduction_plan_schema.py::test_reduction_plan_action_unsourced_validates` : action `{..., source_id=null, unsourced=true}` valide.
- [ ] T044 [P] [US4] Écrire test unitaire `backend/tests/unit/test_reduction_plan_schema.py::test_reduction_plan_action_inconsistency_raises` : `{source_id=null, unsourced=false}` → ValidationError ; `{source_id="<uuid>", unsourced=true}` → ValidationError.
- [ ] T045 [P] [US4] Écrire test d'intégration `backend/tests/integration/test_carbon_pipeline_f17.py::test_finalize_assessment_reduction_plan_validates` : finalisation d'un bilan avec un `reduction_plan` mocké → service `complete_assessment` valide via `ReductionPlan.model_validate(reduction_plan)` ; rejette un plan invalide.

### Implementation pour User Story 4

- [ ] T046 [US4] Mettre à jour `backend/app/modules/carbon/service.py::complete_assessment` pour valider le `reduction_plan` reçu via `ReductionPlan.model_validate(reduction_plan)` (lèvre une `ValueError` si invalide) avant de l'attribuer à `assessment.reduction_plan`.
- [ ] T047 [US4] Mettre à jour `backend/app/prompts/carbon.py` pour instruire le LLM à générer un `reduction_plan` conforme au schéma Pydantic : champ `source_id` (UUID string, optionnel) et `unsourced` (bool) cohérents ; suggérer pour chaque action une source verified si possible (ADEME guides, IEA roadmaps, BOAD policies déjà seedées par F01).
- [ ] T048 [US4] Mettre à jour `frontend/app/pages/carbon/results.vue` (section plan de réduction) pour afficher pour chaque action : titre, description, estimation tCO2e, coût FCFA, timeline, et `<SourceLink>` si `source_id` non null sinon badge « recommandation générale ».
- [ ] T049 [US4] Faire passer les tests T042-T045 au vert ; couverture ≥ 80 % sur `backend/app/modules/carbon/reduction_plan_schema.py`.

**Checkpoint** : Toutes les user stories US1–US4 fonctionnelles.

---

## Phase 7 : Polish & Cross-Cutting Concerns

**Purpose** : Finalisation, tests E2E, validation quickstart, mise à jour documentation.

- [ ] T050 [P] Créer `frontend/tests/e2e/F17-carbone-mix-uemoa-source.spec.ts` (Playwright) avec backend mocké via `page.route()`, couvrant 4 scénarios :
  1. **CI électricité** : navigation vers chat, mock profil PME `country=CI`, mock POST `/api/chat/messages` simulant un échange où `save_emission_entry` est appelé pour 1000 kWh, mock GET `/api/carbon/assessments/{id}/summary` retournant entry avec factor `electricity_ci_2024` (value=0.456, source ADEME/IEA), navigation vers `/carbon/results`, assertion sur affichage `<EmissionFactorBadge>` avec valeur 0.456 et label CI.
  2. **SN électricité** : idem mais profil PME `country=SN`, mock retournant factor `electricity_sn_2024` distinct de CI (value différente).
  3. **Achats ciment** : mock `save_emission_entry(category='purchases', quantity=50, unit='t', subcategory='purchases_cement')` → entry avec factor `purchases_cement_global_2024` (~0.9 kgCO2e/kg, ~45 tCO2e total), assertion sur catégorie « Achats » apparaît dans la ventilation `/carbon/results`.
  4. **SourceLink cliquable** : assertion sur présence du `<SourceLink>` dans `<EmissionFactorBadge>`, simulation de clic → modale `<SourceModal>` ouverte avec publisher (ADEME ou IEA) + page + date + URL ; même test pour une action du plan de réduction sourcée.
- [ ] T051 [P] Mettre à jour `CLAUDE.md` (Active Technologies + Recent Changes) via `.specify/scripts/bash/update-agent-context.sh claude` (relance après finalisation) ou édition manuelle pour refléter F17.
- [ ] T052 [P] Vérifier l'absence de régression : exécuter la suite complète backend `cd backend && source venv/bin/activate && pytest tests/ -v --cov=app --cov-report=term-missing` ; vérifier que tous les anciens tests passent toujours (notamment carbon, esg_scoring, financing, application).
- [ ] T053 [P] Vérifier l'absence de régression frontend : `cd frontend && npm run test -- --coverage` ; vérifier la couverture globale ≥ 80 %.
- [ ] T054 Exécuter le quickstart complet `specs/024-carbone-mix-uemoa-source/quickstart.md` étapes 1 à 14 manuellement (ou via script automation) pour valider le flux end-to-end.
- [ ] T055 [P] Audit sécurité : vérifier qu'aucun secret n'est hardcodé (`grep -rE '(api_key|secret|password|token)\s*=\s*["\047][A-Za-z0-9]' backend/ frontend/` retourne 0 résultat) ; vérifier que l'endpoint `POST /api/admin/carbon/seed-factors` est bien protégé par `Depends(get_current_admin)`.
- [ ] T056 Préparer le commit final : `git add backend/ frontend/ specs/ CLAUDE.md` ; vérifier `git diff --staged` ; commit avec message conventional `feat(F17): mix UEMOA + facteurs sourcés ADEME/IPCC + catégorie Achats` (NE PAS exécuter en Phase A — commit final orchestré en Phase B).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)** : Aucune dépendance.
- **Phase 2 (Foundational)** : Dépend de Phase 1. **BLOQUE toutes les user stories**.
- **Phase 3 (US1 — P1)** : Dépend de Phase 2.
- **Phase 4 (US2 — P1)** : Dépend de Phase 2 ET partiellement de Phase 3 (le tool refactoré T021 doit retourner `source_id` pour permettre `cite_source`). En pratique, T028 (composant Vue) est indépendant et peut démarrer en parallèle de US1.
- **Phase 5 (US3 — P2)** : Dépend de Phase 2 ; peut démarrer en parallèle de US1/US2 (modifications cantonnées au tool + prompt + page).
- **Phase 6 (US4 — P3)** : Dépend de Phase 2 ; peut démarrer en parallèle de US1/US2/US3.
- **Phase 7 (Polish)** : Dépend de toutes les user stories désirées.

### User Story Dependencies

- **US1 (P1)** : MVP critique. Le tool `save_emission_entry` refactoré + service `get_emission_factor` constituent le cœur fonctionnel.
- **US2 (P1)** : Dépend partiellement de US1 (`source_id` retourné par le tool) mais le composant Vue `<EmissionFactorBadge>` et le prompt sont indépendants.
- **US3 (P2)** : Indépendant techniquement de US1/US2 (extension de catégories + élargissement du tool).
- **US4 (P3)** : Indépendant ; peut être livré à tout moment après Foundational.

### Within Each User Story

- Tests TDD écrits AVANT implémentation, vérifiés ROUGES avant de passer à l'implémentation, puis VERTS après.
- Models avant services (Foundational T012-T013 avant US1 T021).
- Services avant tools (T009 avant T021).
- Tools backend avant prompts (T021 avant T029).
- Backend avant frontend (T021 avant T030 pour US1+US2 combinés).
- Story complète avant de passer à la suivante (sauf parallélisme équipe).

### Parallel Opportunities

- **Phase 1** : T003 [P] indépendant de T001-T002.
- **Phase 2** : T004-T007 [P] (tests TDD) écrits en parallèle ; T012-T014 [P] (modèles + schémas) en parallèle après T011 (migration).
- **Phase 3 (US1)** : T017-T020 [P] (tests) en parallèle.
- **Phase 4 (US2)** : T025-T027 [P] (tests) en parallèle ; T028 [P] (composant Vue) indépendant.
- **Phase 5 (US3)** : T033-T035 [P] (tests) en parallèle.
- **Phase 6 (US4)** : T042-T045 [P] (tests) en parallèle.
- **Phase 7 (Polish)** : T050-T053, T055 [P] indépendants.

---

## Parallel Example : User Story 1

```bash
# Lancer les 4 tests TDD US1 en parallèle (différents fichiers/cas) :
Task: "Écrire backend/tests/unit/test_carbon_tools_f17.py::TestSaveEmissionEntryWithCountry"
Task: "Écrire backend/tests/integration/test_carbon_pipeline_f17.py::test_pipeline_ci_electricity_factor"
Task: "Écrire backend/tests/integration/test_carbon_pipeline_f17.py::test_pipeline_sn_electricity_different_from_ci"
Task: "Écrire backend/tests/integration/test_carbon_pipeline_f17.py::test_pipeline_no_country_falls_back_to_global"
```

## Parallel Example : Foundational Phase

```bash
# Tests TDD Foundational en parallèle :
Task: "Écrire test test_reduction_plan_schema.py"
Task: "Écrire test test_factor_service.py"
Task: "Écrire test test_seed_factors.py"
Task: "Écrire test test_alembic_f17.py"

# Puis modèles/schémas en parallèle après migration :
Task: "Étendre app/models/emission_factor.py avec colonne year"
Task: "Étendre app/models/carbon.py avec source_id + factor_id"
Task: "Étendre app/modules/carbon/schemas.py avec EmissionEntryCreate refactoré"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Compléter Phase 1 (Setup) : T001-T003.
2. Compléter Phase 2 (Foundational) : T004-T016 (CRITIQUE — bloque toutes les stories).
3. Compléter Phase 3 (US1) : T017-T024.
4. **STOP and VALIDATE** : tester US1 indépendamment via le chat (profil CI vs SN avec 1000 kWh).
5. Le MVP est livrable.

### Incremental Delivery

1. Setup + Foundational → fondations prêtes.
2. US1 → tester indépendamment → MVP.
3. US2 → ajouter le composant `<EmissionFactorBadge>` + intégration page → tester → livrer.
4. US3 → activer la catégorie Achats → tester → livrer.
5. US4 → enrichir le plan de réduction sourcé → tester → livrer.
6. Polish + E2E → finaliser.

### Parallel Team Strategy

Avec une équipe de 3 :
1. Compléter Setup + Foundational ensemble (T001-T016).
2. Une fois Foundational achevé :
   - Dev A : US1 (T017-T024) backend
   - Dev B : US2 (T025-T032) frontend + prompt + API summary
   - Dev C : US3 (T033-T041) catégorie Achats
3. US4 (T042-T049) repris par celui des 3 qui finit en premier.
4. Tous : Polish + E2E.

---

## Notes

- [P] tasks = fichiers différents, pas de dépendance.
- [Story] label = traçabilité user story.
- Cycle TDD obligatoire : tests d'abord (Red), implémentation minimale (Green), refactor (Improve), couverture ≥ 80 %.
- Commit recommandé après chaque task ou groupe logique (sauf en Phase A — commit unique « chore(F17): SpecKit artifacts »).
- Stop à chaque checkpoint pour valider l'incrémentation indépendamment.
- Avoid : tâches vagues, conflits sur même fichier, dépendances cross-story qui cassent l'indépendance.
- La migration Alembic est `024_carbone_mix_uemoa` (down_revision=`023_create_message_chunks`) — numérotation attribuée après collision résolue avec F03 (021)/F04 (022)/F12 (023) déjà mergés sur `main`.
