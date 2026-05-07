# Feature Specification: F19 — Cron Dispatcher Rappels + Auto-création Alertes

**Feature Branch**: `feat/F19-cron-rappels-dispatcher`
**Created**: 2026-05-07
**Status**: Draft
**Input**: User description: "F19 — APScheduler intégré au lifespan FastAPI, 9 jobs cron (dispatch_reminders, deadlines, silence radio, assessment renewal, attestation expiration, exchange rates F04, purge deletions F05, referential evolution F13, expired accreditations F07), dedup_key unique sur reminders, SSE push reminder_due, polling 60s frontend, NotificationCenter cloche header, activation ReminderForm dead code, toasts par type"

## Clarifications

### Session 2026-05-07

- **Architecture cron MVP** : `APScheduler 3.10+` (`AsyncIOScheduler`) intégré dans le `lifespan` FastAPI. Pas de Redis ni Celery (limitation single-process documentée, migration post-MVP). Démarrage automatique au boot, shutdown gracieux à l'arrêt. Garde-fou : si APScheduler indisponible, l'application démarre quand même (warning log) — les jobs sont silencieusement désactivés (mode dégradé). Tests d'intégration utilisent `BlockingScheduler` ou mock `next_run_time` pour valider sans attendre les triggers réels.
- **Périmètre 9 jobs cron** :
  1. `dispatch_reminders` — toutes les 5 min (`*/5 * * * *`)
  2. `create_deadline_reminders` — 1×/jour à 08:00 (fonds favoris + applications avec deadline + offres avec submission_calendar)
  3. `create_silence_radio_reminders` — 1×/jour à 09:00 (applications submitted_to_intermediary/submitted_to_fund sans activité 14j+)
  4. `create_assessment_renewal_reminders` — 1×/jour à 10:00 (ESGAssessment finalisés J-30 avant `finalized_at + 365j`)
  5. `create_attestation_expiration_reminders` — 1×/jour à 11:00 (Attestation F08 J-30 avant `valid_until`)
  6. `fetch_exchange_rates` — 1×/jour à 02:00 (F04 — déjà script standalone, à câbler dans scheduler)
  7. `purge_scheduled_deletions` — 1×/jour à 03:00 (F05 — déjà script standalone, à câbler)
  8. `check_referential_versions_evolution` — 1×/jour à 04:00 (F13 — déjà script standalone, à câbler)
  9. `check_expired_accreditations` — 1×/jour à 05:00 (F07 — déjà script standalone, à câbler)
