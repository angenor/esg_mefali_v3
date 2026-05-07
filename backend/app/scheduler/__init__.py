"""F19 — Module scheduler APScheduler MVP single-process.

Ce module héberge :
- ``scheduler.py`` : instance ``AsyncIOScheduler`` + ``register_jobs``.
- ``lock.py`` : verrou démarrage best-effort (single-process).
- ``jobs/`` : 10 jobs cron (5 dispatcher/auto-création + 4 wrappers + 1 housekeeping).

L'activation se fait via ``settings.apscheduler_enabled = True`` dans le
lifespan de FastAPI (cf. ``app/main.py``).

Voir ``docs/cron-scheduler.md`` pour l'architecture détaillée et la migration
post-MVP vers Celery + Redis.
"""
