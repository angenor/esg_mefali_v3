# Contracts: APScheduler Jobs Configuration (F19)

**Phase 1 output** | **Date** : 2026-05-07

## Vue d'ensemble

F19 enregistre 10 jobs dans `AsyncIOScheduler` au démarrage du lifespan FastAPI. Tous les jobs sont des coroutines `async def run() -> dict`. Les 4 jobs F04/F05/F07/F13 sont câblés via wrappers minimaux qui invoquent les scripts existants sans modifier leur logique.

## Configuration globale

```python
# app/scheduler/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

scheduler = AsyncIOScheduler(
    jobstores={"default": MemoryJobStore()},
    executors={"default": AsyncIOExecutor()},
    job_defaults={
        "coalesce": True,           # fusionne les runs manqués
        "max_instances": 1,         # 1 instance simultanée par job
        "misfire_grace_time": 3600, # par défaut, override per-job
    },
    timezone="UTC",
)
```

## Tableau des 10 jobs

| Job ID | Trigger | Misfire Grace | Module | Fonction |
|--------|---------|---------------|--------|----------|
| `dispatch_reminders` | `cron(minute="*/5")` | 60s | `app.scheduler.jobs.dispatch_reminders` | `run` |
| `create_deadline_reminders` | `cron(hour=8, minute=0)` | 3600s | `app.scheduler.jobs.create_deadline_reminders` | `run` |
| `create_silence_radio_reminders` | `cron(hour=9, minute=0)` | 3600s | `app.scheduler.jobs.create_silence_radio_reminders` | `run` |
| `create_assessment_renewal_reminders` | `cron(hour=10, minute=0)` | 3600s | `app.scheduler.jobs.create_assessment_renewal_reminders` | `run` |
| `create_attestation_expiration_reminders` | `cron(hour=11, minute=0)` | 3600s | `app.scheduler.jobs.create_attestation_expiration_reminders` | `run` |
| `fetch_exchange_rates` | `cron(hour=2, minute=0)` | 3600s | `app.scheduler.jobs.fetch_exchange_rates_wrapper` | `run` |
| `purge_scheduled_deletions` | `cron(hour=3, minute=0)` | 3600s | `app.scheduler.jobs.purge_scheduled_deletions_wrapper` | `run` |
| `check_referential_versions_evolution` | `cron(hour=4, minute=0)` | 3600s | `app.scheduler.jobs.check_referential_versions_evolution_wrapper` | `run` |
| `check_expired_accreditations` | `cron(hour=5, minute=0)` | 3600s | `app.scheduler.jobs.check_expired_accreditations_wrapper` | `run` |
| `purge_old_reminders` | `cron(day_of_week=0, hour=4, minute=0)` | 7200s | `app.scheduler.jobs.purge_old_reminders` | `run` |

## Spec détaillée de chaque job

### 1. `dispatch_reminders`

- **But** : Picker les reminders dûs (`scheduled_at <= now() AND sent=FALSE`), les marquer `sent=TRUE, sent_at=NOW()`, push SSE `reminder_due`.
- **Trigger** : toutes les 5 minutes.
- **Batch limit** : 100.
- **Concurrency** : `FOR UPDATE SKIP LOCKED`.
- **Retour** : `{"dispatched_count": int, "errors": list[str]}`.
- **Audit F03** : `reminder_dispatched` per reminder.

```python
async def run() -> dict:
    async with async_session() as db:
        # 1. Lock + select 100 pending
        stmt = (
            select(Reminder)
            .where(Reminder.sent.is_(False), Reminder.scheduled_at <= func.now(), Reminder.archived.is_(False))
            .order_by(Reminder.scheduled_at.asc())
            .limit(100)
            .with_for_update(skip_locked=True)
        )
        reminders = (await db.execute(stmt)).scalars().all()
        if not reminders:
            return {"dispatched_count": 0, "errors": []}
        
        now = datetime.now(timezone.utc)
        errors = []
        for r in reminders:
            try:
                r.sent = True
                r.sent_at = now
                # Push SSE
                payload = build_reminder_payload(r)
                await sse_bus.notify_user(r.account_id, "reminder_due", payload)
                # Audit log
                await audit_log_create(db, "reminder_dispatched", "Reminder", r.id, source="cron:dispatch_reminders", account_id=r.account_id)
            except Exception as exc:
                errors.append(f"reminder={r.id}: {exc}")
        await db.commit()
        return {"dispatched_count": len(reminders), "errors": errors}
```

