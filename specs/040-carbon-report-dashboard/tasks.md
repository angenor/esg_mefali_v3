# Tasks: F21 — Dashboard par Offre + Carte Intermédiaires + Rapport Carbone PDF

**Feature** : F21 (spec 040)
**Branch** : `feat/F21-dashboard-par-offre-rapport-carbone`
**Stack** : FastAPI + SQLAlchemy async + WeasyPrint + Jinja2 + matplotlib (backend) ; Nuxt 4 + Pinia + TailwindCSS + Leaflet (frontend) ; Playwright E2E.
**Migration** : AUCUNE (`alembic_or_migration = false`).
**TDD** : tests AVANT implémentation (constitution principe IV).
**Couverture cible** : ≥ 80 % sur le périmètre F21.

Inputs traités : `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/*.{yml,json}`, `quickstart.md`.

## Conventions

- `[P]` = peut être exécuté en parallèle (fichier distinct, pas de dépendance non résolue).
- `[US1]…[US5]` = mappe à une user story de la spec.
- Tests AVANT implémentation à l'intérieur de chaque user story.

---

## Phase 1 : Setup

- [ ] T001 Créer le squelette de répertoires backend `backend/app/modules/reports/carbon/` (avec `__init__.py`, `templates/`, `services et fichiers vides`) et `backend/app/core/uemoa_capitals.py` (skeleton)
- [ ] T002 [P] Créer le squelette de répertoires frontend `frontend/app/components/dashboard/`, `frontend/app/components/reports/`, `frontend/app/types/carbon-report.ts` (vide)
- [ ] T003 [P] Vérifier les dépendances Python (WeasyPrint, Jinja2, matplotlib) sont installées (déjà OK depuis F06 ; lancer `pip list | grep -iE 'weasyprint|jinja2|matplotlib'`)

---

## Phase 2 : Foundational (blocant pour toutes les user stories)

- [ ] T004 [P] Écrire les tests unitaires `backend/tests/unit/core/test_uemoa_capitals.py` couvrant : 8 entrées présentes (BEN/BFA/CIV/GNB/MLI/NER/SEN/TGO), bornes lat/lon plausibles UEMOA, fallback fonction `get_capital_coordinates(country)` (cas trouvé / cas inconnu retourne None)
- [ ] T005 Implémenter `backend/app/core/uemoa_capitals.py` : constante `UEMOA_CAPITAL_COORDINATES` (8 capitales) + helper `get_capital_coordinates(country: str) -> tuple[float, float] | None` (alpha-2 et alpha-3 supportés)
- [ ] T006 [P] Étendre les schémas Pydantic dashboard dans `backend/app/modules/dashboard/schemas.py` : ajouter `ApplicationCard`, `ActiveIntermediary`, `ScoreSourceRef`, `ScoreBlock` étendu (champ `sources: list[ScoreSourceRef]`)
- [ ] T007 [P] Créer les schémas Pydantic carbon report dans `backend/app/modules/reports/carbon/schemas.py` : `CarbonReportRequest`, `CarbonReportResponse`, `CarbonReportListItem`
- [ ] T008 [P] Créer les exceptions dans `backend/app/modules/reports/carbon/exceptions.py` : `AssessmentNotFinalizedError`, `ConcurrentGenerationError`, `AssessmentNotFoundError`
- [ ] T009 [P] Étendre les types TypeScript frontend dans `frontend/app/types/dashboard.ts` : `ApplicationCard`, `ActiveIntermediary`, `ScoreSourceRef`, `ApplicationStatus`, `IntermediaryType` ; créer `frontend/app/types/carbon-report.ts` : `CarbonReportStatus`, `CarbonReportListItem`

---

## Phase 3 : User Story 1 — Cards de candidatures par Offre (P1) [US1]

**Story Goal** : Afficher au plus 5 cards par offre sur le dashboard avec libellé d'étape FR, deadline et lien détail.

**Independent Test** : créer 3 candidatures sur 3 offres distinctes, ouvrir `/dashboard`, observer 3 cards distinctes.

### Tests (avant implémentation)

