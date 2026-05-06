"""Schémas Pydantic v2 pour le module Admin (F02 squelette, enrichi par F09)."""

from pydantic import BaseModel


class AdminHealthResponse(BaseModel):
    """Réponse de l'endpoint health admin."""

    status: str
    role: str
    service: str
