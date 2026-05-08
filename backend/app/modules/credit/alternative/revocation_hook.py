"""F18 — Hook RGPD : marquer les données crédit alternatif comme inutilisées
après révocation d'un consentement F05 (SC-008).

Mapping consent_type → tables à invalider :

- ``mobile_money_analysis`` → ``MobileMoneyTransaction``,
  ``MobileMoneyAnalysis`` (consent_active=False).
- ``photos_ia_analysis`` → ``CreditPhoto``.
- ``public_data_analysis`` → ``PublicDataSource``.

Effet : ``unused=True`` + ``purge_after = now() + 30 jours``. La purge
effective des fichiers + lignes est faite par le cron
:mod:`scripts.purge_revoked_credit_data`.

Idempotent : appelable plusieurs fois sans effet additionnel (les lignes
``unused=True`` ne sont pas re-marquées).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_context import source_of_change_scope
from app.models.credit_alternative import (
    CreditPhoto,
    MobileMoneyAnalysis,
    MobileMoneyTransaction,
    PublicDataSource,
)

logger = logging.getLogger(__name__)


# Délai de rétention RGPD post-révocation (SC-008).
PURGE_DELAY_DAYS: int = 30


def _is_truthy(value: object) -> bool:
    """Tolère bool natif PG et string ``"false"`` / ``"true"`` SQLite."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "t")
    return bool(value)


_CONSENT_TO_TABLES: dict[str, tuple] = {
    "mobile_money_analysis": (MobileMoneyTransaction,),
    "photos_ia_analysis": (CreditPhoto,),
    "public_data_analysis": (PublicDataSource,),
}


async def mark_credit_data_unused_on_revoke(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    consent_type: str,
) -> dict[str, int]:
    """Marque ``unused=True`` et fixe ``purge_after`` sur les données dépendantes.

    Args:
        db: session async (la commit est laissée à l'appelant pour rester
            atomique avec :func:`revoke_consent`).
        account_id: compte concerné par la révocation.
        consent_type: type de consentement révoqué.

    Returns:
        Dict ``{table_name: rows_affected}`` pour observabilité / audit.
    """
    affected: dict[str, int] = {}
    tables = _CONSENT_TO_TABLES.get(consent_type)
    if not tables:
        # Type non concerné (profil/document/communications) — no-op.
        return affected

    purge_after = datetime.now(tz=timezone.utc) + timedelta(days=PURGE_DELAY_DAYS)

    # Source = ``manual`` (l'utilisateur révoque, donc action manuelle PME).
    with source_of_change_scope("manual"):
        for model in tables:
            # Récupérer toutes les lignes du tenant et filtrer en Python
            # (server_default ``"false"`` est stocké en string sur SQLite,
            # rendant ``unused.is_(False)`` peu portable). En production
            # PostgreSQL, le boolean est natif ; le filtre Python est un
            # no-op coûteux mais safe.
            count_stmt = select(model).where(model.account_id == account_id)
            rows = list((await db.execute(count_stmt)).scalars().all())
            # Filtre Python : ne re-marquer que les rows non encore unused
            # (idempotence — l'attribut ``unused`` peut être bool natif PG
            # ou string ``"false"`` sur SQLite tests, donc filtre tolérant).
            to_mark = [r for r in rows if not _is_truthy(r.unused)]
            for row in to_mark:
                row.unused = True
                row.purge_after = purge_after
            affected[model.__tablename__] = len(to_mark)
        await db.flush()

        # Cas particulier : MobileMoneyAnalysis (artefact agrégé) → on
        # invalide consent_active=False sans toucher unused (pas de purge
        # de fichier).
        if consent_type == "mobile_money_analysis":
            ana_stmt = select(MobileMoneyAnalysis).where(
                MobileMoneyAnalysis.account_id == account_id,
            )
            analyses = list((await db.execute(ana_stmt)).scalars().all())
            to_invalidate = [a for a in analyses if _is_truthy(a.consent_active)]
            for a in to_invalidate:
                a.consent_active = False
            affected[MobileMoneyAnalysis.__tablename__] = len(to_invalidate)
            await db.flush()

    logger.info(
        "credit_alternative_consent_revoked",
        extra={
            "account_id": str(account_id),
            "consent_type": consent_type,
            "purge_after": purge_after.isoformat(),
            "affected": affected,
        },
    )
    return affected


__all__ = ["mark_credit_data_unused_on_revoke", "PURGE_DELAY_DAYS"]
