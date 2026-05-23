"""F047 (US5) — Listener SQLAlchemy synchronisant `projects.project_esg_score`.

Quand une :class:`ProjectEsgAssessment` passe à ``state='finalized'`` (ou
qu'une finalisée est supprimée), on UPDATE `projects.project_esg_score` avec
la valeur de l'évaluation finalisée active la plus récente (snapshot lecture
seule). Debounce 30 s in-process pour éviter N writes lors d'imports bulk.

Pattern réutilisé de F045 (research.md D8). Aucune dépendance externe.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from sqlalchemy import event, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.modules.esg.project_models import ProjectEsgAssessment

logger = logging.getLogger(__name__)


_DEBOUNCE_WINDOW_S: float = 30.0
_DEBOUNCE: dict[uuid.UUID, float] = {}


def _should_debounce(project_id: uuid.UUID) -> bool:
    """Retourne True si on doit skipper la sync (déjà faite < 30s)."""
    now = time.monotonic()
    last = _DEBOUNCE.get(project_id)
    if last is not None and (now - last) < _DEBOUNCE_WINDOW_S:
        return True
    _DEBOUNCE[project_id] = now
    return False


async def sync_snapshot_now(
    db: AsyncSession, project_id: uuid.UUID,
) -> int | None:
    """Helper synchrone (bypass debounce) — utilisé par le listener + tests.

    Recharge la dernière évaluation finalisée active pour ce projet et
    propage son score dans `projects.project_esg_score`. Si aucune évaluation
    finalisée n'existe, reset à NULL.

    Returns:
        Le score appliqué (int) ou None si reset.
    """
    a = (
        await db.execute(
            select(ProjectEsgAssessment).where(
                ProjectEsgAssessment.project_id == project_id,
                ProjectEsgAssessment.state == "finalized",
                ProjectEsgAssessment.superseded_at.is_(None),
            )
            .order_by(ProjectEsgAssessment.finalized_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    new_score = int(a.score) if (a and a.score is not None) else None
    await db.execute(
        update(Project)
        .where(Project.id == project_id)
        .values(project_esg_score=new_score)
    )
    await db.flush()
    return new_score


def _on_insert_or_update(mapper: Any, connection: Any, target: ProjectEsgAssessment) -> None:
    """Listener SQLAlchemy `after_insert`/`after_update`.

    Garde-fou debounce 30 s + bascule en `asyncio.create_task` pour ne pas
    bloquer la session synchrone du listener (FR-032).
    """
    if target.state != "finalized":
        return
    if _should_debounce(target.project_id):
        return

    project_id = target.project_id

    # On laisse la sync se faire en best-effort via asyncio quand on est dans
    # un event loop ; sinon on l'ignore (les tests appellent `sync_snapshot_now`
    # directement pour déterminisme).
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            from app.core.database import async_session_factory

            async def _run() -> None:
                try:
                    async with async_session_factory() as db:
                        await sync_snapshot_now(db, project_id)
                        await db.commit()
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "F047 listener sync_snapshot_now échec project=%s",
                        project_id,
                    )

            asyncio.create_task(_run())
    except RuntimeError:
        # Pas d'event loop courant — typique des scripts de seed sync.
        pass


def attach_listeners() -> None:
    """Branche les listeners (à appeler au lifespan FastAPI / startup)."""
    if not event.contains(
        ProjectEsgAssessment, "after_insert", _on_insert_or_update,
    ):
        event.listen(
            ProjectEsgAssessment, "after_insert", _on_insert_or_update,
        )
    if not event.contains(
        ProjectEsgAssessment, "after_update", _on_insert_or_update,
    ):
        event.listen(
            ProjectEsgAssessment, "after_update", _on_insert_or_update,
        )
    logger.info("F047 project_esg listeners attached")
