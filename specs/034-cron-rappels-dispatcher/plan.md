# Implementation Plan: F19 — Cron Dispatcher Rappels + Auto-création Alertes

**Branch**: `feat/F19-cron-rappels-dispatcher` | **Date**: 2026-05-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/034-cron-rappels-dispatcher/spec.md`

## Summary

F19 active l'infrastructure de cron jobs et de notifications du Module 6 (Plan d'Action). Aujourd'hui, le modèle `Reminder` existe et l'endpoint de création manuelle fonctionne, mais **aucun job cron ne tourne, aucun reminder n'est dispatché, le polling frontend est dead code, le composant `ReminderForm` est dead code**. F19 corrige cette inopérance.

3 capacités principales :

1. **Backend cron infrastructure** : `APScheduler 3.10+` intégré au lifespan FastAPI (`AsyncIOScheduler`). 9 jobs cron : 1 dispatcher (5 min) + 4 auto-création reminders + 4 jobs existants câblés (F04 fetch_exchange_rates, F05 purge_scheduled_deletions, F07 check_expired_accreditations, F13 check_referential_versions_evolution) + 1 housekeeping hebdomadaire.
2. **Migration 034** : ajout `dedup_key`, `sent_at`, `archived`, éventuellement `read` et `attestation_renewal` enum value sur la table `reminders`. Index unique partiel sur `(account_id, dedup_key)`.
3. **Frontend NotificationCenter + activations dead code** : composant `<NotificationCenter>` (cloche header + dropdown + badge), composable `useNotifications.ts`, store `useNotificationsStore` (Pinia), activation `startReminderPolling` dans `default.vue`, activation `ReminderForm.vue` dans `/action-plan` via modal, toasts variantes par `ReminderType`.

Inclut aussi : 2 nouveaux endpoints REST (`PATCH /api/action-plan/reminders/{id}/read`, `GET /api/action-plan/reminders/notifications`), tests unit/integration/E2E (couverture ≥ 80 %), audit log F03 sur création/dispatch/archive, doc `docs/cron-scheduler.md`, garde-fou single-process (lock fichier ou env var pour uvicorn `--workers 4`).

## Technical Context

**Language/Version** : Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies** :
- Backend : FastAPI, **APScheduler ≥ 3.10**, SQLAlchemy async, Alembic, Pydantic v2, asyncpg
- Frontend : Nuxt 4, Vue Composition API, Pinia, TailwindCSS, EventSource (SSE natif)

**Storage** : PostgreSQL 16 + pgvector — extension table `reminders` avec 3 colonnes (potentiellement 4 si `read` absente), 1 index unique partiel, 1 valeur enum potentielle (`attestation_renewal`).

**Testing** : pytest + pytest-asyncio (markers `unit`, `integration`, `e2e`, `scheduler`). Frontend : Vitest + Vue Test Utils (composants), Playwright (E2E).

**Target Platform** : Linux server (uvicorn) / GitHub Actions CI (Ubuntu 22.04).

**Project Type** : web-service (mono-repo backend/ + frontend/).

**Performance Goals** :
- `dispatch_reminders` : < 2s P95 pour 100 reminders/run (1 SQL `UPDATE ... RETURNING` + N notify SSE en parallèle)
- `create_deadline_reminders` : < 10s P95 pour 1000 applications (1 SQL JOIN + N inserts en batch UPSERT)
- APScheduler boot : < 500ms (cf SC-008)
- NotificationCenter render : < 200ms (cf SC-003)
- Migration 034 sur 10k reminders : < 5s (cf SC-009)

**Constraints** :
- MVP single-process APScheduler. Documenter migration Celery/Redis post-MVP.
- Aucune régression sur les 935+ tests backend existants (cf SC-005).
- Zero-downtime migration : colonnes nullable, index `CONCURRENTLY` en prod.
- F02 multi-tenant strict : aucune fuite cross-account (cf SC-010, FR-011, FR-024).
- F03 audit log obligatoire sur create/dispatch/archive (FR-012).

**Scale/Scope** :
- 1 migration Alembic (034)
- 1 nouveau module backend `app/scheduler/` avec 9 jobs + scheduler.py + lifespan integration
- 1 nouveau module backend `app/services/notifications/` (SSE bus + helpers)
- 2 nouveaux endpoints REST
- 1 nouveau composant frontend (`<NotificationCenter>`)
- 2 nouveaux composables/store frontend (`useNotifications.ts`, `stores/notifications.ts`)
- 2 activations dead code (polling, ReminderForm)
- ~12 nouveaux fichiers backend, ~6 nouveaux fichiers frontend, ~6 fichiers modifiés (main.py, default.vue, action-plan/index.vue, useActionPlan.ts, etc.)

## Constitution Check

Pas de fichier constitution active dans ce projet (vérification : `/Users/mac/Documents/projets/2025/esg_mefali_v3/.specify/memory/`). Gates standards appliqués :

- **Test coverage** : ≥ 80 % minimum (rule globale) — couvert par tests unit/integration/E2E.
- **Sécurité** : F02 RLS strict (jobs filtrent par account_id), F03 audit log sur toute mutation, pas de fuite cross-account (test conformity).
- **Performance** : `FOR UPDATE SKIP LOCKED` pour la concurrence, batch limit 100 reminders, index unique partiel pour la dédup.
- **Immutabilité** : pas de mutation in-place des reminders existants (sauf `sent`, `sent_at`, `read`, `archived` — états de cycle de vie). Pas de modification du `message` ou du `scheduled_at` après création.
- **Pas de mutation par LLM** : aucun tool LangChain `create_reminder` / `delete_reminder` exposé (les rappels sont créés par les jobs cron et l'endpoint REST manuel — JAMAIS par le LLM).
- **Versioning F04** : table `reminders` ne fait pas partie du référentiel versionné (data utilisateur, pas catalogue). Pas de `VersioningMixin` requis.
- **F02 multi-tenant** : `account_id` obligatoire sur tous les nouveaux reminders créés par les jobs. Test conformity.

## Project Structure

### Documentation (this feature)

```text
specs/034-cron-rappels-dispatcher/
├── spec.md                  # Spec finalisée avec clarifications
├── plan.md                  # Ce fichier
├── research.md              # Phase 0 — recherche APScheduler patterns, FOR UPDATE SKIP LOCKED, SSE
├── data-model.md            # Phase 1 — schéma reminders étendu + dedup_key + audit events
├── quickstart.md            # Phase 1 — démarrer scheduler local, déclencher job manuel, debug
├── contracts/
│   ├── reminder_dispatched_event_schema.json   # Format payload SSE reminder_due
│   ├── notification_center_endpoints.md         # Spec REST des 2 nouveaux endpoints
│   └── apscheduler_jobs_config.md               # Doc des 9 jobs (trigger, fonction, params)
├── checklists/
│   └── quality.md           # Checklist qualité spec
├── analyze.md               # Output /speckit.analyze
└── tasks.md                 # Phase 2 — output /speckit.tasks
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/
│   └── 034_reminder_dedup_key.py           # NOUVEAU — migration 034
├── app/
│   ├── scheduler/                           # NOUVEAU module
│   │   ├── __init__.py
│   │   ├── scheduler.py                     # Instance AsyncIOScheduler + lifespan helper
│   │   ├── lock.py                          # Lock fichier pour single-process
│   │   └── jobs/
│   │       ├── __init__.py
│   │       ├── dispatch_reminders.py        # NOUVEAU — dispatcher 5 min
│   │       ├── create_deadline_reminders.py # NOUVEAU — auto-création J-30/7/1
│   │       ├── create_silence_radio_reminders.py
│   │       ├── create_assessment_renewal_reminders.py
│   │       ├── create_attestation_expiration_reminders.py
│   │       ├── purge_old_reminders.py       # NOUVEAU — housekeeping hebdo
│   │       ├── fetch_exchange_rates_wrapper.py    # Wrapper sur app/scripts/fetch_exchange_rates.py
│   │       ├── purge_scheduled_deletions_wrapper.py # Wrapper sur scripts/purge_scheduled_deletions.py
│   │       ├── check_referential_versions_evolution_wrapper.py
│   │       └── check_expired_accreditations_wrapper.py
│   ├── services/
│   │   └── notifications/                   # NOUVEAU module (ou extension sse_bus existant)
│   │       ├── __init__.py
│   │       ├── sse_bus.py                   # Helpers notify_user(account_id, event)
│   │       └── reminder_notifier.py         # Logique payload reminder_due
│   ├── models/
│   │   └── action_plan.py                   # MODIFIÉ — Reminder + dedup_key, sent_at, archived, read
│   ├── api/
│   │   └── routers/
│   │       └── action_plan.py               # MODIFIÉ — 2 nouveaux endpoints (read, notifications)
│   ├── main.py                              # MODIFIÉ — lifespan intègre scheduler
│   └── core/
│       └── config.py                        # MODIFIÉ — APSCHEDULER_ENABLED env var
├── tests/
│   ├── unit/
│   │   └── scheduler/
│   │       ├── test_dispatch_reminders.py
│   │       ├── test_create_deadline_reminders.py
│   │       ├── test_create_silence_radio_reminders.py
│   │       ├── test_create_assessment_renewal_reminders.py
│   │       ├── test_create_attestation_expiration_reminders.py
│   │       └── test_purge_old_reminders.py
│   ├── integration/
│   │   └── scheduler/
│   │       ├── test_apscheduler_lifespan.py
│   │       ├── test_no_cross_account_reminder_leak.py
│   │       ├── test_apscheduler_starts_only_once.py
│   │       └── test_audit_log_reminder_events.py
│   └── e2e/
│       ├── test_f19_assessment_renewal_e2e.py    # E2E US6 #1
│       └── test_f19_silence_radio_e2e.py         # E2E US6 #2
└── requirements.txt                          # MODIFIÉ — ajout apscheduler>=3.10

