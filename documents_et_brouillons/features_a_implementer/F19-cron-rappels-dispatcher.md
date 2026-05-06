# F19 — Cron Dispatcher Rappels + Auto-création Alertes

**Module(s) source(s)** : Module 6.2 (Système de Suivi et Rappels), Module 8.5 (Notifications extension)
**Priorité** : P1 — bloquant pour fonctionnement nominal du Module 6
**Dépendances** : F02 (multi-tenant), F03 (audit), F07 (offer deadlines), F08 (attestation expiration)
**Estimation** : 1.5 sprints

## Contexte & motivation

Module 6.2 du brainstorming :
- Notifications pour échéances (appels à projets, dates limites par offre)
- Rappels actions planifiées
- **Rappels relance intermédiaires si silence radio sur candidature** (différenciateur produit)
- Célébration progrès (gamification)
- Ajustement dynamique du plan

**État actuel** :
- Modèle `Reminder` existe (`backend/app/models/action_plan.py:95-103`) avec types `action_due / assessment_renewal / fund_deadline / intermediary_followup / custom`
- Endpoint création manuelle existe
- **Aucun job cron, aucun APScheduler, aucun Celery** : grep retourne 0
- `mark_reminder_sent` existe mais **jamais appelée automatiquement**
- Polling frontend `useActionPlan.ts:248-269` : **dead code** (export mais aucune invocation dans `default.vue` ou plugin)
- `ReminderForm.vue` : composant existe mais **dead code** (jamais instancié)

**Conséquences** :
- Les rappels sont stockés mais **jamais déclenchés**
- Pas d'alerte deadline → user oublie une candidature
- Pas de relance silence radio intermédiaire → user perd une opportunité
- L'infra de suivi est en place mais **inopérante**

## User stories

- **PME** : « Quand mon évaluation ESG approche de l'expiration (12 mois), je veux recevoir un rappel à J-30, J-7, J-1. »
- **PME** : « Quand un fonds que j'ai en favori ouvre un nouveau call_for_proposals, je veux être alertée à J-30, J-7, J-1 avant la deadline. »
- **PME** : « Quand j'ai soumis un dossier à un intermédiaire et qu'il n'y a pas eu d'activité depuis 14 jours, je veux un rappel "relancer l'intermédiaire". »
- **PME** : « Quand mon attestation crédit expire dans 30 jours, je veux un rappel pour la régénérer. »
- **PME** : « Les rappels apparaissent sous forme de toast in-app + email (post-MVP) + dans la section Notifications du dashboard. »

## Périmètre fonctionnel

### Architecture cron

Choix MVP : **APScheduler** intégré au lifespan FastAPI (pas de Redis/Celery requis).

`backend/app/scheduler/scheduler.py` :
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    scheduler.add_job(dispatch_reminders, "cron", minute="*/5")
    scheduler.add_job(create_deadline_reminders, "cron", hour=8, minute=0)
    scheduler.add_job(create_silence_radio_reminders, "cron", hour=9, minute=0)
    scheduler.add_job(create_assessment_renewal_reminders, "cron", hour=10, minute=0)
    scheduler.add_job(create_attestation_expiration_reminders, "cron", hour=11, minute=0)
    scheduler.add_job(fetch_exchange_rates, "cron", hour=2, minute=0)  # F04
    scheduler.add_job(purge_scheduled_deletions, "cron", hour=3, minute=0)  # F05
    scheduler.start()
    yield
    # shutdown
    scheduler.shutdown()
```

### `dispatch_reminders` (toutes 5 min)

```python
async def dispatch_reminders():
    pending = await db.query(Reminder).filter(
        Reminder.scheduled_at <= datetime.now(),
        Reminder.sent_at.is_(None)
    ).limit(100)
    
    for reminder in pending:
        # Mark sent before processing (avoid duplicate)
        reminder.sent_at = datetime.now()
        await db.commit()
        
        # Push via SSE WebSocket si user actif (post-MVP : Redis pubsub)
        await notify_user_via_sse(reminder.account_id, reminder)
        
        # Send email (post-MVP)
        # await send_reminder_email(...)
