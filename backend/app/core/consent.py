"""F05 — Helper applicatif `require_consent` (invariant projet n°5).

Tout traitement non-essentiel de la plateforme (analyse Mobile Money,
photos IA, données publiques, génération d'attestation transmissible, etc.)
DOIT invoquer ``require_consent(db, account_id, type)`` au runtime. Si aucun
consentement actif n'existe, la fonction lève
``HTTPException(403, ...)`` en français — protégeant ainsi l'utilisateur
contre tout traitement non autorisé.

Pattern d'usage avec FastAPI :

.. code-block:: python

    from app.core.consent import consent_dependency

    @router.post(
        "/api/credit/mobile-money/preview",
        dependencies=[Depends(consent_dependency("mobile_money_analysis"))],
    )
    async def preview_mobile_money(...):
        ...
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.consent import (
    CONSENT_SHORT_LABELS,
    CONSENT_TYPE_VALUES,
    Consent,
)


async def require_consent(
    db: AsyncSession,
    account_id: uuid.UUID,
    consent_type: str,
) -> None:
    """Vérifie qu'un consentement actif existe pour le couple (account, type).

    Args:
        db: session SQLAlchemy async.
        account_id: UUID du compte demandant le traitement.
        consent_type: l'un des 7 types valides (cf. ``CONSENT_TYPE_VALUES``).

    Raises:
        HTTPException(403): si aucun consentement actif n'est trouvé.
        HTTPException(422): si ``consent_type`` n'est pas une valeur valide
            (défense en profondeur — devrait être bloqué côté Pydantic).
    """
    if consent_type not in CONSENT_TYPE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "detail": "Type de consentement invalide",
                "consent_type": consent_type,
                "valid_types": list(CONSENT_TYPE_VALUES),
            },
        )

    result = await db.execute(
        select(Consent)
        .where(
            Consent.account_id == account_id,
            Consent.consent_type == consent_type,
            Consent.revoked_at.is_(None),
            Consent.granted.is_(True),
        )
        .limit(1)
    )
    consent = result.scalar_one_or_none()
    if consent is None:
        label = CONSENT_SHORT_LABELS.get(consent_type, consent_type)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "detail": f"Consentement {label} requis pour cette analyse",
                "consent_type": consent_type,
                "settings_url": "/mes-donnees/consentements",
            },
        )


def consent_dependency(consent_type: str) -> Callable:
    """Factory pour dépendance FastAPI déclarative.

    Renvoie une dépendance ``Depends`` qui invoque ``require_consent`` pour
    le ``consent_type`` donné en utilisant l'utilisateur courant (JWT).
    """
    # Import différé pour éviter une dépendance circulaire (deps importe
    # require_consent indirectement via les routers F05).
    from app.api.deps import get_current_user

    async def _dep(
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
    ) -> None:
        if user.account_id is None:
            # Admin sans account_id : pas concerné par les consentements PME.
            return
        await require_consent(db, user.account_id, consent_type)

    return _dep


__all__ = ["require_consent", "consent_dependency"]