frontend/
├── app/
│   ├── components/
│   │   └── NotificationCenter.vue            # NOUVEAU
│   ├── composables/
│   │   ├── useActionPlan.ts                  # MODIFIÉ — branchement onDueReminder
│   │   ├── useNotifications.ts               # NOUVEAU — agrège SSE + polling
│   │   └── useToast.ts                       # MODIFIÉ — variantes par type (si existant)
│   ├── stores/
│   │   └── notifications.ts                  # NOUVEAU — Pinia store
│   ├── pages/
│   │   └── action-plan/
│   │       └── index.vue                     # MODIFIÉ — bouton + modal ReminderForm
│   └── layouts/
│       └── default.vue                       # MODIFIÉ — startReminderPolling onMounted
└── tests/
    ├── unit/
    │   └── components/
    │       └── NotificationCenter.spec.ts
    └── e2e/
        └── notification_center.spec.ts

docs/
└── cron-scheduler.md                         # NOUVEAU — limitations, migration post-MVP
```

## Phase 0 — Research

Output : `research.md` couvrant les décisions clés :

- **R1 — APScheduler vs Celery vs cron système** : APScheduler retenu pour MVP (intégration native Python/FastAPI, zero infra). Celery+Redis post-MVP pour scaling horizontal.
- **R2 — `AsyncIOScheduler` vs `BackgroundScheduler`** : `AsyncIOScheduler` retenu (intégré à l'event loop FastAPI, async natif, pas de thread management).
- **R3 — Single-process garantie** : lock fichier `/tmp/apscheduler.lock` (POSIX `fcntl.flock`) ou env var `APSCHEDULER_ENABLED=true` (kube/docker). MVP env var, post-MVP Redis distributed lock.
- **R4 — `FOR UPDATE SKIP LOCKED` pattern** : standard PostgreSQL ≥ 9.5, supporté nativement par SQLAlchemy via `with_for_update(skip_locked=True)`. Test : 2 workers parallèles → chacun pick un sous-set distinct.
- **R5 — UPSERT pour dedup_key** : SQLAlchemy `INSERT ... ON CONFLICT DO NOTHING` via `postgresql.insert(Reminder).on_conflict_do_nothing(index_elements=['account_id', 'dedup_key'])`. Garantit idempotence.
- **R6 — Format `dedup_key`** : `{account_id}:{type}:{entity_id}:{trigger_date}` lisible/debuggable. Index partiel `WHERE account_id IS NOT NULL AND dedup_key IS NOT NULL`.
- **R7 — SSE notification** : utilisation du bus existant si présent. Sinon, helper minimal `notify_user(account_id, event_type, payload)` qui push dans les `EventSourceConnection` actives (dict en mémoire, scoped par account).
- **R8 — APScheduler test patterns** : `MemoryJobStore` + `mock_scheduler` fixture pytest pour avoid attendre les triggers réels. Pattern : injecter une fonction `_trigger_now(job_name)` pour tester.
- **R9 — Migration zero-downtime sur 10k+ reminders** : `ALTER TABLE` add column nullable + `CREATE INDEX CONCURRENTLY` pour PG production (Alembic supporte avec `op.create_index(..., postgresql_concurrently=True)`). Backfill optionnel best-effort.
- **R10 — Frontend dedup SSE+polling** : Pinia store avec Set des `reminder_id` vus, persistance localStorage. Pattern observable.
- **R11 — Toast variantes Tailwind** : map `ReminderType → variant` dans `useToast.ts`. Variants : `info-blue`, `warning`, `danger`, `default`.
- **R12 — Composant ReminderForm dead code** : audit du composant existant pour vérifier qu'il appelle bien `POST /api/action-plan/reminders/`. Si OK, juste l'instancier dans une modal.

## Phase 1 — Design

### Data model (data-model.md)

#### Table `reminders` (extension)

**Nouvelles colonnes** :
- `dedup_key VARCHAR(255) NULL` — clé de déduplication
- `sent_at TIMESTAMPTZ NULL` — timestamp dispatch (distinct de `sent: bool`)
- `archived BOOLEAN NOT NULL DEFAULT FALSE` — flag housekeeping
- `read BOOLEAN NOT NULL DEFAULT FALSE` — si non présente déjà (à vérifier — sinon migration ajoute)

**Nouveaux indexes** :
- `idx_reminders_dedup_key_unique` UNIQUE PARTIAL : `(account_id, dedup_key) WHERE account_id IS NOT NULL AND dedup_key IS NOT NULL`
- `idx_reminders_archived_pending` : `(archived, sent)` pour le polling NotificationCenter

**Enum extension** (si nécessaire) :
- `ReminderType` ajout valeur `attestation_renewal` (vérifier si déjà présente — sinon `ALTER TYPE reminder_type_enum ADD VALUE 'attestation_renewal'`)

#### Audit log events (F03)

3 nouveaux events :
- `reminder_created` (source `cron:{job_name}` ou `manual:{user_id}`)
- `reminder_dispatched` (source `cron:dispatch_reminders`)
- `reminder_archived` (source `cron:purge_old_reminders`)

#### Frontend store schema (notifications)

```typescript
interface NotificationState {
  reminders: Reminder[]              // liste cumulée (max 50, FIFO)
  unreadCount: number
  seenReminderIds: Set<string>       // dedup SSE+polling
  isPollingActive: boolean
}
```

### API contracts (contracts/)

#### `notification_center_endpoints.md`

**Endpoint 1 : `PATCH /api/action-plan/reminders/{id}/read`**
- Auth : Bearer JWT
- Path param : `id` (UUID Reminder)
- Response 200 : `{"id": uuid, "read": true, "read_at": iso8601}`
- Errors : 404 si reminder n'existe pas, 403 si pas le owner

**Endpoint 2 : `GET /api/action-plan/reminders/notifications`**
- Auth : Bearer JWT
- Query : `limit` (default 10, max 50), `include_read` (default true), `include_archived` (default false)
- Response 200 : `{"items": [Reminder...], "unread_count": int}`
- Filtre : `account_id = current_user.account_id` (F02)

#### `reminder_dispatched_event_schema.json`

JSON Schema du payload SSE `reminder_due` :
```json
{
  "type": "object",
  "required": ["reminder_id", "type", "message", "scheduled_at"],
  "properties": {
    "reminder_id": {"type": "string", "format": "uuid"},
    "type": {"enum": ["action_due", "assessment_renewal", "fund_deadline", "intermediary_followup", "attestation_renewal", "custom"]},
    "message": {"type": "string", "maxLength": 500},
    "scheduled_at": {"type": "string", "format": "date-time"},
    "metadata": {
      "type": "object",
      "properties": {
        "entity_id": {"type": "string", "format": "uuid"},
        "entity_type": {"type": "string"},
        "action_url": {"type": "string"}
      }
    }
  }
}
```

#### `apscheduler_jobs_config.md`

Tableau récap des 9 jobs (+ 1 housekeeping) avec trigger, fonction, params.

### Quickstart (quickstart.md)

3 sections :
1. **Démarrer le scheduler en local** : `APSCHEDULER_ENABLED=true uvicorn app.main:app --reload`
2. **Déclencher un job manuellement (dev/debug)** : route admin debug `POST /api/admin/scheduler/trigger/{job_name}` (à créer derrière feature flag)
3. **Inspecter les jobs actifs** : `GET /api/admin/scheduler/jobs` (debug only)

## Phase 2 — Tasks (output `tasks.md`)

Voir `tasks.md` (généré par `/speckit.tasks`).

## Risks & Mitigations

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| APScheduler crash silencieux en prod | Moyen | Haut | Health check endpoint `GET /api/admin/scheduler/health` + monitoring (post-MVP Sentry) |
| Migration 034 bloque sur grosse table | Faible | Haut | Index `CONCURRENTLY` + colonnes nullable. Test SC-009 < 5s sur 10k. |
| Race conditions dispatch (2 workers) | Moyen | Haut | `FOR UPDATE SKIP LOCKED` + lock fichier MVP. Test SC-010. |
| Toast spam (>10 reminders simultanés) | Faible | Moyen | Agrégation par type + plafond 5 visibles. UX dans NotificationCenter pour le reste. |
| Dead code `ReminderForm` cassé après changements | Moyen | Bas | Audit composant + test E2E création reminder custom. |
| SSE déconnexion → miss notification | Moyen | Moyen | Polling 60s fallback. `sent` persisté en DB → replay au reconnect. |
| Token budget LLM (si LLM lit reminders) | Nul | Nul | F19 ne touche pas le LLM. Reminders sont UI-only. |
| Fuite cross-account dans NotificationCenter | Faible | Critique | Test conformity FR-024. Filtre strict `account_id = current_user.account_id` dans tous les endpoints. |
| Backfill `dedup_key` corrompt données | Faible | Bas | Backfill best-effort, NULL par défaut. Pas de transformation des reminders existants. |
| Single-process limitation (scaling) | Élevé | Bas (MVP) | Documenté dans `docs/cron-scheduler.md`. Migration Celery/Redis post-MVP. |

## Open Questions Resolved by Clarifications

Toutes les ambiguïtés du brief F19 ont été résolues lors du `/speckit.clarify` autonome (cf section Clarifications du spec.md). Aucune `[NEEDS CLARIFICATION]` restante.

## Acceptance Gates

Avant `ready_for_implement = true` :

- [x] Spec.md complet (clarifications, US, FR, SC, edge cases, assumptions) — 6 user stories, 25 FR, 10 SC.
- [x] Plan.md complet (technical context, structure, phases, risks).
- [x] Tasks.md complet (output `/speckit.tasks`).
- [x] Analyze.md complet (output `/speckit.analyze`) — 0 blocage critique.
- [x] Migration 034 planifiée avec `down_revision="033_create_skills"`.
- [x] Aucun écrasement de fichier existant non couvert.
- [x] Tests E2E spécifiés (US6).
- [x] Audit conformity tests spécifiés (FR-023, FR-024).
- [x] Doc `docs/cron-scheduler.md` planifiée (FR-022).