- [ ] T010 [P] [US1] Tests unitaires `backend/tests/unit/modules/dashboard/test_service_applications_by_offer.py` : `_get_financing_summary` retourne `applications_by_offer` ≤ 5 ; tri `last_activity_at` desc ; mapping statut → libellé FR (8 statuts) ; fallback intermédiaire « Accès direct » ; format `next_deadline`
- [ ] T011 [P] [US1] Tests intégration `backend/tests/integration/test_dashboard_summary.py` : endpoint `GET /api/dashboard/summary` renvoie `financing.applications_by_offer` conforme au contrat OpenAPI ; isolation RLS multi-tenant (deux comptes ne se voient pas)
- [ ] T012 [P] [US1] Tests Vitest `frontend/tests/components/ApplicationStatusCard.test.ts` : props rendues, libellé FR, format date `DD/MM/YYYY`, dark mode, ARIA, click bouton « Voir détail » émet event ou navigue
- [ ] T013 [P] [US1] Tests Vitest `frontend/tests/composables/useDashboard.test.ts` (extension F21) : champ `applicationsByOffer` typé et exposé

### Implémentation backend

- [ ] T014 [US1] Refactor `backend/app/modules/dashboard/service.py` : `_get_financing_summary` joint `FundApplication` + `Offer` + `Fund` + `Intermediary` via `selectinload`, calcule `last_activity_at`, mappe statut → `current_step` (helper `_status_to_step_fr`), borne à 5 entrées triées desc
- [ ] T015 [US1] Étendre `DashboardSummary` (Pydantic) pour exposer `financing.applications_by_offer: list[ApplicationCard]` aux côtés des compteurs existants

### Implémentation frontend

- [ ] T016 [P] [US1] Créer `frontend/app/components/dashboard/ApplicationStatusCard.vue` : props `card: ApplicationCard`, rend logos, fund_name, intermediary_name, badge statut, deadline, bouton « Voir détail » → `/applications/{id}`. Dark mode + ARIA.
- [ ] T017 [US1] Créer `frontend/app/components/dashboard/ApplicationStatusCardList.vue` : reçoit `cards: ApplicationCard[]` (max 5), rend liste verticale + lien « Voir toutes mes candidatures » → `/applications` quand >5 actives. État vide explicite (lien `/financing/offers`).
- [ ] T018 [US1] Étendre `frontend/app/composables/useDashboard.ts` : champ `applicationsByOffer` exposé depuis le payload `/api/dashboard/summary`
- [ ] T019 [US1] Refactor `frontend/app/pages/dashboard.vue` : injecter `<ApplicationStatusCardList>` à la place du compteur global, dark mode complet
- [ ] T020 [US1] Étendre `frontend/app/stores/dashboard.ts` : state `applicationsByOffer`, getter, mutation lors du fetch

**Checkpoint US1** : `/dashboard` affiche 3 cards distinctes pour 3 candidatures actives liées à 3 offres.

---

## Phase 4 : User Story 2 — Rapport Carbone PDF (P1) [US2]

**Story Goal** : Endpoint + générateur PDF 9 sections sourcées F01 + tool LangChain + bouton frontend.

**Independent Test** : finaliser un bilan carbone, cliquer sur « Générer rapport carbone PDF », vérifier les 9 sections + annexe sources dans le PDF téléchargé.

### Tests (avant implémentation)

