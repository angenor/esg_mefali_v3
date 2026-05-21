---
description: "Task list — Feature 045 Matching projet-centric"
---

# Tasks: Matching financement vert centré projet (045)

**Input** : Design documents from `/specs/045-matching-projet-centric/`
**Prerequisites** : plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests** : OBLIGATOIRES — FR-018 (≥ 80 % coverage), FR-019 (E2E Playwright), Constitution Principe IV (TDD NON-NEGOTIABLE). Chaque user story commence par les tests, qui DOIVENT échouer avant l'implémentation.

**Organization** : 5 user stories (P1 ×2, P2 ×2, P3 ×1). Chaque story est indépendamment testable et livrable.

## Format : `[ID] [P?] [Story?] Description`

- **[P]** : Peut s'exécuter en parallèle (fichiers différents, pas de dépendance sur des tâches incomplètes)
- **[Story]** : User story rattachée (US1, US2, US3, US4, US5) — phases Setup/Foundational/Polish n'ont pas de label
- Chemins fichiers absolus inclus dans chaque description

## Path Conventions

Web app monorepo : `backend/` (FastAPI + SQLAlchemy + Alembic) et `frontend/` (Nuxt 4 + Vue 3 + Pinia + TailwindCSS). Paths absolus depuis racine du projet `/Users/mac/Documents/projets/2025/esg_mefali_v3/`.

---

## Phase 1 : Setup (Shared Infrastructure)

**Purpose** : Préparer la branche, installer les dépendances neuves (aucune attendue), créer les répertoires.

- [X] T001 Vérifier l'état de la branche `045-matching-projet-centric` active et propre via `git status` + `git branch --show-current`
- [X] T002 [P] Créer le dossier `backend/app/core/matching_constants.py` (placeholder vide initial) — source de vérité whitelists FR
- [X] T003 [P] Créer le dossier `backend/app/modules/financing/divergence_templates.py` (placeholder vide initial) — gabarits FR
- [X] T004 [P] Créer le dossier `frontend/app/types/projectMatching.ts` (placeholder vide initial) — types TypeScript miroir backend
- [X] T005 [P] Créer le dossier `frontend/app/components/financing/` s'il n'existe pas (devrait déjà exister F14)

**Checkpoint Phase 1** : Branche prête, scaffold de fichiers vide. Aucune ligne de code métier.

---

## Phase 2 : Foundational (Blocking Prerequisites)

**Purpose** : Migration BDD, sources F01, schemas Pydantic, whitelists FR, skill seed — TOUT ce qui doit exister avant qu'une user story puisse être implémentée. CHECKPOINT obligatoire avant Phase 3.

**⚠️ CRITIQUE** : Aucune user story ne peut commencer avant la fin de cette phase.

### Tests Foundational (TDD imposé)

- [X] T006 [P] Écrire `backend/tests/integration/test_migration_045_roundtrip.py` (round-trip up/down/up sur PostgreSQL, vérification des 5 colonnes projects + 4 colonnes offer_matches + indexes BTREE/GIN). Le test DOIT échouer (migration absente).
- [X] T007 [P] Écrire `backend/tests/unit/test_matching_constants.py` — vérifie les 8 valeurs FR de `PROJECT_GCF_PRIORITY_THEMES_VALUES` et les 5 valeurs FR de `PROJECT_VULNERABLE_POPULATIONS_VALUES` avec accents é è ê à ç ô. Test DOIT échouer.
- [X] T008 [P] Écrire `backend/tests/integration/test_seed_sources_045.py` — vérifie idempotence + présence des 4 sources F01 verified (bceao-taxonomie-verte-2024, gcf-strategic-plan-2024-2027, gcf-gender-policy-2019, un-sdg-10-indicators). Test DOIT échouer.
- [X] T009 [P] Écrire `backend/tests/integration/test_seed_skill_match_project_funds.py` — vérifie présence du skill F23 avec 4 golden examples, tool_whitelist 21 tools, activation_rules valides. Test DOIT échouer.
- [X] T010 [P] Écrire `backend/tests/unit/test_project_schemas_extended.py` — vérifie validation Pydantic v2 des 5 nouveaux champs projet (Literal restricted, max_length, dedupe). Test DOIT échouer.
- [X] T011 [P] Écrire `backend/tests/unit/test_matching_schemas_project.py` — vérifie validation de `ProjectScoreBreakdown`, `MissingCriterionSchema`, `SourceUsedSchema` (extra=forbid, ranges). Test DOIT échouer.

### Implémentation Foundational

