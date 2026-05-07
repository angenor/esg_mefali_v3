"""F19 — Instance globale ``AsyncIOScheduler`` + helpers démarrage/arrêt.

L'enregistrement des jobs est fait par :func:`register_jobs`. L'activation
est conditionnée par ``settings.apscheduler_enabled``.

Limitation MVP : single-process. Pour scaler, prévoir un job store SQL
partagé + lock distribué (cf. ``docs/cron-scheduler.md``).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Import optionnel : si APScheduler n'est pas installé, on désactive
# silencieusement (warning au boot dans le lifespan).
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    APSCHEDULER_AVAILABLE = True
except ImportError:  # pragma: no cover
    AsyncIOScheduler = None  # type: ignore[assignment,misc]
    CronTrigger = None  # type: ignore[assignment,misc]
    IntervalTrigger = None  # type: ignore[assignment,misc]
    APSCHEDULER_AVAILABLE = False


def create_scheduler() -> Any | None:
    """Construit une nouvelle instance ``AsyncIOScheduler`` ou None.

    Retourne None si APScheduler indisponible (extra non installé). Permet au
    lifespan FastAPI de loguer le warning et de continuer le démarrage.
    """
    if not APSCHEDULER_AVAILABLE:
        return None
    return AsyncIOScheduler(timezone="UTC")


def register_jobs(scheduler: Any) -> int:
    """Enregistre les jobs F19 sur l'instance ``scheduler`` fournie.

    Retourne le nombre de jobs enregistrés. La liste réelle dépend des jobs
    disponibles côté code (PRIO 1 = dispatcher uniquement, PRIO 2 = jobs
    auto-création). Tout job manquant est skip avec un log info.
    """
    if not APSCHEDULER_AVAILABLE:
        return 0

    count = 0

    # --- PRIO 1 : Dispatcher (5 min) ---
    try:
        from app.scheduler.jobs.dispatch_reminders import run as dispatch_run

        scheduler.add_job(
            dispatch_run,
            trigger=IntervalTrigger(minutes=5),
            id="dispatch_reminders",
            name="F19 — dispatch des reminders dus",
            misfire_grace_time=120,
            coalesce=True,
            replace_existing=True,
        )
        count += 1
    except ImportError as exc:
        logger.info("scheduler.register_jobs | dispatch_reminders skip: %s", exc)

    # --- PRIO 2 : Auto-création (quotidien 06:00 UTC) ---
    for module_name, job_id, name in [
        (
            "app.scheduler.jobs.create_deadline_reminders",
            "create_deadline_reminders",
            "F19 — auto-création reminders deadlines",
        ),
        (
            "app.scheduler.jobs.create_silence_radio_reminders",
            "create_silence_radio_reminders",
            "F19 — auto-création reminders silence radio",
        ),
        (
            "app.scheduler.jobs.create_assessment_renewal_reminders",
            "create_assessment_renewal_reminders",
            "F19 — auto-création reminders renouvellement ESG",
        ),
        (
            "app.scheduler.jobs.create_attestation_expiration_reminders",
            "create_attestation_expiration_reminders",
            "F19 — auto-création reminders expiration attestation",
        ),
    ]:
        try:
            mod = __import__(module_name, fromlist=["run"])
            scheduler.add_job(
                mod.run,
                trigger=CronTrigger(hour=6, minute=0),
                id=job_id,
                name=name,
                misfire_grace_time=3600,
                coalesce=True,
                replace_existing=True,
            )
            count += 1
        except ImportError as exc:
            logger.info("scheduler.register_jobs | %s skip: %s", job_id, exc)

    # --- Housekeeping : purge (quotidien 03:00 UTC) ---
    try:
        from app.scheduler.jobs.purge_old_reminders import run as purge_run

        scheduler.add_job(
            purge_run,
            trigger=CronTrigger(hour=3, minute=0),
            id="purge_old_reminders",
            name="F19 — purge old reminders (housekeeping)",
            misfire_grace_time=3600,
            coalesce=True,
            replace_existing=True,
        )
        count += 1
    except ImportError as exc:
        logger.info("scheduler.register_jobs | purge_old_reminders skip: %s", exc)

    logger.info("scheduler.register_jobs | %d jobs registered", count)
    return count


# Singleton scheduler global, initialisé par le lifespan FastAPI.
scheduler: Any | None = None


def get_scheduler() -> Any | None:
    """Retourne l'instance scheduler globale (None si non démarré)."""
    return scheduler


def start_scheduler() -> Any | None:
    """Crée l'instance et l'enregistre comme singleton global.

    Idempotent : si déjà démarré, retourne l'instance existante.
    """
    global scheduler
    if scheduler is not None and getattr(scheduler, "running", False):
        return scheduler
    instance = create_scheduler()
    if instance is None:
        logger.warning("scheduler.start_scheduler | APScheduler non installé — skip")
        return None
    register_jobs(instance)
    instance.start()
    scheduler = instance
    logger.info("scheduler.start_scheduler | scheduler started")
    return scheduler


def stop_scheduler() -> None:
    """Arrête le scheduler s'il est actif (idempotent)."""
    global scheduler
    if scheduler is not None and getattr(scheduler, "running", False):
        try:
            scheduler.shutdown(wait=True)
            logger.info("scheduler.stop_scheduler | scheduler stopped")
        except Exception as exc:  # noqa: BLE001
            logger.warning("scheduler.stop_scheduler | error: %s", exc)
    scheduler = None
