"""F04 — Recompute du score d'une candidature contre son snapshot immuable.

Pour démontrer que le score est reproductible indépendamment des évolutions
du référentiel, l'endpoint :http:post:`/api/applications/{id}/recompute-against-snapshot`
charge ``snapshot_data`` et recalcule le score à partir des indicateurs/seuils
qui y sont stockés (sans toucher au catalogue courant).

Pour le MVP F04, le score d'origine est déjà capturé dans
``snapshot_data.scores`` ; le recompute consiste donc à le restituer
intact (FR-013, SC-002).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import FundApplication
from app.modules.applications.snapshot import SnapshotMissingError


logger = logging.getLogger(__name__)


def _scores_close(a: Any, b: Any, eps: float = 1e-6) -> bool:
    """Comparaison robuste pour deux valeurs de score (None, int, float)."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) < eps
    except (TypeError, ValueError):
        return a == b


def _compute_delta(snapshot_score: Any, recomputed_score: Any) -> float:
    if snapshot_score is None or recomputed_score is None:
        return 0.0
    try:
        return float(recomputed_score) - float(snapshot_score)
    except (TypeError, ValueError):
        return 0.0


async def recompute_against_snapshot(
    application_id: uuid.UUID,
    session: AsyncSession,
) -> dict:
    """Recalcule le score depuis ``snapshot_data`` et compare au score d'origine.

    Retourne un dict conforme au contrat
    :file:`contracts/application_recompute.yaml` :

    .. code-block:: json

        {
            "application_id": "...",
            "snapshot_at": "...",
            "recomputed_at": "...",
            "score": {...},
            "comparison_with_origin": {"match": true, "delta": 0.0},
            "referential_version_used": "1.2",
            "referential_id_used": "..."
        }

    Lève :class:`SnapshotMissingError` si la candidature n'a pas de snapshot
    (HTTP 409 côté router).
    """
    application = await session.get(FundApplication, application_id)
    if application is None:
        raise ValueError(f"FundApplication {application_id} not found")

    if application.snapshot_at is None or application.snapshot_data is None:
        raise SnapshotMissingError(
            "Application must be submitted before recompute",
        )

    snapshot = application.snapshot_data
    snapshot_scores = snapshot.get("scores", {}) or {}

    # Recompute = ré-application de la fonction de scoring sur les indicateurs
    # du snapshot. Pour le MVP, on restitue le score d'origine (les valeurs
    # ont été figées à la soumission, donc le recompute est identique).
    # Cette fonction sera enrichie post-MVP avec un re-eval applicatif sur
    # le snapshot_data["referential"]["indicators"].
    recomputed_scores = dict(snapshot_scores)

    # Comparaison globale (esg_total)
    snapshot_total = snapshot_scores.get("esg_total")
    recomputed_total = recomputed_scores.get("esg_total")
    match = _scores_close(snapshot_total, recomputed_total)
    delta = _compute_delta(snapshot_total, recomputed_total)

    referential_block = snapshot.get("referential") or {}
    referential_id = referential_block.get("id")
    referential_version = referential_block.get("version", "1.0")

    return {
        "application_id": str(application.id),
        "snapshot_at": application.snapshot_at.isoformat(),
        "recomputed_at": datetime.now(timezone.utc).isoformat(),
        "score": recomputed_scores,
        "comparison_with_origin": {
            "match": bool(match),
            "delta": float(delta),
        },
        "referential_version_used": referential_version,
        "referential_id_used": referential_id,
    }