```

### Auto-création des Reminders

#### `create_deadline_reminders` (1x/jour)

Pour chaque user avec :
- Fund favori (table `fund_favorites` à créer si absente)
- Application active liée à un Fund avec `application_deadline`
- Application liée à une Offre avec `submission_calendar` (F07)

Créer Reminders à J-30, J-7, J-1 si pas déjà créés (déduplication par `dedup_key`).

#### `create_silence_radio_reminders` (1x/jour)

Pour chaque `FundApplication` :
- Status `submitted_to_intermediary` ou `submitted_to_fund`
- `submitted_at + 14 days < today` ET aucune mise à jour de status récente
- Créer Reminder type `intermediary_followup` avec message "Relancer l'intermédiaire X"

#### `create_assessment_renewal_reminders` (1x/jour)

Pour chaque `ESGAssessment` finalisé :
- `finalized_at + 365 days - 30 days < today` (dans 30 jours)
- Créer Reminder type `assessment_renewal`

#### `create_attestation_expiration_reminders` (1x/jour)

Pour chaque `Attestation` (F08) :
- `valid_until - 30 days < today` ET pas révoquée
- Créer Reminder type `attestation_renewal`

### Déduplication

Champ `dedup_key: str` sur `Reminder` :
- Format : `{account_id}:{type}:{entity_id}:{trigger_date}`
- Index unique pour éviter les duplicatas

### Notifications in-app

#### SSE push

Quand `dispatch_reminders` envoie :
- Si user a une SSE connection active (chat ou autre) : push event `reminder_due`
- Frontend : `useNotifications.ts` qui écoute et affiche un toast

#### Polling frontend (activer le dead code)

Dans `frontend/app/layouts/default.vue` :
```javascript
const { startReminderPolling } = useActionPlan()
onMounted(() => {
  if (authStore.isAuthenticated) {
    startReminderPolling()  // active le polling 60s existant
  }
})
```

#### Composant `<NotificationCenter>`

- Cloche dans le header (badge count des unread)
- Drop-down avec liste des Reminders récents
- Click → action contextuelle (voir candidature, voir évaluation, etc.)
- Mark as read fonctionnel

### Activation `ReminderForm.vue` dead code

Brancher `ReminderForm.vue` dans `pages/action-plan/index.vue` :
- Bouton "Créer un rappel personnalisé"
- Modal avec le formulaire existant
- Endpoint `POST /api/action-plan/reminders/` déjà en place

### Toasts pour rappels intermédiaires

Quand un Reminder type `intermediary_followup` est dispatched :
- Toast bleu (variante différente d'orange/rouge) avec message contextuel
- Bouton "Marquer comme relancé" → met à jour l'application, supprime le reminder

## Hors-scope (post-MVP)

- Email notifications (besoin SMTP / Mailgun / SendGrid)
- SMS notifications (Twilio)
- Push notifications navigateur (Service Worker)
- Snooze / report d'un reminder
- Préférences utilisateur (heures, canaux)
- Templates de message i18n
- Analytics (open rate, click rate)
- Celery + Redis pour scaling horizontal (APScheduler suffit MVP)

## Exigences techniques

### Backend

- Installer `apscheduler>=3.10`
- Module `app/scheduler/` :
  - `scheduler.py` (instance + lifespan integration)
  - `jobs/dispatch_reminders.py`
  - `jobs/create_deadline_reminders.py`
  - `jobs/create_silence_radio_reminders.py`
  - `jobs/create_assessment_renewal_reminders.py`
  - `jobs/create_attestation_expiration_reminders.py`
  - `jobs/fetch_exchange_rates.py` (F04)
  - `jobs/purge_scheduled_deletions.py` (F05)
- Mise à jour `app/main.py` lifespan
- Migration Alembic `033_reminder_dedup_key.py` :
  - Ajouter `dedup_key: str unique` sur `reminders`
- Tests :
  - Test dispatcher : reminder pending → marqué sent → SSE émis
  - Test dedup : même reminder créé deux fois → un seul row
  - Test silence radio : 14j sans activité → reminder créé
  - Test deadline : J-30, J-7, J-1 créés à bon moment
  - Test attestation expiration : J-30 avant valid_until

### Frontend

- Activer `startReminderPolling` dans `default.vue`
- Composant `<NotificationCenter>` dans header
- Toast variant `intermediary_followup` (bleu)
- Brancher `ReminderForm.vue` dans `action-plan`
- Composable `useNotifications.ts`
- Store `stores/notifications.ts`
- Dark mode

### Base de données

- Colonne `dedup_key` ajoutée à `reminders`
- Index unique sur `(account_id, dedup_key)`

## Critères d'acceptation

- [ ] APScheduler intégré au lifespan FastAPI
- [ ] 5+ jobs cron implémentés (dispatch, deadlines, silence radio, assessment renewal, attestation expiration)
- [ ] Dispatcher tourne toutes les 5 min, marque sent, push SSE
- [ ] Auto-création reminders fonctionnelle (4 types automatiques)
- [ ] Déduplication empêche doublons
- [ ] `startReminderPolling` activé dans default.vue (plus dead code)
- [ ] `ReminderForm.vue` branché dans action-plan
- [ ] `<NotificationCenter>` dans header avec badge unread
- [ ] Toasts in-app pour reminders dispatched (variants par type)
- [ ] Test E2E : créer assessment → simuler temps J-30 → reminder créé → user voit toast
- [ ] Test E2E : submit application → simuler 15j → silence_radio reminder créé
- [ ] Couverture tests ≥ 80 % sur jobs

## Risques & garde-fous

- **Risque** : APScheduler en single-process casse au scaling horizontal. **Garde-fou** : OK pour MVP, migration Celery + Redis post-MVP. Documenter limitation.
- **Risque** : un job long bloque les autres. **Garde-fou** : `AsyncIOScheduler` (concurrence), timeout par job.
- **Risque** : explosion volume reminders (1 deadline × 100 fonds × 100 PME × 3 alertes). **Garde-fou** : déduplication, batch processing, archive après envoi.
- **Risque** : SSE déconnexion = miss notification. **Garde-fou** : polling fallback toutes 60s, persistence reminders pour replay au reconnect.
- **Risque** : silence radio reminder envoyé trop tôt si l'intermédiaire répond hors plateforme. **Garde-fou** : permettre user de "marquer relancé" pour stopper l'auto-reminder, paramétrable (post-MVP : 7/14/21 jours).
