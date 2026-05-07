# Contracts: NotificationCenter REST endpoints (F19)

**Phase 1 output** | **Date** : 2026-05-07

## Overview

F19 ajoute 2 nouveaux endpoints REST pour le composant `<NotificationCenter>` frontend. Tous les endpoints sont protégés par `Depends(get_current_user)` (Bearer JWT) et filtrés par `account_id` (F02 multi-tenant).

---

## Endpoint 1 — `PATCH /api/action-plan/reminders/{id}/read`

**Description** : Marque un reminder comme lu (`read=TRUE`).

### Request

- **Method** : `PATCH`
- **Path** : `/api/action-plan/reminders/{id}/read`
- **Path params** :
  - `id` (UUID, required) — UUID du Reminder
- **Auth** : `Authorization: Bearer <token>`
- **Body** : (vide)

### Response 200 OK

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "read": true,
  "read_at": "2026-05-07T14:30:00Z"
}
```

### Errors

| Status | Code | Description |
|--------|------|-------------|
| 401 | `unauthorized` | Token absent ou invalide |
| 403 | `forbidden` | Le reminder appartient à un autre `account_id` (F02) |
| 404 | `reminder_not_found` | UUID inexistant |
| 422 | `invalid_uuid` | Format UUID invalide |

### Pydantic schemas

```python
# app/schemas/reminders.py
class ReminderReadResponse(BaseModel):
    id: UUID
    read: bool
    read_at: datetime
```

### Authorization rule

```python
async def get_reminder_for_user(reminder_id: UUID, current_user: User, db: AsyncSession) -> Reminder:
    reminder = await db.get(Reminder, reminder_id)
    if reminder is None:
        raise HTTPException(404, "reminder_not_found")
    if reminder.account_id != current_user.account_id:
        raise HTTPException(403, "forbidden")
    return reminder
```

### Implementation note

Ajout d'un champ `read_at: datetime | None` sur le modèle Reminder, ou utilisation de `updated_at` si `TimestampMixin` est appliqué. Décision F19 : utiliser un champ implicite mis à jour côté serveur lors du `PATCH read=TRUE` (cf data-model.md).

### Audit log F03

Pas de log F03 sur cette action (lecture, pas mutation métier critique). Optionnel : log `reminder_read` si tracking UX nécessaire.

### Test cases

| Case | Setup | Expected |
|------|-------|----------|
| Happy path | reminder existe, owner | 200 + `read=true` |
| Cross-account | reminder appartient à un autre account | 403 |
| UUID inexistant | id = `00000000-0000-0000-0000-000000000000` | 404 |
| UUID malformé | id = `invalid` | 422 |
| Pas de token | sans Authorization header | 401 |

---

## Endpoint 2 — `GET /api/action-plan/reminders/notifications`

**Description** : Liste paginée des notifications pour le NotificationCenter (cloche header).

### Request

- **Method** : `GET`
- **Path** : `/api/action-plan/reminders/notifications`
- **Query params** :
  - `limit` (int, default 10, max 50) — taille de la page
  - `include_read` (bool, default true) — inclure les reminders lus
  - `include_archived` (bool, default false) — inclure les archivés
  - `since` (ISO 8601, optional) — ne retourner que les reminders avec `created_at > since`
- **Auth** : `Authorization: Bearer <token>`

### Response 200 OK

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "type": "fund_deadline",
      "message": "Le fonds GCF clôt les candidatures dans 30 jours",
      "scheduled_at": "2026-05-07T08:00:00Z",
      "sent": true,
      "sent_at": "2026-05-07T08:00:15Z",
      "read": false,
      "archived": false,
      "metadata": {
        "entity_id": "f1234567-89ab-cdef-0123-456789abcdef",
        "entity_type": "fund",
        "action_url": "/financing/f1234567-89ab-cdef-0123-456789abcdef"
      },
      "created_at": "2026-05-07T08:00:15Z"
    }
  ],
  "unread_count": 1,
  "total_count": 1,
  "has_more": false
}
```

### Errors

| Status | Code | Description |
|--------|------|-------------|
| 401 | `unauthorized` | Token absent ou invalide |
| 422 | `validation_error` | `limit > 50` ou `since` malformé |

### Pydantic schemas

```python
class ReminderNotificationItem(BaseModel):
    id: UUID
    type: ReminderType
    message: str
    scheduled_at: datetime
    sent: bool
    sent_at: datetime | None
    read: bool
    archived: bool
    metadata: dict[str, Any] = {}
    created_at: datetime

class NotificationListResponse(BaseModel):
    items: list[ReminderNotificationItem]
    unread_count: int
    total_count: int
    has_more: bool
```

### Filter rules (server-side)

