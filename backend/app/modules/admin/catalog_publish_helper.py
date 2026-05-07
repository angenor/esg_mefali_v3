"""Helper de publication transversal pour le catalogue admin (F09).

Centralise la logique de :
- transition ``draft -> published`` sur les 9 tables catalogue,
- gestion de l'``IntegrityError`` P0001 levée par le trigger PostgreSQL
  ``before_publish_check_sources_verified()`` (publish gating),
- audit log standardisé ``<entity_type>_published``.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.audit_helpers import log_admin_action

logger = logging.getLogger(__name__)


# Mapping entity_type frontend → table BDD.
_ENTITY_TABLE_MAP = {
    "fund": "funds",
    "intermediary": "intermediaries",
    "offer": "offers",
    "referential": "referentials",
    "indicator": "indicators",
    "criterion": "criteria",
    "emission_factor": "emission_factors",
    "simulation_factor": "simulation_factors",
    "required_document": "required_documents",
    # skills utilise sa propre colonne ``status`` (pas publication_status).
    "skill": "skills",
}


class PublishGatingError(Exception):
    """Le publish est bloqué par des sources non verified."""

    def __init__(self, message: str, blocking_sources: list[uuid.UUID] | None = None):
        super().__init__(message)
        self.blocking_sources = blocking_sources or []


class EntityNotFoundError(Exception):
    """L'entité à publier n'existe pas."""


def _parse_blocking_sources(error_message: str) -> int:
    """Extrait le nombre de sources non verified depuis le message PG."""
    match = re.search(r"(\d+) source", error_message)
    return int(match.group(1)) if match else 0


async def publish_entity(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    admin_id: uuid.UUID,
) -> dict:
    """Tente de passer ``entity_type/entity_id`` en ``published``.

    Retourne un dict ``{publication_status, published_at, entity_id,
    entity_type}``. Lève :class:`PublishGatingError` si le trigger BDD
    bloque, :class:`EntityNotFoundError` si l'entité n'existe pas.
    """
    table = _ENTITY_TABLE_MAP.get(entity_type)
    if table is None:
        raise ValueError(f"entity_type inconnu: {entity_type}")

    # skills → colonne ``status`` au lieu de ``publication_status``.
    column = "status" if table == "skills" else "publication_status"

    # Vérifier l'existence (compat str/uuid pour PG vs SQLite).
    eid_str = str(entity_id).replace("-", "")
    eid_with_dashes = str(entity_id)
    res = await db.execute(
        text(
            f"SELECT id FROM {table} WHERE id = :id_a OR id = :id_b "
            f"OR CAST(id AS TEXT) = :id_a OR CAST(id AS TEXT) = :id_b"
        ),
        {"id_a": eid_with_dashes, "id_b": eid_str},
    )
    if res.first() is None:
        raise EntityNotFoundError(f"{entity_type} {entity_id} introuvable")

    try:
        await db.execute(
            text(
                f"UPDATE {table} SET {column} = 'published' "
                f"WHERE (id = :id_a OR id = :id_b OR CAST(id AS TEXT) = :id_a OR CAST(id AS TEXT) = :id_b) "
                f"AND {column} = 'draft'"
            ),
            {"id_a": eid_with_dashes, "id_b": eid_str},
        )
        await db.flush()
    except (IntegrityError, DBAPIError) as exc:
        await db.rollback()
        msg = str(exc).lower()
        if "p0001" in msg or "cannot publish" in msg or "not verified" in msg:
            blocking_count = _parse_blocking_sources(str(exc))
            logger.warning(
                "publish_entity blocked by trigger: type=%s id=%s blocking=%s",
                entity_type,
                entity_id,
                blocking_count,
            )
            raise PublishGatingError(
                f"Publication bloquée: {blocking_count} source(s) non verified",
            ) from exc
        raise

    now = datetime.now(timezone.utc)
    await log_admin_action(
        db,
        admin_id=admin_id,
        action=f"{entity_type}_published",
        entity_type=entity_type,
        entity_id=entity_id,
        metadata={"published_at": now.isoformat()},
    )

    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "publication_status": "published",
        "published_at": now,
    }
