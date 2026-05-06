---
description: "Task list for feature 020-fondations-sourcage-catalogue (F01)"
---

# Tasks: Fondations Sourçage et Catalogue Source (F01)

**Input** : Design documents from `/specs/020-fondations-sourcage-catalogue/`
**Prerequisites** : plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests** : OBLIGATOIRES (constitution ESG Mefali principe IV Test-First NON-NEGOTIABLE, cible ≥ 80 % de couverture, principe TDD du `.cc-orchestrator.md`).

**Organization** : Tâches groupées par user story (US1..US7) pour permettre implémentation et tests indépendants. Le MVP est constitué des stories P1 (US1, US2, US3, US7).

## Format : `[ID] [P?] [Story] Description`

- **[P]** : peut s'exécuter en parallèle (fichiers différents, pas de dépendance bloquante).
- **[Story]** : story utilisateur concernée (US1..US7) — uniquement pour les phases User Story.
- Chemins absolus ou relatifs au repo root (`backend/` ou `frontend/`).

## Path Conventions

- **Backend** : `backend/app/…`, tests dans `backend/tests/…`.
- **Frontend** : `frontend/app/…`, tests dans `frontend/tests/…`.
- Migration Alembic : `backend/alembic/versions/`.
- Tests E2E Playwright : `frontend/tests/e2e/F01-fondations-sourcage-catalogue.spec.ts`.

---

## Phase 1 : Setup (infrastructure partagée)

**Purpose** : créer le squelette de fichiers et confirmer l'inventaire des dépendances. Aucune nouvelle dépendance Python/npm n'est introduite par F01 ; tout le nécessaire (FastAPI, SQLAlchemy async, Alembic, pgvector, LangGraph, Vue 3, Vitest, Playwright) est déjà installé.

