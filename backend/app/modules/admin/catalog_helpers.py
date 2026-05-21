"""Helpers transverses pour `/api/admin/catalog/*` (F25 / feature 044).

Concentre la logique métier réutilisable hors routers :
- Détection d'incohérences (décision D5 research) pour les 4 entités catalogue.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

EntityType = Literal["fund", "intermediary", "offer", "fund_intermediary"]


def compute_has_incoherence(row: Any, entity_type: EntityType) -> bool:
    """Calcul d'incohérence catalogue (décision D5).

    Règles :
    - ``fund`` / ``intermediary`` / ``offer`` : ``publication_status == 'published'``
      mais ``source_id`` NULL → incohérence (publié sans source obligatoire F01).
    - ``fund_intermediary`` : ``accredited_to`` dépassée (< today) sans
      mécanisme d'expiration applicatif explicite (cf. cron F07).

    Le helper accepte un ORM (SQLAlchemy) ou un mapping (Row, dict).
    """
    if entity_type in {"fund", "intermediary", "offer"}:
        publication_status = _get(row, "publication_status")
        source_id = _get(row, "source_id")
        return publication_status == "published" and source_id is None

    if entity_type == "fund_intermediary":
        accredited_to = _get(row, "accredited_to")
        if accredited_to is None:
            return False
        return accredited_to < date.today()

    return False


def _get(row: Any, attr: str) -> Any:
    """Lecture sûre d'un attribut sur un objet ORM ou un mapping."""
    if isinstance(row, dict):
        return row.get(attr)
    return getattr(row, attr, None)


def escape_like_pattern(value: str, escape_char: str = "\\") -> str:
    """Échappe les métacaractères LIKE (``%`` et ``_``) plus l'escape char.

    À utiliser avec ``.like(pattern, escape=escape_char)`` pour empêcher
    un utilisateur de saisir `100%` ou `_test` et obtenir un match
    pattern non voulu (potentiellement full-table scan).
    """
    return (
        value.replace(escape_char, escape_char + escape_char)
        .replace("%", escape_char + "%")
        .replace("_", escape_char + "_")
    )
