# Research: F19 — Cron Dispatcher Rappels + Auto-création

**Phase 0 output** | **Date** : 2026-05-07

## R1 — APScheduler vs Celery vs cron système

**Décision** : APScheduler (`AsyncIOScheduler`) pour le MVP.

**Alternatives évaluées** :

| Solution | Pour | Contre |
|----------|------|--------|
| **APScheduler** | Zero infra, intégration native FastAPI/asyncio, support cron+interval+date triggers, persistence optionnelle (jobstore SQL si besoin), pure Python | Single-process (limitation scaling), pas de retry distribué |
| Celery + Redis | Distributed, retry, monitoring (Flower), scaling horizontal | Infra complexe (Redis broker), overhead config, latence |
| cron système (host-level) | Simplicité unix, supervised | Pas portable (Docker/K8s), pas accès aux services Python en mémoire, gestion alembic/db config redondante |

**Justification** : MVP < 1000 utilisateurs simultanés. APScheduler suffit largement et évite l'overhead Redis. Documenté dans `docs/cron-scheduler.md` que la migration Celery+Redis est planifiée post-MVP (cf FR-022).

**Référence** : APScheduler 3.10+ documentation officielle (apscheduler.readthedocs.io).

---

## R2 — `AsyncIOScheduler` vs `BackgroundScheduler`

**Décision** : `AsyncIOScheduler`.

**Justification** : FastAPI tourne dans un event loop asyncio. `AsyncIOScheduler` partage cet event loop (pas de thread dédié), permet d'awaiter des coroutines (jobs `async def`), et utilise `asyncio.create_task` pour la planification. C'est la classe canonique pour FastAPI/Starlette.

**Pattern d'intégration** :
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(dispatch_reminders, "cron", minute="*/5", id="dispatch_reminders")
    # ...
    scheduler.start()
    yield
    scheduler.shutdown(wait=True)
```

**Risque** : si un job long (> 60s) bloque, il peut affecter d'autres jobs. Mitigation : timeout par job + monitoring (post-MVP).

---

## R3 — Single-process garantie (uvicorn `--workers N`)

**Décision** : variable d'environnement `APSCHEDULER_ENABLED` (par défaut `false`). Seul le worker dont `APSCHEDULER_ENABLED=true` démarre les jobs.

**Alternatives** :
- Lock fichier `/tmp/apscheduler.lock` (POSIX `fcntl.flock`) — fonctionne mais fragile sur Docker/K8s (FS éphémère).
- Lock distribué Redis — overkill MVP.

**Pattern recommandé en production** :
- Docker Compose / K8s : 1 réplique avec `APSCHEDULER_ENABLED=true`, autres avec `false`.
- Local dev : par défaut `true` (1 process uvicorn).

**Test conformity** (FR-023) : `tests/integration/scheduler/test_apscheduler_starts_only_once.py` :
- Démarre 2 instances FastAPI avec `APSCHEDULER_ENABLED=true` et `false`
- Vérifie qu'un seul a `app.state.scheduler` actif

---

## R4 — `FOR UPDATE SKIP LOCKED` pour la concurrence dispatch

**Décision** : utiliser le pattern PostgreSQL standard pour empêcher 2 workers de dispatcher le même reminder.

**Pattern SQL** :
```sql
WITH locked AS (
  SELECT id FROM reminders
  WHERE sent = FALSE AND scheduled_at <= NOW()
  ORDER BY scheduled_at ASC
  LIMIT 100
  FOR UPDATE SKIP LOCKED
)
UPDATE reminders r
SET sent = TRUE, sent_at = NOW()
FROM locked
WHERE r.id = locked.id
RETURNING r.*;
```

**SQLAlchemy équivalent** :
```python
stmt = (
    select(Reminder)
    .where(Reminder.sent.is_(False), Reminder.scheduled_at <= func.now())
    .order_by(Reminder.scheduled_at.asc())
    .limit(100)
    .with_for_update(skip_locked=True)
)
result = await session.execute(stmt)
reminders = result.scalars().all()
for r in reminders:
    r.sent = True
    r.sent_at = func.now()
await session.commit()
```

**Test** (R8) : 2 sessions parallèles → chacune pick un sous-set distinct, total = 100 reminders distincts.

**Compatibilité SQLite** : `FOR UPDATE SKIP LOCKED` non supporté. Fallback test : ignorer la clause en SQLite (mock ou skip).

---

## R5 — UPSERT pour `dedup_key`

**Décision** : `INSERT ... ON CONFLICT DO NOTHING` via SQLAlchemy `postgresql.insert().on_conflict_do_nothing()`.

**Pattern** :
```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