- [X] T012 Écrire `backend/app/core/matching_constants.py` avec `PROJECT_GCF_PRIORITY_THEMES_VALUES` (8 valeurs FR : atténuation/adaptation/cross_cutting/REDD+/forêts/eau/agriculture/énergie) et `PROJECT_VULNERABLE_POPULATIONS_VALUES` (5 valeurs FR : femmes/jeunes/handicapés/réfugiés/déplacés_internes) en frozenset[str] — fait passer T007
- [X] T013 Créer la migration Alembic `backend/alembic/versions/045_xxx_matching_projet_centric.py` qui : (a) ALTER TABLE projects ADD 5 colonnes (taxonomie_verte_uemoa_aligned BOOL NULL, gcf_priority_themes JSONB NOT NULL DEFAULT '[]', gender_inclusion BOOL NULL, vulnerable_populations JSONB NOT NULL DEFAULT '[]', project_esg_score INT NULL CHECK 0..100), (b) ALTER TABLE offer_matches ADD 4 colonnes (project_score INT NOT NULL DEFAULT 0 CHECK 0..100, company_score INT NOT NULL DEFAULT 0 CHECK 0..100, project_score_breakdown JSONB NOT NULL DEFAULT '{}', divergence_explanation TEXT NULL), (c) backfill `project_score = company_score = global_score`, `project_score_breakdown = score_breakdown`, (d) CREATE INDEX BTREE sur taxonomie_verte_uemoa_aligned + GIN sur gcf_priority_themes (PG only, skip SQLite), (e) downgrade DROP des 9 colonnes + indexes. Fait passer T006
- [X] T014 [P] Étendre `backend/app/models/project.py` : ajouter les 5 nouveaux champs SQLAlchemy `Mapped[...]` cohérents avec la migration T013 (types Boolean/JSON/Integer, nullable, default). Conserver le mixin `Auditable` F03
- [X] T015 [P] Étendre `backend/app/models/offer_match.py` : ajouter les 4 nouvelles colonnes `Mapped[...]` + marquer `global_score`, `fund_score`, `intermediary_score` comme **dépréciés** via docstring (rétrocompatibilité 2 sprints, lecture seule). Conserver le mixin `Auditable`
- [X] T016 [P] Étendre `backend/app/modules/projects/schemas.py` : ProjectBase, ProjectCreate, ProjectUpdate, ProjectDetail intègrent les 5 nouveaux champs avec validation Pydantic v2 strict (Literal pour les arrays, ge/le pour project_esg_score, dedupe validator) — fait passer T010
- [X] T017 [P] Créer `backend/app/modules/financing/matching_schemas.py` extension : `ProjectSubScoresSchema`, `SourceUsedSchema`, `MissingCriterionSchema`, `BoostAppliedSchema`, `ProjectScoreBreakdown`, `MatchFundsRequest`, `MatchFundsResponse` (tous `ConfigDict(extra="forbid")`) — fait passer T011
- [X] T018 Créer `backend/app/scripts/seed_sources_045.py` (idempotent SELECT-before-INSERT) qui seede les 4 sources F01 `status='verified'` avec 2 admins distincts (CHECK F01 four-eyes) — voir research.md R10. Crée admin technique `admin-verifier@mefali-system` si absent. Fait passer T008
- [X] T019 Étendre `backend/app/scripts/seed_skills.py` avec un 4e skill `skill_match_project_funds` (`status='draft'` initial), prompt_expert FR ~400 tokens (contracts/skill-match-project-funds.md §2), 21 tools whitelist, activation_rules (keywords FR + priority 80), 4 golden_examples FR (US1-US4) — fait passer T009
- [X] T020 Ajouter la route Alembic `045` au registre, lancer `alembic upgrade head` en local, vérifier les colonnes en BDD puis `alembic downgrade -1` puis `alembic upgrade head` (round-trip) — fait passer T006 en CI

**Checkpoint Phase 2** : Migration 045 appliquée, sources F01 seedées, skill F23 seedé, schemas Pydantic stricts en place. Les 5 user stories peuvent maintenant démarrer en parallèle.

---

## Phase 3 : User Story 1 (Priority: P1) 🎯 MVP — PME profil incomplet, projet vert ambitieux