- [ ] T021 [P] [US2] Tests unitaires `backend/tests/unit/modules/reports/carbon/test_schemas.py` : `CarbonReportRequest` defaults, `CarbonReportResponse` champs requis, `CarbonReportListItem` sérialisation
- [ ] T022 [P] [US2] Tests unitaires `backend/tests/unit/modules/reports/carbon/test_equivalences.py` : km voiture / vols / foyers / FCFA calculés à partir de tCO2e ; flag `is_sourced` + `source_id` ou « Recommandation générale (non sourcée) »
- [ ] T023 [P] [US2] Tests unitaires `backend/tests/unit/modules/reports/carbon/test_chart_builder.py` : pie chart breakdown SVG produit ; bar chart comparaison sectorielle ; line chart évolution multi-années ; format SVG bytes
- [ ] T024 [P] [US2] Tests unitaires `backend/tests/unit/modules/reports/carbon/test_sources_collector.py` : agrège `EmissionFactor.source_id` + `tool_call_logs(tool_name='cite_source')` ; numérotation `[1], [2]…` stable ; pas de doublons ; fallback « Recommandation générale (non sourcée) »
- [ ] T025 [P] [US2] Tests unitaires `backend/tests/unit/modules/reports/carbon/test_pdf_renderer.py` : rend HTML Jinja2 avec contexte minimal, vérifie présence des 9 sections, dates `DD/MM/YYYY`, annexe sources, validator `source_required.py` invoqué (mock)
- [ ] T026 [P] [US2] Tests unitaires `backend/tests/unit/modules/reports/carbon/test_service.py` : `generate_carbon_report(assessment_id, account_id)` refuse si non finalisé (`AssessmentNotFinalizedError`), refuse si concurrent (`ConcurrentGenerationError`), crée Report `pending`, dispatche BackgroundTask
- [ ] T027 [P] [US2] Tests intégration `backend/tests/integration/test_carbon_report_endpoint.py` : POST 202 (succès), 422 (non finalisé), 409 (concurrent), 403 (autre account), 404 (introuvable) ; polling `GET /api/reports/{id}` reflète transitions ; `GET /api/reports/{id}/download` renvoie 200 + PDF
- [ ] T028 [P] [US2] Tests intégration `backend/tests/integration/test_audit_log_carbon_report.py` : génération PDF inscrit `audit_log(action='create:Report', source_of_change='manual')` ; via tool LangChain → `source_of_change='llm'`
- [ ] T029 [P] [US2] Tests unitaires `backend/tests/unit/graph/tools/test_generate_carbon_report_tool.py` : args Pydantic strict, `additionalProperties:false`, resolve account_id depuis RunnableConfig, retour structuré `{ok, report_id, status, message}`, gestion erreurs typées
- [ ] T030 [P] [US2] Tests Vitest `frontend/tests/components/CarbonReportButton.test.ts` : désactivé si bilan non finalisé ou génération en cours, déclenche POST, polling, toast prêt
- [ ] T031 [P] [US2] Tests Vitest `frontend/tests/composables/useCarbonReports.test.ts` : `generate(assessmentId)`, `pollStatus(reportId)`, `download(reportId)`, gestion erreurs

### Implémentation backend

- [ ] T032 [P] [US2] Créer `backend/app/modules/reports/carbon/equivalences.py` : helper `compute_equivalences(total_tco2e: Decimal) -> list[Equivalence]` avec lookup F01 (whitelist facteurs ADEME) ; flag `unsourced=True` quand pas de source vérifiée
- [ ] T033 [P] [US2] Créer `backend/app/modules/reports/carbon/chart_builder.py` : helpers `build_breakdown_pie_svg(entries)`, `build_sector_comparison_bar_svg(...)`, `build_yearly_line_svg(...)` (matplotlib SVG bytes)
- [ ] T034 [P] [US2] Créer `backend/app/modules/reports/carbon/sources_collector.py` : `collect_sources(assessment_id) -> list[NumberedSource]` (agrège `emission_factors.source_id` + `tool_call_logs(cite_source)`, dédup par `source_id`, numérote)
- [ ] T035 [US2] Créer `backend/app/modules/reports/carbon/templates/_carbon_appendix_sources.html` : partial Jinja2 numéroté `[n]` + libellé / éditeur / version / date / URL
- [ ] T036 [US2] Créer `backend/app/modules/reports/carbon/templates/carbon_report.html` : template 9 sections (Cover, Synthèse, Breakdown, Comparaison sectorielle, Évolution multi-années, Plan de réduction, Équivalences pédagogiques, Méthodologie, Annexe Sources via include) ; filtre `format_date_fr`
- [ ] T037 [US2] Créer `backend/app/modules/reports/carbon/pdf_renderer.py` : `render_carbon_pdf(context: dict, output_path: Path) -> None` (Jinja2 + WeasyPrint + invocation `source_required.py` validator)
- [ ] T038 [US2] Créer `backend/app/modules/reports/carbon/service.py` : `async def generate_carbon_report(db, assessment_id, account_id, source: Literal['manual','llm']='manual') -> Report` ; vérifications (ownership, finalized, concurrent), INSERT Report `pending`, dispatch `BackgroundTasks` (worker `_render_carbon_pdf(report_id)` qui transite `generating` → `ready`/`failed`)
- [ ] T039 [US2] Étendre `backend/app/modules/reports/router.py` : ajouter `POST /api/reports/carbon/{assessment_id}/generate` (auth `Depends(get_current_user)`, BackgroundTasks, retour 202 `CarbonReportResponse`) ; tirer parti du `GET /api/reports/{id}` et `/download` existants F06
- [ ] T040 [US2] Étendre `backend/app/graph/tools/carbon_tools.py` : tool LangChain `generate_carbon_report` (Pydantic args strict, `source_of_change_scope('llm')`, retour JSON structuré conforme `contracts/tool-generate-carbon-report.json`)
- [ ] T041 [US2] Câbler le tool dans `MODULE_TOOL_MAPPING['carbon']` et `PAGE_TOOL_MAPPING['carbon_results']` (fichier `app/graph/tool_selector_config.py`) ; le binder dans le ToolNode `carbon` (`graph.py` + `nodes.py`)

