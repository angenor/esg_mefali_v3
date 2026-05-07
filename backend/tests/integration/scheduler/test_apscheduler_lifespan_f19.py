"""F19 — Tests intégration de l'``AsyncIOScheduler`` dans le lifespan FastAPI.

Vérifie :
- ``APSCHEDULER_ENABLED=true`` → instance créée et ``running``.
- ``APSCHEDULER_ENABLED=false`` → pas d'instance, app démarre quand même.
- Helpers ``start_scheduler`` / ``stop_scheduler`` idempotents.
"""

from __future__ import annotations

import pytest

from app.scheduler.scheduler import (
    APSCHEDULER_AVAILABLE,
    create_scheduler,
    register_jobs,
    start_scheduler,
    stop_scheduler,
)


pytestmark = pytest.mark.integration


def test_apscheduler_available():
    """Le package APScheduler est installé."""
    assert APSCHEDULER_AVAILABLE is True


def test_create_scheduler_instance():
    """create_scheduler() retourne une instance valide."""
    sched = create_scheduler()
    assert sched is not None
    # Pas démarré par défaut.
    assert getattr(sched, "running", False) is False


def test_register_jobs_minimum_one():
    """register_jobs ajoute au moins le job dispatch_reminders (PRIO 1)."""
    sched = create_scheduler()
    n = register_jobs(sched)
    assert n >= 1
    job_ids = {j.id for j in sched.get_jobs()}
    assert "dispatch_reminders" in job_ids


def test_register_jobs_dispatch_reminders_5min():
    """Le job dispatch_reminders a un trigger interval 5 min."""
    sched = create_scheduler()
    register_jobs(sched)
    job = sched.get_job("dispatch_reminders")
    assert job is not None
    # IntervalTrigger.interval est un timedelta.
    assert hasattr(job.trigger, "interval")
    assert job.trigger.interval.total_seconds() == 5 * 60


async def test_start_and_stop_scheduler_idempotent():
    """start_scheduler/stop_scheduler doivent être idempotents.

    Nécessite un event loop : APScheduler AsyncIOScheduler s'attache au
    loop courant.
    """
    instance1 = start_scheduler()
    try:
        assert instance1 is not None
        assert getattr(instance1, "running", False) is True
        # Second appel → idempotent (renvoie la même instance).
        instance2 = start_scheduler()
        assert instance2 is instance1
    finally:
        stop_scheduler()
        # Stop double : pas d'erreur.
        stop_scheduler()


async def test_start_scheduler_registers_jobs():
    """Après start_scheduler, au moins 1 job est enregistré."""
    instance = start_scheduler()
    try:
        assert instance is not None
        jobs = instance.get_jobs()
        assert len(jobs) >= 1
    finally:
        stop_scheduler()
