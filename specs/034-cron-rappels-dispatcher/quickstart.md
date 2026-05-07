# Quickstart: F19 — Cron Dispatcher Rappels

**Phase 1 output** | **Date** : 2026-05-07

## Prérequis

- Backend Python 3.12+ avec `venv` activé
- PostgreSQL 16 + pgvector running (port 5432)
- Migration 034 appliquée : `alembic upgrade head`
- `apscheduler>=3.10` installé : `pip install apscheduler`

## 1. Démarrer le scheduler en local

### Mode dev (single uvicorn)

```bash
cd backend
source venv/bin/activate
export APSCHEDULER_ENABLED=true
uvicorn app.main:app --reload
```

Sortie attendue dans les logs :
```
INFO  Démarrage APScheduler...
INFO  Job 'dispatch_reminders' enregistré (cron */5 minutes)
INFO  Job 'create_deadline_reminders' enregistré (cron 08:00)
INFO  Job 'create_silence_radio_reminders' enregistré (cron 09:00)
INFO  Job 'create_assessment_renewal_reminders' enregistré (cron 10:00)
INFO  Job 'create_attestation_expiration_reminders' enregistré (cron 11:00)
INFO  Job 'fetch_exchange_rates' enregistré (cron 02:00)
INFO  Job 'purge_scheduled_deletions' enregistré (cron 03:00)
INFO  Job 'check_referential_versions_evolution' enregistré (cron 04:00)
INFO  Job 'check_expired_accreditations' enregistré (cron 05:00)
INFO  Job 'purge_old_reminders' enregistré (cron sun 04:00)
INFO  APScheduler démarré avec 10 jobs
```

### Mode production (uvicorn workers)

```bash
# Worker 0 : avec scheduler
APSCHEDULER_ENABLED=true uvicorn app.main:app --workers 1 --port 8000 &

# Workers 1-3 : sans scheduler
APSCHEDULER_ENABLED=false uvicorn app.main:app --workers 3 --port 8001 &
```

Garde-fou : si plusieurs workers ont `APSCHEDULER_ENABLED=true`, le lock fichier (`/tmp/apscheduler.lock`) garantit qu'un seul démarre effectivement.

### Mode dégradé (APScheduler indisponible)

Si `apscheduler` n'est pas installé :
```
WARN  apscheduler unavailable — cron jobs disabled (mode dégradé)
```

L'application démarre quand même. Les reminders ne sont pas dispatchés.

## 2. Déclencher un job manuellement (dev/debug)

### Endpoint debug (feature-flagged)

**Activation** :
```bash
export ADMIN_DEBUG_SCHEDULER=true
uvicorn app.main:app --reload
```

**Lister les jobs** :
```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     http://localhost:8000/api/admin/scheduler/jobs
```

Réponse :
```json
{
  "scheduler_running": true,
  "jobs": [
    {
      "id": "dispatch_reminders",
      "next_run_time": "2026-05-07T14:25:00+00:00",
      "trigger": "cron[minute='*/5']"
    },
    ...
  ]
}
```

**Déclencher un job** :
```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
     http://localhost:8000/api/admin/scheduler/trigger/dispatch_reminders
```

Réponse :
```json
{
  "job_id": "dispatch_reminders",
  "started_at": "2026-05-07T14:23:15+00:00",
  "duration_ms": 245,
  "result": {
    "dispatched_count": 3,
    "errors": []
  }
}
```

### Invocation directe (sans HTTP)

```bash
cd backend
source venv/bin/activate
python -m app.scheduler.jobs.dispatch_reminders
```

## 3. Test E2E manuel : assessment J-30

```bash
# 1. Créer un user + assessment finalisé
curl -X POST http://localhost:8000/api/auth/register \
     -d '{"email":"test@pme.fr","password":"SecurePass123"}'
# Récupérer token

# 2. Créer un ESGAssessment finalisé manuellement (admin SQL)
psql $DATABASE_URL -c "
  UPDATE esg_assessments
  SET finalized_at = NOW() - INTERVAL '335 days'
  WHERE user_id = '$USER_ID' LIMIT 1;
"

# 3. Déclencher le job
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
     http://localhost:8000/api/admin/scheduler/trigger/create_assessment_renewal_reminders

# 4. Vérifier création reminder
psql $DATABASE_URL -c "
  SELECT type, dedup_key, scheduled_at FROM reminders
  WHERE user_id = '$USER_ID' ORDER BY created_at DESC LIMIT 1;
"

# 5. Déclencher le dispatcher
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
     http://localhost:8000/api/admin/scheduler/trigger/dispatch_reminders

# 6. Vérifier dispatch
psql $DATABASE_URL -c "
  SELECT sent, sent_at FROM reminders
  WHERE user_id = '$USER_ID' AND type = 'assessment_renewal' LIMIT 1;
"
```

Frontend : ouvrir `/dashboard` connecté en tant que ce user → toast orange `assessment_renewal` doit apparaître.

## 4. Test E2E manuel : silence radio 15j

```bash
# 1. Créer une FundApplication submitted
curl -X POST -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/applications/ \
     -d '{"fund_id":"$FUND_ID","status":"submitted_to_intermediary"}'

# 2. Backdater submitted_at
psql $DATABASE_URL -c "
  UPDATE fund_applications
  SET submitted_at = NOW() - INTERVAL '15 days'
  WHERE id = '$APP_ID';
"

# 3. Déclencher le job
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
     http://localhost:8000/api/admin/scheduler/trigger/create_silence_radio_reminders

# 4. Vérifier
psql $DATABASE_URL -c "
  SELECT type, dedup_key FROM reminders
  WHERE type = 'intermediary_followup' AND user_id = '$USER_ID';
"
```

