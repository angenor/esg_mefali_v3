"""F04 — Exceptions du module versioning."""

from __future__ import annotations


class VersioningError(Exception):
    """Erreur générique du versioning catalogue (format invalide, etc.)."""


class SupersedeCycleError(VersioningError):
    """Cycle détecté dans la chaîne ``superseded_by`` (défense applicative)."""


class NotPublishedError(VersioningError):
    """Une opération de versioning a été tentée sur une entité non publiée."""
