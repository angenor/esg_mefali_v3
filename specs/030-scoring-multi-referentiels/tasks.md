---
description: "Task list F13 — Scoring ESG Multi-Référentiels (TDD strict, couverture ≥ 80%)"
---

# Tasks: F13 — Scoring ESG Multi-Référentiels

**Input** : Design documents from `/specs/030-scoring-multi-referentiels/`
**Prerequisites** : plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Tests** : Tests sont OBLIGATOIRES (TDD strict, couverture ≥ 80 %, voir `.cc-orchestrator.md` invariant n°12).

## Format

`- [ ] [TaskID] [P?] [Story?] Description avec chemin de fichier absolu`

- `[P]` : tâche parallélisable (fichiers distincts, pas de dépendance bloquante).
- `[S]` : tâche sérialisée (zone protégée ou dépendance forte).
- `[USx]` : appartient à une user story P1/P2/P3 (label dans spec.md).
- Pas de label `[USx]` pour les phases Setup, Foundational, Polish.

## Path Conventions

- Backend : `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/`
- Frontend : `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/`
- Specs : `/Users/mac/Documents/projets/2025/esg_mefali_v3/specs/030-scoring-multi-referentiels/`

---

## Phase 1: Setup (Infrastructure partagée)

**Objectif** : préparer l'arborescence et les constantes nécessaires aux phases suivantes.

- [ ] T001 [P] Créer la constante `MEFALI_REFERENTIAL_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")` + codes des référentiels MVP (`MEFALI_REFERENTIAL_CODE`, `GCF_REFERENTIAL_CODE`, `IFC_PS_REFERENTIAL_CODE`, `BOAD_ESS_REFERENTIAL_CODE`, `GRI_2021_REFERENTIAL_CODE`, `REFERENTIAL_CODES_MVP`, `DEFAULT_MIN_COVERAGE_FOR_PDF=0.5`, `DEFAULT_REFERENTIAL_THRESHOLD=50.0`) dans `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/app/core/constants.py`.
- [ ] T002 [P] Créer le répertoire `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/app/modules/esg/` (existant) et confirmer la présence de `__init__.py`. Créer `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/tests/migrations/` si absent (mkdir).
- [ ] T003 [P] Créer le répertoire `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/app/components/esg/` (extension du dossier F05 existant) et `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/tests/components/esg/`.
- [ ] T004 Vérifier les dépendances déjà installées (`pytest-asyncio`, `pytest-cov`, `WeasyPrint`, `Jinja2`, `matplotlib`, `@playwright/test`, `vue-chartjs`, `chart.js`) via `cd backend && source venv/bin/activate && pip list | grep -E '(pytest|weasyprint|matplotlib)'` et `cd frontend && npm list | grep -E '(playwright|chart)'`. Pas d'installation nouvelle attendue (toutes déjà présentes via F05/F06/F12).

**Checkpoint** : arborescence prête, constantes définies, dépendances confirmées.

---

## Phase 2: Foundational (Préalables bloquants)

**Objectif** : créer la table `referential_scores`, les modèles SQLAlchemy, les schémas Pydantic, et seeder les 5 référentiels MVP. Aucune US ne peut commencer avant cette phase.

> ⚠️ CRITIQUE : T005-T010 sont prérequis pour TOUTES les user stories.

### Tests d'abord (TDD)

- [ ] T005 [P] Créer le test `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/tests/unit/test_referential_score_model.py` qui valide : (a) la création d'un `ReferentialScore` avec tous les champs ; (b) la contrainte `coverage_rate BETWEEN 0 AND 1` (CHECK) ; (c) le pattern `superseded_by` self-référent ; (d) les valeurs ENUM `ComputedByEnum` (manual/llm/auto) ; (e) le default `pillar_scores={}`, `covered_criteria=[]`, `missing_criteria=[]`. Le test doit ÉCHOUER avant T007.
- [ ] T006 [P] Créer le test `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/tests/unit/test_pydantic_schemas_referential_score.py` qui valide les schémas Pydantic (PillarScore, CoveredCriterion, MissingCriterion, ReferentialScoreRead, ReferentialScoreCreate, ComparisonResult, RecomputeRequestResponse, FinalizeAssessmentResult, BottleneckInfo, DualReferentialResponse) selon les contraintes de `data-model.md`. Tests : valeurs hors bornes (score > 100), champs manquants, MissingReason enum invalide. Le test doit ÉCHOUER avant T008.
- [ ] T007 [P] Créer le test `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/tests/migrations/test_alembic_030.py` qui valide : (a) `alembic upgrade head` crée la table `referential_scores` avec les bons indexes (unique partiel, secondaires) ; (b) le seed Mefali avec UUID stable + 4 référentiels MVP idempotents (ON CONFLICT DO NOTHING) ; (c) le backfill `EsgAssessment` → `referential_scores` (count avant = count après pour `EsgAssessment`, et `count(referential_scores) >= count(esg_assessments WHERE overall_score IS NOT NULL)`) ; (d) `alembic downgrade -1` réversible (drop table + ENUM) ; (e) `alembic upgrade head` 2ème fois idempotent. Le test doit ÉCHOUER avant T009.

### Implémentation