### Implémentation frontend

- [ ] T042 [P] [US2] Créer `frontend/app/composables/useCarbonReports.ts` : `generate(assessmentId)`, `getStatus(reportId)`, `pollUntilReady(reportId, {timeoutMs:30000, intervalMs:2000})`, `download(reportId)`
- [ ] T043 [P] [US2] Créer `frontend/app/components/reports/CarbonReportButton.vue` : props `assessmentId`, `isFinalized`, état chargement/désactivé, déclenche `useCarbonReports.generate`, toast in-app, dark mode, ARIA
- [ ] T044 [US2] Étendre `frontend/app/pages/carbon/results.vue` : intégrer `<CarbonReportButton>` ; désactivé si bilan non finalisé ou génération en cours

### Audit & sourçage

- [ ] T045 [US2] Vérifier que `Report` figure dans `AUDITABLE_MODELS` ; sinon l'ajouter (tâche purement déclarative, pas de migration)
- [ ] T046 [US2] Vérifier dans le test d'intégration que `cite_source` est invoqué pour les chiffres clés (tCO2e total, intensité, scope 1/2/3) — ajout de `cite_source` calls dans le pipeline de finalisation si manquant

**Checkpoint US2** : `POST /api/reports/carbon/{id}/generate` aboutit sur un PDF 9 sections sourcé téléchargeable.

---

## Phase 5 : User Story 3 — Carte UEMOA des intermédiaires actifs (P2) [US3]

**Story Goal** : Endpoint `active-intermediaries` + composant `<IntermediariesMap>` consommant `<MapBlock>` F11 + fallback capitale.

**Independent Test** : 2 intermédiaires actifs (1 avec lat/lon, 1 sans) → 2 markers sur la carte, popup complet, fallback capitale visible.

### Tests (avant implémentation)

- [ ] T047 [P] [US3] Tests unitaires `backend/tests/unit/modules/dashboard/test_active_intermediaries_service.py` : agrège candidatures actives + projets ouverts ; dédup par `intermediary_id` ; calcule `applications_count` ; fallback capitale via `get_capital_coordinates` quand lat/lon null ; flag `is_fallback_capital`
- [ ] T048 [P] [US3] Tests intégration `backend/tests/integration/test_dashboard_active_intermediaries.py` : endpoint `GET /api/dashboard/active-intermediaries` ; 401 sans auth ; isolation RLS multi-tenant ; payload conforme contrat OpenAPI
- [ ] T049 [P] [US3] Tests Vitest `frontend/tests/components/IntermediariesMap.test.ts` : rend `<MapBlock>` avec markers `type=intermediary`, popup contenu, état vide message + lien `/financing/intermediaries`, dark mode

### Implémentation backend

- [ ] T050 [US3] Implémenter dans `backend/app/modules/dashboard/service.py` la fonction `get_active_intermediaries(db, account_id) -> list[ActiveIntermediary]` (agrégation candidatures non clôturées + projets ouverts, jointures Fund pour `accreditations`, fallback capitale)
- [ ] T051 [US3] Ajouter dans `backend/app/api/dashboard_router.py` la route `GET /api/dashboard/active-intermediaries` (Pydantic response model, `Depends(get_current_user)`)
- [ ] T052 [US3] Étendre `_get_financing_summary` (ou le composer) pour également exposer `active_intermediaries` dans `GET /api/dashboard/summary`

### Implémentation frontend

- [ ] T053 [P] [US3] Créer `frontend/app/components/dashboard/IntermediariesMap.vue` : reçoit `intermediaries: ActiveIntermediary[]` + lazy-load `MapBlock` (F11) ; popup : nom, type, pays, accréditations, applications_count, lien fiche ; état vide
- [ ] T054 [US3] Câbler la map dans `frontend/app/pages/dashboard.vue` (section dédiée) ; dark mode complet via `useMapTiles` (F11)
- [ ] T055 [US3] Étendre `frontend/app/composables/useDashboard.ts` et `frontend/app/stores/dashboard.ts` pour propager `activeIntermediaries`

**Checkpoint US3** : carte UEMOA affiche markers intermédiaires + popups complets, fallback capitale fonctionne.

---

## Phase 6 : User Story 4 — Scores cliquables vers sources (P2) [US4]