- **Déduplication `dedup_key`** : nouvelle colonne `dedup_key: str` sur `reminders` au format `{account_id}:{type}:{entity_id}:{trigger_date}` (ex `acc-uuid:fund_deadline:fund-uuid:2026-06-01:J-30`). Index unique partiel `WHERE account_id IS NOT NULL` pour permettre les rappels legacy sans account_id. Migration Alembic 034 ajoute la colonne nullable, backfill best-effort en best-effort sur les rappels existants (nullable car format dépend d'entity_id qui peut manquer pour `custom`), puis création de l'index unique. Pour les types `custom` (rappels personnalisés sans entité métier), le `dedup_key` reste `NULL` — pas de déduplication.
- **`dispatch_reminders` — atomicité et concurrence** : pour éviter les doublons de notification SSE, le job utilise une mise à jour conditionnelle :
  ```sql
  UPDATE reminders
  SET sent = TRUE, sent_at = NOW()
  WHERE id IN (
    SELECT id FROM reminders
    WHERE sent = FALSE AND scheduled_at <= NOW()
    ORDER BY scheduled_at ASC
    LIMIT 100
    FOR UPDATE SKIP LOCKED
  )
  RETURNING *;
  ```
  Pattern `FOR UPDATE SKIP LOCKED` garantit qu'aucun autre worker ne picke le même reminder. Ajout d'une colonne `sent_at: timestamptz | null` (la migration 034 l'ajoute aussi, distincte de `sent: bool`). Limite batch : 100 reminders/run pour éviter blocage long.
- **SSE push `reminder_due`** : utilise le bus SSE existant (`app/services/sse_bus.py` ou équivalent). Si user a une connexion SSE active (chat ou autre), event `reminder_due` est pushé immédiatement après marquage `sent`. Format payload : `{"reminder_id": uuid, "type": ReminderType, "message": str, "scheduled_at": iso8601, "metadata": {...}}`. Si user n'a pas de SSE actif, le polling 60s frontend (à activer) le récupère au prochain tick. Idempotence : le frontend déduplique par `reminder_id` (ne notifie pas 2× le même).
- **Polling frontend 60s** : activation du dead code `useActionPlan.startReminderPolling` dans `frontend/app/layouts/default.vue`. Hook `onMounted` démarre le polling si `authStore.isAuthenticated`, hook `onUnmounted` arrête. Endpoint backend existant `GET /api/action-plan/reminders/upcoming?limit=5` (à vérifier — sinon créer). Polling expose l'event `onDueReminder(reminder)` qui notifie le composable `useNotifications` (nouveau).
- **`<NotificationCenter>` cloche header** : nouveau composant Vue dans `frontend/app/components/NotificationCenter.vue`. Cloche avec badge unread count, dropdown listant les 10 derniers reminders (lus + non lus), action contextuelle au click selon `type` (ex `intermediary_followup` → `/applications/{entity_id}`, `fund_deadline` → `/financing/{entity_id}`, `assessment_renewal` → `/esg`). Bouton "Tout marquer comme lu" + endpoint `PATCH /api/action-plan/reminders/{id}/read` (à créer si absent). Dark mode obligatoire.
- **Activation `ReminderForm.vue`** : composant existe déjà mais dead code. Brancher dans `frontend/app/pages/action-plan/index.vue` via un bouton "Créer un rappel personnalisé" qui ouvre une modal avec le formulaire. Endpoint `POST /api/action-plan/reminders/` existe déjà, on réutilise. Validation : `type=custom`, `scheduled_at > now()`, `message` 10-500 caractères.
- **Toasts variantes par type** :
  - `intermediary_followup` → bleu (variant `info-blue`) avec icône `MessageCircle`
  - `fund_deadline` → orange (variant `warning`) avec icône `Calendar`
  - `assessment_renewal` → orange (variant `warning`) avec icône `RefreshCw`
  - `attestation_renewal` → rouge (variant `danger`) avec icône `AlertCircle`
  - `action_due` → orange (variant `warning`) avec icône `Clock`
  - `custom` → gris (variant `default`) avec icône `Bell`
- **`<NotificationCenter>` source de vérité** : agrège (a) les reminders polled depuis `/api/action-plan/reminders/upcoming`, (b) les events SSE `reminder_due`, (c) le store `useNotificationsStore` (nouveau — Pinia). Le store conserve la liste cumulée, gère `unread_count`, et expose `markAsRead(id)`, `markAllAsRead()`, `dismiss(id)`. Persistance localStorage de la liste lue (limitée à 50 items, FIFO eviction).
- **Eviction et archivage des reminders** : pas de suppression physique. Reminders avec `sent=TRUE` et `created_at < now() - 90 days` sont marqués `archived=TRUE` (nouvelle colonne booléenne ajoutée par la migration 034) par un job de housekeeping `purge_old_reminders` exécuté hebdomadairement (dimanche 04:00). Les archived sont exclus de l'API list/upcoming. Décision : pas de suppression hard pour préserver l'audit log F03 (event `reminder_dispatched` + `reminder_archived`).
- **F02 multi-tenant** : tous les jobs filtrent strictement par `account_id`. Les reminders sont scopés au compte. Le SSE push est filtré par user (un user ne reçoit que ses propres reminders). Test conformity : `test_no_cross_account_reminder_leak`.
- **F03 audit log** : chaque création de reminder par un job loggué dans `audit_log` (event `reminder_created` avec source=`cron:{job_name}`, account_id, entity_id, dedup_key). Chaque dispatch loggué `reminder_dispatched`. Chaque archive `reminder_archived`. Pas d'audit pour les reminders polled (lecture seule).
- **F07 deadlines** : intégration avec la table `offers.submission_calendar` (jsonb) qui contient les calendriers d'appels à projets. Le job `create_deadline_reminders` parse les `submission_calendar` actifs et crée les rappels J-30/J-7/J-1 pour chaque user dont l'application est liée à l'offre.
- **F08 attestation expiration** : intégration avec la table `attestations` (créée en F08). Champs utilisés : `valid_until`, `revoked_at`. Filtre : `valid_until - 30 days < today() AND revoked_at IS NULL`.
- **F04 versioning + F05 RGPD + F13 referential** : les 3 scripts existent déjà (`backend/scripts/`). F19 ne les modifie PAS — elle les invoque depuis l'APScheduler comme jobs cron. Si le script échoue, log error + send alert (post-MVP : Sentry). Pas de retry MVP (les jobs sont idempotents et tournent quotidiennement).
- **Garde-fou single-process APScheduler** : MVP single-process. Documenté limitation `docs/cron-scheduler.md`. Migration post-MVP : Celery + Redis. Garde-fou : si plusieurs workers FastAPI démarrent (uvicorn `--workers 4`), seul le worker 0 démarre l'APScheduler (variable d'env `APSCHEDULER_ENABLED=true` + lock fichier `/tmp/apscheduler.lock`). Test conformity : `test_apscheduler_starts_only_once`.

## User Scenarios & Testing

### User Story 1 — Dispatcher reminders avec SSE push (Priority: P1)

En tant que **PME utilisatrice**, je veux que mes rappels programmés (deadline fonds, échéance évaluation ESG, etc.) soient automatiquement déclenchés à l'heure prévue et que je reçoive une notification in-app immédiate (toast + cloche header), sans dépendre d'un rafraîchissement manuel.

**Why this priority** : sans dispatcher, tous les reminders existants restent en base mais ne sont jamais envoyés. C'est le cœur fonctionnel de F19, sans quoi le reste (auto-création) est inutile.

**Independent Test** : peut être validé en (a) créant manuellement un Reminder avec `scheduled_at = now() - 1min`, (b) attendant un cycle de 5 min ou en forçant l'exécution du job, (c) vérifiant qu'un event SSE `reminder_due` est émis et que le toast apparaît côté frontend.

**Acceptance Scenarios** :

1. **Given** un Reminder existe avec `scheduled_at = now() - 5min, sent=FALSE`, **When** `dispatch_reminders` s'exécute, **Then** le reminder est marqué `sent=TRUE, sent_at=now()` et un event SSE `reminder_due` est pushé au user actif.
2. **Given** un Reminder déjà marqué `sent=TRUE`, **When** `dispatch_reminders` s'exécute, **Then** il est ignoré (filtre `WHERE sent=FALSE`).
3. **Given** 2 workers tentent de picker le même Reminder, **When** ils utilisent `FOR UPDATE SKIP LOCKED`, **Then** un seul prend la ligne, l'autre passe au reminder suivant (pas de double dispatch).
4. **Given** un user n'a pas de connexion SSE active, **When** un reminder est dispatché, **Then** il sera servi au prochain polling 60s (frontend) via `GET /api/action-plan/reminders/upcoming`.
5. **Given** un Reminder est dispatché, **When** l'event SSE est pushé, **Then** le payload contient `{reminder_id, type, message, scheduled_at, metadata}` et le toast frontend affiche la variante de couleur correspondant au `type`.
6. **Given** un Reminder de type `intermediary_followup` est dispatché, **When** le toast s'affiche, **Then** il utilise la variante bleue (différencier des autres types orange/rouge).
7. **Given** la table contient 200 reminders pending, **When** `dispatch_reminders` s'exécute, **Then** seuls les 100 premiers (ordre `scheduled_at ASC`) sont traités dans ce cycle ; les 100 suivants au prochain cycle (5 min plus tard).

---

### User Story 2 — Auto-création des reminders deadline + silence radio + renewal (Priority: P1)

En tant que **PME utilisatrice**, je veux que des rappels soient automatiquement créés J-30/J-7/J-1 avant chaque échéance importante (deadline fonds, expiration évaluation ESG, expiration attestation, silence radio sur dossier en cours), sans avoir à les saisir manuellement.

**Why this priority** : c'est la valeur métier différenciante de F19 — sans auto-création, l'utilisateur doit créer manuellement chaque rappel, ce qui annule le bénéfice. Les 4 jobs auto-création (deadline, silence radio, assessment renewal, attestation expiration) couvrent les 4 cas d'usage critiques du Module 6.

**Independent Test** : peut être validé en (a) seedant une donnée d'entrée (ex Application avec `application_deadline = today() + 30 days`), (b) exécutant manuellement le job `create_deadline_reminders`, (c) vérifiant qu'un Reminder a été créé avec le `dedup_key` correct et `scheduled_at = today()` (pour J-30).

**Acceptance Scenarios** :

1. **Given** une Application liée à un Fund avec `application_deadline = today() + 30 days`, **When** `create_deadline_reminders` s'exécute, **Then** un Reminder type `fund_deadline` est créé avec `scheduled_at = today()`, `dedup_key = "{account}:fund_deadline:{fund_id}:J-30"`.
2. **Given** la même Application avec `application_deadline = today() + 7 days` ET un reminder J-30 existant, **When** le job s'exécute, **Then** un nouveau Reminder J-7 est créé (dedup_key différent), le J-30 est conservé.
3. **Given** le même reminder est créé 2× le même jour (dedup_key identique), **When** la seconde insertion tente, **Then** la contrainte unique `(account_id, dedup_key)` rejette l'insert (UPSERT idempotent ON CONFLICT DO NOTHING).
4. **Given** une FundApplication `submitted_to_intermediary` avec `submitted_at = today() - 14 days` et aucune mise à jour récente, **When** `create_silence_radio_reminders` s'exécute, **Then** un Reminder type `intermediary_followup` est créé avec `scheduled_at = today()` et `dedup_key = "{account}:intermediary_followup:{application_id}:silence14"`.
5. **Given** la même FundApplication avec `last_status_update = today() - 5 days` (récent), **When** le job s'exécute, **Then** AUCUN reminder n'est créé.
6. **Given** un ESGAssessment finalisé avec `finalized_at = today() - 335 days` (donc J-30 avant 365 jours), **When** `create_assessment_renewal_reminders` s'exécute, **Then** un Reminder type `assessment_renewal` est créé.
7. **Given** une Attestation F08 avec `valid_until = today() + 30 days`, `revoked_at IS NULL`, **When** `create_attestation_expiration_reminders` s'exécute, **Then** un Reminder type `attestation_renewal` est créé.
8. **Given** une Attestation avec `revoked_at != NULL`, **When** le job s'exécute, **Then** AUCUN reminder n'est créé pour cette attestation.

---

### User Story 3 — APScheduler dans lifespan FastAPI + 9 jobs cron (Priority: P1)

En tant qu'**Architecte de la plateforme**, je veux qu'APScheduler soit démarré au boot du backend FastAPI (lifespan) et arrête proprement à l'arrêt, en exécutant 9 jobs cron à des fréquences différentes, sans dépendance Redis ni Celery au MVP. Les 5 scripts standalone existants (F04 fetch_exchange_rates, F05 purge_scheduled_deletions, F07 check_expired_accreditations, F13 check_referential_versions_evolution) doivent être câblés comme jobs cron sans modification.

**Why this priority** : sans APScheduler, aucun job ne tourne. C'est l'infrastructure qui rend US1 et US2 opérationnelles. Les 5 scripts existants tournent actuellement en mode manuel (cron système ou exécution ad-hoc) — F19 les centralise dans le scheduler in-process.

**Independent Test** : peut être validé en (a) démarrant le serveur FastAPI, (b) interrogeant `scheduler.get_jobs()` via une route admin debug ou en logs, (c) vérifiant les 9 jobs présents avec les triggers attendus.

**Acceptance Scenarios** :

1. **Given** le backend démarre (`uvicorn app.main:app`), **When** le lifespan s'exécute, **Then** `AsyncIOScheduler` démarre et 9 jobs sont enregistrés avec les bons triggers cron.
2. **Given** le backend reçoit SIGTERM, **When** le lifespan se termine, **Then** `scheduler.shutdown(wait=True)` est appelé pour terminer proprement les jobs en cours.
3. **Given** APScheduler n'est pas installé (cas dégradé), **When** le backend démarre, **Then** un warning log apparaît (`APScheduler unavailable, cron jobs disabled`) et l'application démarre quand même (mode dégradé).
4. **Given** le backend tourne avec uvicorn `--workers 4`, **When** seul le worker 0 a `APSCHEDULER_ENABLED=true`, **Then** seul ce worker démarre les jobs (lock fichier garantit l'unicité).
5. **Given** le job `fetch_exchange_rates` est appelé par APScheduler à 02:00, **When** il s'exécute, **Then** il invoque la fonction du script `app/scripts/fetch_exchange_rates.py` sans modification de la logique métier.

---

### User Story 4 — Frontend : NotificationCenter + polling 60s + ReminderForm activé (Priority: P2)

En tant que **PME utilisatrice**, je veux voir une cloche de notifications dans le header avec un badge "X non lus", consulter le détail des rappels reçus, marquer comme lu, et créer un rappel personnalisé sans quitter ma page.

**Why this priority** : sans UI, l'utilisateur ne voit pas les rappels en dehors des toasts éphémères. Le NotificationCenter est le hub central des notifications (modèle Slack/Gmail). L'activation de `ReminderForm` (dead code) débloque la fonctionnalité "rappel personnalisé".

**Independent Test** : peut être validé en (a) seedant 3 reminders pour un user, (b) ouvrant le frontend connecté en tant que ce user, (c) vérifiant le badge "3" sur la cloche et la liste correcte dans le dropdown.

**Acceptance Scenarios** :

1. **Given** un user connecté avec 3 reminders unread, **When** la page charge, **Then** la cloche header affiche un badge "3" rouge.
2. **Given** le user clique sur la cloche, **When** le dropdown s'ouvre, **Then** la liste des 10 derniers reminders s'affiche, ordonnée par `scheduled_at DESC`, avec un séparateur visuel entre lus et non lus.
3. **Given** le user clique sur un reminder type `fund_deadline` avec `entity_id={fund-uuid}`, **When** l'action se déclenche, **Then** la navigation va vers `/financing/{fund-uuid}` ET le reminder est marqué `read=TRUE` (via `PATCH /api/action-plan/reminders/{id}/read`).
4. **Given** le user clique "Tout marquer comme lu", **When** l'action s'exécute, **Then** tous les reminders unread sont marqués read en batch + le badge se met à 0.
5. **Given** le user est sur `/action-plan`, **When** il clique "Créer un rappel personnalisé", **Then** la modal `ReminderForm` s'ouvre avec les champs `type=custom`, `scheduled_at`, `message` (10-500 chars).
6. **Given** le user soumet le formulaire avec `scheduled_at=now() + 1 day, message="Préparer dossier ESG"`, **When** la requête `POST /api/action-plan/reminders/` aboutit, **Then** la modal se ferme, un toast succès s'affiche et le NotificationCenter rafraîchit la liste.
7. **Given** le polling 60s est actif, **When** un reminder devient dû entre 2 ticks, **Then** le frontend le récupère au prochain tick et déclenche le toast (si pas déjà vu via SSE).
8. **Given** un reminder est reçu via SSE ET via polling (race condition), **When** le store déduplique par `reminder_id`, **Then** un seul toast s'affiche.

---

### User Story 5 — Migration Alembic 034 (dedup_key + sent_at + archived) + audit log F03 (Priority: P1)

En tant qu'**Architecte**, je veux que la table `reminders` soit étendue avec les colonnes nécessaires (`dedup_key`, `sent_at`, `archived`), avec un index unique partiel sur `(account_id, dedup_key)` pour empêcher les doublons, et que chaque création/dispatch/archive soit logguée dans `audit_log` (F03) pour traçabilité.

**Why this priority** : sans la migration BDD, aucune US ne peut fonctionner (dedup_key requis pour US2, sent_at requis pour US1, archived requis pour le housekeeping). Sans audit log F03, les opérations cron sont invisibles aux admins.

**Independent Test** : peut être validé en (a) lançant `alembic upgrade head`, (b) inspectant la structure de `reminders` (`\d reminders`), (c) tentant un INSERT avec dedup_key déjà présent → rejet IntegrityError.

**Acceptance Scenarios** :

1. **Given** la migration 034 est appliquée, **When** on inspecte la table `reminders`, **Then** 3 nouvelles colonnes existent : `dedup_key VARCHAR(255) NULL`, `sent_at TIMESTAMPTZ NULL`, `archived BOOLEAN NOT NULL DEFAULT FALSE`.
2. **Given** la migration 034 est appliquée, **When** on inspecte les indexes, **Then** un index unique partiel `idx_reminders_dedup_key_unique` existe : `UNIQUE (account_id, dedup_key) WHERE account_id IS NOT NULL AND dedup_key IS NOT NULL`.
3. **Given** 2 INSERT avec même `(account_id, dedup_key)`, **When** le second tente, **Then** `IntegrityError` ou (avec `ON CONFLICT DO NOTHING`) skip silencieux.
4. **Given** un job cron crée un reminder, **When** l'INSERT réussit, **Then** un event `reminder_created` apparaît dans `audit_log` avec `source="cron:create_deadline_reminders"`, `entity_type="Reminder"`, `entity_id={reminder.id}`.
5. **Given** `dispatch_reminders` envoie un reminder, **When** le marquage `sent=TRUE` réussit, **Then** un event `reminder_dispatched` apparaît dans `audit_log`.
6. **Given** la migration est rollback (`alembic downgrade -1`), **When** on inspecte, **Then** les 3 colonnes et l'index sont supprimés sans corruption des données existantes.

---

### User Story 6 — Tests E2E end-to-end (assessment J-30 + silence radio 15j) (Priority: P1)

En tant qu'**Architecte qualité**, je veux des tests E2E qui couvrent les 2 scénarios métier critiques : (a) création d'un assessment ESG, simulation du temps J-30 avant expiration, vérification qu'un reminder est créé puis dispatché et que l'utilisateur voit le toast ; (b) submit d'une application, simulation de 15 jours sans activité, vérification qu'un reminder silence_radio est créé puis dispatché.

**Why this priority** : sans tests E2E, aucune garantie que la chaîne complète (auto-création → dispatch → SSE → toast) fonctionne. C'est la validation finale qui assure que le feature est livrable.

**Independent Test** : autonome, exécuté en CI avec `pytest tests/e2e/test_f19_*.py` + `pytest tests/integration/test_scheduler.py`.

**Acceptance Scenarios** :

1. **Given** un user crée un ESGAssessment finalisé, **When** on simule `finalized_at = now() - 335 days` (J-30 avant 365 jours), **Then** un appel à `create_assessment_renewal_reminders()` crée 1 reminder type `assessment_renewal`.
2. **Given** le reminder est créé avec `scheduled_at = now()`, **When** on appelle `dispatch_reminders()`, **Then** le reminder est marqué `sent=TRUE` et un event SSE `reminder_due` est émis vers le user.
3. **Given** un user submit une FundApplication avec `submitted_at = now() - 15 days`, **When** on appelle `create_silence_radio_reminders()`, **Then** un reminder type `intermediary_followup` est créé.
4. **Given** le reminder silence_radio est dispatché, **When** le frontend reçoit l'event SSE, **Then** un toast bleu s'affiche avec le message "Aucune activité sur votre dossier depuis 14 jours. Relancez l'intermédiaire {nom}."
5. **Given** le user clique "Marquer comme relancé", **When** l'action se déclenche, **Then** le reminder est marqué `read=TRUE` ET un nouveau reminder silence_radio n'est PAS recréé tant que le statut de l'application change ou qu'il n'y a pas de nouvelle activité (déduplication par `dedup_key` empêche la recréation).

---

### Edge Cases

- **Reminder avec `scheduled_at` dans le passé lointain (>30j)** : doit être dispatché tel quel, log warning "stale reminder".
- **Reminder créé à minuit (J-30) mais user en fuseau horaire UTC-7** : `scheduled_at` stocké en UTC, frontend convertit en local. Pas de double dispatch.
- **Backfill `dedup_key` pour reminders existants** : NULL pour `custom`, best-effort pour les autres (basé sur `type` + `action_item_id`).
- **APScheduler crash en cours de job** : le job est marqué failed, retry au prochain trigger. Pas de blocking.
- **Migration appliquée sur BDD avec millions de reminders** : `archived` ajout de colonne avec default = `FALSE` (rapide PG ≥11). `dedup_key` initialement NULL (rapide). L'index unique partiel est créé `CONCURRENTLY` pour ne pas bloquer la table en prod.
- **User supprimé (RGPD F05)** : ses reminders sont purgés via cascade ou via le job F05 `purge_scheduled_deletions` (déjà existant).
- **Toast spam (10 reminders dispatched simultanément)** : le frontend agrège les toasts de même type (ex "Vous avez 3 nouveaux rappels deadline"). Plafond 5 toasts visibles simultanément, le reste va dans la cloche.
- **SSE déconnecté après dispatch** : reminder déjà marqué `sent=TRUE` côté DB → polling 60s frontend le récupère au reconnect.
- **Job cron tourne 2× en parallèle (race)** : `FOR UPDATE SKIP LOCKED` empêche le double-pick. Pour les jobs auto-création, dedup_key empêche les doublons.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système MUST intégrer `APScheduler 3.10+` au lifespan FastAPI (`AsyncIOScheduler`), démarré au boot et stoppé gracieusement à l'arrêt.
- **FR-002**: Le système MUST exposer 9 jobs cron : `dispatch_reminders` (5min), `create_deadline_reminders` (08:00), `create_silence_radio_reminders` (09:00), `create_assessment_renewal_reminders` (10:00), `create_attestation_expiration_reminders` (11:00), `fetch_exchange_rates` (02:00), `purge_scheduled_deletions` (03:00), `check_referential_versions_evolution` (04:00), `check_expired_accreditations` (05:00).
- **FR-003**: La table `reminders` MUST être étendue par la migration 034 avec les colonnes `dedup_key VARCHAR(255) NULL`, `sent_at TIMESTAMPTZ NULL`, `archived BOOLEAN NOT NULL DEFAULT FALSE`, plus un index unique partiel `(account_id, dedup_key)`.
- **FR-004**: Le job `dispatch_reminders` MUST utiliser `FOR UPDATE SKIP LOCKED` pour la concurrence et limiter le batch à 100 reminders/run.
- **FR-005**: Le job `dispatch_reminders` MUST émettre un event SSE `reminder_due` au user concerné après marquage `sent=TRUE, sent_at=now()`.
- **FR-006**: Les 4 jobs auto-création (`create_deadline_reminders`, `create_silence_radio_reminders`, `create_assessment_renewal_reminders`, `create_attestation_expiration_reminders`) MUST utiliser le `dedup_key` au format `{account_id}:{type}:{entity_id}:{trigger_date}` pour empêcher les doublons (UPSERT `ON CONFLICT DO NOTHING`).
- **FR-007**: Le job `create_silence_radio_reminders` MUST détecter les FundApplication avec status `submitted_to_intermediary` ou `submitted_to_fund` ET `submitted_at + 14 days < today()` ET aucune mise à jour de status récente (configurable, défaut 14j).
- **FR-008**: Le job `create_assessment_renewal_reminders` MUST détecter les ESGAssessment finalisés avec `finalized_at + 365 days - 30 days < today()`.
- **FR-009**: Le job `create_attestation_expiration_reminders` MUST détecter les Attestation (F08) avec `valid_until - 30 days < today() AND revoked_at IS NULL`.
- **FR-010**: Le job `create_deadline_reminders` MUST créer 3 reminders par échéance : J-30, J-7, J-1 (3 dedup_keys distincts).
- **FR-011**: Tous les jobs cron MUST scoper strictement par `account_id` (F02 multi-tenant) — aucune fuite cross-account.
- **FR-012**: Toute création de reminder par un job cron MUST être logguée dans `audit_log` (F03) avec `event="reminder_created"`, `source="cron:{job_name}"`.
- **FR-013**: Le frontend MUST activer `useActionPlan.startReminderPolling()` dans `default.vue` (60s) — sortir du dead code.
- **FR-014**: Le frontend MUST exposer un composant `<NotificationCenter>` (cloche header + dropdown + badge unread).
- **FR-015**: Le frontend MUST afficher des toasts variantes par `ReminderType` : `intermediary_followup` bleu, `fund_deadline`/`assessment_renewal`/`action_due` orange, `attestation_renewal` rouge, `custom` gris.
- **FR-016**: Le frontend MUST brancher `ReminderForm.vue` dans `/action-plan` via un bouton + modal.
- **FR-017**: Le frontend MUST déduplique par `reminder_id` les notifications reçues via SSE et polling (pas de double toast).
- **FR-018**: Le système MUST exposer l'endpoint `PATCH /api/action-plan/reminders/{id}/read` pour marquer comme lu (créer si absent).
- **FR-019**: Le système MUST exposer l'endpoint `GET /api/action-plan/reminders/notifications?limit=10&include_read=true` pour le NotificationCenter (créer si absent).
- **FR-020**: Le store frontend `useNotificationsStore` (Pinia) MUST agréger SSE + polling + persistance localStorage (50 items max).
- **FR-021**: Un job hebdomadaire `purge_old_reminders` (dimanche 04:00) MUST archiver les reminders avec `sent=TRUE AND created_at < now() - 90 days`.
- **FR-022**: Le système MUST documenter les limitations APScheduler (single-process MVP) dans `docs/cron-scheduler.md` avec plan migration Celery/Redis post-MVP.
- **FR-023**: Le test conformity `test_apscheduler_starts_only_once` MUST garantir qu'avec uvicorn `--workers 4`, un seul worker démarre les jobs (lock fichier ou env var).
- **FR-024**: Le test conformity `test_no_cross_account_reminder_leak` MUST garantir qu'aucun job ne fuite entre comptes.
- **FR-025**: La migration 034 MUST avoir `down_revision="033_create_skills"` et `revision="034_reminder_dedup_key"`.

### Key Entities

- **Reminder** (extension table existante) : ajout `dedup_key`, `sent_at`, `archived`. Plus une colonne implicite `read` (à vérifier — sinon migration ajoute aussi `read BOOLEAN NOT NULL DEFAULT FALSE`).
- **ReminderType** (enum existant) : `action_due`, `assessment_renewal`, `fund_deadline`, `intermediary_followup`, `custom`. F19 utilise tous ces types + ajoute optionnellement `attestation_renewal` si non couvert (cf clarifications — vérification : si `attestation_renewal` n'existe pas, l'ajouter à l'enum dans la migration 034).
- **ScheduledJob** (concept APScheduler, pas BDD) : 9 jobs configurés au runtime, tracés dans logs.
- **AuditLogEvent** (table F03 existante) : nouveaux events `reminder_created`, `reminder_dispatched`, `reminder_archived`.
- **NotificationStore** (frontend Pinia) : agrège reminders, gère unread_count, dedup par reminder_id.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % des reminders avec `scheduled_at <= now()` sont dispatchés dans les 5 minutes (taux de dispatch effectif sur 1 cycle).
- **SC-002**: 0 doublon de reminder créé par les jobs auto-création (test : exécuter `create_deadline_reminders` 2× consécutivement → 0 nouveau reminder au second run).
- **SC-003**: Le composant `<NotificationCenter>` affiche le bon badge unread count en < 200ms après chargement (perception utilisateur).
- **SC-004**: Couverture tests ≥ 80 % sur les modules `app/scheduler/` et `app/services/notifications/` (rule globale projet).
- **SC-005**: 0 régression sur les 935+ tests backend existants (run `pytest`).
- **SC-006**: Le test E2E "assessment J-30 → reminder créé → toast" passe en moins de 30s.
- **SC-007**: Le test E2E "submit application → silence_radio 15j → reminder créé → toast bleu" passe en moins de 30s.
- **SC-008**: APScheduler démarre en < 500ms au boot (mesure logs).
- **SC-009**: La migration 034 s'applique en < 5s sur BDD avec 10 000 reminders existants (test perf).
- **SC-010**: 0 fuite cross-account détectée par `test_no_cross_account_reminder_leak`.

## Assumptions

- Les 5 scripts standalone existants (`fetch_exchange_rates`, `purge_scheduled_deletions`, `check_referential_versions_evolution`, `check_expired_accreditations`, plus les futurs) exposent une fonction `async def run() -> None` ou équivalent, importable depuis l'APScheduler. Si le contrat n'est pas respecté, créer un wrapper `app/scheduler/jobs/{job}.py` qui adapte.
- Le bus SSE existe déjà (utilisé par le chat) et expose une fonction `notify_user(account_id, event_type, payload)`. Si absent, créer `app/services/sse_bus.py` minimal.
- La table `reminders` a déjà la colonne `read` (vérifier dans la migration 034 — sinon ajouter).
- Le `ReminderType` enum supporte l'ajout de `attestation_renewal` (vérifier — sinon ajouter dans la migration 034 via `ALTER TYPE`).
- Le frontend utilise déjà un système de toasts (vérifier `useToast` ou similaire) — sinon créer un composable minimal.
- L'authentification SSE existe (token dans header ou query) et permet de filtrer par user/account.
- Le composant `ReminderForm.vue` actuel n'a pas de bug bloquant (juste dead code) — vérifier au moment de l'activation.
- Les 5 scripts existants sont idempotents (peuvent être ré-exécutés sans casse) — vérifier sur F04, F05, F07, F13.
- L'environnement single-process suffit pour le MVP (< 1000 utilisateurs actifs simultanés). Migration Celery/Redis est pour post-MVP, documenté.
- La migration 034 peut être appliquée en zero-downtime (colonnes nullable, index `CONCURRENTLY`).
- Les fichiers `frontend/app/components/NotificationCenter.vue`, `frontend/app/composables/useNotifications.ts`, `frontend/app/stores/notifications.ts` n'existent pas encore (à créer).