stmt = pg_insert(Reminder).values(
    user_id=user.id,
    account_id=user.account_id,
    type=ReminderType.fund_deadline,
    message="...",
    scheduled_at=trigger_date,
    dedup_key=f"{user.account_id}:fund_deadline:{fund.id}:J-30",
).on_conflict_do_nothing(
    index_elements=["account_id", "dedup_key"]
)
await session.execute(stmt)
```

**Justification** : idempotence native, pas de SELECT avant INSERT, performance. Pas besoin de gérer `IntegrityError` au niveau Python.

**Compatibilité SQLite** : `ON CONFLICT DO NOTHING` supporté nativement (syntaxe SQLite).

---

## R6 — Format `dedup_key`

**Décision** : `{account_id}:{type}:{entity_id}:{trigger_date}` (chaîne lisible).

**Exemples** :
- `acc-uuid:fund_deadline:fund-uuid:2026-06-01:J-30`
- `acc-uuid:intermediary_followup:application-uuid:silence14`
- `acc-uuid:assessment_renewal:assessment-uuid:2027-05-07`
- `acc-uuid:attestation_renewal:attestation-uuid:2026-06-07`

**Justification** : human-readable pour debug, longueur < 255 chars, garantit unicité par tuple métier.

**Index partiel** : `CREATE UNIQUE INDEX idx_reminders_dedup_key_unique ON reminders (account_id, dedup_key) WHERE account_id IS NOT NULL AND dedup_key IS NOT NULL`. Permet les `custom` reminders sans dedup_key (NULL) et les legacy reminders sans account_id.

---

## R7 — SSE notification

**Décision** : utilisation du bus SSE existant si présent dans le code base (vérifier `app/services/sse_bus.py`, `app/api/sse.py` ou similaire). Sinon, créer un helper minimal.

**Helper minimal** :
```python
# app/services/notifications/sse_bus.py
from collections import defaultdict
from typing import AsyncIterator
import asyncio
import json

class SSEBus:
    def __init__(self):
        self._connections: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def connect(self, account_id: str) -> AsyncIterator[str]:
        queue: asyncio.Queue = asyncio.Queue()
        self._connections[account_id].append(queue)
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            self._connections[account_id].remove(queue)

    async def notify_user(self, account_id: str, event_type: str, payload: dict):
        for queue in self._connections.get(account_id, []):
            await queue.put({"type": event_type, "payload": payload})

bus = SSEBus()
```

**Note** : si le bus chat existe déjà, le réutiliser. Pas de double infrastructure SSE.

---

## R8 — APScheduler test patterns

**Décision** : tests unitaires invoquent les fonctions de job directement (pas via le scheduler). Tests d'intégration utilisent `MemoryJobStore` + `mock` pour vérifier l'enregistrement des jobs.

**Pattern unit test** :
```python
async def test_create_deadline_reminders_creates_J30():
    # Setup : seed Application avec deadline today() + 30 days
    # Call : await create_deadline_reminders(session)
    # Assert : 1 reminder en base avec scheduled_at=today()
```

**Pattern integration test scheduler** :
```python
def test_apscheduler_lifespan_registers_9_jobs():
    # Boot FastAPI test client
    # Assert : len(app.state.scheduler.get_jobs()) == 10  # 9 + housekeeping hebdo
