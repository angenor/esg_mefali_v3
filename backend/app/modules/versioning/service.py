"""F04 — Service de versioning catalogue (bump version, supersede, anti-cycle).

Le pattern : à l'édition d'une entité publiée, on insère une nouvelle ligne
avec ``version`` incrémenté (bump minor par défaut), et on met à jour
l'ancienne ligne avec ``valid_to=today`` et ``superseded_by=new.id``.

Le cycle dans ``superseded_by`` est protégé par un trigger PL/pgSQL
(``prevent_supersede_cycle()``) côté PostgreSQL et par une vérification
applicative dans :func:`supersede` côté SQLite (tests).
"""

from __future__ import annotations

import re
import uuid
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.versioning.exceptions import (
    NotPublishedError,
    SupersedeCycleError,
    VersioningError,
)


VERSION_FORMAT_RE = re.compile(r"^(\d+)\.(\d+)$")


def bump_version(current: str, force_major: bool = False) -> str:
    """Incrémente une version semver-like ``MAJOR.MINOR``.

    - ``force_major=False`` (défaut) : bump minor (1.0 → 1.1).
    - ``force_major=True`` : bump major (1.0 → 2.0, minor remis à 0).

    Lève :class:`VersioningError` si le format ne correspond pas à
    ``^\\d+\\.\\d+$``.
    """
    if not isinstance(current, str):
        raise VersioningError(f"version must be a string, got {type(current).__name__}")
    m = VERSION_FORMAT_RE.match(current)
    if not m:
        raise VersioningError(
            f"invalid version format '{current}' (expected MAJOR.MINOR)",
        )
    major, minor = int(m.group(1)), int(m.group(2))
    if force_major:
        return f"{major + 1}.0"
    return f"{major}.{minor + 1}"


def is_published(entity: object) -> bool:
    """Détermine si une entité versionnée est publiée (active).

    Convention : une entité est « publiée » si elle a soit :

    - un champ ``publication_status`` égal à ``'published'`` ;
    - OU un champ ``valid_to`` à ``None`` (et pas de ``publication_status``).
    """
    pub_status = getattr(entity, "publication_status", None)
    if pub_status is not None:
        return str(pub_status) == "published"
    valid_to = getattr(entity, "valid_to", None)
    return valid_to is None


async def _walk_supersede_chain(
    session: AsyncSession,
    model_cls: type,
    start_id: uuid.UUID | None,
    max_depth: int = 100,
) -> list[uuid.UUID]:
    """Retourne la liste des ids visités en remontant ``superseded_by``."""
    visited: list[uuid.UUID] = []
    cur = start_id
    depth = 0
    while cur is not None:
        if cur in visited:
            return visited
        visited.append(cur)
        depth += 1
        if depth > max_depth:
            raise SupersedeCycleError(
                f"supersede chain too deep on {model_cls.__name__} (max={max_depth})",
            )
        result = await session.execute(
            select(model_cls.superseded_by).where(model_cls.id == cur),
        )
        row = result.scalar_one_or_none()
        cur = row
    return visited


async def supersede(
    session: AsyncSession,
    model_cls: type,
    old_id: uuid.UUID,
    new_id: uuid.UUID,
    today: date | None = None,
) -> None:
    """Marque ``old_id`` comme remplacé par ``new_id`` (mise à jour atomique).

    - Vérifie l'absence de cycle (recherche applicative en remontant la chaîne
      depuis ``new_id`` ; si ``old_id`` est rencontré → :class:`SupersedeCycleError`).
    - Met à jour ``valid_to=today`` et ``superseded_by=new_id`` sur la ligne
      ``old_id``.

    Cette fonction n'insère PAS la nouvelle version : c'est la responsabilité
    de l'appelant (helper :func:`create_new_version` ou code admin).
    """
    if old_id == new_id:
        raise SupersedeCycleError(
            f"cannot supersede {model_cls.__name__} {old_id} by itself",
        )

    # Vérification applicative anti-cycle : remonter depuis new_id
    chain = await _walk_supersede_chain(session, model_cls, new_id)
    if old_id in chain:
        raise SupersedeCycleError(
            f"supersede cycle detected: {old_id} appears in chain of {new_id} "
            f"on {model_cls.__name__}",
        )

    today = today or date.today()
    await session.execute(
        update(model_cls)
        .where(model_cls.id == old_id)
        .values(valid_to=today, superseded_by=new_id),
    )


async def create_new_version(
    session: AsyncSession,
    entity: object,
    *,
    force_major: bool = False,
    today: date | None = None,
) -> dict:
    """Prépare la création d'une nouvelle version d'une entité publiée.

    Retourne un dict ``{old_id, new_version, new_valid_from}`` que l'appelant
    utilisera pour insérer la nouvelle ligne (le service ne connaît pas les
    champs concrets de l'entité).

    Lève :class:`NotPublishedError` si l'entité n'est pas publiée.
    """
    if not is_published(entity):
        raise NotPublishedError(
            f"{type(entity).__name__} is not published, "
            "edit-in-place instead of versioning",
        )
    today = today or date.today()
    current_version = getattr(entity, "version", "1.0") or "1.0"
    return {
        "old_id": entity.id,
        "new_version": bump_version(str(current_version), force_major=force_major),
        "new_valid_from": today,
    }