**Story Goal** : ScoreCard expose `<SourceLink>` (F01) ou badge « Non sourcé ».

**Independent Test** : ouvrir `/dashboard` avec score ESG sourcé, cliquer icône source, modale `<SourceModal>` s'ouvre avec sources F01/F13.

### Tests (avant implémentation)

- [ ] T056 [P] [US4] Tests unitaires `backend/tests/unit/modules/dashboard/test_score_sources.py` : helper `collect_score_sources(account_id, score_type)` agrège tool_call_logs(cite_source) + referential_indicators (F13) ; dédup par source_id
- [ ] T057 [P] [US4] Tests Vitest `frontend/tests/components/ScoreCard.f21.test.ts` : props `sources: ScoreSourceRef[]` rend `<SourceLink>` ; sans sources → badge `Non sourcé` ; click ouvre `<SourceModal>` ; dark mode

### Implémentation backend

- [ ] T058 [US4] Implémenter `collect_score_sources(...)` dans `backend/app/modules/dashboard/service.py` (lecture seule) et l'injecter dans `ScoreBlock.sources` pour ESG, carbon, credit
- [ ] T059 [US4] Mettre à jour le payload de `GET /api/dashboard/summary` pour inclure les sources des scores (extension Pydantic + tests intégration mis à jour)

### Implémentation frontend

- [ ] T060 [US4] Étendre `frontend/app/components/dashboard/ScoreCard.vue` : prop `sources?: ScoreSourceRef[]` ; rend `<SourceLink>` (F01) si non vide, sinon badge `Non sourcé` ; dark mode

**Checkpoint US4** : score ESG sourcé sur dashboard, click → SourceModal F01.

---

## Phase 7 : User Story 5 — Rapports Carbone listés sur /reports (P2) [US5]

**Story Goal** : tabs ESG | Carbone sur `/reports` avec download.

**Independent Test** : générer un rapport carbone, ouvrir `/reports`, cliquer onglet Carbone, télécharger.

### Tests (avant implémentation)

- [ ] T061 [P] [US5] Tests intégration `backend/tests/integration/test_reports_list_carbon.py` : `GET /api/reports?type=carbon` filtre correctement, tri date desc, RLS multi-tenant
- [ ] T062 [P] [US5] Tests Vitest `frontend/tests/pages/reports-index.f21.test.ts` (ou composant équivalent) : 2 tabs visibles, compteurs, listes, download button rend bon download_url

### Implémentation backend

- [ ] T063 [US5] Étendre `backend/app/modules/reports/router.py` : `GET /api/reports` accepte query `?type=carbon|esg` (filtrage) — sinon ajouter `GET /api/reports/carbon` dédié si plus simple
- [ ] T064 [US5] Étendre `backend/app/modules/reports/service.py` : `list_reports(account_id, report_type=None) -> list[CarbonReportListItem | EsgReportListItem]`

### Implémentation frontend

- [ ] T065 [US5] Refactor `frontend/app/pages/reports/index.vue` : composant `<Tabs>` avec onglets « ESG » et « Carbone » ; charge listes via composable approprié (`useCarbonReports.list()` + composable ESG existant)
- [ ] T066 [US5] Étendre `frontend/app/stores/reports.ts` : state séparés pour ESG et Carbon ; actions `fetchEsg()`, `fetchCarbon()`

**Checkpoint US5** : `/reports` propose ESG | Carbone et permet le téléchargement.

---

## Phase 8 : Polish & Cross-Cutting

- [ ] T067 [P] Créer `frontend/app/components/dashboard/RecentActivityCard.vue` : reçoit 5 derniers événements F03, lien `/historique`, dark mode (FR-023)
- [ ] T068 [P] Câbler `RecentActivityCard` dans `frontend/app/pages/dashboard.vue` (section Activité récente)
- [ ] T069 [P] Filtre Jinja2 `format_date_fr` : créer `backend/app/lib/date_fr.py` (helper) si absent ; enregistrer dans l'environnement Jinja2 commun aux rapports F06 et F21
- [ ] T070 [P] Spec Playwright `frontend/tests/e2e/F21-dashboard-carbon-report.spec.ts` : 4 scénarios (cards par offre, carte intermédiaires + popup, génération PDF + téléchargement, score cliquable → SourceModal)
- [ ] T071 [P] Vérifier la couverture backend ≥ 80 % sur les chemins F21 : `cd backend && pytest --cov=app/modules/reports/carbon --cov=app/modules/dashboard --cov=app/core/uemoa_capitals --cov=app/graph/tools/carbon_tools --cov-report=term-missing`
- [ ] T072 [P] Vérifier la couverture frontend ≥ 80 % via `cd frontend && npm run test -- --coverage`
- [ ] T073 [P] Mettre à jour `CLAUDE.md` (section Recent Changes) avec un résumé F21 (les 5 user stories, NO MIGRATION, dépendances réutilisées)
- [ ] T074 Documentation `docs/carbon-report.md` : architecture (réutilise F06), 9 sections du PDF, sourçage F01, fallback capitale, anti-concurrence
- [ ] T075 Round-trip dépendances : exécuter la suite complète `cd backend && pytest` + `cd frontend && npm run test` + `npx playwright test tests/e2e/F21-*.spec.ts` ; corriger toute régression