Frontend : toast bleu `intermediary_followup` doit apparaître après dispatch.

## 5. Test idempotence (déduplication)

```bash
# Lancer le job 2× consécutivement
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
     http://localhost:8000/api/admin/scheduler/trigger/create_assessment_renewal_reminders

curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
     http://localhost:8000/api/admin/scheduler/trigger/create_assessment_renewal_reminders

# Vérifier qu'aucun doublon n'a été créé
psql $DATABASE_URL -c "
  SELECT COUNT(*), dedup_key FROM reminders
  WHERE type = 'assessment_renewal'
  GROUP BY dedup_key;
"
# Doit retourner 1 reminder par dedup_key
```

## 6. Inspecter l'audit log F03

```bash
psql $DATABASE_URL -c "
  SELECT event_type, source, entity_type, entity_id, created_at
  FROM audit_log
  WHERE entity_type = 'Reminder'
  ORDER BY created_at DESC LIMIT 20;
"
```

Sortie attendue :
```
   event_type      |              source              | entity_type |    entity_id     |       created_at
-------------------+----------------------------------+-------------+------------------+------------------------
 reminder_dispatched | cron:dispatch_reminders         | Reminder    | abc-...          | 2026-05-07 14:25:01+00
 reminder_created   | cron:create_assessment_renewal  | Reminder    | abc-...          | 2026-05-07 14:23:32+00
```

## 7. Frontend : NotificationCenter

### Activer le polling (déjà fait par F19 dans `default.vue`)

```vue
<!-- frontend/app/layouts/default.vue -->
<script setup lang="ts">
const { startReminderPolling } = useActionPlan()
const notifStore = useNotificationsStore()

onMounted(() => {
  if (authStore.isAuthenticated) {
    notifStore.hydrateFromStorage()
    startReminderPolling((reminder) => {
      notifStore.addReminder(reminder)
      // Toast déclenché automatiquement par le watcher du store
    })
  }
})

onUnmounted(() => {
  stopReminderPolling()
})
</script>
```

### Tester la cloche

1. Ouvrir le frontend connecté.
2. Déclencher un dispatch côté backend.
3. Vérifier la cloche header : badge "1" doit apparaître.
4. Cliquer sur la cloche : dropdown s'ouvre avec le reminder.
5. Cliquer sur le reminder : navigation vers `metadata.action_url` + reminder marqué `read=TRUE`.
6. Cloche revient à 0.

### Créer un reminder personnalisé (ReminderForm activé)

1. Naviguer vers `/action-plan`.
2. Cliquer sur le bouton "Créer un rappel personnalisé" (en haut à droite).
3. Remplir le formulaire : `scheduled_at = demain 09:00`, `message = "Préparer mon dossier"`.
4. Soumettre. Toast succès.
5. Vérifier dans le NotificationCenter (dropdown) : reminder visible.

## 8. Debug & monitoring

### Logs structurés

Tous les jobs émettent des logs structurés au format :
```
INFO  scheduler.dispatch_reminders | dispatched=3 errors=0 duration_ms=245
INFO  scheduler.create_deadline_reminders | created=12 skipped_dup=8 duration_ms=850
WARN  scheduler.create_silence_radio_reminders | created=0 (no candidate found)
ERROR scheduler.fetch_exchange_rates | failed: HTTPError 503 (api.exchangerate.host)
```

### Health check

```bash
curl http://localhost:8000/api/admin/scheduler/health
```

Réponse :
```json
{
  "scheduler_running": true,
  "jobs_count": 10,
  "last_dispatch_run": "2026-05-07T14:25:00+00:00",
  "last_dispatch_dispatched_count": 3,
  "errors_last_24h": 0
}
```

### Désactiver temporairement un job

```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
     http://localhost:8000/api/admin/scheduler/pause/dispatch_reminders
```

```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
     http://localhost:8000/api/admin/scheduler/resume/dispatch_reminders
```

## 9. Tests automatisés

```bash
# Unit tests
pytest backend/tests/unit/scheduler/ -v

# Integration tests (PostgreSQL réel via Docker Compose)
docker-compose up -d postgres
pytest backend/tests/integration/scheduler/ -v

# E2E tests F19
pytest backend/tests/e2e/test_f19_*.py -v

# Couverture
pytest backend/tests/ --cov=app/scheduler --cov=app/services/notifications --cov-report=term-missing
# Cible : ≥ 80 %
```

## 10. Migration / rollback

```bash
# Appliquer
cd backend && alembic upgrade head

# Vérifier
alembic current
# Doit afficher : 034_reminder_dedup_key (head)

# Rollback (si besoin)
alembic downgrade -1
# Retire dedup_key, sent_at, archived (et les indexes)
# La valeur enum 'attestation_renewal' n'est PAS retirée (PG ne supporte pas DROP VALUE)
```

## 11. Références

- Spec : [spec.md](./spec.md)
- Plan : [plan.md](./plan.md)
- Data model : [data-model.md](./data-model.md)
- Contracts : [contracts/](./contracts/)
- Tasks : [tasks.md](./tasks.md)
- APScheduler doc : https://apscheduler.readthedocs.io/en/3.x/
- Pattern `FOR UPDATE SKIP LOCKED` : https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE
- Doc projet : `docs/cron-scheduler.md` (créé par F19)
