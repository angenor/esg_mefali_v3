"""ContextVar pour propager la source de mutation à travers les couches.

Module utilitaire (F03 — audit log append-only) qui expose une `ContextVar`
Python ``current_source_of_change`` lue par le mixin ``Auditable`` lors de
l'écriture d'une ligne ``audit_log``.

Valeurs autorisées : ``manual`` (défaut), ``llm`` (positionné par les
nœuds LangGraph), ``import`` (positionné par les futurs scripts CLI batch),
``admin`` (positionné par le middleware ``AdminAuditContextMiddleware`` sur
les routes ``/api/admin/*``).

Pattern recommandé : helper ``source_of_change_scope`` (context manager) qui
``set`` puis ``reset`` automatiquement via Token, garantissant que la valeur
ne « fuit » pas vers la coroutine appelante :

    >>> from app.core.audit_context import source_of_change_scope
    >>> with source_of_change_scope("llm"):
    ...     await service.update(...)  # audit_log.source_of_change = "llm"
    >>> # ici, current_source_of_change.get() == "manual" (valeur restaurée)
"""

from __future__ import annotations

import contextlib
from contextvars import ContextVar, Token
from typing import Iterator, Literal

# Valeurs autorisées pour `source_of_change` (alignées sur l'ENUM PG `audit_source`).
SourceOfChange = Literal["manual", "llm", "import", "admin"]

# Valeurs valides utilisées pour la validation (le ENUM PG les rejette
# également, mais une garde Python évite des erreurs PG silencieuses).
VALID_SOURCES: frozenset[str] = frozenset({"manual", "llm", "import", "admin"})


# ContextVar par défaut « manual » : toute mutation hors LangGraph / hors
# admin / hors import est par conséquent traçée comme manuelle (API REST PME).
current_source_of_change: ContextVar[str] = ContextVar(
    "current_source_of_change", default="manual"
)


def get_current_source_of_change() -> str:
    """Retourne la valeur courante de ``current_source_of_change``.

    Garantit qu'aucune valeur invalide ne fuite vers le mixin (renvoie
    ``"manual"`` en cas de valeur inattendue, par sécurité).
    """
    value = current_source_of_change.get()
    if value not in VALID_SOURCES:
        return "manual"
    return value


def set_source_of_change(value: SourceOfChange) -> Token[str]:
    """Positionne la ``ContextVar`` et retourne un ``Token`` à reset après usage.

    Utiliser de préférence le context manager :func:`source_of_change_scope`
    qui automatise le ``Token.reset``.

    :raises ValueError: si ``value`` n'est pas dans :data:`VALID_SOURCES`.
    """
    if value not in VALID_SOURCES:
        raise ValueError(
            f"source_of_change invalide : {value!r}. "
            f"Attendu : {sorted(VALID_SOURCES)}"
        )
    return current_source_of_change.set(value)


@contextlib.contextmanager
def source_of_change_scope(value: SourceOfChange) -> Iterator[None]:
    """Context manager qui positionne la source du changement puis restaure
    la valeur précédente à la sortie (même en cas d'exception).

    Exemple ::

        with source_of_change_scope("llm"):
            await service.update_company_profile(...)
    """
    token = set_source_of_change(value)
    try:
        yield
    finally:
        current_source_of_change.reset(token)
