# Cross-Artifact Analysis: F19 — Cron Dispatcher Rappels + Auto-création

**Date** : 2026-05-07
**Auteur** : SpecKit Phase A (autonome, post `/speckit.tasks`)
**Status** : OK — pas de blocage critique identifié

## Vue d'ensemble

| Artefact | Taille | Conformité |
|----------|--------|------------|
| spec.md | 6 user stories, 25 FR, 10 SC, 10+ assumptions, 9 edge cases | ✓ Format respecté |
| plan.md | Technical context complet, structure projet, 10 risks/mitigations, 8 acceptance gates | ✓ Format respecté |
| research.md | 15 décisions documentées (R1-R15) | ✓ Couvre toutes les ambiguïtés |
| data-model.md | Schéma extension reminders + dedup_key + audit events + frontend store | ✓ Schémas complets |
| quickstart.md | 11 sections (démarrage, debug, E2E manuel, idempotence, migration) | ✓ Actionnable |
| contracts/ | 3 fichiers (event JSON Schema, REST endpoints, jobs config) | ✓ JSON Schema valides |
| tasks.md | 68 tâches en 9 phases, mapping US correct | ✓ Format respecté |

## Couverture FR → Tasks

| FR | Description | Coverage | Tasks |
|----|-------------|----------|-------|
| FR-001 | APScheduler lifespan | ✓ | T017, T035, T038 |
| FR-002 | 9 jobs cron + 1 housekeeping | ✓ | T021, T024, T026, T028, T030, T032, T037, T038 |
| FR-003 | Migration 034 (3 cols + index) | ✓ | T009, T010, T011 |
| FR-004 | dispatch_reminders FOR UPDATE SKIP LOCKED + batch 100 | ✓ | T019, T020, T021 |
| FR-005 | SSE `reminder_due` après dispatch | ✓ | T015, T021 |
| FR-006 | UPSERT `ON CONFLICT DO NOTHING` pour dedup | ✓ | T024, T026, T028, T030 |
| FR-007 | silence radio 14j sans activité | ✓ | T025, T026 |
| FR-008 | assessment renewal J-30 avant 365j | ✓ | T027, T028 |
| FR-009 | attestation expiration J-30 | ✓ | T029, T030 |
| FR-010 | deadline J-30/J-7/J-1 | ✓ | T023, T024 |
| FR-011 | F02 multi-tenant scope account_id | ✓ | T020, T024-T030, T057 |
| FR-012 | F03 audit log sur création | ✓ | T021, T024-T030, T056 |
| FR-013 | startReminderPolling activé | ✓ | T049, T052 |
| FR-014 | NotificationCenter cloche header | ✓ | T050, T051, T052 |
| FR-015 | Toasts variantes par type | ✓ | T044, T055, T047 |
| FR-016 | ReminderForm activé dans /action-plan | ✓ | T053, T054 |
| FR-017 | Dedup SSE+polling par reminder_id | ✓ | T045, T046 |
| FR-018 | PATCH /reminders/{id}/read | ✓ | T042, T043 |
| FR-019 | GET /reminders/notifications | ✓ | T042, T043 |
| FR-020 | useNotificationsStore Pinia | ✓ | T045, T046 |
| FR-021 | purge_old_reminders hebdo | ✓ | T031, T032 |
| FR-022 | docs/cron-scheduler.md | ✓ | T062 |
| FR-023 | test_apscheduler_starts_only_once | ✓ | T034 |
| FR-024 | test_no_cross_account_reminder_leak | ✓ | T057 |
| FR-025 | Migration `down_revision="033_create_skills"` | ✓ | T010 |

**Conclusion** : 25/25 FR couverts par au moins une tâche.

## Couverture User Stories → Tasks

