# Tasks — F14 Matching Projet ↔ Offre

Légende : `[P]` = parallélisable, `[D:X]` = dépend de la tâche X.

## Phase B1 — Backend models & migration

- **T01** — Créer `backend/app/models/offer_match.py` (`OfferMatch` SQLAlchemy avec mixins UUIDMixin/TimestampMixin, 4 CHECK, UNIQUE, 5 indexes, relations selectin). Ajouter à `AUDITABLE_MODELS`.
- **T02** [P] — Créer `backend/app/models/match_alert_subscription.py` (`MatchAlertSubscription` avec UNIQUE project_id, CHECK min_score). Ajouter à `AUDITABLE_MODELS`.
- **T03** [D:T01,T02] — Tests unitaires modèles : `tests/models/test_offer_match.py`, `tests/models/test_match_alert_subscription.py` (validation CHECK, UNIQUE, defaults, relations).
- **T04** [D:T01,T02] — Migration Alembic `036_offer_matches_and_alerts.py` : down_revision = dernière migration sur main au moment du Phase B (cf. `git log --oneline -- backend/alembic/versions/`). CREATE TABLE × 2, RLS PG-only, backfill SQL idempotent ON CONFLICT DO NOTHING, downgrade DROP. Round-trip up/down/up validé.
- **T05** [D:T04] — Tests migration : `tests/test_alembic_036.py` (round-trip, structure, indexes, CHECK, RLS policies, backfill idempotent).

## Phase B2 — Schemas & service

- **T06** [D:T01] — Schemas Pydantic v2 `backend/app/modules/financing/matching_schemas.py` : `OfferMatchRead`, `OfferMatchListResponse`, `OfferMatchDetail`, `MatchSubBreakdown`, `ScoreBreakdown`, `MissingCriterion`, `RecomputeMatchesResponse`, `ComparisonResult`, `MatchAlertSubscriptionRead`, `MatchAlertSubscriptionUpdate` (`frozen=True` sur les value objects, `from_attributes=True`).
- **T07** [D:T06] — Tests schemas : `tests/modules/financing/test_matching_schemas.py` (validation Literal bottleneck/status, ge/le, frozen).
- **T08** [D:T01,T06] — Service `backend/app/modules/financing/matching_service.py` :
  - Constante `MATCHING_WEIGHTS` (sector=0.25, esg=0.30, size=0.15, location=0.10, documents=0.10, instrument=0.10)
  - `compute_offer_match(db, project_id, offer_id) -> OfferMatch` : load Project + Offer (selectin), load latest finalized ESGAssessment (assessment_missing flag si None), compute 5 sub-scores, déléguer ESG à `compute_referential_score_for_offer` (F13), bottleneck rule, UPSERT in-place
  - `_compute_sector_match(project, fund) -> int` (binaire 100/0)
  - `_compute_size_match(project, fund) -> int` (graduel linéaire ±50% via Money typed F04 + currency conversion)
  - `_compute_location_match(project, fund) -> int` (binaire)
  - `_compute_documents_match(project, offer) -> int` (ratio 0-100)
  - `_compute_instrument_match(project, fund) -> int` (binaire)
  - `_compute_bottleneck(fund_score, intermediary_score) -> str` (règle déterministe ±10)
  - `_build_recommended_actions(missing_criteria) -> list[dict]` (top 3 actions FR)
  - `list_matches_for_project(db, account_id, project_id, filters) -> tuple[list, int]` (RLS-aware via session)
  - `recompute_matches_for_project(db, project_id) -> RecomputeMatchesResponse` (BackgroundTasks dispatch, cap 50 offres)
  - `compare_offers_for_fund(db, project_id, fund_id) -> ComparisonResult` (génère subjects + rows F11)
  - `get_match_details(db, project_id, offer_id) -> OfferMatchDetail`
- **T09** [D:T08] — Tests service : `tests/modules/financing/test_matching_service.py` (~30 cas : compute avec ESG present/absent, sub-scores fronts, bottleneck rules tous chemins, recompute UPSERT in-place, cap 50 offres, list pagination + filters, compare cohérent multi-offres).
- **T10** [D:T01,T02] — Service alertes `backend/app/modules/financing/alerts_service.py` :
  - `subscribe_to_alerts(db, account_id, project_id) -> MatchAlertSubscription` (idempotent)
  - `unsubscribe_from_alerts(db, project_id) -> None` (set is_active=False)
  - `update_subscription(db, project_id, payload) -> MatchAlertSubscription`
  - `notify_new_offer_matches(db) -> NotificationResult` (cron logic : pick subscriptions actives → recompute → if new match score>=min → create Reminder F19 → mark last_notified_at)
- **T11** [D:T10] — Tests alertes : `tests/modules/financing/test_alerts_service.py` (~10 cas : auto-subscribe sur création projet, idempotence, toggle, notify nouveau match, idempotence du cron via last_notified_at).

## Phase B3 — Hooks & cron