### 2. `create_deadline_reminders`

- **But** : Pour chaque user, créer reminders J-30/J-7/J-1 avant chaque deadline (Fund favori, Application liée à Fund avec deadline, Application liée à Offre avec submission_calendar).
- **Trigger** : 1×/jour à 08:00 UTC.
- **Idempotence** : UPSERT `ON CONFLICT (account_id, dedup_key) DO NOTHING`.
- **dedup_key** : `{account_id}:fund_deadline:{fund_or_offer_id}:{deadline_iso}:J-{N}`.
- **Retour** : `{"created_count": int, "skipped_dup": int}`.
- **Audit F03** : `reminder_created` per insert.

### 3. `create_silence_radio_reminders`

- **But** : Détecter FundApplications submitted depuis 14j+ sans activité, créer reminder `intermediary_followup`.
- **Trigger** : 1×/jour à 09:00 UTC.
- **Filtre** : `status IN ('submitted_to_intermediary', 'submitted_to_fund') AND submitted_at + 14 days < today() AND last_status_update IS NULL OR last_status_update + 7 days < today()`.
- **dedup_key** : `{account_id}:intermediary_followup:{application_id}:silence14`.
- **Retour** : `{"created_count": int, "skipped_dup": int}`.

### 4. `create_assessment_renewal_reminders`

- **But** : Détecter ESGAssessment finalisés à J-30 avant expiration 365j.
- **Trigger** : 1×/jour à 10:00 UTC.
- **Filtre** : `finalized_at + 365 days - 30 days < today() AND finalized_at + 365 days > today()`.
- **dedup_key** : `{account_id}:assessment_renewal:{assessment_id}`.
- **Retour** : `{"created_count": int, "skipped_dup": int}`.

### 5. `create_attestation_expiration_reminders`

- **But** : Détecter Attestations F08 à J-30 avant `valid_until`.
- **Trigger** : 1×/jour à 11:00 UTC.
- **Filtre** : `valid_until - 30 days < today() AND valid_until > today() AND revoked_at IS NULL`.
- **dedup_key** : `{account_id}:attestation_renewal:{attestation_id}`.
- **Retour** : `{"created_count": int, "skipped_dup": int}`.

### 6. `fetch_exchange_rates` (wrapper F04)

- **But** : Récupérer taux de change BCEAO/ECB → table `exchange_rates`.
- **Trigger** : 1×/jour à 02:00 UTC.
- **Wrapper** : invoque `app.scripts.fetch_exchange_rates.run()` (existant).
- **Pas de modification du script F04**.

```python
# app/scheduler/jobs/fetch_exchange_rates_wrapper.py
from app.scripts import fetch_exchange_rates as f04_script

async def run() -> dict:
    return await f04_script.run()
```

### 7. `purge_scheduled_deletions` (wrapper F05)

- **But** : Purger comptes/données scheduled_for_deletion (RGPD).
- **Trigger** : 1×/jour à 03:00 UTC.
- **Wrapper** : invoque `scripts.purge_scheduled_deletions.run()`.

### 8. `check_referential_versions_evolution` (wrapper F13)

- **But** : Détecter évolutions de référentiels (taxonomies, ODD), créer alertes.
- **Trigger** : 1×/jour à 04:00 UTC.
- **Wrapper** : invoque `scripts.check_referential_versions_evolution.check_referential_versions_evolution(dry_run=False)`.

### 9. `check_expired_accreditations` (wrapper F07)

- **But** : Marquer expired les accréditations Fund-Intermediary.
- **Trigger** : 1×/jour à 05:00 UTC.
- **Wrapper** : invoque `scripts.check_expired_accreditations.run()`.

### 10. `purge_old_reminders` (housekeeping nouveau)

- **But** : Marquer `archived=TRUE` les reminders avec `sent=TRUE AND created_at < now() - 90 days`.
- **Trigger** : hebdomadaire dimanche 04:00 UTC.
- **Pas de DELETE physique** (préservation audit log F03).
- **Retour** : `{"archived_count": int}`.

## Lifespan integration

