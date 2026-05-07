---
description: "Task list for F19 — Cron Dispatcher Rappels + Auto-création Alertes"
---

# Tasks: F19 — Cron Dispatcher Rappels + Auto-création Alertes

**Input**: Design documents from `/specs/034-cron-rappels-dispatcher/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/

**Tests**: TDD obligatoire (rule globale projet, 80 % coverage min). Tests E2E + integration inclus.

**Organization**: Tasks groupées par user story pour permettre implémentation/test/livraison indépendants.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : Parallèle (fichiers différents, aucune dépendance)
- **[Story]** : US1 / US2 / US3 / US4 / US5 / US6 (cf. spec.md)
- Chemins absolus des fichiers (par convention projet)

---

## Phase 1 : Setup (Shared Infrastructure)

**Purpose** : Préparer l'environnement et les outils communs.

- [ ] **T001** [P] Vérifier que `apscheduler>=3.10` est dans `backend/requirements.txt`. Ajouter `apscheduler>=3.10.4` si absent.
- [ ] **T002** [P] Créer le module Python vide `backend/app/scheduler/__init__.py` (avec docstring expliquant le rôle).
- [ ] **T003** [P] Créer le dossier `backend/app/scheduler/jobs/` avec `__init__.py` vide.
- [ ] **T004** [P] Créer le dossier `backend/app/services/notifications/` avec `__init__.py` vide (s'il n'existe pas déjà).
- [ ] **T005** [P] Créer le dossier `backend/tests/unit/scheduler/` avec `__init__.py`.
- [ ] **T006** [P] Créer le dossier `backend/tests/integration/scheduler/` avec `__init__.py`.
- [ ] **T007** [P] Créer le dossier `frontend/app/components/` (existant) — vérifier la présence du futur fichier `NotificationCenter.vue`.
- [ ] **T008** [P] Vérifier l'existence d'un système de toast frontend (`useToast` ou similaire). Si absent, créer un composable minimal `frontend/app/composables/useToast.ts`.

---

## Phase 2 : Foundational (Blocking Prerequisites)

**Purpose** : Migration BDD + modèle SQLAlchemy + bus SSE de base.

**CRITICAL** : Aucune US ne peut commencer avant Phase 2.

### Migration Alembic 034 (US5)

- [ ] **T009** [US5] Créer test unit `backend/tests/unit/test_migration_034.py` (TDD — AVANT T010) :
  - Test : `alembic upgrade 034_reminder_dedup_key` ajoute les colonnes `dedup_key`, `sent_at`, `archived` (et `read` si absente).
  - Test : insert 2 reminders avec même `(account_id, dedup_key)` → 2nd échoue (IntegrityError).
  - Test : insert reminder avec `dedup_key=NULL` n'est pas soumis à la contrainte unique.
  - Test : `alembic downgrade -1` supprime les 3 colonnes sans corrompre les données.
  - Test : insert reminder type `attestation_renewal` réussit (enum extension).

- [ ] **T010** [US5] Créer migration Alembic `backend/alembic/versions/034_reminder_dedup_key.py` :
  - `revision = "034_reminder_dedup_key"`
  - `down_revision = "033_create_skills"`
  - Add columns : `dedup_key VARCHAR(255) NULL`, `sent_at TIMESTAMPTZ NULL`, `archived BOOLEAN NOT NULL DEFAULT false`
  - Add column conditionnel `read` si absente.
  - `ALTER TYPE reminder_type_enum ADD VALUE 'attestation_renewal'` conditionnel (vérification pg_enum) — PostgreSQL only, dans `autocommit_block`.
  - Index unique partiel `idx_reminders_dedup_key_unique` `CONCURRENTLY` (PG) ou standard (SQLite).
  - Index `idx_reminders_archived_pending` `CONCURRENTLY` (PG) ou standard.
  - `downgrade()` retire les 3 colonnes et les indexes, ne retire PAS la valeur enum (limitation PG).

- [ ] **T011** [US5] Modifier modèle SQLAlchemy `backend/app/models/action_plan.py` :
  - Ajouter à `class ReminderType` : `attestation_renewal = "attestation_renewal"`.
  - Ajouter à `class Reminder` : champs `sent_at`, `archived`, `read` (si absent), `dedup_key`.
  - Ajouter `Index("idx_reminders_dedup_key_unique", "account_id", "dedup_key", unique=True, postgresql_where=text("..."))`.
  - Ajouter `Index("idx_reminders_archived_pending", "archived", "sent")`.

- [ ] **T012** [US5] Créer test unit `backend/tests/unit/models/test_reminder_model.py` :
  - Test : création Reminder avec champs minimum requis OK.
  - Test : champ `archived` défaut `False`.
  - Test : champ `read` défaut `False`.
  - Test : type `attestation_renewal` accepté.
  - Test : `dedup_key` peut être NULL.
  - Test : 2 inserts avec même dedup_key et même account_id → IntegrityError (PG only — skip si SQLite).

### Bus SSE / notifications (US1)

- [ ] **T013** [US1] Créer test unit `backend/tests/unit/services/test_sse_bus.py` (TDD AVANT T014) :
  - Test : `notify_user(account_id, event_type, payload)` push dans la queue du user connecté.
  - Test : si user pas connecté, message stocké pas perdu (queue tampon courte ou drop graceful).
  - Test : event JSON serializable.
  - Test : 2 users connectés → seul celui ciblé reçoit.

- [ ] **T014** [US1] Créer ou étendre `backend/app/services/notifications/sse_bus.py` :
  - Classe `SSEBus` avec dict `_connections: dict[str, list[asyncio.Queue]]`.
  - Méthodes `connect(account_id) -> AsyncIterator`, `disconnect(account_id, queue)`, `notify_user(account_id, event_type, payload)`.
  - Singleton global `bus = SSEBus()`.
  - **Note** : si bus chat existant, le réutiliser. Documenter dans le code.

- [ ] **T015** [US1] Créer `backend/app/services/notifications/reminder_notifier.py` :
  - Fonction `build_reminder_payload(reminder: Reminder) -> dict` qui construit le payload conforme au schema `reminder_dispatched_event_schema.json`.
  - Inclut metadata : `entity_id`, `entity_type`, `action_url`, `intermediary_name` (si applicable).
  - Mapping `ReminderType → action_url` :
    - `fund_deadline` → `/financing/{entity_id}`
    - `assessment_renewal` → `/esg`
    - `attestation_renewal` → `/applications/{entity_id}/attestation`
    - `intermediary_followup` → `/applications/{entity_id}`
    - `action_due` → `/action-plan`
    - `custom` → `/action-plan`

- [ ] **T016** [US1] Créer test unit `backend/tests/unit/services/test_reminder_notifier.py` :
  - Test : payload pour `fund_deadline` contient `metadata.action_url = "/financing/{fund_id}"`.
  - Test : payload pour `intermediary_followup` contient `metadata.intermediary_name`.
  - Test : payload conforme au JSON schema (validation Pydantic).

### Config / env vars

- [ ] **T017** [US3] Modifier `backend/app/core/config.py` :
  - Ajouter `apscheduler_enabled: bool = False` (env `APSCHEDULER_ENABLED`).
  - Ajouter `admin_debug_scheduler: bool = False` (env `ADMIN_DEBUG_SCHEDULER`).
  - Ajouter `silence_radio_delay_days: int = 14`.
  - Ajouter `assessment_renewal_grace_days: int = 30`.
  - Ajouter `attestation_expiration_grace_days: int = 30`.
  - Ajouter `deadline_reminder_days: list[int] = [30, 7, 1]` (parser CSV depuis env).
  - Ajouter `dispatch_batch_limit: int = 100`.
  - Ajouter `purge_old_reminders_after_days: int = 90`.

- [ ] **T018** [US3] Créer test unit `backend/tests/unit/core/test_config_f19.py` :
  - Test : default values pour les 7 nouvelles env vars.
  - Test : parse `DEADLINE_REMINDER_DAYS=30,7,1` en `[30, 7, 1]`.

---

## Phase 3 : User Story 1 — Dispatcher reminders avec SSE push (P1)

**Goal** : Reminder dû (`scheduled_at <= now() AND sent=FALSE`) → marqué `sent=TRUE` → SSE event `reminder_due` pushé.

**Independent Test** : Créer reminder avec `scheduled_at=now() - 1min`, lancer `dispatch_reminders.run()`, vérifier `sent=TRUE` et SSE émis.

### TDD

- [ ] **T019** [US1] Créer test unit `backend/tests/unit/scheduler/test_dispatch_reminders.py` (TDD AVANT T020) :
  - Test : 1 reminder pending → `dispatched_count=1`, `sent=TRUE`, `sent_at` non-null.
  - Test : 1 reminder déjà sent → ignoré (filtre `sent=FALSE`).
  - Test : 1 reminder `archived=TRUE` → ignoré (filtre `archived=FALSE`).
  - Test : 1 reminder `scheduled_at = now() + 1h` → ignoré (futur).
  - Test : SSE bus mock appelé avec payload conforme au schema.
  - Test : audit log F03 entry créée (`event_type=reminder_dispatched`).
  - Test : 200 reminders pending, batch_limit=100 → 100 dispatchés, 100 restants pour le prochain cycle.

- [ ] **T020** [US1] Créer test integration `backend/tests/integration/scheduler/test_dispatch_reminders_concurrent.py` :
  - Test : 2 sessions PG parallèles utilisent `FOR UPDATE SKIP LOCKED` → pas de double dispatch (total = N reminders).
  - Skip ou xfail en SQLite.

### Implementation

- [ ] **T021** [US1] Créer `backend/app/scheduler/jobs/dispatch_reminders.py` :
  - Fonction `async def run() -> dict`.
  - Query : `select(Reminder).where(sent=False, scheduled_at <= now(), archived=False).order_by(scheduled_at).limit(batch_limit).with_for_update(skip_locked=True)`.
  - Pour chaque reminder : marquer `sent=True, sent_at=now()`, push SSE via `sse_bus.notify_user`, audit log F03.
  - Retour `{"dispatched_count": N, "errors": []}`.
  - Logging structuré : `logger.info("scheduler.dispatch_reminders | dispatched=%d errors=%d duration_ms=%d", ...)`.

- [ ] **T022** [US1] Vérifier que `T019` et `T020` passent.

---

## Phase 4 : User Story 2 — Auto-création des reminders (P1)

**Goal** : Jobs `create_*_reminders` détectent les conditions et créent les reminders avec dedup_key.

**Independent Test** : Seed une condition (Application avec deadline+30j), lancer le job, vérifier reminder créé avec dedup_key correct.

### Job 1 : create_deadline_reminders

- [ ] **T023** [US2] Créer test unit `backend/tests/unit/scheduler/test_create_deadline_reminders.py` (TDD AVANT T024) :
  - Test : Application liée à Fund avec `application_deadline = today() + 30 days` → 1 reminder J-30 créé.
  - Test : Application avec deadline+7d → 1 reminder J-7 créé (en plus de J-30 si déjà existant).
  - Test : 2 runs consécutifs → pas de doublon (UPSERT idempotent).
  - Test : `dedup_key` au format `{account_id}:fund_deadline:{fund_id}:2026-06-01:J-30`.
  - Test : pas de reminder créé si `application_deadline > today() + 30 days` ET pas de fond favori.
  - Test : 1 fond favori avec deadline → reminder J-30/J-7/J-1 créés.

- [ ] **T024** [US2] Créer `backend/app/scheduler/jobs/create_deadline_reminders.py` :
  - Détection 3 sources : (a) `fund_favorites` (table à vérifier — sinon skip cette source en MVP), (b) `fund_applications` actives liées à Fund avec `application_deadline`, (c) `fund_applications` liées à Offre avec `submission_calendar` (jsonb F07).
  - Pour chaque deadline + chaque J-N (default `[30, 7, 1]`) : insert UPSERT `ON CONFLICT DO NOTHING`.
  - `scheduled_at = deadline_date - timedelta(days=N)` (UTC 08:00).
  - Audit log F03 par insert.

### Job 2 : create_silence_radio_reminders

- [ ] **T025** [US2] Créer test unit `backend/tests/unit/scheduler/test_create_silence_radio_reminders.py` (TDD AVANT T026) :
  - Test : FundApplication `submitted_to_intermediary` avec `submitted_at=now() - 14 days` → reminder créé.
  - Test : `submitted_at=now() - 13 days` (juste sous le seuil) → pas de reminder.
  - Test : FundApplication avec `last_status_update=now() - 5 days` (récent) → pas de reminder.
  - Test : 2 runs consécutifs → idempotent (dedup `silence14`).
  - Test : `dedup_key = "{account_id}:intermediary_followup:{application_id}:silence14"`.

- [ ] **T026** [US2] Créer `backend/app/scheduler/jobs/create_silence_radio_reminders.py` :
  - Filtre : `status IN ('submitted_to_intermediary', 'submitted_to_fund')`, `submitted_at + N days < today()` (N = `silence_radio_delay_days`), `last_status_update IS NULL OR last_status_update + 7 days < today()`.
  - Message : `"Aucune activité sur votre dossier depuis {N} jours. Relancez l'intermédiaire {nom}."`
  - UPSERT `ON CONFLICT DO NOTHING`.
  - Audit log F03.

### Job 3 : create_assessment_renewal_reminders

- [ ] **T027** [US2] Créer test unit `backend/tests/unit/scheduler/test_create_assessment_renewal_reminders.py` (TDD AVANT T028) :
  - Test : ESGAssessment finalisé avec `finalized_at = now() - 335 days` → reminder créé (J-30 avant 365j).
  - Test : `finalized_at = now() - 300 days` (trop tôt) → pas de reminder.
  - Test : `finalized_at = now() - 366 days` (déjà expiré) → pas de reminder (filtre `finalized_at + 365 > today()`).
  - Test : idempotent.

- [ ] **T028** [US2] Créer `backend/app/scheduler/jobs/create_assessment_renewal_reminders.py` :
  - Filtre : `finalized_at + 365 days - N days < today() AND finalized_at + 365 days > today()` (N = `assessment_renewal_grace_days`).
  - Message : `"Votre évaluation ESG du {date} expire dans {N} jours. Renouvelez-la pour conserver vos accréditations."`
  - UPSERT.

### Job 4 : create_attestation_expiration_reminders

- [ ] **T029** [US2] Créer test unit `backend/tests/unit/scheduler/test_create_attestation_expiration_reminders.py` (TDD AVANT T030) :
  - Test : Attestation avec `valid_until = today() + 30 days, revoked_at = NULL` → reminder créé.
  - Test : Attestation avec `revoked_at != NULL` → pas de reminder.
  - Test : `valid_until = today() + 60 days` (trop tôt) → pas de reminder.

- [ ] **T030** [US2] Créer `backend/app/scheduler/jobs/create_attestation_expiration_reminders.py` :
  - Filtre : `valid_until - N days < today() AND valid_until > today() AND revoked_at IS NULL` (N = `attestation_expiration_grace_days`).
  - Message : `"Votre attestation ESG #{numero} expire le {date}. Pensez à la renouveler."`
  - UPSERT.

### Job 5 : purge_old_reminders (housekeeping)

- [ ] **T031** [US2] Créer test unit `backend/tests/unit/scheduler/test_purge_old_reminders.py` :
  - Test : reminder `sent=TRUE, created_at = now() - 91 days` → archivé.
  - Test : reminder `sent=FALSE` même ancien → pas archivé (encore en attente).
  - Test : reminder déjà `archived=TRUE` → ignoré.
  - Test : audit log F03 `reminder_archived`.

- [ ] **T032** [US2] Créer `backend/app/scheduler/jobs/purge_old_reminders.py` :
  - Filtre : `sent=TRUE AND archived=FALSE AND created_at < now() - N days` (N = `purge_old_reminders_after_days`).
  - UPDATE batch `archived=TRUE`.
  - Audit log F03 par batch.

---

## Phase 5 : User Story 3 — APScheduler dans lifespan FastAPI (P1)

**Goal** : 9 jobs cron + 1 housekeeping enregistrés au boot, démarrage gracieux, lock single-process.

**Independent Test** : Boot FastAPI, vérifier `app.state.scheduler.get_jobs() == 10`.

### TDD

- [ ] **T033** [US3] Créer test integration `backend/tests/integration/scheduler/test_apscheduler_lifespan.py` (TDD AVANT T034) :
  - Test : `APSCHEDULER_ENABLED=true` → `scheduler.running == True`, 10 jobs enregistrés.
  - Test : `APSCHEDULER_ENABLED=false` → pas de scheduler dans `app.state`.
  - Test : `apscheduler` non installé (mock ImportError) → warning + app démarre.
  - Test : shutdown gracieux à la fermeture du lifespan.
  - Test : noms des 10 jobs corrects.

- [ ] **T034** [US3] Créer test integration `backend/tests/integration/scheduler/test_apscheduler_starts_only_once.py` :
  - Test : 2 instances FastAPI avec `APSCHEDULER_ENABLED=true` + lock fichier → seul le 1er démarre effectivement.
  - Test : avec env var → seul celui avec `APSCHEDULER_ENABLED=true` démarre.

### Implementation

- [ ] **T035** [US3] Créer `backend/app/scheduler/scheduler.py` :
  - Instance globale `scheduler = AsyncIOScheduler(...)`.
  - Fonction `register_jobs(scheduler)` qui add les 10 jobs avec triggers et misfire grace.
  - Helper `acquire_single_process_lock() -> bool` (env var + optionnel lock fichier).

- [ ] **T036** [US3] Créer `backend/app/scheduler/lock.py` :
  - Helper POSIX `fcntl.flock` pour le lock fichier `/tmp/apscheduler.lock` (best-effort).
  - Fonction `try_acquire_lock(path) -> file_handle | None`.

- [ ] **T037** [US3] Créer wrappers pour les 4 scripts existants (T038-T041) :
  - `backend/app/scheduler/jobs/fetch_exchange_rates_wrapper.py`
  - `backend/app/scheduler/jobs/purge_scheduled_deletions_wrapper.py`
  - `backend/app/scheduler/jobs/check_referential_versions_evolution_wrapper.py`
  - `backend/app/scheduler/jobs/check_expired_accreditations_wrapper.py`
  - Chaque wrapper : import du script, fonction `async def run() -> dict` qui invoque la fonction principale et retourne un dict de stats.

- [ ] **T038** [US3] Modifier `backend/app/main.py` lifespan :
  - Importer `from app.scheduler.scheduler import scheduler, register_jobs`.
  - Dans le lifespan, après LangGraph init :
    ```python
    if settings.apscheduler_enabled and try_acquire_lock(...):
        register_jobs(scheduler)
        scheduler.start()
        app.state.scheduler = scheduler
    ```
  - Shutdown : `scheduler.shutdown(wait=True)` si actif.

- [ ] **T039** [US3] Vérifier que T033 et T034 passent.

### Endpoints debug (feature-flagged)

- [ ] **T040** [US3] Créer test unit `backend/tests/unit/api/test_scheduler_debug_endpoints.py` :
  - Test : `GET /api/admin/scheduler/jobs` retourne liste des 10 jobs si `ADMIN_DEBUG_SCHEDULER=true`.
  - Test : `404 feature_disabled` si `ADMIN_DEBUG_SCHEDULER=false`.
  - Test : `403` si pas admin.
  - Test : `POST /api/admin/scheduler/trigger/{job_id}` invoque le job et retourne le résultat.
  - Test : `GET /api/admin/scheduler/health` retourne running + counts.

- [ ] **T041** [US3] Créer router `backend/app/api/routers/admin_scheduler.py` :
  - Endpoints : `GET /api/admin/scheduler/jobs`, `POST /api/admin/scheduler/trigger/{job_id}`, `GET /api/admin/scheduler/health`, `POST /api/admin/scheduler/pause/{job_id}`, `POST /api/admin/scheduler/resume/{job_id}`.
  - Tous protégés par `Depends(require_admin_role)` et feature flag `settings.admin_debug_scheduler`.
  - Inclus dans `app.main` via `include_router`.

---

## Phase 6 : User Story 4 — Frontend NotificationCenter + polling + ReminderForm (P2)

**Goal** : Cloche header + dropdown + badge unread + activation polling 60s + activation ReminderForm.

**Independent Test** : Connecté, ouvrir layout, voir cloche. Backend dispatch un reminder, voir badge passer à 1, dropdown l'affiche.

### Backend endpoints (US4 supports)

- [ ] **T042** [US4] Créer test unit `backend/tests/unit/api/test_reminders_endpoints_f19.py` (TDD AVANT T043) :
  - Test : `PATCH /api/action-plan/reminders/{id}/read` → 200, `read=true`.
  - Test : `PATCH` avec UUID inexistant → 404.
  - Test : `PATCH` cross-account → 403.
  - Test : `GET /api/action-plan/reminders/notifications` → liste filtrée par account_id, ordre desc, dedup déjà-lus.
  - Test : `GET` avec `limit=200` → 422.
  - Test : `GET` avec `since=hier` → uniquement les reminders d'aujourd'hui.

- [ ] **T043** [US4] Modifier `backend/app/api/routers/action_plan.py` (ou créer router dédié reminders si absent) :
  - Endpoint `PATCH /api/action-plan/reminders/{id}/read` : marque `read=TRUE`, retourne `{id, read, read_at}`.
  - Endpoint `GET /api/action-plan/reminders/notifications` : pagine, filtre par `account_id`, support `limit`, `include_read`, `include_archived`, `since`.
  - Schemas Pydantic : `ReminderReadResponse`, `ReminderNotificationItem`, `NotificationListResponse`.

### Frontend types & store

- [ ] **T044** [US4] [P] Créer `frontend/app/types/reminders.ts` (ou étendre existant) :
  - Type `Reminder` aligné sur le backend (id, type, message, scheduled_at, sent, sent_at, read, archived, metadata, created_at).
  - Type union `ReminderType`.
  - Type `ToastVariant` : `'info-blue' | 'warning' | 'danger' | 'default'`.
  - Maps `TOAST_VARIANT_BY_TYPE`, `TOAST_ICON_BY_TYPE`, `ACTION_URL_BY_TYPE`.

- [ ] **T045** [US4] [P] Créer test unit `frontend/tests/unit/stores/notifications.spec.ts` (TDD AVANT T046) :
  - Test : `addReminder` ajoute si pas vu (par id).
  - Test : `addReminder` skip si déjà vu (dedup).
  - Test : `unreadCount` incrémenté correctement.
  - Test : `markAsRead` décrémente `unreadCount`.
  - Test : `markAllAsRead` reset à 0.
  - Test : `persistSeenIds` écrit en localStorage.
  - Test : `hydrateFromStorage` restaure depuis localStorage.

- [ ] **T046** [US4] Créer `frontend/app/stores/notifications.ts` :
  - Pinia store avec state `reminders, seenReminderIds, unreadCount, isPollingActive, isLoading`.
  - Actions : `addReminder`, `markAsRead`, `markAllAsRead`, `dismiss`, `persistSeenIds`, `hydrateFromStorage`, `fetchNotifications`.
  - Getters : `unreadReminders`, `recentReminders`.
  - Persistance localStorage clé `notif:seen` (50 IDs max FIFO).

### Composables

- [ ] **T047** [US4] Créer test unit `frontend/tests/unit/composables/useNotifications.spec.ts` :
  - Test : agrège SSE + polling sans double notification (par id).
  - Test : appelle `useToast` avec la variante correcte par type.
  - Test : navigation vers `metadata.action_url` au click sur reminder.

- [ ] **T048** [US4] Créer `frontend/app/composables/useNotifications.ts` :
  - Hook `onMounted(() => store.hydrateFromStorage())`.
  - Hook `onMounted` : si SSE bus chat existe, écouter `reminder_due` events.
  - Watcher sur `notificationsStore.reminders` pour déclencher toasts.
  - Helper `notifyReminder(reminder, toast)` qui choisit la variante par type.

- [ ] **T049** [US4] Modifier `frontend/app/composables/useActionPlan.ts` (le polling existe déjà en dead code) :
  - Pas de modif majeure : juste s'assurer que `startReminderPolling(onDueReminder)` est correctement câblable.

### Composant NotificationCenter

- [ ] **T050** [US4] Créer test unit `frontend/tests/unit/components/NotificationCenter.spec.ts` (TDD AVANT T051) :
  - Test : badge affiche `unreadCount` si > 0, caché sinon.
  - Test : click cloche → dropdown ouvert.
  - Test : reminders triés par `scheduled_at desc`.
  - Test : click sur reminder → navigation + `markAsRead`.
  - Test : "Tout marquer comme lu" → `markAllAsRead`.
  - Test : dark mode classes appliquées.

- [ ] **T051** [US4] Créer `frontend/app/components/NotificationCenter.vue` :
  - Cloche (icône `Bell`) + badge rouge si `unreadCount > 0`.
  - Dropdown avec liste 10 derniers reminders.
  - Séparation visuelle entre lus / non lus.
  - Action click : navigation `metadata.action_url` + `markAsRead`.
  - Bouton "Tout marquer comme lu".
  - Empty state : "Aucune notification".
  - Dark mode complet (`dark:bg-dark-card`, `dark:border-dark-border`, etc.).

- [ ] **T052** [US4] Modifier `frontend/app/layouts/default.vue` :
  - Importer et instancier `<NotificationCenter />` dans le header (à droite de l'avatar).
  - Importer `useNotificationsStore`, `useActionPlan`.
  - `onMounted` : `notifStore.hydrateFromStorage()` + `startReminderPolling(reminder => notifStore.addReminder(reminder))`.
  - `onUnmounted` : `stopReminderPolling()`.

### Activation ReminderForm

- [ ] **T053** [US4] Audit `frontend/app/components/ReminderForm.vue` :
  - Vérifier qu'il appelle `POST /api/action-plan/reminders/`.
  - Vérifier validation : `scheduled_at > now()`, `message` 10-500 chars, `type=custom`.
  - Vérifier dark mode.
  - Si KO mineur : fix dans le même PR F19.

- [ ] **T054** [US4] Modifier `frontend/app/pages/action-plan/index.vue` :
  - Ajouter bouton "Créer un rappel personnalisé" en haut à droite.
  - Ajouter modal (composant `ConfirmDialog` ou similaire existant) qui ouvre `<ReminderForm @success="onReminderCreated" />`.
  - Refresh la liste de reminders après création réussie.

### Toast variantes

- [ ] **T055** [US4] Étendre `frontend/app/composables/useToast.ts` :
  - Ajouter variantes `info-blue`, `warning`, `danger`, `default` avec classes Tailwind correspondantes.
  - Helper `toastForReminder(reminder)` qui choisit variante + icône + action_url.

---

## Phase 7 : User Story 5 — Audit log F03 + conformity tests (P1)

**Goal** : Toutes les mutations cron loggées dans `audit_log`.

**Independent Test** : Lancer un job, vérifier les events dans `audit_log`.

- [ ] **T056** [US5] Créer test integration `backend/tests/integration/scheduler/test_audit_log_reminder_events.py` :
  - Test : `dispatch_reminders` insert event `reminder_dispatched`.
  - Test : `create_*_reminders` insert event `reminder_created` avec source `cron:{job_name}`.
  - Test : `purge_old_reminders` insert event `reminder_archived`.
  - Test : payload contient `reminder_id`, `entity_id` si applicable.

- [ ] **T057** [US5] Créer test conformity `backend/tests/integration/scheduler/test_no_cross_account_reminder_leak.py` :
  - Test : 2 accounts (A, B). Reminder créé pour A. SSE bus `notify_user(B.account_id, ...)` ne reçoit rien.
  - Test : `GET /api/action-plan/reminders/notifications` connecté en B → ne voit pas le reminder de A.
  - Test : `PATCH .../{id}/read` connecté en B sur reminder de A → 403.

- [ ] **T058** [US5] Vérifier que tous les jobs auto-création loggent F03 (revue de code post-implémentation).

---

## Phase 8 : User Story 6 — Tests E2E (P1)

**Goal** : 2 scénarios métier complets : assessment J-30 et silence radio 15j.

**Independent Test** : `pytest backend/tests/e2e/test_f19_*.py` passe.

- [ ] **T059** [US6] Créer test E2E `backend/tests/e2e/test_f19_assessment_renewal_e2e.py` :
  - Setup : créer user + ESGAssessment finalisé avec `finalized_at = now() - 335 days`.
  - Run : appeler `create_assessment_renewal_reminders.run()`.
  - Assert : 1 reminder type `assessment_renewal` créé en BDD.
  - Run : appeler `dispatch_reminders.run()`.
  - Assert : reminder marqué `sent=TRUE, sent_at` non-null.
  - Assert : SSE bus `notify_user` appelé avec payload conforme.
  - Assert : audit_log contient `reminder_created` + `reminder_dispatched`.

- [ ] **T060** [US6] Créer test E2E `backend/tests/e2e/test_f19_silence_radio_e2e.py` :
  - Setup : créer user + FundApplication `submitted_to_intermediary` avec `submitted_at = now() - 15 days`.
  - Run : `create_silence_radio_reminders.run()`.
  - Assert : 1 reminder type `intermediary_followup` créé.
  - Run : `dispatch_reminders.run()`.
  - Assert : reminder dispatché, payload contient `metadata.intermediary_name`.
  - Assert : payload mappe vers variante `info-blue` côté frontend (vérification map).

- [ ] **T061** [US6] [P] Créer test E2E frontend `frontend/tests/e2e/notification_center.spec.ts` (Playwright) :
  - Setup : seed reminders, login.
  - Naviguer `/dashboard`.
  - Assert : cloche header visible, badge "X" si unread.
  - Click cloche → dropdown ouvert.
  - Click reminder → navigation correcte + badge décrémenté.

---

## Phase 9 : Polish & Documentation

- [ ] **T062** [P] Créer documentation `docs/cron-scheduler.md` :
  - Architecture APScheduler MVP (single-process).
  - Liste des 10 jobs avec triggers.
  - Limitations (pas de retry distribué, single-process).
  - Plan migration post-MVP : Celery + Redis.
  - Comment ajouter un nouveau job.
  - Debug / monitoring.

- [ ] **T063** [P] Mettre à jour `CLAUDE.md` :
  - Ajouter dans "Recent Changes" : `034-cron-rappels-dispatcher: ...`.
  - Ajouter dans "Active Technologies" : `APScheduler 3.10+`.

- [ ] **T064** [P] Lancer `pytest backend/tests/ -m "unit or integration or e2e"` complet pour vérifier 0 régression.
- [ ] **T065** [P] Lancer `pytest backend/tests/ --cov=app/scheduler --cov=app/services/notifications --cov-report=term-missing` et viser ≥ 80 %.
- [ ] **T066** [P] Vérifier les warnings de typage : `mypy app/scheduler/ app/services/notifications/`.
- [ ] **T067** [P] Vérifier le linting : `ruff check app/scheduler/ app/services/notifications/`.
- [ ] **T068** [P] Code review interne : checklist code-review.md (security, perf, dark mode, F02/F03).

---

## Récapitulatif des tâches par US

| User Story | Tasks | TDD inclus | Indépendant ? |
|------------|-------|------------|---------------|
| US1 (Dispatcher SSE) | T013-T016, T019-T022 (8) | T013, T019, T020 (TDD) | ✓ après Phase 2 |
| US2 (Auto-création) | T023-T032 (10) | T023, T025, T027, T029, T031 (TDD) | ✓ après Phase 2 |
| US3 (APScheduler lifespan) | T017-T018, T033-T041 (11) | T018, T033, T034, T040 (TDD) | ✓ après Phase 2 |
| US4 (Frontend NotificationCenter) | T042-T055 (14) | T042, T045, T047, T050 (TDD) | ✓ après US3 |
| US5 (Migration + audit) | T009-T012, T056-T058 (7) | T009, T012, T056, T057 (TDD) | ✓ Phase 2 + 7 |
| US6 (Tests E2E) | T059-T061 (3) | — | ✓ après US1+US2 |
| Setup + Polish | T001-T008, T062-T068 (15) | — | — |

**Total** : 68 tâches.

## Critères de complétude

- [ ] Toutes les 68 tâches `[x]`.
- [ ] Coverage ≥ 80 % sur `app/scheduler/` et `app/services/notifications/`.
- [ ] 0 régression sur 935+ tests existants.
- [ ] Migration 034 appliquée et testée up/down.
- [ ] Frontend dark mode complet sur les nouveaux composants.
- [ ] Documentation `docs/cron-scheduler.md` créée.
- [ ] Tests E2E US6 passent en < 60s.
- [ ] Audit conformity FR-023, FR-024 passent.

## Ordre d'exécution recommandé

1. **Setup (T001-T008)** — parallèle, ~ 30 min.
2. **Phase 2 Foundational (T009-T018)** — séquentiel, blocage tout le reste, ~ 4-6h.
3. **Phase 3 US1 (T019-T022)** — séquentiel, ~ 3-4h.
4. **Phase 4 US2 (T023-T032)** — peut être parallélisé par job (T024+T026+T028+T030+T032 indépendants), ~ 6-8h.
5. **Phase 5 US3 (T033-T041)** — séquentiel, ~ 4-6h.
6. **Phase 6 US4 (T042-T055)** — séquentiel pour backend (T042-T043), parallèle pour frontend (T044-T055), ~ 8-10h.
7. **Phase 7 US5 (T056-T058)** — parallèle, ~ 2h.
8. **Phase 8 US6 (T059-T061)** — séquentiel, ~ 3-4h.
9. **Phase 9 Polish (T062-T068)** — parallèle, ~ 2-3h.

**Estimation totale** : 30-45h de dev (cohérent avec 1.5 sprint annoncé dans la fiche F19).