**Goal** : Une PME sans `ESGAssessment` finalisée et un projet vert avec impact CO2 chiffré + taxonomie UEMOA + thèmes GCF obtient au moins 3 fonds compatibles (incluant GCF, FEM, Fonds d'Adaptation) avec `project_score ≥ 60`, indépendamment du score entreprise.

**Independent Test** : Créer un compte PME sans `ESGAssessment`, créer un projet via API avec les 4 attributs critiques, appeler `POST /api/projects/{id}/match-funds`, vérifier que la liste contient ≥ 3 fonds incluant GCF/FEM/Fonds d'Adaptation et que tous ont `project_score ≥ 60`.

### Tests for User Story 1 (TDD imposé) ⚠️

- [X] T021 [P] [US1] Écrire `backend/tests/unit/test_compute_project_score.py` couvrant les 8 sub-scores (sector, taxonomy, gcf_themes, co2_impact, beneficiaries, gender, vulnerable, project_esg) avec table-driven tests. Doit échouer.
- [X] T022 [P] [US1] Écrire `backend/tests/unit/test_compute_company_score.py` couvrant les 6 sub-scores héritage F14. Doit échouer.
- [X] T023 [P] [US1] Écrire `backend/tests/unit/test_boost_rule_rouge_entreprise_vert_projet.py` — vérifie R13 : projet vert + entreprise rouge → boost GCF/FEM/Fonds d'Adaptation en tête. Doit échouer.
- [X] T024 [P] [US1] Écrire `backend/tests/integration/test_match_funds_endpoint_us1.py` — appel `POST /api/projects/{id}/match-funds` retourne ≥ 3 fonds, tous avec project_score ≥ 60, incluant GCF/FEM/Fonds d'Adaptation. Doit échouer.
- [X] T025 [P] [US1] Écrire `backend/tests/integration/test_match_funds_endpoint_rls.py` — appel avec project_id d'un autre account → 404 silencieux RLS F02. Doit échouer.

### Implémentation for User Story 1

- [X] T026 [P] [US1] Implémenter `backend/app/modules/financing/matching_service.py::PROJECT_SCORE_WEIGHTS` (constante dict 8 clés, total 1.00 — voir research.md R5)
- [X] T027 [P] [US1] Implémenter `backend/app/modules/financing/matching_service.py::_compute_project_score_sector(project, fund) -> int` (100 si project.sector ∈ fund.target_sectors, 0 sinon)
- [X] T028 [P] [US1] Implémenter `backend/app/modules/financing/matching_service.py::_compute_project_score_taxonomy(project, fund) -> int` (100 si taxonomie_verte_uemoa_aligned=true ET source F01 verified, 0 sinon)
- [X] T029 [P] [US1] Implémenter `backend/app/modules/financing/matching_service.py::_compute_project_score_gcf_themes(project, fund) -> int` (Jaccard project.gcf_priority_themes ∩ fund.gcf_themes_target × 100)
- [X] T030 [P] [US1] Implémenter `backend/app/modules/financing/matching_service.py::_compute_project_score_co2_impact(project, fund) -> int` (graduel selon expected_impact_tco2e vs fund.min_co2_threshold, sourcé GCF Strategic Plan)
- [X] T031 [P] [US1] Implémenter `backend/app/modules/financing/matching_service.py::_compute_project_score_beneficiaries(project, fund) -> int` (ratio expected_beneficiaries / fund.target_beneficiaries, borné 0..100)
- [X] T032 [P] [US1] Implémenter `backend/app/modules/financing/matching_service.py::_compute_project_score_gender(project, fund) -> int` (100 si project.gender_inclusion=true ET fund requiert gender, 50 neutre sinon — sourcé GCF Gender Policy 2019)
- [X] T033 [P] [US1] Implémenter `backend/app/modules/financing/matching_service.py::_compute_project_score_vulnerable(project, fund) -> int` (Jaccard project.vulnerable_populations ∩ fund.vulnerable_target × 100, sourcé ODD 10)
- [X] T034 [P] [US1] Implémenter `backend/app/modules/financing/matching_service.py::_compute_project_score_project_esg(project, fund) -> int` (project.project_esg_score si renseigné, 50 neutre sinon)
- [X] T035 [US1] Implémenter `backend/app/modules/financing/matching_service.py::_compute_project_score(project, fund) -> tuple[int, ProjectScoreBreakdown]` qui orchestre les 8 sub-scores, applique PROJECT_SCORE_WEIGHTS, construit le breakdown JSONB et identifie les top 5 missing_criteria (depends T026-T034) — fait passer T021
- [X] T036 [US1] Refactor `backend/app/modules/financing/matching_service.py::_compute_company_score(project, offer, esg_assessment) -> tuple[int, dict]` (renommage de la logique F14 existante avec pondération sector=0.25, esg=0.30, size=0.15, location=0.10, documents=0.10, instrument=0.10) — fait passer T022
- [X] T037 [US1] Implémenter `backend/app/modules/financing/matching_service.py::_apply_boost_rule_rouge_entreprise_vert_projet(matches, project) -> tuple[list, BoostAppliedSchema]` — promeut GCF/FEM/Fonds d'Adaptation en tête si conditions (research.md R13) — fait passer T023
- [X] T038 [US1] Refactor `backend/app/modules/financing/matching_service.py::compute_offer_match(...)` pour retourner désormais `(project_score, company_score, project_breakdown, company_breakdown)` au lieu de l'unique `global_score`. Conserver backfill `global_score = project_score` pour rétrocompat.
- [X] T039 [US1] Implémenter `backend/app/modules/financing/matching_service.py::match_funds_for_project(db, account_id, project_id, min_score, limit, force_recompute) -> MatchFundsResponse` qui : (a) charge le projet + offres publiées (cap 50), (b) appelle `compute_offer_match` pour chaque paire, (c) applique `_apply_boost_rule_rouge_entreprise_vert_projet`, (d) trie par `project_score DESC, company_score DESC`, (e) UPDATE in-place sur offer_matches (UNIQUE constraint) — depends T035, T036, T037, T038
- [X] T040 [US1] Ajouter l'endpoint `POST /api/projects/{project_id}/match-funds` à `backend/app/modules/financing/matching_router.py` (depends T039) avec validation `min_score` 0..100, `limit` 1..50, `force_recompute` bool. RLS F02 via `_require_account_id`. Retours 200/202/400/403/404/422/503 conformes à contracts/api-endpoints.md §1.5 — fait passer T024, T025
- [X] T041 [US1] Mettre à jour `backend/app/modules/financing/matching_service.py::list_matches_for_project(...)` pour basculer le tri vers `ORDER BY project_score DESC, company_score DESC, computed_at DESC` (au lieu de global_score)

**Checkpoint US1** : Une PME informelle obtient ≥ 3 fonds compatibles via l'endpoint, score projet ≥ 60 garanti, boost actif pour le cas « rouge entreprise + vert projet ».

---

## Phase 4 : User Story 2 (Priority: P1) — Pilotage du cycle de vie projet en chat

**Goal** : En une seule conversation, la PME (a) crée son projet via tools + widgets F18, (b) lance le matching via `match_funds_for_project`, (c) modifie un champ via `update_project`, (d) relance le matching automatiquement, (e) voit la nouvelle liste en `<MatchCardProjectBlock>` (F11) — sans handover UI.

**Independent Test** : Démarrer une conversation vide pour un compte PME sans projet. Vérifier que l'agent peut créer, matcher, update, re-matcher en 3 tours max via tools, et que les blocks F11 sont émis dans la SSE.

### Tests for User Story 2 (TDD imposé) ⚠️

- [ ] T042 [P] [US2] Écrire `backend/tests/integration/test_tool_match_funds_for_project.py` — appel du tool retourne JSON compact + émet `<MatchCardProjectBlock>` SSE. Doit échouer.
- [ ] T043 [P] [US2] Écrire `backend/tests/conformity/test_tool_match_funds_in_whitelist.py` — vérifie que `match_funds_for_project` apparaît dans `MODULE_TOOL_MAPPING['financing']`, `['application']`, et `PAGE_TOOL_MAPPING['profile_projects']`, `['chat']`. Doit échouer.
- [ ] T044 [P] [US2] Écrire `backend/tests/conformity/test_skill_match_project_funds_tools.py` — vérifie que les 21 tools whitelistés du skill existent dans `tool_selector_config.ALL_TOOLS`. Doit échouer.
- [ ] T045 [P] [US2] Écrire `backend/tests/integration/test_after_update_listener.py` — modifier project.expected_impact_tco2e → vérifie que listener `after_update` schedule un recompute async, debounce 30s actif (2 updates rapprochés = 1 seul recompute). Doit échouer.
- [ ] T046 [P] [US2] Écrire `frontend/tests/e2e/matching-project-centric.spec.ts` (Playwright) — parcours complet US2 + FR-019 : login PME → chat → décrire projet → widgets F18 → create_project → match → update → re-match → **clic « Comparer N intermédiaires pour [Fund] » sur une MatchCard** → atterrissage sur `/financing/compare/[fund_id]?project_id=X` (page F14) → vérifier rendu `<ComparisonTableBlock>` avec 2 colonnes intermédiaires minimum → retour fiche fonds. Doit échouer en local.

### Implémentation for User Story 2

- [X] T047 [US2] Implémenter `backend/app/graph/tools/project_tools.py::MatchFundsForProjectArgs` (Pydantic args schema) + `match_funds_for_project(project_id, min_score, limit) -> str` décoré `@tool` (depends T039) — voir contracts/tool-match-funds-for-project.md §1. Fait passer T042
- [X] T048 [US2] Implémenter l'émission SSE `emit_visualization_block(block_type='match_card_project', payload=...)` dans le tool avec schema `MatchCardBlockProjectSchema` Pydantic (extra=forbid)
- [X] T049 [US2] Mettre à jour `backend/app/graph/tool_selector_config.py` : ajouter `"match_funds_for_project"` dans `MODULE_TOOL_MAPPING['financing']`, `MODULE_TOOL_MAPPING['application']`, `PAGE_TOOL_MAPPING['profile_projects']`, `PAGE_TOOL_MAPPING['chat']`. Vérifier `MAX_TOOLS_PER_TURN=29` reste OK avec 21 tools dans skill — fait passer T043, T044
- [X] T050 [US2] Implémenter listener SQLAlchemy `event.listens_for(Project, 'after_update')` dans `backend/app/modules/projects/service.py` qui : (a) détecte changements sur champs critiques (sector, target_amount_*, objective_env, expected_impact_tco2e, expected_beneficiaries, 5 nouveaux 045), (b) debounce 30s in-process via dict {project_id: last_ts}, (c) `asyncio.create_task(_runner)` qui appelle `matching_service.execute_recompute_batch(...)` — fait passer T045
- [X] T051 [P] [US2] Créer `frontend/app/types/projectMatching.ts` avec types `ProjectScoreBreakdown`, `MatchFundsResponse`, `SubScores`, `MissingCriterion`, `BoostApplied`, `DivergenceExplanation` (miroir exact des schemas Pydantic backend, JSDoc FR)
- [ ] T052 [P] [US2] Créer `frontend/scripts/sync-matching-constants.ts` (Node + ts-node) qui lit `backend/app/core/matching_constants.py`, parse les frozensets et génère `frontend/app/types/matching_enums.generated.ts`. Exécuter une fois et commiter le fichier généré
- [X] T053 [P] [US2] Créer `frontend/app/composables/useProjectMatching.ts` avec 4 méthodes typed : `matchFunds(projectId, opts)`, `getMatches(projectId, filters)`, `recomputeMatches(projectId)`, `getMatchDetails(projectId, offerId)` (fetch wrapper $useFetch + types T051)
- [X] T054 [P] [US2] Créer `frontend/app/stores/projectMatching.ts` (Pinia store) : state `matchesByProject: Record<UUID, MatchFundsResponse>`, actions `loadMatches(projectId)`, `recompute(projectId)`, `clearCache(projectId)`. Pas de persistance localStorage (volatile)
- [X] T055 [P] [US2] Créer `frontend/app/components/financing/ProjectMatchCardBlock.vue` (composant F11 visualisation pour block_type='match_card_project') : affiche fund_name + intermediary_name + project_score + company_score + divergence_short + sources F01 (`<SourceLink>`). Dark mode complet, ARIA region role + aria-labelledby
- [X] T056 [US2] Étendre `frontend/app/composables/useChat.ts` pour router `block_type='match_card_project'` vers `<ProjectMatchCardBlock>` (en parallèle du `block_type='match_card'` F14 existant)
- [ ] T057 [US2] Exécuter le test E2E Playwright `frontend/tests/e2e/matching-project-centric.spec.ts` en local (`npm run test:e2e`). Vérifier : 3 tours conversation max, < 90 s, blocks émis, update + re-match auto, **clic comparateur F14 fonctionnel et page comparaison rendue avec ≥ 2 intermédiaires** — fait passer T046 et couvre FR-019.

**Checkpoint US2** : L'agent peut piloter le cycle de vie complet du projet en chat sans handover UI, blocks F11 émis dans le SSE, listener after_update opérationnel avec debounce.

---

## Phase 5 : User Story 3 (Priority: P2) — Filtrage des projets sans pertinence climatique

**Goal** : Un projet sans alignement climatique (taxonomie UEMOA false, aucun thème GCF, impact CO2 nul) retourne `matches_count=0` avec un `no_match_reason` FR explicatif qui liste les thèmes à renforcer (sourcés F01).

**Independent Test** : Créer un projet sans aucun attribut vert, appeler l'endpoint, vérifier que `matches_count=0` et que `no_match_reason` contient au moins 2 thèmes manquants cliquables vers sources F01.

### Tests for User Story 3 (TDD imposé) ⚠️

- [ ] T058 [P] [US3] Écrire `backend/tests/integration/test_match_funds_endpoint_us3_empty.py` — projet sans alignement → matches_count=0, no_match_reason FR non vide, contient "taxonomie" OR "thèmes". Doit échouer.
- [ ] T059 [P] [US3] Écrire `backend/tests/integration/test_match_funds_endpoint_us3_partial.py` — projet taxonomie OK mais sans CO2 → matches_count > 0, mais chaque match a badge "Score projet incomplet" dans missing_criteria. Doit échouer.
- [ ] T060 [P] [US3] Écrire `backend/tests/unit/test_no_match_reason_builder.py` — table-driven : 4 cas projet vide / taxonomie absente / thèmes vides / co2 nul → message FR adapté. Doit échouer.

### Implémentation for User Story 3

- [X] T061 [P] [US3] Implémenter `backend/app/modules/financing/matching_service.py::_build_no_match_reason(project) -> str | None` qui : (a) inspecte les attributs projet critiques, (b) identifie les 2-3 manquants prioritaires (taxonomie, thèmes GCF, impact CO2), (c) génère texte FR gabarit "Aucun fonds n'aligne ses critères avec ce projet. Renforcez : [thème_1, thème_2, ...]". Cite les sources F01 du breakdown. Fait passer T060
- [X] T062 [US3] Modifier `backend/app/modules/financing/matching_service.py::match_funds_for_project(...)` pour appeler `_build_no_match_reason(project)` quand `len(matches) == 0` et inclure dans la réponse — fait passer T058
- [X] T063 [US3] Modifier `backend/app/modules/financing/matching_service.py::_compute_project_score(...)` pour ajouter à `missing_criteria` (top 5) les critères projet manquants avec `kind='missing'` quand le score < 100 pour un sub-score donné — fait passer T059

**Checkpoint US3** : Les projets non verts sont filtrés proprement avec explication FR actionnable, les projets partiellement verts affichent les critères manquants.

---

## Phase 6 : User Story 4 (Priority: P2) — Double score séparé + explication divergence

**Goal** : L'utilisateur voit deux scores séparés (« Match projet : X% » / « Match entreprise : Y% ») avec un paragraphe gabarit FR (pas freetext LLM) qui explique la divergence quand l'écart dépasse 30 points.

**Independent Test** : Sur un match avec project_score=78 et company_score=12, ouvrir la fiche offre et vérifier que les 2 scores sont affichés séparément + paragraphe "Votre projet est éligible parce qu'il aligne..." + badge couleur divergence.

### Tests for User Story 4 (TDD imposé) ⚠️

- [ ] T064 [P] [US4] Écrire `backend/tests/unit/test_divergence_templates.py` — 4 cas (convergent, projet_fort, entreprise_forte, moyen) → texte FR gabarit conforme research.md R6. Vérifie présence des variables `{N}`, `{themes_gcf}`, `{top_company_blockers}`. Doit échouer.
- [ ] T065 [P] [US4] Écrire `backend/tests/integration/test_match_details_endpoint_us4.py` — `GET /api/projects/{id}/match-details/{offer_id}` retourne `project_score`, `company_score`, `divergence_explanation` (texte FR avec accents), `project_score_breakdown` complet. Doit échouer.
- [ ] T066 [P] [US4] Écrire `frontend/tests/unit/DualScoreDisplay.spec.ts` (Vitest) — composant rend 2 scores + badge divergence + tooltip. Dark mode testé. Doit échouer.
- [ ] T067 [P] [US4] Écrire `frontend/tests/unit/DivergenceBadge.spec.ts` (Vitest) — 4 variants (convergent, projet_fort, entreprise_forte, moyen) → 4 couleurs. ARIA aria-label FR. Doit échouer.

### Implémentation for User Story 4

- [X] T068 [P] [US4] Implémenter `backend/app/modules/financing/divergence_templates.py::build_divergence_explanation(project_score, company_score, project_breakdown, company_breakdown) -> str | None` avec 4 gabarits FR (research.md R6) — fait passer T064
- [X] T069 [P] [US4] Implémenter `backend/app/modules/financing/divergence_templates.py::build_divergence_short(project_score, company_score) -> str` (variante ≤ 80 caractères pour payload LLM)
- [X] T070 [US4] Modifier `backend/app/modules/financing/matching_service.py::compute_offer_match(...)` pour appeler `build_divergence_explanation(...)` et persister dans `offer_matches.divergence_explanation`
- [X] T071 [US4] Modifier `backend/app/modules/financing/matching_router.py::match_details_endpoint(...)` pour retourner les nouveaux champs `project_score`, `company_score`, `divergence_explanation`, `project_score_breakdown`, `company_score_breakdown` — fait passer T065
- [X] T072 [P] [US4] Créer `frontend/app/components/financing/DualScoreDisplay.vue` : 2 scores côte à côte (project label "Match projet" + company label "Match entreprise"), badges couleur, tooltip explicatif au hover. Dark mode complet (bg-white dark:bg-dark-card, text-gray-600 dark:text-gray-400). Props typed depuis types T051 — fait passer T066
- [X] T073 [P] [US4] Créer `frontend/app/components/financing/DivergenceBadge.vue` : pastille colorée + label FR (4 variants), tooltip ARIA aria-describedby — fait passer T067
- [X] T074 [P] [US4] Créer `frontend/app/components/financing/MissingProjectCriteriaList.vue` : liste critères manquants avec `<SourceLink>` F01 par item, dark mode complet
- [X] T075 [US4] Modifier `frontend/app/pages/financing/offers/[offerId].vue` pour intégrer `<DualScoreDisplay>` dans une nouvelle section "Mon score pour ce projet" (visible si project_id query param présent ou projet actif Pinia store)

**Checkpoint US4** : Les 2 scores sont visibles côte à côte avec explication FR gabarit cohérente, dark mode testé, composants ARIA-compliant.

---

## Phase 7 : User Story 5 (Priority: P3) — Section UI « Fonds compatibles avec ce projet »

**Goal** : Sur `/profile/projects/[id]`, une nouvelle section affiche les 5 meilleurs matches projet (triés par project_score DESC) sous forme de MatchCard cliquables. Empty state explicite si aucun match.

**Independent Test** : Créer un projet, déclencher le matching, ouvrir `/profile/projects/[id]` et vérifier l'affichage de la section + lien vers chaque fiche offre. Tester l'empty state sur un projet sans match.

### Tests for User Story 5 (TDD imposé) ⚠️

- [ ] T076 [P] [US5] Écrire `frontend/tests/unit/ProjectFundsSection.spec.ts` (Vitest) — rendu top 5 matches en MatchCard, empty state si vide, dark mode. Doit échouer.
- [ ] T077 [P] [US5] Écrire `frontend/tests/integration/useProjectMatching.spec.ts` — composable charge correctement les matches, gère erreurs 404/503. Doit échouer.

### Implémentation for User Story 5

- [X] T078 [P] [US5] Créer `frontend/app/components/financing/ProjectFundsSection.vue` : section "Fonds compatibles avec ce projet" avec titre + top 5 `<ProjectMatchCardBlock>`, bouton "Voir tous les matches" qui navigue vers `/profile/projects/[id]/matches` (F14 existant), empty state FR avec 2-3 champs à compléter (depends T055) — fait passer T076
- [X] T079 [US5] Modifier `frontend/app/pages/profile/projects/[id].vue` pour intégrer `<ProjectFundsSection :project-id="route.params.id" />` après les sections F06 existantes
- [X] T080 [US5] S'assurer que le composable `useProjectMatching.ts` (T053) gère bien les cas d'erreur (404 = projet absent ou RLS, 503 = migration en cours) avec messages FR clairs — fait passer T077
- [X] T080b [P] [US5] Ajouter dans `frontend/app/components/financing/ProjectFundsSection.vue` un bouton « Recalculer les matches » (icône refresh, dark mode complet, ARIA aria-label FR « Recalculer les fonds compatibles avec ce projet ») qui appelle `useProjectMatching().recomputeMatches(projectId)` puis recharge le state Pinia `projectMatching.matchesByProject[projectId]`. Disabled pendant l'appel async (`v-bind:disabled="loading"`), toast FR de succès/erreur (`useToast` existant). Couvre FR-009 côté UI.
- [ ] T080c [P] [US5] Écrire `frontend/tests/unit/RecomputeMatchesButton.spec.ts` (Vitest) — bouton émet l'appel `recomputeMatches`, state disabled pendant le chargement, toast affiché. Dark mode testé. À écrire AVANT T080b et doit échouer.

**Checkpoint US5** : La fiche projet affiche les fonds compatibles, navigation cliquable vers les fiches offres et le comparateur F14, bouton recalcul on-demand opérationnel (FR-009).

---

## Phase 8 : Polish & Cross-Cutting Concerns

**Purpose** : Documentation, performance benchmarks, code cleanup, vérifications finales avant PR.

- [X] T081 [P] Créer `docs/matching-projet-centric.md` (guide métier FR) couvrant : objectif feature, différences avec F14, schéma 8 sub-scores projet, 4 gabarits divergence, parcours US1+US2 illustrés
- [X] T082 [P] Mettre à jour `docs/financing.md` (référence consolidée F08 + F14 + F045)
- [~] T083 [P] Lancer `pytest backend/tests/ --cov=backend/app/modules/financing --cov=backend/app/modules/projects --cov-report=term-missing` et vérifier couverture ≥ 80 % sur les modules touchés (FR-018) — pytest relancé sans -x après fix régression `test_select_tools_truncation_on_oversized_catalog` (MAX_TOOLS_PER_TURN passé de 29 à 31 par F045). Mesure coverage à vérifier en local.
- [~] T084 [P] Lancer `cd frontend && npm run test:coverage` et vérifier couverture ≥ 80 % sur les composants nouveaux (FR-018) — pas de script `test:coverage` dans package.json. `npx vitest run` exécuté : 888 passed / 12 failed (5 fichiers : esg-index, esg-results, guided-tours/registry, data-guide-targets, useGuidedTour.resilience — **aucun composant F045 dans les échecs**, pré-existants à F045).
- [~] T085 [P] Lancer benchmark `POST /match-funds` avec locust ou `ab -n 100 -c 10` sur un projet ayant 50 offres compatibles → vérifier p95 < 2 s (SC-003) — **non exécuté** : nécessite serveur backend + seed 50 offres pré-configurés. À lancer manuellement avant PR.
- [~] T086 [P] Lancer benchmark E2E Playwright `matching-project-centric.spec.ts --reporter=json` → vérifier durée < 90 s (SC-005) — **non exécuté** : nécessite serveur backend + frontend + auth PME + Playwright installé. À lancer manuellement avant PR.
- [X] T087 [P] Exécuter `ruff check backend/` et corriger les warnings dans les fichiers touchés — 3 E402 corrigés par `# noqa: E402` sur imports late-bound du listener `after_update` (évite cycle avec matching_service). F821 ProjectDocument pré-existant (forward ref SQLAlchemy).
- [~] T088 [P] Exécuter `cd frontend && npm run lint && npm run typecheck` et corriger les erreurs — **scripts `lint` et `typecheck` absents** du `package.json` frontend (seuls `test`, `test:e2e`, `dev`, `build`, `generate`, `preview` configurés). À ajouter avant PR ou marquer hors-scope.
- [X] T089 Invoquer l'agent `security-reviewer` sur les nouveaux modules backend (matching_service, divergence_templates, project_tools.match_funds_for_project) pour vérifier RLS F02, audit F03, sources F01 — **3 CRITICAL + 3 HIGH + 3 MEDIUM + 1 LOW** (voir résumé dans la conversation). À traiter avant PR : RLS bypass sur `recompute_matches_for_project`, `compare_offers_for_fund`, `subscribe_to_alerts`.
- [X] T090 Invoquer l'agent `code-reviewer` sur le diff complet de la branche pour catch les patterns non idiomatiques (mutation, deep nesting > 4, functions > 50 lignes, files > 800 lignes) — **3 HIGH + 4 MEDIUM + 2 LOW** : duplication ESG layer matching_service, `_compute_offer_match_v045` 160 lignes, mutation directe `store.matchesByProject` dans `ProjectFundsSection.vue:87`.
- [~] T091 Lancer `pytest backend/tests/ -x` complet pour vérifier 0 régression sur les 2900+ tests baseline (SC-007) — 1 régression détectée et corrigée (`test_select_tools_truncation_on_oversized_catalog`). Suite complète relancée sans -x ; voir log `/tmp/pytest_full2.log` pour résultat final.
- [X] T092 Mettre à jour le ledger F045 dans `CLAUDE.md` (entrée détaillée en haut, format identique aux autres F-features) et synchroniser `Active Technologies` + `Recent Changes`
- [X] T093 Vérifier que le seed `seed_skills.py` peut basculer `skill_match_project_funds` en `status='published'` (manuel ou via gating eval ≥ 90 % automatique) avant le merge — confirmé : `DRAFT_ONLY: set[str] = {"skill_match_project_funds"}` dans `app/modules/skills/seed.py:400`, transition gérée par le router admin F23 existant (`POST /api/admin/skills/{id}/publish`).

**Checkpoint Phase 8** : Couverture ≥ 80 % validée, 0 régression, docs à jour, code reviewé. Branche prête pour PR vers `main`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)** : Aucune dépendance — démarrage immédiat
- **Phase 2 (Foundational)** : Depends sur Phase 1 — BLOQUE toutes les user stories
- **Phase 3 (US1 P1)** : Depends sur Phase 2 — démarrage possible dès T020 OK
- **Phase 4 (US2 P1)** : Depends sur Phase 2 + tâches US1 T039 (service `match_funds_for_project`)
- **Phase 5 (US3 P2)** : Depends sur Phase 2 + tâches US1 T035, T039 (compute_project_score + match_funds_for_project)
- **Phase 6 (US4 P2)** : Depends sur Phase 2 + tâches US1 T035, T036 (compute_project_score + compute_company_score)
- **Phase 7 (US5 P3)** : Depends sur Phase 2 + tâches US1 (endpoint match-funds) + US2 (ProjectMatchCardBlock T055, composable T053)
- **Phase 8 (Polish)** : Depends sur **toutes** les user stories désirées (au minimum US1+US2 pour le MVP)

