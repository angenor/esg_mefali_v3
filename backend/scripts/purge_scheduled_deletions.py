"""F05 — Cron job de purge des comptes programmés pour suppression (RGPD Art. 17).

Sélectionne les comptes dont ``deletion_scheduled_at < now() AND deleted_at IS NULL``
puis appelle ``purge_account_data`` pour chacun.

Usage :

.. code-block:: bash

    cd backend
    source venv/bin/activate
    python scripts/purge_scheduled_deletions.py

Idempotent : peut être lancé plusieurs fois par jour sans effet secondaire.
Sera intégré au scheduler global F19 (cron dispatcher) une fois ce dernier
mergé.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone

from sqlalchemy import select

# Ajout du chemin backend pour permettre l'import direct via python scripts/...
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.database import async_session_factory  # noqa: E402
from app.models.account import Account  # noqa: E402
from app.modules.me.purge import purge_account_data  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def fetch_accounts_to_purge() -> list[Account]:
    """Récupère les comptes éligibles à la purge."""
    now = datetime.now(tz=timezone.utc)
    async with async_session_factory() as session:
        result = await session.execute(
            select(Account)
            .where(Account.deletion_scheduled_at.is_not(None))
            .where(Account.deletion_scheduled_at < now)
            .where(Account.deleted_at.is_(None))
            .order_by(Account.deletion_scheduled_at.asc())
        )
        return list(result.scalars().all())


async def main() -> int:
    """Point d'entrée du cron. Retourne le code de sortie."""
    accounts = await fetch_accounts_to_purge()
    if not accounts:
        logger.info("Aucun compte à purger.")
        return 0

    logger.info("Comptes à purger : %d", len(accounts))
    success = 0
    failure = 0
    for account in accounts:
        async with async_session_factory() as session:
            try:
                result = await purge_account_data(session, account.id)
                await session.commit()
                logger.info(
                    "Purge OK : account_id=%s rows_deleted=%s files_removed=%d audit_log_anonymized=%d",
                    result.account_id,
                    result.rows_deleted,
                    result.files_removed,
                    result.audit_log_anonymized,
                )
                success += 1
            except Exception as exc:
                await session.rollback()
                logger.exception(
                    "Purge KO : account_id=%s erreur=%s",
                    account.id,
                    exc,
                )
                failure += 1
    logger.info("Bilan : %d réussites, %d échecs.", success, failure)
    return 0 if failure == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