- [ ] T001 Créer le dossier `backend/app/modules/sources/` avec `__init__.py` vide.
- [ ] T002 [P] Créer le dossier `backend/app/graph/validators/` avec `__init__.py` vide.
- [ ] T003 [P] Créer le dossier `frontend/app/components/sources/` (placeholders Vue à créer dans les phases User Story).
- [ ] T004 [P] Créer le dossier `frontend/app/pages/sources/` avec `index.vue` placeholder vide.
- [ ] T005 [P] Vérifier que `backend/requirements.txt` contient déjà `langchain-openai>=0.3.0` (pour les embeddings) ; sinon, ajouter (zone interdite — signaler `zone_conflict` à l'orchestrateur si modification nécessaire).
- [ ] T006 [P] Créer le fichier `backend/tests/llm_eval/__init__.py` vide pour les tests d'éval LLM.

**Checkpoint** : squelette de fichiers en place, dépendances confirmées.

---

## Phase 2 : Foundational (prérequis bloquants)

**Purpose** : modèle Source, migration Alembic, schémas Pydantic et services de base. Aucune story utilisateur ne peut démarrer avant cette phase.

⚠️ **CRITIQUE** : la migration Alembic 020 est dans la zone interdite `backend/alembic/versions/` ; coordination orchestrateur obligatoire (une seule migration en flight maximum). F02 (multitenant) crée potentiellement la migration 019 ou 021 en parallèle.

### Tests d'abord (TDD RED) ⚠️

- [ ] T010 [P] Créer `backend/tests/unit/test_source_model.py` avec tests unitaires : invariant `verified_by != captured_by` (contrainte CHECK), enum `verification_status` (draft/pending/verified/outdated), création basique, contrainte UNIQUE sur `url`.
- [ ] T011 [P] Créer `backend/tests/unit/test_source_schemas.py` avec tests Pydantic : validation `url` HttpUrl, longueurs `title`/`publisher`/`version`, `page` ≥ 1, `outdated_reason` requise pour status `outdated`, `verified_at` cohérent avec status.
- [ ] T012 [P] Créer `backend/tests/integration/test_alembic_020_migration.py` avec tests up/down/up : la migration crée 11 tables, le seed insère ≥ 30 sources verified, downgrade rollback complet.

### Modèles & migration (TDD GREEN)

- [ ] T013 Créer `backend/app/models/source.py` avec classe `Source` (SQLAlchemy async), Enum `VerificationStatus`, FK `captured_by` / `verified_by` / `created_by_user_id` vers `users.id`, marker `# TODO(F02): account_id`, marker `# TODO(F03): Auditable`, colonnes `embedding vector(1536)` via pgvector.
- [ ] T014 [P] Créer `backend/app/models/indicator.py` avec classes `Indicator`, `Criterion`, `Formula`, `Threshold` ; FK `source_id NOT NULL` ; champ `publication_status` ; markers F02/F03.
- [ ] T015 [P] Créer `backend/app/models/referential.py` avec classes `Referential` et `ReferentialIndicator` (jointure N-N avec `weight`, `threshold`, `source_id`) ; UNIQUE `(referential_id, indicator_id)` ; markers F02/F03.
- [ ] T016 [P] Créer `backend/app/models/emission_factor.py` avec classe `EmissionFactor` (`code`, `category`, `country`, `value`, `unit`, FK `source_id`, `publication_status`, markers F02/F03).
- [ ] T017 [P] Créer `backend/app/models/required_document.py` avec classe `RequiredDocument` (XOR `fund_id` / `intermediary_id`, FK `source_id`, markers F02/F03).
- [ ] T018 [P] Créer `backend/app/models/simulation_factor.py` avec classe `SimulationFactor` (`status` ∈ verified/pending, contrainte CHECK `status='verified' AND source_id NOT NULL` ou `status='pending' AND source_id NULL`, markers F02/F03).
- [ ] T019 [P] Créer `backend/app/models/unsourced_flag.py` avec classe `UnsourcedFlag` (journal `flag_unsourced`, FK `conversation_id`, `message_id` nullable).
- [ ] T020 Mettre à jour `backend/app/models/__init__.py` pour exposer les nouveaux modèles.
- [ ] T021 Créer `backend/alembic/versions/020_create_sources_catalog.py` (migration Alembic additive) : `op.create_table` pour les 11 tables avec toutes les contraintes (CHECK 4-yeux, CHECK source_required, FK ON DELETE RESTRICT/CASCADE/SET NULL), index (`verification_status`, `publisher`, `category`, `country`, full-text français, HNSW pgvector), trigger `enforce_published_requires_verified_sources` ; `op.add_column publication_status` sur `funds`, `intermediaries` (skip si table inexistante) ; fonction `data_upgrade()` appelant `seed_sources()` après création.
- [ ] T022 Vérifier la migration : `cd backend && source venv/bin/activate && alembic upgrade head && alembic downgrade -1 && alembic upgrade head`.

### Schémas Pydantic (TDD GREEN)

- [ ] T023 Créer `backend/app/schemas/source.py` avec : `Source` (réponse complète), `SourceCitation` (compact), `SourceCreate`, `SourceUpdate`, `SourceVerify` (vide), `SourceMarkOutdated`, `SourceListItem`, `PaginatedSources`. Validators Pydantic v2 conformes à `contracts/api-sources.md`.
- [ ] T024 Mettre à jour `backend/app/schemas/__init__.py` pour exposer les schémas.

### Service de base (TDD GREEN minimal)

- [ ] T025 Créer `backend/app/modules/sources/service.py::SourceService` avec stub `get_by_id(id)` minimal (sera étoffé en US3) pour permettre aux autres stories de démarrer.

**Checkpoint** : foundation prête. Les User Stories peuvent démarrer en parallèle.

---

## Phase 3 : User Story 3 — Workflow administrateur 4-yeux (Priorité : P1) 🎯 MVP

**Goal** : un administrateur peut saisir une nouvelle source ; un autre administrateur la valide ; le workflow 4-yeux est strictement appliqué (créateur ≠ validateur).

**Independent Test** : créer source par admin A, demander validation, tenter validation par A → 403, valider par admin B → status `verified`, lister sources → la nouvelle entrée apparaît.

### Tests d'abord (TDD RED) ⚠️

- [ ] T030 [P] [US3] Créer `backend/tests/unit/test_source_service.py` avec tests : `create_source` (set `captured_by=current_user`, status=`draft`), `request_verification` (transition draft→pending), `verify_source` (rejet si `current_user == captured_by` → exception `FourEyesViolation`), `verify_source` (succès si différent), `mark_outdated` (requiert `outdated_reason`), `update_source` (rejet si pas en `draft`), `delete_source` (interdit si référencé par catalogue).
- [ ] T031 [P] [US3] Créer `backend/tests/integration/test_sources_api.py` avec tests des 7 routes spécifiées dans `contracts/api-sources.md` : list_pme_filtered, list_admin_all, get_404_on_non_verified_for_pme, create_admin_only_403, create_url_unique_409, request_verification_200, verify_four_eyes_403, verify_success_other_admin_200, mark_outdated_requires_reason_422, patch_blocked_after_verification_403.
- [ ] T032 [P] [US3] Créer `backend/tests/unit/test_source_repository.py` avec tests bas-niveau (lookup par UUID, lookup par URL UNIQUE, filtrage par statut+publisher, pagination).

### Implémentation (TDD GREEN)

- [ ] T033 [US3] Étoffer `backend/app/modules/sources/service.py::SourceService` : implémenter `create_source`, `request_verification`, `verify_source` (avec invariant 4-yeux applicatif + propagation de la `IntegrityError` du CHECK constraint), `mark_outdated`, `update_source`, `delete_source`. Logger les transitions. Marker `# TODO(F03): Auditable` sur les méthodes mutantes.
- [ ] T034 [US3] Créer `backend/app/modules/sources/router.py` avec les 7 routes REST de `contracts/api-sources.md` (`GET /api/sources`, `GET /api/sources/{id}`, `POST /api/sources`, `POST /api/sources/{id}/request-verification`, `POST /api/sources/{id}/verify`, `POST /api/sources/{id}/mark-outdated`, `PATCH /api/sources/{id}`). Réutiliser `api/deps.py::get_current_user`, `require_admin`. Pour les PME, forcer `verification_status=verified` côté backend (FR-023).
- [ ] T035 [US3] Inclure le router dans `backend/app/api/__init__.py` (ne PAS modifier `backend/app/main.py` qui est en zone interdite — utiliser le pattern d'inclusion existant via `api/__init__.py`).
- [ ] T036 [US3] Créer `backend/app/modules/sources/__init__.py` exposant `service` et `router`.
- [ ] T037 [US3] Vérifier la couverture : `cd backend && pytest tests/unit/test_source_service.py tests/unit/test_source_repository.py tests/integration/test_sources_api.py --cov=app/modules/sources --cov-report=term-missing` → ≥ 80 %.

**Checkpoint** : US3 fonctionnelle. Un admin peut créer/valider une source via API REST.

---

## Phase 4 : User Story 7 — Migration des données existantes (Priorité : P1)

**Goal** : à la mise en production, les 30+ sources de référence sont seedées, les `EMISSION_FACTORS`, `ESGCriterion`, `SECTOR_WEIGHTS` et constantes simulateur sont migrés en table avec FK source pointant vers les sources seedées.

**Independent Test** : exécuter la migration ; vérifier en base que les emission_factors, indicators, referential_indicators et simulation_factors sont peuplés ; les éléments sans source officielle ont status `pending`.

### Tests d'abord (TDD RED) ⚠️

- [ ] T040 [P] [US7] Créer `backend/tests/integration/test_seed_sources.py` avec tests : ≥ 30 sources verified après seed, publishers couverts (ADEME, IPCC, IEA, UEMOA, BCEAO, GCF, IFC, BOAD, Gold Standard, Verra, ODD ONU), idempotence (ré-exécution n'insère pas de doublon), users système `system-curator` et `system-validator` créés (ou réutilisés s'ils existent).
- [ ] T041 [P] [US7] Créer `backend/tests/integration/test_seed_emission_factors.py` avec tests : tous les codes du dict `EMISSION_FACTORS` dans `app/modules/carbon/emission_factors.py` sont présents en table, `source_id` non null et pointe vers ADEME ou IEA, valeurs numériquement cohérentes.
- [ ] T042 [P] [US7] Créer `backend/tests/integration/test_seed_esg_indicators.py` avec tests : 30 indicators (10 E + 10 S + 10 G), codes `E1..E10`, `S1..S10`, `G1..G10`, `source_id` cohérent avec le pillar (UEMOA pour E par défaut, IFC pour S, ODD ONU pour G), `publication_status='draft'` initialement.
- [ ] T043 [P] [US7] Créer `backend/tests/integration/test_seed_sector_weights.py` avec tests : pour chaque secteur du dict `SECTOR_WEIGHTS`, un référentiel sectoriel créé + N referential_indicators avec poids non-unitaires.
- [ ] T044 [P] [US7] Créer `backend/tests/integration/test_seed_simulation_factors.py` avec tests : `_SAVINGS_RATE` et `_CARBON_IMPACT_PER_MXOF` migrés avec `status='pending'` et `source_id IS NULL`.

### Implémentation (TDD GREEN)

- [ ] T045 [US7] Créer `backend/app/modules/sources/seed.py::seed_sources()` qui crée les 30+ sources verified (ADEME Base Carbone v23, IPCC AR6 WG3, IEA Africa Energy Outlook 2024, Taxonomie verte UEMOA, Circulaire BCEAO 002-2024, GCF Investment Framework, IFC Performance Standards 2012, BOAD Politique Sectorielle ESS, Gold Standard, Verra VCS, ODD ONU 8/9/10/12/13/17, etc.). Crée préalablement les users système `system-curator@esg-mefali.local` (admin) et `system-validator@esg-mefali.local` (admin). `captured_by=curator`, `verified_by=validator` pour respecter l'invariant 4-yeux. Idempotent (ON CONFLICT DO NOTHING sur `url`).
- [ ] T046 [P] [US7] Créer `backend/app/modules/sources/migration_helpers.py::seed_emission_factors()` qui lit `EMISSION_FACTORS` dict et insère 1 ligne par code. Mapping `source_id` : ADEME pour énergie/transport/déchets, IEA pour électricité par pays, IPCC AR6 WG3 pour les facteurs sectoriels.
- [ ] T047 [P] [US7] Créer `seed_esg_indicators()` qui lit les 30 critères ESG du module `app/modules/esg/criteria.py` et insère 30 indicators avec mapping source_id selon pilier (Taxonomie verte UEMOA pour E, IFC Performance Standards pour S, ODD ONU pour G, sauf cas particuliers documentés inline).
- [ ] T048 [P] [US7] Créer `seed_sector_weights()` qui lit `SECTOR_WEIGHTS` et crée pour chaque secteur 1 référentiel + N referential_indicators. Les poids sont sourcés (BOAD Politique Sectorielle ESS pour les pondérations sectorielles UEMOA si disponibles, sinon `simulation_factors` adapté).
- [ ] T049 [P] [US7] Créer `seed_simulation_factors()` qui migre `_SAVINGS_RATE = 0.15` et `_CARBON_IMPACT_PER_MXOF = 1.7` vers la table `simulation_factors` avec `status='pending'`, `source_id=NULL`, et un commentaire explicite (« source officielle reste à fournir »).
- [ ] T050 [US7] Mettre à jour la migration `020_create_sources_catalog.py` pour appeler `seed_sources()` puis les helpers de migration `seed_emission_factors()`, `seed_esg_indicators()`, `seed_sector_weights()`, `seed_simulation_factors()` dans `data_upgrade()`.
- [ ] T051 [US7] Vérifier en localhost : `alembic upgrade head` puis `psql` queries de la quickstart.md étape 4-5 valident le seed.

**Checkpoint** : US7 fonctionnelle. La base contient 30+ sources, 30 indicators, ≥ 25 emission_factors, des referential_indicators sectoriels et 2 simulation_factors `pending`.

---

## Phase 5 : User Story 1 — UI : pictos Source cliquables et modal détail (Priorité : P1)

**Goal** : sur chaque chiffre/score/critère affiché, un picto `<SourceLink>` est rendu ; cliquer dessus ouvre une modal `SourceModal` qui affiche les métadonnées de la source et un lien vers le document officiel.

**Independent Test** : naviguer vers la page de résultats ESG d'une PME, voir un picto à côté du score global, cliquer dessus, observer la modal avec lien externe fonctionnel.

### Tests d'abord (TDD RED) ⚠️

- [ ] T060 [P] [US1] Créer `frontend/tests/unit/SourceLink.test.ts` (Vitest + happy-dom) : rend le picto, déclenche emit `click`, label aria descriptif, dark mode (classes `dark:` présentes), désactivé si `sourceId` invalide.
- [ ] T061 [P] [US1] Créer `frontend/tests/unit/SourceModal.test.ts` : rend les métadonnées (titre, publisher, version, date, page, section, statut), bouton « Ouvrir le document officiel » avec `target="_blank"` `rel="noopener noreferrer"`, focus piégé (Tab cyclique), Esc ferme la modal, dark mode complet.
- [ ] T062 [P] [US1] Créer `frontend/tests/unit/SourceBadge.test.ts` : 3 statuts (verified/pending/outdated) avec couleurs distinctes, raison affichée pour outdated, dark mode.
- [ ] T063 [P] [US1] Créer `frontend/tests/unit/useSources.test.ts` : `fetchSource(id)` cache hit/miss, `searchSources(query)` retourne items, invalidation TTL 5 min.

### Implémentation (TDD GREEN)

- [ ] T064 [P] [US1] Créer `frontend/app/types/source.ts` avec types TypeScript : `Source`, `SourceCitation`, `SourceListItem`, `VerificationStatus = 'draft'|'pending'|'verified'|'outdated'`. Strict mode.
- [ ] T065 [P] [US1] Créer `frontend/app/stores/sources.ts` (Pinia) avec map `sources: Record<string, Source>`, méthodes `getById(id)`, `setSource(s)`, `invalidate(id)`, TTL 5 min via timestamp `_fetchedAt`.
- [ ] T066 [P] [US1] Créer `frontend/app/composables/useSources.ts` exposant `fetchSource(id: string): Promise<Source>`, `searchSources(query: string, opts?: { publisher?: string }): Promise<SourceListItem[]>`, `cacheSource(s: Source): void`. Utilise `$fetch` Nuxt + store `sources.ts`.
- [ ] T067 [P] [US1] Créer `frontend/app/components/sources/SourceLink.vue` : prop `sourceId: string`, bouton `<button>` avec icône `i-heroicons-link`, `aria-label="Voir la source de cette donnée"`, emit `open` au clic. Dark mode complet (`text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400`).
- [ ] T068 [P] [US1] Créer `frontend/app/components/sources/SourceBadge.vue` : prop `status: VerificationStatus`, prop `reason?: string` ; rendu pastille colorée (vert/orange/rouge) avec libellé FR ; dark mode.
- [ ] T069 [P] [US1] Créer `frontend/app/components/sources/SourceModal.vue` : prop `sourceId: string`, charge la source via `useSources().fetchSource(id)`, rend titre/publisher/version/date_publi/page/section/captured_at/verified_by/badge statut + bouton « Ouvrir le document officiel » (`<a target="_blank" rel="noopener noreferrer">`). Réutilise `useFocusTrap.ts` existant (composable feature 018). `role="dialog"`, `aria-modal="true"`. Dark mode complet.
- [ ] T070 [US1] Intégrer `<SourceLink :sourceId="..." />` dans `frontend/app/components/dashboard/ScoreCard.vue` à côté du score affiché.
- [ ] T071 [P] [US1] Intégrer `<SourceLink>` dans `frontend/app/components/esg/Recommendations.vue` à côté de chaque recommandation chiffrée.
- [ ] T072 [P] [US1] Intégrer `<SourceLink>` dans `frontend/app/components/esg/StrengthsBadges.vue` (chaque badge force chiffrée).
- [ ] T073 [P] [US1] Intégrer `<SourceLink>` dans `frontend/app/components/esg/CriteriaProgress.vue` à côté de chaque critère.
- [ ] T074 [P] [US1] Intégrer `<SourceLink>` dans `frontend/app/components/credit/FactorsRadar.vue` (chaque axe chiffré).
- [ ] T075 [P] [US1] Intégrer `<SourceLink>` dans `frontend/app/components/credit/Recommendations.vue` (chaque recommandation chiffrée).
- [ ] T076 [P] [US1] Intégrer `<SourceLink>` dans `frontend/app/components/dashboard/FinancingCard.vue` (montants, frais, délais).
- [ ] T077 [P] [US1] Intégrer `<SourceLink>` dans `frontend/app/pages/carbon/results.vue` à côté de chaque facteur d'émission affiché.
- [ ] T078 [P] [US1] Intégrer `<SourceLink>` dans `frontend/app/pages/financing/[id].vue` (critères du fonds, montants).
- [ ] T079 [P] [US1] Intégrer `<SourceLink>` dans `frontend/app/pages/applications/[id].vue` (montants, frais, délais).
- [ ] T080 [US1] Vérifier la couverture frontend : `cd frontend && npm run test -- --coverage` → ≥ 80 % sur `components/sources/`.

**Checkpoint** : US1 fonctionnelle. Tous les chiffres affichés ont un picto cliquable et la modal détail apparaît au clic.

---

## Phase 6 : User Story 2 — Tools LangChain et validator backend (Priorité : P1)

**Goal** : l'agent IA dispose des actions `cite_source`, `search_source`, `flag_unsourced` ; le validator backend rejette toute réponse contenant un chiffre sans citation et substitue un libellé de repli après échec du retry.

**Independent Test** : envoyer dans le chat une question requérant un chiffre ; vérifier que `cite_source` est invoqué (`tool_call_logs`) ; mocker une réponse sans citation ; vérifier substitution par fallback.

### Tests d'abord (TDD RED) ⚠️

- [ ] T090 [P] [US2] Créer `backend/tests/unit/test_sourcing_tools.py` avec les classes `TestCiteSource`, `TestSearchSource`, `TestFlagUnsourced` couvrant les 16 cas listés dans `contracts/tools-sourcing.md` (lookup verified happy path, lookup pending error, lookup outdated error, unknown UUID, invalid UUID, FTS+publisher filter, exclusion non-verified, limit hard cap 5, query trop courte, claim too short, journal `unsourced_flags`).
- [ ] T091 [P] [US2] Créer `backend/tests/unit/test_source_required_validator.py` avec les 10 cas listés dans `contracts/validator-source-required.md` (no claim, paragraph cite_source, missing citation, flag_unsourced cover, ISO ignored, grouped paragraph, multi-paragraph requires multi-cite, retry fallback, error citation rejected, French decimal).
- [ ] T092 [P] [US2] Créer `backend/tests/integration/test_sourcing_tools_in_graph.py` avec tests bout-en-bout simulés (les 4 cas de `contracts/tools-sourcing.md`).
- [ ] T093 [P] [US2] Créer `backend/tests/integration/test_source_required_in_chat.py` avec tests bout-en-bout simulés (3 cas validator dans le pipeline chat).
- [ ] T094 [P] [US2] Créer `backend/tests/llm_eval/test_cite_source_golden_set.py` avec les 10 questions du golden set (FR-018, SC-003). Marqueur pytest `@pytest.mark.llm_eval` (skipped par défaut sauf si `RUN_LLM_EVAL=true`).
- [ ] T095 [P] [US2] Créer `backend/tests/llm_eval/golden_set_50.json` (50 réponses LLM annotées avec ground truth « citation présente » ou « non sourçable »). Le validator doit atteindre ≤ 5 % d'erreur sur ce set (FR-018).

### Implémentation (TDD GREEN)

- [ ] T096 [US2] Créer `backend/app/graph/tools/sourcing_tools.py` avec les 3 tools LangChain `@tool` décorés conformément à `contracts/tools-sourcing.md`. Chaque tool écrit dans `tool_call_logs` (table existante feature 012). `flag_unsourced` insère également dans `unsourced_flags`. Aucune mutation du catalogue.
- [ ] T097 [P] [US2] Créer `backend/app/prompts/sourcing.py::SOURCING_INSTRUCTION` (texte FR injecté dans les 7 prompts modules) qui explique à l'agent les règles : « tu dois invoquer `cite_source(source_id)` chaque fois que tu mentionnes un chiffre vérifiable, ou `flag_unsourced(claim, reason)` si aucune source n'est disponible ; le backend rejettera ta réponse sinon ».
- [ ] T098 [P] [US2] Créer `backend/app/graph/validators/source_required.py` avec `validate_response(final_text, tool_calls, db, retry_count) → ValidationResult`. Regex compilée `NUMERIC_CLAIM_RE`, liste `IGNORED_NUMERIC_PATTERNS`, fonctions `_strip_ignored`, `_detect_claims`, `_extract_cite_source_calls`, `_extract_flag_unsourced_calls`, `_check_coverage`, `_substitute_with_fallback` conformément à `contracts/validator-source-required.md`.
- [ ] T099 [US2] Étendre les imports de tools dans `backend/app/graph/nodes.py::chat_node` pour inclure `cite_source`, `search_source`, `flag_unsourced` ; injecter `SOURCING_INSTRUCTION` dans le prompt système du chat (post-onboarding).
- [ ] T100 [P] [US2] Étendre `backend/app/graph/nodes.py::esg_scoring_node` pour inclure les 3 tools + injection de `SOURCING_INSTRUCTION`.
- [ ] T101 [P] [US2] Étendre `backend/app/graph/nodes.py::carbon_node` pour inclure les 3 tools + injection.
- [ ] T102 [P] [US2] Étendre `backend/app/graph/nodes.py::financing_node` pour inclure les 3 tools + injection.
- [ ] T103 [P] [US2] Étendre `backend/app/graph/nodes.py::application_node` pour inclure les 3 tools + injection.
- [ ] T104 [P] [US2] Étendre `backend/app/graph/nodes.py::credit_node` pour inclure les 3 tools + injection.
- [ ] T105 [P] [US2] Étendre `backend/app/graph/nodes.py::action_plan_node` pour inclure les 3 tools + injection.
- [ ] T106 [US2] Étendre `backend/app/api/chat.py::stream_graph_events` (zone autorisée) pour invoquer `source_required.validate_response()` après collecte de la réponse + tool_calls. Implémenter la boucle retry max 1 et la substitution par fallback. Émettre les events SSE `text_replace` et `incident_logged` au besoin.
- [ ] T107 [US2] Vérifier l'invariant : aucun tool de mutation du catalogue n'est exposé à l'agent (relecture de `sourcing_tools.py`).
- [ ] T108 [US2] Vérifier la couverture : `pytest tests/unit/test_sourcing_tools.py tests/unit/test_source_required_validator.py tests/integration/test_sourcing_tools_in_graph.py tests/integration/test_source_required_in_chat.py --cov=app/graph/tools/sourcing_tools --cov=app/graph/validators/source_required --cov-report=term-missing` → ≥ 80 %.
- [ ] T109 [US2] Exécuter `RUN_LLM_EVAL=true pytest backend/tests/llm_eval/test_cite_source_golden_set.py -v` (10 cas) ; cible ≥ 9 / 10 conformes (SC-003).

**Checkpoint** : US2 fonctionnelle. L'agent cite ses sources et le validator rejette les chiffres sans citation.

---

## Phase 7 : User Story 4 — Annexe « Sources et références » dans rapports PDF (Priorité : P2)

**Goal** : tout rapport PDF généré contient en fin de document une section auto-générée listant les sources mobilisées avec [n], titre, publisher, version, date, page, section, statut, URL ; renvois inline cohérents.

**Independent Test** : générer un rapport ESG d'une PME ayant 5+ chiffres sourcés ; ouvrir le PDF ; vérifier la section finale + 5 entrées numérotées.

### Tests d'abord (TDD RED) ⚠️

- [ ] T120 [P] [US4] Créer `backend/tests/integration/test_pdf_sources_appendix.py` avec tests : (a) génère un rapport mocké avec 5 cite_source dans tool_call_logs, vérifie que le PDF contient les 5 entrées numérotées et que les chiffres du corps portent un renvoi `[n]` ; (b) génère un rapport sans aucune cite_source, vérifie que la section apparaît avec libellé « Aucune source mobilisée » (FR-028).

### Implémentation (TDD GREEN)

- [ ] T121 [US4] Étendre `backend/app/modules/reports/service.py::generate_esg_report()` pour collecter les `cite_source` invoqués pendant la génération (lookup table `tool_call_logs` filtrée par `conversation_id` et `tool_name='cite_source'` depuis `report.generation_started_at`). Construire la liste `mobilized_sources: list[Source]` injectée dans le contexte Jinja2.
- [ ] T122 [P] [US4] Modifier `backend/app/modules/reports/templates/esg_report.html` pour ajouter une section finale `{% if mobilized_sources %}` listant les sources avec [n], titre, publisher, version, date, page, section, badge statut, URL ; sinon afficher « Aucune source mobilisée pour ce rapport ».
- [ ] T123 [P] [US4] Étendre le rendu : remplacer dans le corps du rapport les chiffres par `chiffre [n]` (post-traitement HTML avant WeasyPrint, ou directement dans le template via filtre Jinja personnalisé `with_source_ref(source_id)`).
- [ ] T124 [US4] Vérifier visuellement avec un rapport de test : le PDF contient bien la section finale et au moins un renvoi inline cohérent.

**Checkpoint** : US4 fonctionnelle.

---

## Phase 8 : User Story 5 — Page `/sources` catalogue public (Priorité : P2)

**Goal** : l'utilisateur PME ouvre la page `/sources` et voit le catalogue des sources `verified` filtrable par publisher avec recherche full-text.

**Independent Test** : ouvrir `http://localhost:3000/sources`, taper « ADEME » dans la recherche, voir la liste filtrée, cliquer sur une entrée → modal détail.

### Tests d'abord (TDD RED) ⚠️

- [ ] T130 [P] [US5] Créer `frontend/tests/unit/SourcesList.test.ts` : rend N items, gère état vide « Aucune source disponible », état chargement, dark mode.
- [ ] T131 [P] [US5] Créer `frontend/tests/unit/sources-page.test.ts` (test composant page) : recherche déclenche `searchSources()`, filtre publisher fonctionne, pagination, click sur item ouvre modal.

### Implémentation (TDD GREEN)

- [ ] T132 [P] [US5] Créer `frontend/app/components/sources/SourcesList.vue` : props `sources: SourceListItem[]`, `loading: boolean`, emit `select(id)` au clic ; rendu carte par item avec titre, publisher, version, date, badge statut. Dark mode complet.
- [ ] T133 [US5] Créer `frontend/app/pages/sources/index.vue` : page complète avec barre de recherche (debounce 300 ms), select publisher (options `ADEME`, `IPCC`, `IEA`, `UEMOA`, `BCEAO`, `GCF`, `IFC`, `BOAD`, `Gold Standard`, `Verra`, `ODD ONU`, `Tous`), pagination 20/page, integration `<SourcesList>` + `<SourceModal>`. Utilise `useSources()`. Dark mode + responsive.
- [ ] T134 [US5] Étendre `useSources.ts::searchSources()` pour appeler `GET /api/sources?search=<query>&publisher=<publisher>&page=<page>` (route déjà créée en Phase 3 / US3).

**Checkpoint** : US5 fonctionnelle.

---

## Phase 9 : User Story 6 — Recherche full-text + pgvector pour l'agent IA (Priorité : P2)

**Goal** : l'agent IA peut invoquer `search_source(query, publisher, limit=5)` qui retourne les top-k sources vérifiées les plus pertinentes via combinaison full-text PostgreSQL + cosine similarity pgvector.

**Independent Test** : envoyer une requête `search_source(query="émission électricité Afrique de l'Ouest")` ; vérifier ≤ 5 résultats triés par rrf, tous `verified`.

### Tests d'abord (TDD RED) ⚠️

- [ ] T140 [P] [US6] Créer `backend/tests/integration/test_search_source_hybrid.py` avec tests : full-text français match `ADEME`, embedding match « facteur d'émission » sémantique, rrf combine les deux, filtre publisher, exclusion non-verified, limit hard 5.

### Implémentation (TDD GREEN)

- [ ] T141 [US6] Implémenter `backend/app/modules/sources/service.py::search_sources(query, publisher, limit)` avec requête SQL hybride (cf. `contracts/tools-sourcing.md` étape 3) : `to_tsvector('french', ...) @@ plainto_tsquery('french', :query)` + cosine similarity sur embedding HNSW.
- [ ] T142 [P] [US6] Implémenter calcul d'embedding `_compute_embedding(text)` via `langchain-openai` `OpenAIEmbeddings(model="text-embedding-3-small")`. Cache LRU en mémoire pour les requêtes fréquentes.
- [ ] T143 [P] [US6] Étendre `backend/app/modules/sources/service.py::create_source()` pour calculer et stocker l'embedding lors de la création.
- [ ] T144 [P] [US6] Étendre `seed_sources()` (Phase 4 US7) pour calculer les embeddings des 30+ sources seedées (ou mark TODO si OpenAI key absente en seed initial).
- [ ] T145 [US6] Vérifier la couverture : `pytest tests/integration/test_search_source_hybrid.py --cov=app/modules/sources/service --cov-report=term-missing` ≥ 80 %.

**Checkpoint** : US6 fonctionnelle. L'agent IA trouve une source pertinente même sans connaître son UUID.

---

## Phase 10 : Polish & cross-cutting concerns

**Purpose** : tests E2E, accessibilité, perf, documentation, et vérification globale des invariants.

### Tests E2E Playwright (OBLIGATOIRES — orchestrateur invariant #11)

- [ ] T150 Créer `frontend/tests/e2e/F01-fondations-sourcage-catalogue.spec.ts` avec 3 parcours :
   - **Parcours 1 (US5)** : un utilisateur PME ouvre `/sources`, recherche « ADEME », filtre publisher « ADEME », clique sur une entrée, vérifie modal détail + lien externe ouvert dans nouvel onglet (`page.context().expect(...)` sur le nouveau context).
   - **Parcours 2 (US1)** : un fund officer simulé navigue vers `/esg`, vérifie le picto à côté du score global, clique dessus, vérifie modal avec statut « vérifiée », et que le bouton « Ouvrir le document officiel » a `target="_blank"`.
   - **Parcours 3 (US2)** : test API mockée — envoie une requête au chat avec une réponse LLM stubbée contenant « 0,41 kgCO2e/kWh » sans `cite_source` ; vérifie que la réponse SSE finale contient le fallback « [je ne dispose pas d'une source vérifiée pour ce chiffre] » et qu'un incident est journalisé.
- [ ] T151 Lancer les E2E : `cd frontend && npx playwright test tests/e2e/F01-fondations-sourcage-catalogue.spec.ts --reporter=html`. Cible : 3/3 parcours green.

### Documentation et invariants

- [ ] T152 [P] Mettre à jour `CLAUDE.md` racine pour ajouter F01 dans la section « Recent Changes » (déjà fait par `update-agent-context.sh`, vérifier la cohérence).
- [ ] T153 [P] Vérifier que toutes les nouvelles tables ont les markers `# TODO(F02): account_id` (invariant #2) sur les modèles SQLAlchemy.
- [ ] T154 [P] Vérifier qu'aucun secret n'est hardcodé dans le seed : `grep -rE '(api_key|secret|password|token)\s*=\s*["\047][A-Za-z0-9]' backend/app/modules/sources/`.
- [ ] T155 [P] Vérifier l'invariant #7 : aucun tool muteur dans `sourcing_tools.py` (`grep -E 'INSERT INTO sources|UPDATE sources|DELETE FROM sources' backend/app/graph/tools/sourcing_tools.py` doit retourner 0 résultat).

### Performance et accessibilité

- [ ] T156 [P] Vérifier le temps de chargement de la modal `<SourceModal>` ≤ 1 s p95 (SC-009) via test Playwright avec `page.evaluate(performance.now())`.
- [ ] T157 [P] Vérifier le temps de chargement de la page `/sources` filtrée par publisher ≤ 2 s (SC-011) via Lighthouse ou Playwright timing.
- [ ] T158 [P] Vérifier l'accessibilité : navigation clavier (Tab cyclique dans la modal, Esc ferme), labels ARIA présents (`role="dialog"`, `aria-modal="true"`, `aria-label`), focus visible.
- [ ] T159 [P] Vérifier le mode sombre sur tous les composants (`SourceLink`, `SourceModal`, `SourceBadge`, `SourcesList`, page `/sources`).

### Vérification finale

- [ ] T160 Couverture globale backend : `cd backend && pytest tests/ --cov=app --cov-report=term-missing` ≥ 80 % global, et ≥ 80 % spécifique sur `app/modules/sources/`, `app/graph/tools/sourcing_tools.py`, `app/graph/validators/source_required.py`.
- [ ] T161 Couverture globale frontend : `cd frontend && npm run test -- --coverage` ≥ 80 % sur `components/sources/`, `composables/useSources.ts`, `stores/sources.ts`.
- [ ] T162 Validation alembic : `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` (la migration 020 doit être idempotente).
- [ ] T163 Quickstart end-to-end : exécuter manuellement les 15 étapes de `quickstart.md` (ou via script CI dédié).
- [ ] T164 Aucun `TODO` non documenté hors `# TODO(F02)`, `# TODO(F03)`, `# TODO(F04)`, `# TODO(F05)`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** : pas de dépendance. Démarrage immédiat.
- **Foundational (Phase 2)** : dépend de Setup. **BLOQUE toutes les User Stories**.
- **Phase 3 (US3)** : dépend de Foundational.
- **Phase 4 (US7)** : dépend de Foundational + de US3 (le seed crée des sources via le service).
- **Phase 5 (US1)** : dépend de Foundational. Peut s'exécuter en parallèle avec US3, US7 (différents fichiers).
- **Phase 6 (US2)** : dépend de Foundational + des sources seedées (US7) pour les tests d'intégration.
- **Phase 7 (US4)** : dépend de US2 (collecte des cite_source via tool_call_logs).
- **Phase 8 (US5)** : dépend de Foundational + US3 (route GET /api/sources).
- **Phase 9 (US6)** : dépend de Foundational + US7 (sources seedées avec embeddings).
- **Polish (Phase 10)** : dépend de toutes les User Stories.

### User Story Dependencies

- **US3 (P1)** : démarre après Phase 2. Aucune dépendance sur autres stories.
- **US7 (P1)** : démarre après US3 (utilise `SourceService.create_source()` indirectement via le seed).
- **US1 (P1)** : démarre après Phase 2. Indépendant des autres stories (UI seulement, mock API si besoin).
- **US2 (P1)** : démarre après US7 (sources seedées requises pour `cite_source` réels).
- **US4 (P2)** : dépend de US2 (les `cite_source` doivent être loggés).
- **US5 (P2)** : dépend de US3 (route API REST).
- **US6 (P2)** : dépend de US7 (embeddings calculés au seed).

### Within Each User Story

- Tests écrits AVANT l'implémentation (TDD strict).
- Modèles AVANT services AVANT routes AVANT intégration.
- Couverture vérifiée à la fin de chaque phase.

### Parallel Opportunities

- Toutes les tâches Setup [P] (T002, T003, T004, T005, T006).
- Foundational : tous les modèles split (T014-T019) en parallèle ; les tests (T010-T012) en parallèle.
- US3 : les 3 tests (T030, T031, T032) en parallèle.
- US7 : les 5 tests (T040-T044) en parallèle ; les 4 helpers (T046-T049) en parallèle.
- US1 : tous les tests Vitest (T060-T063) en parallèle ; les composants atomiques (T064-T069) en parallèle ; les intégrations sur 10 emplacements (T070-T079) en parallèle.
- US2 : tests (T090-T095) en parallèle ; les 6 nœuds non-chat (T100-T105) en parallèle.
- US4, US5, US6, US7 sont totalement parallélisables entre elles une fois Phase 2 terminée.

---

## Parallel Example: User Story 1 (UI pictos source)

```bash
# Lancer en parallèle les 4 tests Vitest :
Task: "Créer frontend/tests/unit/SourceLink.test.ts"
Task: "Créer frontend/tests/unit/SourceModal.test.ts"
Task: "Créer frontend/tests/unit/SourceBadge.test.ts"
Task: "Créer frontend/tests/unit/useSources.test.ts"

# Puis lancer en parallèle les composants atomiques :
Task: "Créer frontend/app/components/sources/SourceLink.vue"
Task: "Créer frontend/app/components/sources/SourceBadge.vue"
Task: "Créer frontend/app/components/sources/SourceModal.vue"

# Enfin, intégrations en parallèle (10 fichiers différents) :
Task: "Intégrer <SourceLink> dans frontend/app/components/dashboard/ScoreCard.vue"
Task: "Intégrer <SourceLink> dans frontend/app/components/esg/Recommendations.vue"
# ... 8 autres intégrations
```

---

## Implementation Strategy

### MVP First (User Stories P1 only)

1. Phase 1 (Setup) — ~30 min.
2. Phase 2 (Foundational) — modèles + migration + tests modèle, ~3 h.
3. Phase 3 (US3 — workflow admin) — ~3 h.
4. Phase 4 (US7 — seed et migration de données) — ~4 h.
5. Phase 5 (US1 — UI pictos source) — ~5 h (10 intégrations + composants atomiques).
6. Phase 6 (US2 — tools + validator) — ~6 h (validator + 7 nœuds + golden set).
7. **STOP & VALIDATE** : exécuter les tests E2E Playwright (T150-T151) — MVP livrable.

### Incremental Delivery

- **MVP (P1 stories)** : US1 + US2 + US3 + US7 → catalogue + UI cliquable + agent qui cite + validator strict + sources seedées.
- **Incrément 1 (US4 — annexe PDF)** : la trace écrite arrive dans les rapports.
- **Incrément 2 (US5 — page /sources)** : le catalogue devient explorable côté PME.
- **Incrément 3 (US6 — search hybrid)** : l'agent trouve des sources sans en connaître l'UUID.
- **Polish (Phase 10)** : E2E final, couverture globale, accessibilité, performance.

### Parallel Team Strategy

Avec ≥ 3 développeurs après Phase 2 :
- Dev A : Phase 3 (US3 — backend admin) puis Phase 6 (US2 — tools + validator).
- Dev B : Phase 4 (US7 — seed) puis Phase 9 (US6 — search).
- Dev C : Phase 5 (US1 — UI) puis Phase 8 (US5 — page) puis Phase 7 (US4 — annexe PDF).
- Tous : Phase 10 (E2E + polish) en collaboration.

---

## Notes

- [P] tasks = fichiers différents, pas de dépendance.
- [Story] label maps task to user story for traceability.
- Chaque user story est complétable et testable indépendamment.
- Tests vérifiés failing AVANT implémentation (TDD RED → GREEN).
- Commit après chaque tâche ou groupe logique cohérent.
- Stop à chaque checkpoint pour valider la story indépendamment.
- Éviter : tâches vagues, conflits de fichiers, dépendances cross-story brisant l'indépendance.
- Migration Alembic 020 est zone interdite : sérialisation orchestrateur OBLIGATOIRE avec F02 (multitenant).
- Aucun secret hardcodé : URLs OpenRouter, API keys via `backend/app/core/config.py` (zone interdite, ne pas modifier en F01).
- Mode sombre obligatoire sur tous les composants Vue introduits (constitution ESG Mefali).
- UI 100 % FR avec accents corrects ; code anglais ; commentaires FR.