- [ ] T008 Créer le modèle SQLAlchemy `ReferentialScore` dans `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/app/models/referential_score.py` selon le DDL data-model.md (champs, ENUM `ComputedByEnum`, relations vers Account/EsgAssessment/Referential, self-ref `superseded_by`, contraintes `__table_args__` index unique partiel + 2 secondaires + CheckConstraint coverage_rate). Doit faire passer T005.
- [ ] T009 Créer les schémas Pydantic v2 dans `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/app/schemas/referential_score.py` (PillarScore, CoveredCriterion, MissingCriterion, ComputedBy, MissingReason, ReferentialScoreRead, ReferentialScoreCreate, ComparisonResult, RecomputeRequestResponse, FinalizeAssessmentResult, BottleneckInfo, DualReferentialResponse). Doit faire passer T006.
- [ ] T010 [S] Créer la migration Alembic `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/alembic/versions/030_create_referential_scores.py` avec `revision="030_create_referential_scores"`, `down_revision="028_offers_and_enrich"`. Contenu : (a) ENUM `referential_score_computed_by_enum` ; (b) table `referential_scores` avec colonnes data-model.md ; (c) index unique partiel `idx_referential_scores_current` ; (d) 2 indexes secondaires + 1 sur account_id ; (e) RLS PostgreSQL (`ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, policy `referential_scores_account_isolation`) ; (f) trigger `updated_at` ; (g) seed Mefali (UUID stable) + 4 référentiels MVP `ON CONFLICT (code) DO NOTHING` ; (h) backfill `INSERT INTO referential_scores ... SELECT FROM esg_assessments` avec `ON CONFLICT (assessment_id, referential_id) WHERE superseded_by IS NULL DO NOTHING` ; (i) downgrade: drop table + ENUM. Doit faire passer T007. **ZONE PROTÉGÉE** : signaler `zone_conflict` si une autre migration est en flight.
- [ ] T011 [P] Mettre à jour les relations sur les modèles existants : ajouter `referential_scores: Mapped[list["ReferentialScore"]]` dans `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/app/models/account.py` (Account) et `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/app/models/esg.py` (EsgAssessment) avec `back_populates` et cascade delete. Vérifier qu'`alembic check` ne génère pas de drift.
- [ ] T012 Exécuter `cd backend && source venv/bin/activate && alembic upgrade head && alembic downgrade -1 && alembic upgrade head` pour valider l'idempotence et la réversibilité. Vérifier visuellement la DB avec `psql $DATABASE_URL -c "\\dt referential_scores"` et `psql $DATABASE_URL -c "SELECT code, version FROM referentials WHERE code IN ('mefali','gcf','ifc_ps','boad_ess','gri_2021');"`.

**Checkpoint** : Table `referential_scores` créée + migrée + backfill réussi. Modèles + schémas Pydantic prêts. Les US peuvent commencer.

---

## Phase 3: User Story 1 — PME bascule entre référentiels et découvre les écarts (Priorité P1) MVP

**Objectif** : la PME ouvre `/esg/results`, voit son score Mefali (78/100), bascule via le sélecteur vers IFC PS (52/100), voit le radar par pilier, le badge coverage, la liste des critères manquants avec sources cliquables F01.

**Independent Test** : créer une `EsgAssessment` avec 35 indicateurs, calculer 5 référentiels via `compute_all_referential_scores`, ouvrir `/esg/results`, vérifier le sélecteur, basculer entre 2 référentiels, vérifier que le score, le radar, les listes critères couverts/manquants changent sans rechargement.

### Tests d'abord (TDD)

- [ ] T013 [P] [US1] Créer le test `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/tests/unit/test_compute_score_for_referential.py` qui valide la fonction refactorée `compute_score_for_referential(referential, indicator_values)` : (a) pondération qui ignore les non-renseignés (pas zéro) ; (b) calcul `coverage_rate` correct ; (c) score `null` si coverage=0 ; (d) `gap_to_threshold` cohérent ; (e) `eligibility=true` si `score >= referentials.threshold` ; (f) traçabilité `source_id` sur `covered_criteria.*` et `missing_criteria.*`. Le test doit ÉCHOUER avant T020.
- [ ] T014 [P] [US1] Créer le test `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/tests/unit/test_multi_referential_service.py` qui valide `compute_all_referential_scores(assessment_id)` : (a) calcule N référentiels en parallèle (asyncio.gather) ; (b) idempotent (UPSERT) ; (c) atomicité par référentiel (échec d'un ne casse pas les autres) ; (d) `audit_log` `referential_score_recompute_partial` créé en cas d'échec partiel ; (e) filtrage `only_referentials_using_indicators` retourne seulement les référentiels concernés. Le test doit ÉCHOUER avant T021.
- [ ] T015 [P] [US1] Créer le test `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/tests/integration/test_referential_scores_router.py` qui valide les endpoints `GET /api/esg/assessments/{id}/referential-scores` et `GET /api/esg/assessments/{id}/referential-scores/history` : (a) liste filtrée par `superseded_by IS NULL` ; (b) historique trié `computed_at DESC` ; (c) RLS multi-tenant : compte B → 404 sur assessment de A ; (d) référentiel inactif filtré. Le test doit ÉCHOUER avant T023.
- [ ] T016 [P] [US1] Créer le test E2E Playwright `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/tests/e2e/F13-scoring-multi-referentiels.spec.ts` (scénario 1 US1) : (a) login PME ; (b) seed assessment finalisé avec 35 indicateurs et 5 référentiels calculés ; (c) ouvrir `/esg/results` ; (d) vérifier que `<ReferentialSelector>` liste les 5 référentiels ; (e) cliquer sur « IFC PS » ; (f) vérifier que `<ReferentialScoreCard>` affiche le score `52/100` et le radar par pilier IFC ; (g) vérifier le badge orange « Couverture indicateurs : 48 % » et le bouton « Inclure dans rapport PDF » désactivé ; (h) cliquer sur un critère manquant dans `<MissingCriteriaList>` et vérifier l'ouverture d'une modale avec `<SourceLink>` cliquable. Le test doit ÉCHOUER avant T026, T028, T029.
- [ ] T017 [P] [US1] Créer le test composant Vitest `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/tests/components/esg/ReferentialSelector.spec.ts` : (a) v-model émet le code du référentiel sélectionné ; (b) liste affichée avec nom et code ; (c) dark mode classes appliquées ; (d) ARIA role `listbox` + options `role="option"`. Le test doit ÉCHOUER avant T026.
- [ ] T018 [P] [US1] Créer le test composant Vitest `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/tests/components/esg/ReferentialScoreCard.spec.ts` : (a) affiche overall_score ; (b) affiche le radar Chart.js par pilier ; (c) affiche le badge orange si `coverage_rate < 0.5` ; (d) gère `overall_score=null` en cachant la card ; (e) dark mode. Le test doit ÉCHOUER avant T028.
- [ ] T019 [P] [US1] Créer le test composant Vitest `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/tests/components/esg/MissingCriteriaList.spec.ts` : (a) liste les critères manquants ; (b) chaque critère a un `<SourceLink>` cliquable F01 ; (c) suggestion affichée si présente ; (d) ouvre une modale au clic ; (e) dark mode + ARIA. Le test doit ÉCHOUER avant T029.

### Implémentation Backend

- [ ] T020 [US1] Refactorer `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/app/modules/esg/service.py` pour exposer une fonction générique `compute_score_for_referential(referential, indicator_values, db)` qui calcule le score selon les indicateurs liés au référentiel + pondération qui ignore les non-renseignés + coverage_rate + covered_criteria/missing_criteria avec source_id F01. **Conserver** `compute_overall_score` 2 sprints en deprecated (cohérence F11/F06). Doit faire passer T013.
- [ ] T021 [US1] Créer `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/app/modules/esg/multi_referential_service.py` avec : (a) `compute_all_referential_scores(assessment_id, only_referentials_using_indicators=None) -> list[ReferentialScore]` (asyncio.gather, atomicité par référentiel via return_exceptions, UPSERT idempotent, audit_log sur échec partiel) ; (b) `compute_referential_score_for_offer(assessment_id, offer_id) -> DualReferentialResponse` (chargement Offer F07, fallback Mefali si fund.referential_id IS NULL, calcul du goulot d'étranglement, audit_log `dual_view_fallback_used`) ; (c) `recompute_score_async(assessment_id, referentiel_id, request_id)` (helper pour BackgroundTasks) ; (d) update colonnes legacy esg_assessments avec score Mefali pour cohérence F11. Doit faire passer T014.
- [ ] T022 [US1] Étendre `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/app/modules/esg/router.py` (existant F05) avec 3 nouveaux endpoints : (a) `GET /api/esg/assessments/{id}/referential-scores` (liste courante, RLS) ; (b) `GET /api/esg/assessments/{id}/referential-scores/history?referential_id=X` (historique `superseded_by IS NOT NULL`) ; (c) `POST /api/esg/assessments/{id}/recompute-score?referentiel_id=X` (enqueue BackgroundTasks, retourne 202 + `recompute_request_id`). Utiliser `Depends(get_db_session_with_rls)` (F02).
- [ ] T023 [US1] Créer le test d'égalité legacy `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/tests/integration/test_legacy_columns_equality.py` qui vérifie après chaque appel à `compute_all_referential_scores` que `referential_scores[Mefali].overall_score == esg_assessments.overall_score` (cohérence F11/F06 transition). Doit passer.
- [ ] T024 [US1] Créer le test sécurité `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/tests/security/test_referential_scores_rls.py` qui valide SC-009 : 2 comptes A et B, B tente l'URL d'A → 404 (pas 403) ; SQL direct simulé via `SET LOCAL app.current_account_id` retourne 0 lignes. Doit passer.

### Implémentation Frontend

- [ ] T025 [P] [US1] Créer/étendre les types TS dans `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/app/types/esg.ts` : `ReferentialScore`, `PillarScore`, `CoveredCriterion`, `MissingCriterion`, `MissingReason`, `ComparisonResult`, `RecomputeRequestResponse`, `BottleneckInfo`, `DualReferentialResponse`. Strict TypeScript (cohérent OpenAPI contracts).
- [ ] T026 [US1] Créer le composable `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/app/composables/useEsgMultiReferential.ts` exposant : `getReferentialScores(assessmentId)`, `getReferentialScoresHistory(assessmentId, referentialId)`, `recomputeScore(assessmentId, referentielId)`, `pollRecomputeStatus(requestId, intervalMs=2000)`. Utilise `$fetch` Nuxt avec gestion d'erreur typée.
- [ ] T027 [P] [US1] Créer le composant `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/app/components/esg/ReferentialSelector.vue` avec props `options: Referential[]`, `modelValue: string`, emits `update:modelValue`. UI : dropdown avec dark mode (`bg-white dark:bg-dark-card`, `text-surface-text dark:text-surface-dark-text`, `border-gray-200 dark:border-dark-border`). ARIA `role="listbox"`. Doit faire passer T017.
- [ ] T028 [US1] Créer le composant `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/app/components/esg/ReferentialScoreCard.vue` avec props `score: ReferentialScore`. Affiche : overall_score, gauge SVG, radar Chart.js par pilier (réutilise composant F05), badge orange si `coverage_rate < 0.5`, bouton « Inclure dans rapport PDF » désactivé si coverage insuffisante (sauf override admin). Cache la card si `score.overall_score === null`. Dark mode complet. Doit faire passer T018.
- [ ] T029 [US1] Créer le composant `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/app/components/esg/MissingCriteriaList.vue` avec props `criteria: MissingCriterion[]`. Liste cliquable, chaque item : titre indicateur + reason badge + `<SourceLink :source-id="criterion.source_id" />` (composant F01) + suggestion. Modale au clic affichant définition + URL source + suggestion d'indicateur Mefali à renseigner. Dark mode + ARIA. Doit faire passer T019.
- [ ] T030 [US1] Mettre à jour `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/app/stores/esg.ts` (Pinia) pour exposer : `referentialScores: ReferentialScore[]`, `selectedReferential: string`, `isRecomputing: boolean`, `recomputeRequestId: string | null`. Getters : `currentScore` (filtré sur `selectedReferential`), `scoresWithCoverageOk` (coverage >= 0.5).
- [ ] T031 [US1] Refactorer `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/app/pages/esg/results.vue` : (a) intégrer `<ReferentialSelector :options="store.referentialScores.map(s => s.referential)" v-model="store.selectedReferential">` ; (b) afficher dynamiquement `<ReferentialScoreCard :score="store.currentScore">` ; (c) afficher `<MissingCriteriaList :criteria="store.currentScore.missing_criteria">` ; (d) bouton « Mode côte-à-côte » qui affiche en grid 2 cards par ligne pour comparer N référentiels ; (e) loading state avec badge « Mise à jour en cours » si `store.isRecomputing` ; (f) dark mode complet ; (g) onMount : `useEsgMultiReferential().getReferentialScores(assessmentId)`. Doit faire passer T016 (partiellement).

### Validation US1

- [ ] T032 [US1] Lancer `cd backend && source venv/bin/activate && pytest tests/unit/test_multi_referential_service.py tests/unit/test_compute_score_for_referential.py tests/integration/test_referential_scores_router.py tests/integration/test_legacy_columns_equality.py tests/security/test_referential_scores_rls.py -v --cov=app/modules/esg --cov-report=term-missing` et vérifier couverture ≥ 80 %.
- [ ] T033 [US1] Lancer `cd frontend && npm run test -- tests/components/esg/ --coverage` et vérifier couverture ≥ 80 % sur les 3 composants.
- [ ] T034 [US1] Lancer `cd frontend && npx playwright test tests/e2e/F13-scoring-multi-referentiels.spec.ts -g "US1" --reporter=html` et vérifier que le scénario 1 passe.

**Checkpoint** : US1 livrable indépendamment. La PME peut basculer entre référentiels et explorer les critères manquants avec sources F01.

---

## Phase 4: User Story 2 — PME consulte une Offre et voit son éligibilité réelle avec goulot d'étranglement (Priorité P1)

**Objectif** : sur `/financing/offers/{id}`, afficher 2 scores (fund + intermediary) côte-à-côte avec bandeau goulot d'étranglement et bouton « Renseigner maintenant ».

**Independent Test** : seeder une offre GCF × BOAD avec leurs référentiels, créer une EsgAssessment finalisée, ouvrir `/financing/offers/{id}` et vérifier dual view + bandeau goulot.

### Tests d'abord (TDD)

- [ ] T035 [P] [US2] Étendre `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/tests/unit/test_multi_referential_service.py` avec tests pour `compute_referential_score_for_offer(assessment_id, offer_id)` : (a) retourne `DualReferentialResponse` avec fund_score et intermediary_score ; (b) fallback Mefali si `fund.referential_id IS NULL` avec `is_fallback=true` ; (c) `is_dual_view=false` si fund.referential == intermediary.referential ; (d) calcul `bottleneck` (`min(fund_score, intermediary_score)`) avec top 3 critères manquants ; (e) audit_log `dual_view_fallback_used` créé. Le test doit ÉCHOUER avant T038.
- [ ] T036 [P] [US2] Créer le test `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/tests/integration/test_offers_router_dual_score.py` qui valide l'extension du router F07 `GET /api/financing/offers/{id}` : (a) la réponse inclut `dual_referential_score` (DualReferentialResponse) si une `EsgAssessment` finalisée existe pour l'utilisateur ; (b) `null` si pas d'assessment ; (c) RLS : utilisateur d'un autre compte voit l'offre sans son score (l'offre est catalogue global, le score est per-tenant). Le test doit ÉCHOUER avant T039.
- [ ] T037 [P] [US2] Étendre `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/tests/e2e/F13-scoring-multi-referentiels.spec.ts` (scénario 2 US2) : (a) seed une offre GCF × BOAD ; (b) seed une EsgAssessment PME finalisée ; (c) ouvrir `/financing/offers/{offer_id}` ; (d) vérifier `<DualReferentialView>` avec score GCF (45/100, gauche) et score BOAD (68/100, droite) ; (e) vérifier la bannière `<BottleneckBanner>` « Goulot d'étranglement : référentiel GCF (45/100) » + bouton « Renseigner maintenant » ; (f) cliquer le bouton et vérifier la redirection vers `/esg?focus=...` ; (g) tester le cas fallback : `fund.referential_id IS NULL` → badge « Référentiel Mefali — fallback ». Le test doit ÉCHOUER avant T040, T041.
- [ ] T038 [P] [US2] Créer le test composant Vitest `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/tests/components/esg/DualReferentialView.spec.ts` : (a) affiche les deux ReferentialScoreCard côte-à-côte ; (b) affiche le BottleneckBanner ; (c) gère le cas `is_dual_view=false` (un seul score) ; (d) gère les fallbacks avec badge spécifique ; (e) dark mode + responsive (grid → stack mobile). Le test doit ÉCHOUER avant T040.
- [ ] T039 [P] [US2] Créer le test composant Vitest `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/tests/components/esg/BottleneckBanner.spec.ts` : (a) affiche le code/nom du référentiel goulot ; (b) liste top 3 critères manquants ; (c) bouton « Renseigner maintenant » émet event `focus-indicators` avec les codes ; (d) gère le cas `eligibility_min=true` (pas de bandeau rouge, juste info) ; (e) dark mode. Le test doit ÉCHOUER avant T041.

### Implémentation Backend

- [ ] T040 [US2] Vérifier que `compute_referential_score_for_offer` (déjà créé en T021) implémente bien tous les cas (fallback Mefali, is_dual_view, bottleneck, top 3 critères). Si lacune, l'étendre. Doit faire passer T035.
- [ ] T041 [US2] Étendre `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/app/modules/financing/router.py` (existant F07) : enrichir `GET /api/financing/offers/{id}` pour inclure `dual_referential_score` si une `EsgAssessment` finalisée existe pour l'utilisateur authentifié (helper `get_latest_finalized_assessment_for_user`). Doit faire passer T036.

### Implémentation Frontend

- [ ] T042 [US2] Créer le composant `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/app/components/esg/DualReferentialView.vue` avec props `dualResponse: DualReferentialResponse`. Layout : grid 2 colonnes desktop, stack mobile. Chaque côté = `<ReferentialScoreCard>` + identifiant (fund/intermediary). Affiche `<BottleneckBanner>` au-dessus si `bottleneck !== null`. Gère les fallbacks avec différenciation visuelle (couleur estompée + badge « Référentiel Mefali — fallback »). Dark mode complet. Doit faire passer T038.
- [ ] T043 [US2] Créer le composant `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/app/components/esg/BottleneckBanner.vue` avec props `bottleneck: BottleneckInfo`. Affiche : titre « Goulot d'étranglement : {bottleneck.bottleneck_referential_name} ({score}/100) », liste top 3 critères, bouton « Renseigner maintenant » qui émet event `focus-indicators` avec `bottleneck.top_3_critical_indicators`. Couleur rouge si `eligibility_min=false`, jaune si `gap > 5`, vert si éligible. Dark mode + ARIA. Doit faire passer T039.
- [ ] T044 [US2] Refactorer `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/app/pages/financing/offers/[id].vue` : ajouter une section « Mon éligibilité pour cette offre » entre le détail offre et les critères/documents. Cette section utilise `<DualReferentialView :dual-response="offer.dual_referential_score">` avec listener `@focus-indicators="navigateTo('/esg?focus=' + indicators.join(','))"`. Affiche un placeholder pédagogique si `dual_referential_score` est null (« Finalisez votre évaluation ESG pour voir votre éligibilité »). Dark mode complet. Doit faire passer T037 (partiellement).

### Validation US2

- [ ] T045 [US2] Lancer `pytest tests/unit/test_multi_referential_service.py tests/integration/test_offers_router_dual_score.py -v` et vérifier couverture ≥ 80 % sur les nouvelles fonctions.
- [ ] T046 [US2] Lancer `cd frontend && npm run test -- tests/components/esg/DualReferentialView.spec.ts tests/components/esg/BottleneckBanner.spec.ts --coverage` et vérifier couverture ≥ 80 %.
- [ ] T047 [US2] Lancer `cd frontend && npx playwright test tests/e2e/F13-scoring-multi-referentiels.spec.ts -g "US2" --reporter=html` et vérifier le scénario 2.

**Checkpoint** : US2 livrable. La PME identifie son goulot d'étranglement avant de candidater.

---

## Phase 5: User Story 3 — PME génère un rapport PDF avec sélection multi-référentiels (Priorité P1)

**Objectif** : sur `/esg/results`, modale « Générer rapport PDF » avec cases à cocher référentiels + annexe sources. Endpoint refactorisé `POST /api/reports/esg/{id}/generate` avec body `{referentials, include_appendix_sources}`. Template Jinja2 refactoré.

**Independent Test** : appeler `POST /api/reports/esg/{id}/generate` avec body `{"referentials": ["mefali", "ifc_ps"], "include_appendix_sources": true}`, vérifier que le PDF résultant contient 2 sections référentiels + tableau comparatif + annexe sources.

### Tests d'abord (TDD)

- [ ] T048 [P] [US3] Créer le test `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/tests/integration/test_reports_router_multi_ref.py` : (a) `POST /api/reports/esg/{id}/generate` avec body multi-référentiels retourne 202 + `report_id` ; (b) défaut `referentials=["mefali"]` (rétrocompat F06) si body vide ; (c) `referentials=["xyz_invalid"]` retourne 422 avec liste codes valides ; (d) PDF contient sections par référentiel + annexe sources si `include_appendix_sources=true` ; (e) bannière « Rapport préliminaire » si un référentiel a `coverage_rate < 0.5` ; (f) RLS multi-tenant. Le test doit ÉCHOUER avant T053.
- [ ] T049 [P] [US3] Créer le test `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/tests/integration/test_pdf_generation_multi_ref.py` qui valide la génération PDF via WeasyPrint : (a) parse le HTML généré pour vérifier la présence des sections ; (b) compare avec snapshot ; (c) vérifie que le PDF est un PDF valide (header `%PDF-`) ; (d) vérifie la taille raisonnable (5 référentiels < 5 Mo) ; (e) génération en < 30s (SC-003). Le test doit ÉCHOUER avant T054.
- [ ] T050 [P] [US3] Étendre `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/tests/e2e/F13-scoring-multi-referentiels.spec.ts` (scénario 3 US3) : (a) ouvrir `/esg/results` avec scores calculés ; (b) cliquer « Générer rapport PDF » ; (c) cocher [Mefali, IFC PS] dans la modale + Inclure annexe sources ; (d) cliquer « Générer » ; (e) polling jusqu'à PDF prêt ; (f) télécharger PDF ; (g) parser le PDF et vérifier : (i) page de garde Mefali, (ii) section Mefali, (iii) section IFC PS avec radar 8 piliers, (iv) tableau comparatif, (v) annexe sources avec URLs cliquables. Le test doit ÉCHOUER avant T055.

### Implémentation Backend

- [ ] T051 [US3] Refactorer `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/app/modules/reports/router.py` : modifier `POST /api/reports/esg/{id}/generate` pour accepter body Pydantic `GenerateReportRequest{referentials: list[str] = ["mefali"], include_appendix_sources: bool = True, format: str = "pdf"}`. Validation des codes via constante `REFERENTIAL_CODES_MVP` ; 422 si invalide avec liste valide. Retourne `GenerateReportResponse` 202.
- [ ] T052 [US3] Refactorer `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/app/modules/reports/service.py` : ajouter `generate_multi_referential_pdf(assessment_id, referentials, include_appendix_sources)` qui : (a) charge les `referential_scores` pour les codes demandés ; (b) charge les sources F01 citées (si annexe demandée) ; (c) appelle `render_template("esg_report.html", context)` avec contexte enrichi (`referentials_data`, `sources_data`, `comparison_table`, `coverage_warnings`) ; (d) génère PDF via WeasyPrint ; (e) sauvegarde dans `/uploads/reports/`. Doit faire passer T048, T049.
- [ ] T053 [US3] Refactorer `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/app/modules/reports/templates/esg_report.html` : (a) section page de garde inchangée ; (b) boucler `{% for ref in referentials_data %}` sur les sections référentiels (chaque section : titre, score global, radar SVG matplotlib, critères couverts/manquants avec liens sources) ; (c) tableau comparatif `indicateur × référentiel` (rendu en Jinja2) ; (d) `{% if include_appendix_sources %}` bloc partial `_appendix_sources.html` ; (e) bannière « Rapport préliminaire » si un référentiel a `coverage_rate < 0.5`.
- [ ] T054 [US3] Créer le partial Jinja2 `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/app/modules/reports/templates/_appendix_sources.html` : liste des sources F01 citées avec URL, page, date d'extraction, statut `verified`. Mise en page tableau pour le PDF.

### Implémentation Frontend

- [ ] T055 [US3] Étendre `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/app/composables/useEsgMultiReferential.ts` avec `generateMultiReferentialReport(assessmentId, referentials, includeAppendixSources): Promise<{report_id, status}>`. Polling helper `pollReportStatus(reportId)`.
- [ ] T056 [US3] Créer la modale `<MultiReferentialReportModal>` dans `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/app/components/esg/MultiReferentialReportModal.vue` : (a) checkboxes pour les référentiels (default Mefali coché) ; (b) checkbox « Inclure annexe sources » (default true) ; (c) bouton « Générer » ; (d) barre de progression pendant génération ; (e) bouton « Télécharger » quand prêt ; (f) dark mode + ARIA modal. Désactive un référentiel si `coverage_rate < 0.5` (sauf override admin).
- [ ] T057 [US3] Intégrer `<MultiReferentialReportModal>` dans `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/app/pages/esg/results.vue` : bouton « Générer un rapport PDF » qui ouvre la modale. Doit faire passer T050.

### Validation US3

- [ ] T058 [US3] Lancer `pytest tests/integration/test_reports_router_multi_ref.py tests/integration/test_pdf_generation_multi_ref.py -v --cov=app/modules/reports` et vérifier couverture ≥ 80 %.
- [ ] T059 [US3] Lancer `cd frontend && npx playwright test tests/e2e/F13-scoring-multi-referentiels.spec.ts -g "US3" --reporter=html` et vérifier le scénario 3.

**Checkpoint** : US3 livrable. La PME peut générer un rapport PDF multi-référentiels avec annexe sources.

---

## Phase 6: User Story 4 — Recalcul asynchrone après modification d'indicateur (Priorité P2)

**Objectif** : `PATCH /api/esg/assessments/{id}/indicator-values` → recalcul async via BackgroundTasks → polling frontend 2s.

### Tests d'abord (TDD)

- [ ] T060 [P] [US4] Créer le test `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/tests/integration/test_indicator_values_recompute_async.py` : (a) PATCH retourne 202 + `recompute_request_id` ; (b) après 5s, les `referential_scores` ont `computed_at` mis à jour ; (c) qu'un seul `IndicatorValue` est créé (pas de duplication, contrainte unique) ; (d) en cas d'échec du job, audit_log `referential_score_recompute_failed` créé. Le test doit ÉCHOUER avant T062.

### Implémentation

- [ ] T061 [US4] Étendre l'endpoint `PATCH /api/esg/assessments/{id}/indicator-values` (existant F05) dans `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/app/modules/esg/router.py` pour : (a) persister `IndicatorValue` synchrone (UPSERT) ; (b) générer `recompute_request_id` UUID ; (c) `background_tasks.add_task(recompute_score_async, assessment_id, only_referentials=...)` filtré sur les référentiels concernés via `only_referentials_using_indicators=[indicator_id]` ; (d) retourner 202 + request_id. Doit faire passer T060.
- [ ] T062 [US4] Étendre `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/app/composables/useEsgMultiReferential.ts` avec : `pollReferentialScores(assessmentId, intervalMs=2000)` qui appelle `getReferentialScores` toutes les 2s jusqu'à voir un `computed_at` plus récent que `recompute_started_at`. Timeout 30s.
- [ ] T063 [US4] Mettre à jour `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/app/pages/esg/results.vue` : afficher un badge « Mise à jour en cours » quand `store.isRecomputing=true`, démarrer le polling au retour de `PATCH`.

### Validation US4

- [ ] T064 [US4] Lancer `pytest tests/integration/test_indicator_values_recompute_async.py -v` et vérifier le polling end-to-end.

**Checkpoint** : US4 livrable. Pattern « 1 saisie = N scores » fonctionnel.

---

## Phase 7: User Story 5 — Versioning F04 et historique défendable (Priorité P2)

**Objectif** : `referential_version` snapshot, pattern `superseded_by`, cron mensuel `check_referential_versions_evolution.py`.

### Tests d'abord (TDD)

- [ ] T065 [P] [US5] Créer le test `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/tests/unit/test_check_referential_versions_evolution.py` : (a) cron détecte `referentials.version` modifiée depuis dernier passage ; (b) crée un reminder F11 `kind='referential_version_evolved'` par PME concernée ; (c) idempotent (2ème exécution ne crée pas de doublon) ; (d) `metadata` JSONB contient `{referential_id, old_version, new_version, delta_summary}` ; (e) audit_log `cron_referential_version_evolution`. Le test doit ÉCHOUER avant T067.
- [ ] T066 [P] [US5] Créer le test `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/tests/integration/test_referential_score_versioning.py` : (a) recalcul après évolution version → nouvelle ligne avec `referential_version='1.2.0'` + ancienne ligne UPDATE `superseded_by=<new_id>` ; (b) un seul score courant garanti par index unique partiel ; (c) `GET /history` retourne triées DESC par `computed_at`. Le test doit ÉCHOUER avant T068.

### Implémentation

- [ ] T067 [US5] Créer le cron `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/scripts/check_referential_versions_evolution.py` : parcourir `referentials` modifiés depuis dernier passage (table `cron_runs.last_run_at` ou file-based marker), pour chaque PME ayant un `referential_scores` sur ce référentiel : créer un `Reminder` F11 idempotent. Doit faire passer T065.
- [ ] T068 [US5] Étendre `multi_referential_service.compute_all_referential_scores` : avant UPSERT, si une ligne existante a `referential_version != référentiel.version` actuel, marquer `superseded_by=<new_id>` plutôt que UPSERT en place. Doit faire passer T066.

### Validation US5

- [ ] T069 [US5] Lancer `pytest tests/unit/test_check_referential_versions_evolution.py tests/integration/test_referential_score_versioning.py -v` et vérifier.
- [ ] T070 [US5] Tester le cron manuellement : modifier `referentials.version` pour IFC PS, lancer `python scripts/check_referential_versions_evolution.py`, vérifier création reminder dans `psql`.

**Checkpoint** : US5 livrable. Score historique défendable + notification opt-in.

---

## Phase 8: User Story 6 — Tools LangChain pour le chat (Priorité P2)

**Objectif** : 3 tools LangChain (`finalize_esg_assessment` refactor + `recompute_score` + `compare_referentials`) avec instrumentation tool_call_logs F12.

### Tests d'abord (TDD)

- [ ] T071 [P] [US6] Créer le test `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/tests/unit/test_esg_tools_multi_ref.py` : (a) `finalize_esg_assessment(assessment_id, referentials_to_compute=["mefali", "ifc_ps"])` retourne `FinalizeAssessmentResult` typé ; (b) `recompute_score(entity_id, referentiel_id)` retourne `RecomputeRequestResponse` ; (c) `compare_referentials(assessment_id, referentials)` retourne `ComparisonResult` avec gaps, divergent_criteria, summary_text ; (d) erreurs structurées : code invalide, assessment inexistant, référentiel inactif ; (e) instrumentation `tool_call_logs` créée pour chaque appel. Le test doit ÉCHOUER avant T073.
- [ ] T072 [P] [US6] Créer le test d'intégration `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/tests/integration/test_chat_with_multi_ref_tools.py` : (a) envoyer un message PME au graph LangGraph « Compare-moi mes scores Mefali et IFC » ; (b) capturer le tool call → `compare_referentials` ; (c) vérifier que la réponse LLM contient les scores et le gap ; (d) vérifier `tool_call_logs` enrichi. Le test doit ÉCHOUER avant T074.

### Implémentation

- [ ] T073 [US6] Refactorer `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/app/graph/tools/esg_tools.py` : (a) refactor `finalize_esg_assessment` pour accepter `referentials_to_compute: list[str] | None = None` (défaut tous actifs) et appeler `compute_all_referential_scores` ; (b) NOUVEAU `recompute_score(entity_id, referentiel_id)` qui enqueue background task ; (c) NOUVEAU `compare_referentials(assessment_id, referentials)` qui retourne `ComparisonResult` + summary_text formaté français. Tous décorés avec `@instrumented_tool` (F12). Doit faire passer T071.
- [ ] T074 [US6] Vérifier l'enregistrement des tools dans `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/app/graph/tools/__init__.py` et le tool selector `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/app/graph/tool_selector_config.py` (zone protégée — minimal touch). Doit faire passer T072.

### Validation US6

- [ ] T075 [US6] Lancer `pytest tests/unit/test_esg_tools_multi_ref.py tests/integration/test_chat_with_multi_ref_tools.py -v --cov=app/graph/tools/esg_tools` et vérifier couverture ≥ 80 %.
- [ ] T076 [US6] Tester manuellement via le chat (cf. quickstart.md §6) : « Compare-moi mes scores selon Mefali et IFC PS » et vérifier la réponse formulée par le LLM.

**Checkpoint** : US6 livrable. Le chat est un acteur dynamique du scoring multi-référentiel.

---

## Phase 9: User Story 7 — Multi-tenant strict (Priorité P3)

**Objectif** : RLS multi-tenant garantit qu'aucun score ne fuite entre comptes.

> Note : déjà couvert par T024 (`test_referential_scores_rls.py`). Cette phase ajoute des tests E2E supplémentaires pour exhaustivité.

### Tests

- [ ] T077 [P] [US7] Étendre `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/tests/security/test_referential_scores_rls.py` avec : (a) `POST /admin/recompute-referential-scores` sans rôle admin → 403 ; (b) super-admin avec `bypass_rls=true` voit les 2 comptes ; (c) cascade ON DELETE : suppression EsgAssessment → suppression scores. Le test doit passer.

### Validation US7

- [ ] T078 [US7] Lancer `pytest tests/security/test_referential_scores_rls.py -v` et vérifier que tous les scénarios passent.

**Checkpoint** : US7 validé. Multi-tenant strict garanti.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Objectif** : finitions, observabilité, documentation, vérifications globales.

### Refactor & Cleanup

- [ ] T079 [P] Vérifier que les fichiers ne dépassent pas 800 lignes (cf. coding-style.md). Si `multi_referential_service.py` > 500 lignes, l'extraire en sous-modules (`compute.py`, `helpers.py`, `audit.py`).
- [ ] T080 [P] Vérifier que les fonctions ne dépassent pas 50 lignes. Refactorer si nécessaire.
- [ ] T081 [P] Linter Python : `cd backend && source venv/bin/activate && python -m py_compile $(find app -name '*.py')` et vérifier zéro erreur.
- [ ] T082 [P] TypeScript : `cd frontend && npx nuxt typecheck` (si dispo) ou `npm run build` pour vérifier zéro erreur de typage strict.
- [ ] T083 [P] Vérifier l'absence de secrets hardcodés : `grep -rE '(api_key|secret|password|token)\s*=\s*["\047][A-Za-z0-9]' backend/app frontend/app` doit ne rien retourner.
- [ ] T084 [P] Dark mode audit : ouvrir chaque page (`/esg/results`, `/financing/offers/*`) en dark mode et vérifier visuellement (pas de zone blanche, contrastes corrects).

### Observabilité

- [ ] T085 [P] Vérifier que les événements `audit_log` sont correctement créés pour : `referential_score_recompute_failed`, `referential_score_recompute_partial`, `dual_view_fallback_used`, `cron_referential_version_evolution`.
- [ ] T086 [P] Vérifier que `tool_call_logs` enrichi pour les 3 nouveaux tools (`finalize_esg_assessment`, `recompute_score`, `compare_referentials`).

### Documentation

- [ ] T087 [P] Mettre à jour `/Users/mac/Documents/projets/2025/esg_mefali_v3/CLAUDE.md` (déjà mis à jour automatiquement par `update-agent-context.sh`) — vérifier que la section « Active Technologies » mentionne F13 et que « Recent Changes » résume F13 (1-2 lignes).
- [ ] T088 [P] Vérifier que `quickstart.md` est exécutable : suivre les 12 étapes manuellement et corriger toute divergence.

### Couverture finale

- [ ] T089 Lancer la suite complète backend : `cd backend && source venv/bin/activate && pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html`. Vérifier couverture globale F13 ≥ 80 % et couverture des modules touchés (`app/modules/esg/`, `app/graph/tools/esg_tools.py`, `app/modules/reports/`, `app/models/referential_score.py`, `app/schemas/referential_score.py`) ≥ 80 %.
- [ ] T090 Lancer la suite complète frontend : `cd frontend && npm run test -- --coverage`. Vérifier couverture des composants F13 ≥ 80 %.
- [ ] T091 Lancer la suite E2E complète : `cd frontend && npx playwright test tests/e2e/F13-scoring-multi-referentiels.spec.ts --reporter=html`. Vérifier que les 3 scénarios passent (US1, US2, US3 P1).

### Performance

- [ ] T092 [P] Benchmark `compute_all_referential_scores` : avec 5 référentiels et 35 indicateurs, mesurer la latence p95. Cible SC-002 < 5s. Si > 5s, optimiser via parallélisation accrue ou batch SELECT.
- [ ] T093 [P] Benchmark génération PDF multi-référentiels : 5 référentiels + annexe sources, < 30s (SC-003).
- [ ] T094 [P] Benchmark bascule UI sélecteur : < 500ms (SC-001) — vérifier via Playwright timing.

---

## Dependencies & Story Completion Order

### Graph de dépendances par phase

```
Phase 1 (Setup) ──→ Phase 2 (Foundational) ──→ ┬─→ Phase 3 (US1 P1) ─┐
                                                ├─→ Phase 4 (US2 P1) ─┤
                                                ├─→ Phase 5 (US3 P1) ─┤
                                                ├─→ Phase 6 (US4 P2) ─┤
                                                ├─→ Phase 7 (US5 P2) ─┼─→ Phase 10 (Polish)
                                                ├─→ Phase 8 (US6 P2) ─┤
                                                └─→ Phase 9 (US7 P3) ─┘
```

### Dépendances inter-stories

- **US1, US2, US3** sont **P1 parallélisables** entre elles après Phase 2 (chacune touche des fichiers majoritairement disjoints).
- **US4** dépend de US1 (réutilise `compute_all_referential_scores` et le composable `useEsgMultiReferential`).
- **US5** dépend de US1 (réutilise le pattern `superseded_by` introduit en T010).
- **US6** dépend de US1 (réutilise les services `compute_all_referential_scores` et `compute_referential_score_for_offer`).
- **US7** dépend de Phase 2 (RLS appliquée par migration T010).
- **Phase 10 (Polish)** dépend de toutes les phases précédentes.

### Tâches parallélisables [P] dans la même phase

- Phase 2 : T005, T006, T007 (tests TDD parallèles) ; T008, T009, T011 (modèles/schémas/relations en // mais pas avec T010 qui est zone protégée).
- Phase 3 (US1) : tests T013-T019 en // ; implémentation T025, T027, T029 en //.
- Phase 4 (US2) : tests T035-T039 en // ; implémentation T042, T043 en // après T040.
- Phase 5 (US3) : tests T048-T050 en // ; implémentation T054 en // de T053.
- Phase 6 (US4) : test T060 en // d'autres phases.
- Phase 7 (US5) : tests T065, T066 en //.
- Phase 8 (US6) : tests T071, T072 en //.
- Phase 10 (Polish) : T079-T088 en //, T092-T094 en //.

---

## Implementation Strategy (MVP First)

### MVP Recommandé (US1 + US2 + US3 P1)

Livrer ensemble **Phase 1 + Phase 2 + Phase 3 (US1) + Phase 4 (US2) + Phase 5 (US3)**, soit T001-T059. Cela donne :

- Sélecteur multi-référentiels fonctionnel.
- Dual view goulot d'étranglement sur les offres.
- PDF multi-référentiels avec annexe sources F01.
- Migration BDD + seed + backfill complets.
- Couverture tests ≥ 80 % sur les chemins MVP.
- 3 scénarios E2E Playwright passants.

### Incréments post-MVP (US4-US7 P2/P3)

Ajouter ensuite :
- **US4 (Phase 6)** : recalcul async polling (améliore UX exploration indicateurs).
- **US5 (Phase 7)** : cron versioning + reminders F11 (résilience long terme).
- **US6 (Phase 8)** : tools LangChain chat (UX conversationnelle).
- **US7 (Phase 9)** : tests RLS exhaustifs (déjà couverts par T024 en MVP).
- **Phase 10 (Polish)** : finitions, performance benchmarks, documentation.

### Critères d'arrêt par feature

- Phase A (spec/plan/tasks) : `analyze_status=ok|warnings`, ≤ 2 retries.
- Phase B (implementation) : `tests_status=ok`, couverture ≥ 80 %, ≤ 5 itérations correction.
- Phase B' (E2E) : 3 scénarios Playwright passent (les 3 P1 minimum, idéalement les 7 user stories).

---

## Validation finale (avant PR)

- [ ] Tous les tests unit + integration backend passent (`pytest tests/`).
- [ ] Couverture backend ≥ 80 % (`pytest --cov=app`).
- [ ] Tous les tests composants frontend passent (`npm run test`).
- [ ] Couverture frontend ≥ 80 % (`npm run test -- --coverage`).
- [ ] 3 scénarios E2E Playwright passent (`npx playwright test`).
- [ ] Migration up/down/up réversible (`alembic upgrade head && alembic downgrade -1 && alembic upgrade head`).
- [ ] Zéro secret hardcodé.
- [ ] Dark mode complet sur tous les nouveaux composants.
- [ ] Français avec accents corrects partout.
- [ ] Aucune zone protégée modifiée hors stricte nécessité.
- [ ] PR créée avec label `auto-generated, F13` (cf. orchestrator).
