"""F07 — Cron quotidien de désactivation des offres aux accréditations expirées.

Parcourt les ``FundIntermediary`` ayant ``accredited_to < CURRENT_DATE`` et,
pour chaque offre publiée correspondante, désactive l'offre
(``is_active=false``, ``publication_status='draft'``) + journalise dans
``audit_log`` (F03) avec ``entity_type='offer'``,
``action='auto_unpublished_accreditation_expired'``.

Idempotent : 2 exécutions consécutives n'ont d'effet qu'une fois.

Usage :

.. code-block:: bash

    cd backend
    source venv/bin/activate
    python scripts/check_expired_accreditations.py

Sera intégré au scheduler global F19 (cron dispatcher) une fois ce dernier
mergé.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from datetime import date
from pathlib import Path

# Ajout du chemin backend pour permettre l'import direct via python scripts/...
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import and_, select  # noqa: E402

from app.core.audit_context import source_of_change_scope  # noqa: E402
from app.core.database import async_session_factory  # noqa: E402
from app.models.audit_log import AuditLog  # noqa: E402
from app.models.financing import FundIntermediary  # noqa: E402
from app.models.offer import Offer  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# Action enum value (utilise la valeur string compatible AuditAction enum).
# Note : les actions valides sont 'create', 'update', 'delete', 'view_admin'.
# Pour cron expiration on utilise 'update' avec field='publication_status'.
AUDIT_ACTION = "update"
AUDIT_ENTITY_TYPE = "offer"


async def run(today: date | None = None) -> dict:
    """Exécution principale du cron. Retourne un résumé.

    :param today: date de référence (par défaut ``date.today()``). Permet
        d'injecter une date pour les tests.
    :returns: dict ``{checked, deactivated, unchanged}``.
    """
    today = today or date.today()
    checked = 0
    deactivated = 0
    unchanged = 0

    async with async_session_factory() as session:
        # Sélectionner les fund_intermediaries avec accreditation expirée
        fi_result = await session.execute(
            select(FundIntermediary).where(
                and_(
                    FundIntermediary.accredited_to.isnot(None),
                    FundIntermediary.accredited_to < today,
                )
            )
        )
        expired_pairs = list(fi_result.scalars().all())

        for fi in expired_pairs:
            checked += 1
            # Récupérer les offres publiées+actives correspondantes
            offer_result = await session.execute(
                select(Offer).where(
                    and_(
                        Offer.fund_id == fi.fund_id,
                        Offer.intermediary_id == fi.intermediary_id,
                    )
                )
            )
            offers = list(offer_result.scalars().all())

            for offer in offers:
                # Idempotence : ne désactiver que si publié OU actif
                if offer.publication_status != "published" and not offer.is_active:
                    unchanged += 1
                    continue

                # Désactiver
                offer.publication_status = "draft"
                offer.is_active = False
                deactivated += 1

                # Journaliser via audit_log (F03)
                with source_of_change_scope("import"):
                    audit_entry = AuditLog(
                        id=uuid.uuid4(),
                        user_id=None,  # cron sans user
                        account_id=None,  # offer = catalogue, pas multi-tenant
                        entity_type=AUDIT_ENTITY_TYPE,
                        entity_id=offer.id,
                        action=AUDIT_ACTION,
                        field="publication_status",
                        old_value={"publication_status": "published", "is_active": True},
                        new_value={"publication_status": "draft", "is_active": False},
                        source_of_change="import",
                        actor_metadata={
                            "cron": "check_expired_accreditations",
                            "accreditation_source_id": (
                                str(fi.accreditation_source_id)
                                if fi.accreditation_source_id else None
                            ),
                            "accredited_to": str(fi.accredited_to),
                            "fund_id": str(fi.fund_id),
                            "intermediary_id": str(fi.intermediary_id),
                        },
                    )
                    session.add(audit_entry)
                logger.info(
                    "Offre %s désactivée (accréditation expirée le %s)",
                    offer.id, fi.accredited_to,
                )

        await session.commit()

    summary = {
        "checked": checked,
        "deactivated": deactivated,
        "unchanged": unchanged,
    }
    logger.info("Cron expiration : %s", summary)
    return summary


def main() -> int:
    """Point d'entrée CLI."""
    asyncio.run(run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
