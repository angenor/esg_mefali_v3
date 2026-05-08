"""F18 — Cron : purger les données crédit alternatif post-révocation (SC-008).

Cible les lignes ``unused=True`` AND ``purge_after <= now()`` sur :

- :class:`MobileMoneyTransaction` (delete + delete fichier source si dernier
  transaction d'un import ; l'import lui-même est conservé pour traçabilité
  audit ``status='completed'`` mais ses transactions sont effacées).
- :class:`CreditPhoto` (delete + delete fichier disque, best-effort).
- :class:`PublicDataSource` (delete uniquement, pas de fichier — sauf
  ``evidence_path`` si présent).

Idempotent : à chaque run, ne supprime QUE ce qui est arrivé à échéance.
Journalise via le logger applicatif (``audit_log`` est cabré côté
``revoke_consent`` → ici on log structuré pour ops).

Usage::

    cd backend
    source venv/bin/activate
    python scripts/purge_revoked_credit_data.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Permet d'exécuter le script depuis n'importe quel répertoire.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.audit_context import source_of_change_scope  # noqa: E402
from app.core.database import async_session_factory  # noqa: E402
from app.models.credit_alternative import (  # noqa: E402
    CreditPhoto,
    MobileMoneyTransaction,
    PublicDataSource,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def _delete_file_safe(path_str: str | None) -> bool:
    """Best-effort delete d'un fichier disque. Retourne True si supprimé."""
    if not path_str:
        return False
    try:
        p = Path(path_str)
        if p.is_file():
            os.remove(p)
            return True
    except OSError:
        logger.exception("purge_file_delete_failed", extra={"path": path_str})
    return False


async def _purge_mm_transactions(db: AsyncSession, now: datetime) -> tuple[int, int]:
    """Purge MobileMoneyTransaction expirés. Retourne (rows, files)."""
    stmt = select(MobileMoneyTransaction).where(
        MobileMoneyTransaction.unused.is_(True),
        MobileMoneyTransaction.purge_after.isnot(None),
        MobileMoneyTransaction.purge_after <= now,
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    files_deleted = 0
    # Pour chaque transaction, effacer le fichier d'import correspondant
    # SI plus aucune transaction du même import_id n'existe encore.
    seen_imports: set = set()
    for tx in rows:
        seen_imports.add(tx.import_id)
        await db.delete(tx)
    await db.flush()

    if seen_imports:
        from app.models.credit_alternative import MobileMoneyImport

        for import_id in seen_imports:
            # Vérifier qu'il ne reste aucune transaction sur cet import.
            remaining = await db.execute(
                select(MobileMoneyTransaction)
                .where(MobileMoneyTransaction.import_id == import_id)
                .limit(1)
            )
            if remaining.scalar_one_or_none() is None:
                imp = await db.get(MobileMoneyImport, import_id)
                if imp is not None and _delete_file_safe(imp.file_path):
                    files_deleted += 1
                    # On garde l'import en BDD pour audit (status reste).

    return len(rows), files_deleted


async def _purge_credit_photos(db: AsyncSession, now: datetime) -> tuple[int, int]:
    """Purge CreditPhoto expirés."""
    stmt = select(CreditPhoto).where(
        CreditPhoto.unused.is_(True),
        CreditPhoto.purge_after.isnot(None),
        CreditPhoto.purge_after <= now,
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    files_deleted = 0
    for photo in rows:
        if _delete_file_safe(photo.file_path):
            files_deleted += 1
        await db.delete(photo)
    return len(rows), files_deleted


async def _purge_public_data(db: AsyncSession, now: datetime) -> tuple[int, int]:
    """Purge PublicDataSource expirés."""
    stmt = select(PublicDataSource).where(
        PublicDataSource.unused.is_(True),
        PublicDataSource.purge_after.isnot(None),
        PublicDataSource.purge_after <= now,
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    files_deleted = 0
    for src in rows:
        if _delete_file_safe(src.evidence_path):
            files_deleted += 1
        await db.delete(src)
    return len(rows), files_deleted


async def purge_revoked_credit_data(db: AsyncSession) -> dict[str, dict]:
    """Exécute la purge globale (idempotente). Retourne un rapport structuré."""
    now = datetime.now(tz=timezone.utc)
    report: dict[str, dict] = {}

    with source_of_change_scope("manual"):
        rows, files = await _purge_mm_transactions(db, now)
        report["mobile_money_transactions"] = {"rows": rows, "files": files}
        rows, files = await _purge_credit_photos(db, now)
        report["credit_photos"] = {"rows": rows, "files": files}
        rows, files = await _purge_public_data(db, now)
        report["public_data_sources"] = {"rows": rows, "files": files}
        await db.commit()

    logger.info(
        "purge_revoked_credit_data_done",
        extra={"report": report, "now": now.isoformat()},
    )
    return report


async def main() -> int:
    async with async_session_factory() as session:
        report = await purge_revoked_credit_data(session)
    total = sum(v["rows"] for v in report.values())
    logger.info("Purge terminée : %d lignes au total. Détail : %s", total, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