- **T12** [D:T08] — Event listeners `backend/app/modules/financing/matching_hooks.py` : `after_update` Project (champs déclencheurs), `after_update` Offer (is_active/publication_status/effective_*). Schedule async via FastAPI BackgroundTasks. ContextVar `_recompute_in_progress` pour anti-récursion.
- **T13** [D:T12] — Tests hooks : `tests/modules/financing/test_matching_hooks.py` (4 cas : trigger sur project update, trigger sur offer update, anti-récursion, cap 50).
- **T14** [D:T08] — Cron `backend/scripts/recompute_stale_matches.py` (idempotent, picks WHERE expires_at < now(), batch 100, audit source=import).
- **T15** [D:T10] — Cron `backend/scripts/notify_new_offer_matches.py` (idempotent via last_notified_at).
- **T16** [D:T14,T15] — Tests crons : `tests/scripts/test_cron_matching.py` (~6 cas : idempotence, batch limit, audit log F03 source=import).

## Phase B4 — Router REST & tools LangChain

- **T17** [D:T08,T10] — Router `backend/app/modules/financing/matching_router.py` : 5 endpoints (`GET /matches`, `POST /recompute-matches`, `GET /compare`, `GET /match-details/{offer_id}`, `PATCH /match-alerts`). Tous protégés par `Depends(get_current_user)` avec RLS PG via `set_rls_context`.
- **T18** [D:T17] — Tests router : `tests/modules/financing/test_matching_router.py` (~20 cas : 5 endpoints × happy path + 401 + 404 RLS + 422 validation + filters + pagination + 202 BackgroundTasks).
- **T19** [D:T08] — Tools LangChain `backend/app/graph/tools/matching_tools.py` : 4 tools (`list_matches_for_project`, `compare_offers_for_fund`, `recompute_matches_for_project`, `get_match_details`) avec `args_schema` Pydantic strict, `source_of_change_scope('llm')` sur mutations, sérialisation JSON. `compare_offers_for_fund` émet le marker SSE `<!--SSE:{"__sse_visualization_block__":true,"block_type":"comparison_table",...}-->`.
- **T20** [D:T19] — Tests tools : `tests/graph/tools/test_matching_tools.py` (~15 cas : args validation, sérialisation, marker SSE, scope source_of_change, gestion erreurs).
- **T21** [D:T19] — Injection tools dans 3 nœuds via `app/graph/tools/tool_selector_config.py` :
  - `MODULE_TOOL_MAPPING['chat']` += MATCHING_READ_TOOLS
  - `MODULE_TOOL_MAPPING['financing']` += MATCHING_TOOLS (4)
  - `MODULE_TOOL_MAPPING['application']` += MATCHING_TOOLS (4)
  - `PAGE_TOOL_MAPPING['profile_projects']` += MATCHING_READ_TOOLS
  - Borne `MAX_TOOLS_PER_TURN` portée de 14 à 18
- **T22** [D:T19,T21] — Refactor `compare_offers_for_fund` existant (F07 stub) → délégation à F14 implémentation. Test conformity `test_compare_offers_for_fund_uses_f14.py`.
- **T23** [D:T17] — Tests RLS PostgreSQL : `tests/security/test_offer_matches_rls.py` (~5 cas : pme ne voit que son account, admin voit tout, INSERT bloqué cross-account, RLS FORCE actif).

## Phase B5 — Audit & conformity

- **T24** [D:T01,T02] — Validation Audit F03 : `OfferMatch` et `MatchAlertSubscription` ajoutés à `AUDITABLE_MODELS`. Tests : `tests/modules/audit/test_audit_offer_match.py` (~5 cas : INSERT/UPDATE/DELETE tracés, source_of_change correct).
- **T25** [D:T17] — Test conformity `tests/conformity/test_no_fund_match_writes.py` : grep AST sur le code F14 → aucun `db.add(FundMatch(...))` ou `INSERT INTO fund_matches`.
- **T26** [D:T19] — Test conformity `tests/conformity/test_no_skill_mutation_in_matching.py` : aucun tool F14 ne mute Skills (pattern interdit).

## Phase F1 — Frontend types & composable & store

- **T27** [P] — Types TypeScript `frontend/app/types/matching.ts` (8 interfaces miroir Pydantic).
- **T28** [D:T27] — Composable `frontend/app/composables/useMatching.ts` (8 méthodes : listMatches, recomputeMatches, compareOffersForFund, getMatchDetails, subscribeToAlerts, unsubscribeFromAlerts, pollMatchesAfterRecompute, getMatchById). `useFetchAuth` Bearer token.
- **T29** [D:T28] — Tests composable : `frontend/tests/unit/composables/useMatching.test.ts` (~12 cas : 8 méthodes × happy path + 401 + 404 + 422).
- **T30** [D:T27] — Store Pinia `frontend/app/stores/matches.ts` (state matchesByProject/comparisonsByFund/subscriptionsByProject + getters getActiveMatches, getBottleneck, getTopMatch + mutations).
- **T31** [D:T30] — Tests store : `frontend/tests/unit/stores/matches.test.ts` (~10 cas : state, getters, mutations).

## Phase F2 — Composants Vue