```python
# app/main.py (extrait)
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ... LangGraph init ...
    
    # F19 — APScheduler
    scheduler_started = False
    if settings.apscheduler_enabled:
        try:
            from app.scheduler.scheduler import scheduler, register_jobs
            register_jobs(scheduler)
            scheduler.start()
            app.state.scheduler = scheduler
            scheduler_started = True
            logger.info("APScheduler démarré avec %d jobs", len(scheduler.get_jobs()))
        except ImportError as e:
            logger.warning("apscheduler unavailable — cron jobs disabled: %s", e)
        except Exception as e:
            logger.error("Failed to start APScheduler: %s", e)
    else:
        logger.info("APSCHEDULER_ENABLED=false — scheduler désactivé pour ce worker")
    
    yield
    
    # Shutdown
    if scheduler_started and hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown(wait=True)
        logger.info("APScheduler arrêté")
```

## Configuration via env vars

```bash
# .env
APSCHEDULER_ENABLED=true              # Active le scheduler sur ce worker
ADMIN_DEBUG_SCHEDULER=false           # Active les endpoints admin debug (default false en prod)
APSCHEDULER_LOCK_PATH=/tmp/apscheduler.lock  # Path du lock fichier (optionnel)
SILENCE_RADIO_DELAY_DAYS=14           # Configurable (default 14)
ASSESSMENT_RENEWAL_GRACE_DAYS=30      # J-N avant 365 (default 30)
ATTESTATION_EXPIRATION_GRACE_DAYS=30  # J-N avant valid_until (default 30)
DEADLINE_REMINDER_DAYS=30,7,1         # Liste des J-N créés (default 30,7,1)
DISPATCH_BATCH_LIMIT=100              # Max reminders/dispatch run (default 100)
PURGE_OLD_REMINDERS_AFTER_DAYS=90     # Archive après N jours (default 90)
```

## Test patterns

### Unit test

```python
@pytest.mark.unit
@pytest.mark.asyncio
async def test_dispatch_reminders_marks_sent_and_emits_sse(db_session, sse_bus_mock):
    # Setup : 1 reminder pending
    reminder = await create_test_reminder(db_session, scheduled_at=now() - timedelta(minutes=5))
    
    # Run
    from app.scheduler.jobs.dispatch_reminders import run
    result = await run()
    
    # Assert
    assert result["dispatched_count"] == 1
    await db_session.refresh(reminder)
    assert reminder.sent is True
    assert reminder.sent_at is not None
    sse_bus_mock.notify_user.assert_called_once()
```

### Integration test (lifespan)

```python
@pytest.mark.integration
def test_apscheduler_registers_10_jobs(monkeypatch):
    monkeypatch.setenv("APSCHEDULER_ENABLED", "true")
    with TestClient(app) as client:
        scheduler = client.app.state.scheduler
        assert scheduler.running
        assert len(scheduler.get_jobs()) == 10
        job_ids = {j.id for j in scheduler.get_jobs()}
        assert job_ids == {
            "dispatch_reminders",
            "create_deadline_reminders",
            "create_silence_radio_reminders",
            "create_assessment_renewal_reminders",
            "create_attestation_expiration_reminders",
            "fetch_exchange_rates",
            "purge_scheduled_deletions",
            "check_referential_versions_evolution",
            "check_expired_accreditations",
            "purge_old_reminders",
        }
```

### Concurrency test

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_dispatch_reminders_concurrent_no_double_dispatch(db_session_factory):
    # Setup : 100 reminders pending
    async with db_session_factory() as db:
        for _ in range(100):
            await create_test_reminder(db, scheduled_at=now() - timedelta(minutes=5))
        await db.commit()
    
    # Run 2 dispatchers in parallel
    from app.scheduler.jobs.dispatch_reminders import run
    results = await asyncio.gather(run(), run())
    
    # Assert : no overlap (some did 100, the other did 0 or split)
    total = sum(r["dispatched_count"] for r in results)
    assert total == 100  # No double dispatch
```

## Garde-fous

- **Single-process** : env var `APSCHEDULER_ENABLED` + lock fichier optional. Test conformity FR-023.
- **F02 isolation** : tous les jobs filtrent par `account_id`. Test FR-024.
- **Idempotence** : UPSERT `ON CONFLICT DO NOTHING` partout.
- **Misfire** : `coalesce=True` empêche les exécutions cumulées après downtime.
- **Max 1 instance par job** : pas d'overlap entre 2 ticks du même cron.