| US | Priority | Tasks | Tests TDD inclus | Indépendant ? |
|----|----------|-------|------------------|---------------|
| US1 (Dispatcher SSE) | P1 | T013-T016, T019-T022 (8) | T013, T019, T020 | ✓ après Phase 2 |
| US2 (Auto-création reminders) | P1 | T023-T032 (10) | T023, T025, T027, T029, T031 | ✓ après Phase 2 |
| US3 (APScheduler lifespan) | P1 | T017-T018, T033-T041 (11) | T018, T033, T034, T040 | ✓ après Phase 2 |
| US4 (Frontend NotificationCenter) | P2 | T042-T055 (14) | T042, T045, T047, T050 | ✓ après US3 |
| US5 (Migration + audit log) | P1 | T009-T012, T056-T058 (7) | T009, T012, T056, T057 | ✓ Phase 2 + 7 |
| US6 (E2E tests) | P1 | T059-T061 (3) | — (E2E test self-test) | ✓ après US1+US2 |

**Conclusion** : Chaque US a sa story indépendamment livrable + tests TDD avant implémentation. US4 (P2) peut être livrée après les US1/US2/US3 (P1) pour le MVP.

## Couverture Success Criteria

| SC | Description | Comment vérifié |
|----|-------------|-----------------|
| SC-001 | 100 % reminders dûs dispatchés < 5 min | T019, T020, mesure logs prod |
| SC-002 | 0 doublon par auto-création | T024, T026, T028, T030 (idempotence tests) |
| SC-003 | NotificationCenter render < 200ms | T050 + Playwright performance assertion |
| SC-004 | Coverage ≥ 80 % sur scheduler + notifications | T065 |
| SC-005 | 0 régression sur 935+ tests existants | T064 |
| SC-006 | E2E assessment J-30 < 30s | T059 |
| SC-007 | E2E silence radio < 30s | T060 |
| SC-008 | APScheduler boot < 500ms | T035 + benchmark logs |
| SC-009 | Migration 034 sur 10k reminders < 5s | Manual perf test (post-T010) |
| SC-010 | 0 fuite cross-account | T057 |

**Conclusion** : 10/10 SC couverts.

## Détection d'incohérences

### Cohérences vérifiées (vert)