```python
stmt = (
    select(Reminder)
    .where(Reminder.account_id == current_user.account_id)
    .where(Reminder.sent.is_(True))  # uniquement les dispatched
)
if not include_read:
    stmt = stmt.where(Reminder.read.is_(False))
if not include_archived:
    stmt = stmt.where(Reminder.archived.is_(False))
if since:
    stmt = stmt.where(Reminder.created_at > since)
stmt = stmt.order_by(Reminder.scheduled_at.desc()).limit(limit)
```

### Audit log F03

Pas de log F03 (lecture).

### Test cases

| Case | Setup | Expected |
|------|-------|----------|
| Happy path | 3 reminders dispatched, 1 unread | items=3, unread_count=1 |
| Limit 1 | 5 reminders, limit=1 | items=1, has_more=true |
| include_read=false | 5 dispatched, 3 read | items=2 |
| include_archived=true | 2 actifs, 1 archived | items=3 |
| since filter | 5 reminders, since=hier | items=2 (ceux d'aujourd'hui) |
| Cross-account isolation | user account A, reminders account B | items=[] |
| Limit > max | limit=200 | 422 validation_error |

---

## Endpoint 3 (debug, feature-flagged) — `GET /api/admin/scheduler/jobs`

**Description** : Liste des jobs APScheduler enregistrés. Activé uniquement si `ADMIN_DEBUG_SCHEDULER=true`.

### Request

- **Method** : `GET`
- **Path** : `/api/admin/scheduler/jobs`
- **Auth** : `Authorization: Bearer <admin_token>` + `require_admin_role`

### Response 200 OK

```json
{
  "scheduler_running": true,
  "scheduler_state": "running",
  "jobs": [
    {
      "id": "dispatch_reminders",
      "name": "F19 — Dispatch des reminders pending",
      "trigger": "cron[minute='*/5']",
      "next_run_time": "2026-05-07T14:25:00+00:00",
      "misfire_grace_time": 60
    },
    ...
  ]
}
```

### Implementation

```python
@router.get("/api/admin/scheduler/jobs", dependencies=[Depends(require_admin_role)])
async def list_scheduler_jobs(request: Request):
    if not settings.admin_debug_scheduler:
        raise HTTPException(404, "feature_disabled")
    scheduler = request.app.state.scheduler
    jobs = [
        {
            "id": job.id,
            "name": job.name,
            "trigger": str(job.trigger),
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "misfire_grace_time": job.misfire_grace_time,
        }
        for job in scheduler.get_jobs()
    ]
    return {
        "scheduler_running": scheduler.running,
        "scheduler_state": scheduler.state,
        "jobs": jobs,
    }
```

---

## Endpoint 4 (debug, feature-flagged) — `POST /api/admin/scheduler/trigger/{job_id}`

**Description** : Déclenche manuellement un job. Activé uniquement si `ADMIN_DEBUG_SCHEDULER=true`. Pour tests E2E et debug.

### Request

- **Method** : `POST`
- **Path** : `/api/admin/scheduler/trigger/{job_id}`
- **Auth** : Admin Bearer + `require_admin_role`

### Response 200 OK

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

### Errors

| Status | Code | Description |
|--------|------|-------------|
| 403 | `forbidden` | Pas admin |
| 404 | `job_not_found` | `job_id` inconnu |
| 404 | `feature_disabled` | `ADMIN_DEBUG_SCHEDULER=false` |
| 500 | `job_failed` | Exception lors du run (payload contient le traceback) |

---

## Endpoint 5 (health) — `GET /api/admin/scheduler/health`

**Description** : Health check du scheduler pour monitoring.

### Response 200 OK

```json
{
  "scheduler_running": true,
  "jobs_count": 10,
  "last_dispatch_run": "2026-05-07T14:25:00+00:00",
  "last_dispatch_dispatched_count": 3,
  "errors_last_24h": 0
}
```

### Response 503 Service Unavailable

```json
{
  "scheduler_running": false,
  "reason": "apscheduler_unavailable_or_lock_held"
}
```

---

## Compliance with project conventions

- **Endpoint 1 et 2** : prefixe `/api/action-plan/reminders/` aligné avec les endpoints existants du module Action Plan.
- **Endpoints 3-5** : prefixe `/api/admin/scheduler/` pour la séparation admin/user.
- **F02 multi-tenant** : tous les endpoints utilisateurs filtrent par `current_user.account_id`. Les endpoints admin requièrent `require_admin_role`.
- **F03 audit log** : pas requis sur la lecture. Optionnel sur les actions admin (`scheduler_job_triggered_manually`).
- **Pagination** : pattern `limit + has_more` cohérent avec le reste de l'API.
- **Format datetime** : ISO 8601 UTC, conforme à la convention projet.
