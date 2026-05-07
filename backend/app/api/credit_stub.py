"""F05 — Stub pour démontrer le gating ``consent_dependency``.

Ce router est volontairement minimaliste : il existe pour permettre aux
tests d'intégration F05 (T091, T092 + scénario E2E n°4) de vérifier que
le helper ``consent_dependency`` bloque effectivement les appels lorsque le
consentement requis n'est pas accordé.

Quand F18 (Mobile Money + Photos IA + Données publiques) sera implémenté,
ce stub sera remplacé par le router F18 qui réutilisera la même garde
``Depends(consent_dependency('mobile_money_analysis'))`` etc.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.core.consent import consent_dependency

router = APIRouter()


@router.post(
    "/mobile-money/preview",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    dependencies=[Depends(consent_dependency("mobile_money_analysis"))],
)
async def preview_mobile_money() -> dict[str, str]:
    """Endpoint stub démontrant le gating consent ``mobile_money_analysis``.

    Renvoie 501 (NotImplemented) si le consentement est accordé, 403 sinon
    (via la dépendance ``consent_dependency``).
    """
    return {
        "detail": "F18 not implemented yet, but consent gating works",
    }


__all__ = ["router"]