1. **Migration Alembic** — `down_revision="033_create_skills"` cohérent avec dernière migration F23 mergée.
2. **Spec number 034** — disponible (specs/ contient jusqu'à 033).
3. **Modèle Reminder** — la table existe (`backend/app/models/action_plan.py:263`), extension par migration nullable + default false → zero-downtime.
4. **Scripts existants F04/F05/F07/F13** — vérifiés présents dans `backend/scripts/` et `backend/app/scripts/`. Wrappers minimaux suffisent.
5. **Frontend dead code** — `useActionPlan.startReminderPolling` (lignes 250-269) et `ReminderForm.vue` confirmés présents et inutilisés.
6. **APScheduler dans requirements** — vérifié absent de `requirements.txt` (à ajouter par T001).
7. **F02 multi-tenant** — modèle Reminder a déjà `account_id` (ligne 278-282) → cohérent avec FR-011.
8. **F03 audit log** — listener `Auditable` existe (`app.core.auditable`), import dans `main.py` ligne 15. F19 ajoute juste les events `reminder_created/dispatched/archived`.
9. **Format dedup_key** — `{account_id}:{type}:{entity_id}:{trigger_date}` lisible, < 255 chars, indexable.
10. **Compat SQLite/PostgreSQL** — patterns documentés (R5, R9, R15) : `ON CONFLICT DO NOTHING` natif SQLite, `FOR UPDATE SKIP LOCKED` skipé en SQLite, `CREATE INDEX CONCURRENTLY` PG-only.

### Points d'attention (non-bloquants)

1. **`fund_favorites` table** — la fiche F19 mentionne un fond favori. Vérification : cette table n'existe peut-être pas encore. **Décision F19** : si absente, le job `create_deadline_reminders` skip cette source au MVP (commentaire TODO dans le code, sera complété quand la table sera créée). Documenté dans clarifications via "vérifier dans le data-model.md".

2. **`fund_applications.last_status_update`** — colonne référencée par `create_silence_radio_reminders`. Vérifier qu'elle existe (sinon utiliser `updated_at` ou créer la colonne dans la migration). **Action** : ajouter une vérification au début de T026 et adapter si besoin.

3. **Enum `attestation_renewal`** — la fiche F19 le suggère implicitement. Migration 034 doit gérer son ajout conditionnel (déjà documenté dans T010 + data-model.md).

4. **SSE bus existant vs nouveau** — le code base a probablement déjà un bus SSE (utilisé par le chat). Au lieu de créer un nouveau bus, F19 doit le réutiliser. **Action** : audit de `app/services/` ou `app/api/sse.py` au début de T014. Si présent, étendre. Sinon, créer le helper minimal.

5. **`read` column** — pas certain qu'elle existe déjà sur la table reminders. Migration T010 fait un `inspect` conditionnel. Documenté.

6. **Lock fichier en Docker/K8s** — POSIX `fcntl.flock` peut être fragile en environnement containerisé. **Mitigation** : env var `APSCHEDULER_ENABLED` est la méthode primaire. Lock fichier est best-effort secondaire. Documenté dans research.md (R3).

7. **APScheduler timezone** — configuré sur UTC. Les utilisateurs en fuseaux différents (UEMOA/CEDEAO sont UTC+0, mais Cap-Vert UTC-1) verront leurs `scheduled_at` en UTC. Frontend convertit en local. Pas de bug, mais clarifier dans la doc.

8. **CSV parsing `DEADLINE_REMINDER_DAYS`** — Pydantic v2 nécessite un validator pour parser CSV depuis env. **Action** : implémenter dans T017 avec `field_validator`.

### Risques mitigés

| Risque | Mitigation |
|--------|------------|
| Régression tests existants | T064 (run pytest complet) |
| Migration bloque grosse table | `CREATE INDEX CONCURRENTLY` (R9) |
| Race condition dispatch | `FOR UPDATE SKIP LOCKED` (R4) + test T020 |
| Fuite cross-account | F02 strict + test T057 |
| Toast spam | Plafond 5 visibles, agrégation NotificationCenter |
| Single-process limitation | Documenté `docs/cron-scheduler.md` (T062) |
| Fail silencieux APScheduler | Health endpoint `/api/admin/scheduler/health` (T041) |
| Backfill dedup_key corrompt | NULL par défaut, pas de transformation forcée |
| ReminderForm cassé après période dead code | Audit T053 + fix mineur si KO |

## Conformité Architecture

- **Modules existants modifiés** : 4 fichiers (`main.py`, `models/action_plan.py`, `core/config.py`, `api/routers/action_plan.py`).
- **Modules nouveaux backend** : 12 fichiers dans `app/scheduler/` (scheduler.py, lock.py, 10 jobs) + 3 fichiers dans `app/services/notifications/` (sse_bus.py, reminder_notifier.py, schemas.py) + 1 router admin (`app/api/routers/admin_scheduler.py`).
- **Modules nouveaux frontend** : 1 composant (`NotificationCenter.vue`), 1 store (`stores/notifications.ts`), 1 composable (`useNotifications.ts`), 1 type file (`types/reminders.ts`).
- **Modules modifiés frontend** : 4 fichiers (`layouts/default.vue`, `composables/useActionPlan.ts`, `composables/useToast.ts`, `pages/action-plan/index.vue`).
- **Migration** : 1 (`034_reminder_dedup_key.py`).
- **Tests nouveaux backend** : 12+ fichiers (unit/integration/e2e).
- **Tests nouveaux frontend** : 3 fichiers (specs Vitest + 1 Playwright).
- **Doc** : 1 fichier (`docs/cron-scheduler.md`).

**Total** : ~ 35 fichiers nouveaux + 8 fichiers modifiés.

## Conformité Sécurité

- ✓ Endpoints admin debug protégés par `Depends(require_admin_role)` + feature flag `ADMIN_DEBUG_SCHEDULER` (off par défaut en prod).
- ✓ Endpoints user (PATCH read, GET notifications) filtrent strictement par `account_id` (F02). Test T057 garde-fou.
- ✓ Pas de hardcoded secret. Toutes les configs via env vars.
- ✓ Pas de tool LangChain `create_reminder` / `delete_reminder` (LLM ne mute jamais les reminders).
- ✓ Validation Pydantic sur query params (limit max 50, types stricts).
- ✓ Audit log F03 sur create/dispatch/archive (immuable).

## Conformité Performance

- ✓ Dispatch < 2s P95 pour 100 reminders (R13).
- ✓ Migration 034 zero-downtime (`CONCURRENTLY` + nullable).
- ✓ Index unique partiel pour la dédup (taille < 5 MB en steady state).
- ✓ APScheduler boot < 500ms (SC-008).
- ✓ NotificationCenter render < 200ms (SC-003).

## Conformité Tests

- ✓ TDD obligatoire (test avant impl) — T009, T012, T013, T019, T020, T023, T025, T027, T029, T031, T033, T034, T040, T042, T045, T047, T050, T056, T057.
- ✓ Couverture ≥ 80 % (rule globale) — T065.
- ✓ Tests E2E inclus (US6) — T059, T060, T061.
- ✓ 0 régression — T064.
- ✓ Markers pytest standardisés : `unit`, `integration`, `e2e`, `scheduler`.

## Conformité Frontend

- ✓ Dark mode obligatoire (T051, T054, T055).
- ✓ Réutilisabilité : map `TOAST_VARIANT_BY_TYPE` partagée, store Pinia centralisé.
- ✓ Pas de duplication : utilise composants existants (`ConfirmDialog`, `useToast` étendu).
- ✓ Composition API : `<script setup lang="ts">` partout.
- ✓ Pinia state immuable (actions, pas de mutation directe).

## Garde-fous métier

- ✓ Pas de reminder créé sans `dedup_key` pour les types métier (US2).
- ✓ Pas de double dispatch (FOR UPDATE SKIP LOCKED).
- ✓ Pas de fuite cross-account (F02 strict).
- ✓ Pas de DELETE physique de reminders (préservation audit log F03).
- ✓ Toast variantes différenciées par type pour UX claire (`intermediary_followup` bleu vs autres orange/rouge).
- ✓ Idempotence tous les jobs auto-création.

## Statut

**ANALYZE STATUS: OK** — aucun blocage critique. Le feature est prêt pour `/speckit.implement`.

Points mineurs à confirmer en implémentation :

1. **Audit `fund_favorites`** : vérifier si la table existe au début de T024. Si absente, skip cette source au MVP (commenté).
2. **Audit `fund_applications.last_status_update`** : vérifier si la colonne existe au début de T026. Sinon, utiliser `updated_at` ou créer.
3. **Audit `read` column sur reminders** : vérifier dans la migration T010 (déjà géré conditionnellement).
4. **Audit `attestation_renewal` enum value** : vérifier dans la migration T010 (déjà géré conditionnellement).
5. **Audit SSE bus existant** : au début de T014, vérifier `app/services/sse_bus.py`, `app/api/sse.py`, ou similaire. Réutiliser si présent.
6. **Audit `useToast` existant** : T008 vérifie. Si absent, créer minimal.
7. **Audit `ReminderForm.vue`** : T053 fait l'audit complet avant intégration.

## Prochaines étapes

1. ✓ Commit SpecKit artifacts (`chore(F19): SpecKit artifacts (spec/plan/tasks/analyze)`).
2. `/speckit.implement` ou implémentation manuelle dans une session dédiée (~ 30-45h dev).
3. Valider chaque US indépendamment (P1 d'abord, P2 ensuite).
4. Run `pytest backend/tests/ -m "unit or integration"` localement.
5. Run E2E `pytest backend/tests/e2e/test_f19_*.py`.
6. Frontend : `npm run test` + `npm run test:e2e`.
7. PR avec test plan détaillé.