---

## Dependency Graph (User Stories)

```
Setup (Phase 1)
   ↓
Foundational (Phase 2: T004→T009)
   ↓
   ├──── US1 (P1) — applications_by_offer
   ├──── US2 (P1) — rapport carbone PDF
   ├──── US3 (P2) — carte intermédiaires
   ├──── US4 (P2) — scores cliquables
   └──── US5 (P2) — onglet Carbone /reports  (dépend de US2 pour avoir des rapports à lister)
                ↓
            Polish (Phase 8)
```

- US1 et US2 sont indépendants et peuvent être parallélisés.
- US3 et US4 sont indépendants entre eux et indépendants de US1/US2.
- US5 dépend fonctionnellement de US2 pour avoir un cas de test complet (mais peut être implémenté en parallèle avec mock).

## Parallel Execution Examples

**Foundational** (3 développeurs ou 3 sessions parallèles) :
- T004 + T006 + T007 + T008 + T009 sont tous `[P]` (fichiers distincts).

**US1** :
- T010, T011, T012, T013 (tests) en parallèle.
- T014 puis T015 séquentiels (même fichier `service.py` + `schemas.py`).
- T016, T018 en parallèle (fichiers distincts).
- T017 dépend de T016 ; T019 dépend de T017 ; T020 indépendant.

**US2** :
- T021, T022, T023, T024, T025, T026, T027, T028, T029, T030, T031 (tests) en parallèle.
- T032, T033, T034 (helpers indépendants) en parallèle.
- T035 → T036 → T037 → T038 → T039 → T040 → T041 séquentiels (chaîne).
- T042, T043 en parallèle, T044 dépend de T043.

**US3** :
- T047, T048, T049 en parallèle.
- T050 → T051 → T052 séquentiels.
- T053 indépendant ; T054 dépend de T053.

**US4** :
- T056, T057 en parallèle.
- T058 → T059 séquentiels ; T060 indépendant côté frontend.

**US5** :
- T061, T062 en parallèle ; T063 → T064 séquentiels ; T065 → T066 séquentiels.

**Polish** : T067–T075 majoritairement `[P]`, sauf T075 qui agrège.

## Implementation Strategy — MVP First

**MVP** = US1 + US2 (les 2 P1).

1. Compléter Setup + Foundational.
2. Livrer US1 (cards par offre) — dashboard immédiatement utile.
3. Livrer US2 (rapport carbone PDF) — promesse Module 7.2.
4. Itérer US3 / US4 / US5 selon retour utilisateur.

## Test Format Validation

Tous les tasks ci-dessus respectent le format `- [ ] T### [P?] [USx?] Description with file path`.

---

**Total tasks** : 75
- Phase 1 Setup : 3
- Phase 2 Foundational : 6
- Phase 3 US1 : 11 (tests 4 + impl backend 2 + impl frontend 5)
- Phase 4 US2 : 26 (tests 11 + impl backend 11 + impl frontend 3 + audit 1)
- Phase 5 US3 : 9 (tests 3 + impl backend 3 + impl frontend 3)
- Phase 6 US4 : 5 (tests 2 + impl backend 2 + impl frontend 1)
- Phase 7 US5 : 6 (tests 2 + impl backend 2 + impl frontend 2)
- Phase 8 Polish : 9

**Indépendamment testable** :
- US1 : ouvrir /dashboard, voir 3 cards.
- US2 : générer un PDF carbone, vérifier 9 sections + annexe.
- US3 : voir markers intermédiaires sur la carte UEMOA.
- US4 : cliquer score ESG → SourceModal F01.
- US5 : ouvrir /reports → onglet Carbone → télécharger.