- **T32** [D:T27] — `frontend/app/components/matching/BottleneckBadge.vue` : pastille colorée (rouge fund / amber intermediary / vert balanced), tooltip ARIA `aria-describedby`, dark mode (`dark:bg-red-950 dark:border-red-800` etc).
- **T33** [D:T27] — `frontend/app/components/matching/MatchScoreBreakdown.vue` : graphe radar 5 axes en SVG natif, ARIA `role="img" aria-label`, dark mode (stroke `dark:stroke-emerald-400`).
- **T34** [D:T27] — `frontend/app/components/matching/MissingCriteriaList.vue` : extrait simplifié de F13 + `<SourceLink>` (F01) par critère, dark mode complet.
- **T35** [D:T27] — `frontend/app/components/matching/MatchAlertToggle.vue` : switch ARIA `role=switch aria-checked`, persiste via API, dark mode.
- **T36** [D:T32,T33,T34] — `frontend/app/components/matching/OffersCompatibleSection.vue` : section pour `/profile/projects/[id]` avec liste de `<MatchCard>` (F11 réutilisée), bouton « Comparer N intermédiaires », empty state, dark mode complet.
- **T37** [D:T32,T33,T34,T35,T36] — Tests composants Vitest : `frontend/tests/unit/components/matching/*.test.ts` (~25 tests : 5 composants × empty/with data/dark mode/ARIA/events).

## Phase F3 — Pages Vue

- **T38** [D:T28,T30,T36] — Extension `frontend/app/pages/profile/projects/[id].vue` : ajouter `<OffersCompatibleSection>` après les sections existantes. Toggle « Recevoir des alertes » via `<MatchAlertToggle>`.
- **T39** [D:T28,T30] — Nouvelle page `frontend/app/pages/profile/projects/[id]/matches.vue` : liste paginée tous les matches, filtres URL-synchronisés (`min_score`, `bottleneck`, `fund_id`), empty state.
- **T40** [D:T28,T30] — Nouvelle page `frontend/app/pages/financing/compare/[fund_id].vue` : query `?project_id=X` obligatoire (redirige sinon), header explicite, `<ComparisonTableBlock>` (F11) avec lignes Score/Frais/Délais/Documents/Track record/Bottleneck, bouton CTA « Démarrer ma candidature » par colonne.
- **T41** [D:T28,T30,T33,T34] — Extension `frontend/app/pages/financing/offers/[offer_id].vue` : section « Mon score pour ce projet » avec sélecteur de projet (Pinia `projects.activeProjects`), affichage décomposé fund/intermediary, critères manquants cliquables vers `<SourceModal>` (F01).
- **T42** [D:T38,T39,T40,T41] — Tests pages Vitest : `frontend/tests/unit/pages/matching-pages.test.ts` (~10 cas : routing, query params, empty states, redirects).

## Phase F4 — E2E Playwright

- **T43** [D:T17,T28,T30,T38,T39,T40,T41] — Helpers `frontend/tests/e2e/F14-helpers.ts` : mock backend complet (matching API + comparator + projects + offers + sources F01).
- **T44** [D:T43] — Spec `frontend/tests/e2e/F14-matching-projet-offre.spec.ts` (4 scénarios) :
  1. US1 : créer projet → page projet → section Offres compatibles affiche ≥ 1 MatchCard avec score décomposé
  2. US2 : naviguer `/financing/compare/[fund_id]?project_id=X` → table comparative ≥ 2 colonnes intermédiaires + highlight gagnant
  3. US3 : cliquer critère manquant → SourceModal F01 s'ouvre avec source verified
  4. US4 : toggle « Recevoir des alertes » → confirmation visuelle + état persisté après refresh

## Phase F5 — Documentation & finalisation

- **T45** — Documentation `docs/matching-offers.md` : modèle conceptuel projet↔offre, règles bottleneck, formule pondération MATCHING_WEIGHTS, cycle de vie d'un match, troubleshooting RLS, ajout d'un nouveau sub-score.
- **T46** [D:tous] — Verification finale : couverture ≥ 80 % (`pytest --cov=app.modules.financing.matching_service --cov=app.models.offer_match --cov=app.modules.financing.alerts_service --cov=app.graph.tools.matching_tools`), aucune régression sur les ~2693 tests baseline, lint backend (ruff) + frontend (eslint), build frontend OK, round-trip Alembic OK.
- **T47** [D:T46] — Mise à jour `CLAUDE.md` (entrée Recent Changes pour F14).
- **T48** [D:T47] — Commit conventional `feat(F14): matching projet/offre + comparateur multi-intermédiaires + alertes nouvelles offres`.

---

## Tasks count : **48**

## Parallelization map

- T01 + T02 (modèles indépendants)
- T27 (types frontend) en parallèle de toute la phase B1-B5
- T32, T33, T34, T35 (composants atomiques) en parallèle après T27
- T14, T15 (crons) en parallèle après leurs services
- Phase F1-F2-F3 entièrement parallélisable avec phase B5 si contrats stables

## Critical path

T01/T02 → T04 → T08 → T17 → T19/T21 → T28/T30 → T38/T39/T40 → T44 → T46
