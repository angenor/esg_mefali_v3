"""F21 — Exceptions typées du module rapport carbone."""

from __future__ import annotations


class CarbonReportError(Exception):
    """Erreur de base du module rapport carbone."""


class AssessmentNotFinalizedError(CarbonReportError):
    """Le bilan carbone n'est pas finalisé : génération refusée (FR-017)."""


class ConcurrentGenerationError(CarbonReportError):
    """Une génération est déjà en cours pour ce bilan (FR-018)."""


class AssessmentNotFoundError(CarbonReportError):
    """Bilan carbone introuvable ou non possédé par la PME courante."""