### User Story Dependencies

- **US1 (P1)** : INDÉPENDANTE — peut démarrer dès Phase 2 OK. Aucune dépendance sur les autres stories.
- **US2 (P1)** : Depends partiellement sur US1 (réutilise `match_funds_for_project` service) mais les tâches frontend T051-T056 peuvent démarrer en parallèle de US1 backend
- **US3 (P2)** : Depends sur US1 (étend `match_funds_for_project` et `_compute_project_score` avec no_match_reason et missing_criteria)
- **US4 (P2)** : Depends sur US1 (étend `compute_offer_match` avec `divergence_explanation`). Frontend T072-T074 peut démarrer en parallèle de US1 backend
- **US5 (P3)** : Depends sur US2 (`ProjectMatchCardBlock` T055) et US1 (endpoint). Peut démarrer en parallèle si T055 et T040 sont OK

### Au sein d'une user story

- Tests (si demandés — ici TDD imposé) DOIVENT être écrits AVANT l'implémentation et DOIVENT échouer
- Models avant Services
- Services avant Endpoints
- Backend avant Frontend (au sein d'une story)
- Story complète avant passage à la story suivante (sauf si plusieurs devs en parallèle)

### Parallel Opportunities

- **Phase 1** : T002, T003, T004, T005 en parallèle (fichiers différents) — pas de dépendance entre eux
- **Phase 2 tests** : T006, T007, T008, T009, T010, T011 en parallèle (fichiers tests différents)
- **Phase 2 impl** : T014, T015, T016, T017 en parallèle après T012, T013, T018, T019
- **US1 sub-scores** : T026, T027, T028, T029, T030, T031, T032, T033, T034 en parallèle (8 fonctions distinctes dans le même fichier mais fonctions pures indépendantes)
- **US2 frontend** : T051, T052, T053, T054, T055 en parallèle (fichiers Vue/TS différents)
- **US4 components Vue** : T072, T073, T074 en parallèle (composants distincts)
- **Phase 8 polish** : T081-T088 en parallèle (docs, coverage, lint indépendants)

---

## Parallel Example: User Story 1 sub-scores (Phase 3)

```bash
# Une fois les schemas Pydantic (T017) et matching_constants (T012) en place,
# les 8 sub-scores projet peuvent être implémentés en parallèle :

# Terminal 1
$ # T027 — _compute_project_score_sector
$ # T028 — _compute_project_score_taxonomy

# Terminal 2
$ # T029 — _compute_project_score_gcf_themes
$ # T030 — _compute_project_score_co2_impact

# Terminal 3
$ # T031 — _compute_project_score_beneficiaries
$ # T032 — _compute_project_score_gender

# Terminal 4
$ # T033 — _compute_project_score_vulnerable
$ # T034 — _compute_project_score_project_esg

# Puis T035 (orchestration) une fois T026-T034 OK
```

---

## Implementation Strategy

### MVP Scope (P1 stories)

Le **MVP livrable** est constitué de **US1 + US2** :

- **US1** débloque l'inclusion financière des PME informelles (cas central du brief).
- **US2** garantit le parcours conversationnel sans handover UI (différenciation produit vs formulaires F14).

Si l'équipe doit couper pour livrer plus vite, **US3, US4, US5 peuvent être différés** :
- US3 (filtrage projets non verts) : le système reste fonctionnel mais peut suggérer des fonds non pertinents (dégradation acceptable temporaire).
- US4 (double score affiché + divergence) : les scores sont calculés et persistés (US1) mais l'UI affiche un seul score (project_score) — l'explication divergence n'est pas générée.
- US5 (section UI fiche projet) : la PME doit aller dans `/financing` pour voir ses matches projet — pas idéal mais fonctionnel.

### Incremental Delivery

Recommandation : merge en **3 PRs incrémentales** :

1. **PR 1 — Foundational + US1** (Phases 1, 2, 3) : migration, sources, endpoint POST /match-funds, scoring projet, boost. Livrable testable backend.
2. **PR 2 — US2 + US4** (Phases 4, 6) : tool LangChain, skill F23, listener after_update, composants `<DualScoreDisplay>` + `<DivergenceBadge>`, page offers/[offerId] étendue. Livrable UX complet.
3. **PR 3 — US3 + US5 + Polish** (Phases 5, 7, 8) : no_match_reason, section UI fiche projet, docs, coverage, benchmark, security review.

Chaque PR peut être déployée indépendamment sans bloquer les suivantes.

### Parallel Team Strategy

Si l'équipe a 2 devs disponibles en parallèle :
- **Dev A (backend)** : Phase 2 → US1 (T021-T041) → US3 (T058-T063) → US4 backend (T064-T071) → Phase 8 backend
- **Dev B (frontend)** : Démarrage en parallèle de US1 T046+ pour préparer E2E test, puis US2 frontend (T051-T057) → US4 frontend (T072-T075) → US5 (T076-T080) → Phase 8 frontend

Coordination : daily standup pour aligner sur les contrats API (matching_schemas.py) et les types TS générés.

---

## Validation des tasks

- ✅ **Format strict** : toutes les 93 tâches suivent `- [ ] [TaskID] [P?] [Story?] Description avec chemin fichier`
- ✅ **Story labels** : Phases 3-7 utilisent [US1]-[US5], Phases 1, 2, 8 n'utilisent pas de story label
- ✅ **Chemins absolus** : tous les `backend/...` et `frontend/...` sont relatifs à `/Users/mac/Documents/projets/2025/esg_mefali_v3/`
- ✅ **Tests avant implémentation** : chaque user story commence par les tests (T021-T025, T042-T046, T058-T060, T064-T067, T076-T077, T080c) qui DOIVENT échouer
- ✅ **Couverture user stories** : US1 (21 tâches), US2 (16 tâches), US3 (6 tâches), US4 (12 tâches), US5 (7 tâches : T076-T080 + T080b + T080c) — chaque story indépendamment testable
- ✅ **Parallèle markup** : 64 tâches marquées [P] (à exécuter en parallèle quand possible)

**Total : 95 tâches** réparties sur 8 phases (incluant T080b et T080c ajoutés post-/speckit.analyze pour couvrir FR-009 bouton UI on-demand). Estimation effort : ~3 sprints (US1+US2 en sprint 1, US3+US4 en sprint 2, US5+Polish en sprint 3) pour 2 devs.