```

**Pas de wait_real_clock** : on n'attend pas les triggers cron réels. On invoque les fonctions directement.

---

## R9 — Migration zero-downtime sur 10k+ reminders

**Décision** : ajouter colonnes nullable + index `CONCURRENTLY`.

**Pattern Alembic** :
```python
def upgrade():
    op.add_column("reminders", sa.Column("dedup_key", sa.String(255), nullable=True))
    op.add_column("reminders", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reminders", sa.Column("archived", sa.Boolean(), nullable=False, server_default="false"))
    # `read` ajout conditionnel si absente
    
    # Index unique partiel CONCURRENTLY
    op.execute("""
        CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_reminders_dedup_key_unique
        ON reminders (account_id, dedup_key)
        WHERE account_id IS NOT NULL AND dedup_key IS NOT NULL
    """)
    
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reminders_archived_pending
        ON reminders (archived, sent)
    """)
```

**Compat SQLite (tests)** : `CONCURRENTLY` ignoré, `op.create_index` standard.

**Backfill** : best-effort optionnel, pas obligatoire (les reminders existants ne sont pas dispatché par F19 — les nouveaux le sont).

---

## R10 — Frontend dedup SSE+polling

**Décision** : Pinia store avec `Set<string>` des `reminder_id` vus, persistance localStorage limitée à 50 IDs (FIFO).

**Pattern** :
```typescript
// stores/notifications.ts
export const useNotificationsStore = defineStore('notifications', {
  state: () => ({
    reminders: [] as Reminder[],
    seenReminderIds: new Set<string>(),
    unreadCount: 0,
  }),
  actions: {
    addReminder(reminder: Reminder) {
      if (this.seenReminderIds.has(reminder.id)) return  // dedup
      this.seenReminderIds.add(reminder.id)
      this.reminders.unshift(reminder)
      if (this.reminders.length > 50) this.reminders.pop()
      if (!reminder.read) this.unreadCount++
      this.persist()
    },
    persist() {
      const ids = Array.from(this.seenReminderIds).slice(-50)
      localStorage.setItem('notif:seen', JSON.stringify(ids))
    },
  },
})
```

**Justification** : empêche le double toast si un reminder arrive via SSE puis via polling 60s. Set en mémoire + persist localStorage pour survie aux reloads.

---

## R11 — Toast variantes Tailwind

**Décision** : map `ReminderType → variant` dans `useToast.ts` ou helper.

**Mapping** :
```typescript
const TOAST_VARIANT_BY_TYPE: Record<ReminderType, ToastVariant> = {
  intermediary_followup: 'info-blue',
  fund_deadline: 'warning',
  assessment_renewal: 'warning',
  attestation_renewal: 'danger',
  action_due: 'warning',
  custom: 'default',
}

const TOAST_ICON_BY_TYPE: Record<ReminderType, string> = {
  intermediary_followup: 'message-circle',
  fund_deadline: 'calendar',
  assessment_renewal: 'refresh-cw',
  attestation_renewal: 'alert-circle',
  action_due: 'clock',
  custom: 'bell',
}
```

**Classes Tailwind par variant** :
- `info-blue` : `bg-blue-50 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 border-blue-200 dark:border-blue-700`
- `warning` : `bg-orange-50 dark:bg-orange-900/30 text-orange-800 dark:text-orange-200`
- `danger` : `bg-red-50 dark:bg-red-900/30 text-red-800 dark:text-red-200`
- `default` : `bg-gray-50 dark:bg-gray-800 text-gray-800 dark:text-gray-200`

---

## R12 — `ReminderForm.vue` dead code

**Décision** : audit du composant existant avant intégration.

**Checklist audit** :
- [ ] `ReminderForm.vue` appelle bien `POST /api/action-plan/reminders/` ?
- [ ] Validation côté front (scheduled_at > now, message 10-500 chars) ?
- [ ] Émission `success` event après création ?
- [ ] Dark mode complet ?

**Si KO** : fix mineur dans le même PR F19 (sans rewrite complet).

**Intégration** : modal dans `pages/action-plan/index.vue` :
```vue
<ConfirmDialog :open="showReminderModal" @close="showReminderModal = false">
  <ReminderForm @success="onReminderCreated" />
</ConfirmDialog>
```

---

## R13 — Performance dispatch_reminders

**Cible** : < 2s P95 pour 100 reminders/run.

**Mesure** :
- 1 SQL UPDATE...RETURNING avec `FOR UPDATE SKIP LOCKED` : ~ 50-100ms
- N notifications SSE en parallèle (`asyncio.gather`) : ~ 10-50ms total (pas synchronous)
- Overhead audit log F03 : ~ 50-100ms (1 INSERT par reminder dispatched)

**Total estimé** : 150-300ms P50, < 1s P95. Marge confortable vs cible.

**Optimisation si dépassement** : batch audit log inserts, désactiver audit en mode dev.

---

## R14 — Format SSE `reminder_due` event

**Décision** : payload riche avec metadata pour navigation contextuelle.

**Format** :
```json
{
  "type": "reminder_due",
  "payload": {
    "reminder_id": "uuid",
    "type": "fund_deadline",
    "message": "Le fonds GCF clôt les candidatures dans 30 jours",
    "scheduled_at": "2026-05-07T08:00:00Z",
    "metadata": {
      "entity_id": "uuid",
      "entity_type": "fund",
      "action_url": "/financing/{entity_id}"
    }
  }
}
```

**Justification** : `action_url` permet au frontend de naviguer directement au click sur la notification (cf US4 #3).

---

## R15 — Compatibilité tests SQLite (CI rapide)

**Décision** : utiliser `aiosqlite` pour les tests unit/integration. Skip ou mock les patterns PG-only.

**Patterns à adapter** :
- `FOR UPDATE SKIP LOCKED` → ignoré en SQLite (clause silently dropped via dialect check ou monkey-patch)
- `CREATE INDEX CONCURRENTLY` → `CREATE INDEX` (Alembic gère via dialect)
- `ON CONFLICT DO NOTHING` → supporté par SQLite (syntaxe identique)
- `JSONB` → `JSON` via `JSONB().with_variant(JSON(), "sqlite")`

**Tests E2E** : sur PostgreSQL réel via Docker Compose CI.

---

## Décisions transversales

- **Migration revision** : `034_reminder_dedup_key`, `down_revision="033_create_skills"`.
- **Pas de modification du modèle Reminder existant** sauf ajout de colonnes (immutabilité).
- **Pas de tool LangChain** exposé pour création/dispatch reminders (jobs cron only + endpoint REST manuel).
- **Format ISO 8601 UTC** pour tous les timestamps (côté SSE, API, BDD).
- **Pas de retry MVP** : si un job cron échoue, log error + ressaye au prochain trigger. Post-MVP : Sentry alert.
- **Test markers pytest** : `unit`, `integration`, `e2e`, `scheduler`.
