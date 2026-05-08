"""F18 — Script CLI pour seeder les facteurs méthodologiques crédit (v1.2).

Idempotent : check ``(version, name)`` UNIQUE avant INSERT.

Pré-requis : les sources F01 doivent être seedées (publishers BCEAO, ADEME,
UEMOA, IPCC). Sinon le script échoue avec un message clair.

Usage::

    cd backend
    source venv/bin/activate
    python scripts/seed_credit_methodology.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Permet d'exécuter le script depuis n'importe quel répertoire.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.database import async_session_factory  # noqa: E402
from app.modules.credit.alternative.seed_methodology import (  # noqa: E402
    seed_credit_methodology_factors,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


async def main() -> int:
    async with async_session_factory() as session:
        try:
            created, skipped = await seed_credit_methodology_factors(session)
            await session.commit()
        except RuntimeError as exc:
            logger.error("Seed échoué : %s", exc)
            return 1

        if created == 0:
            logger.info(
                "Seed credit methodology : tous les facteurs sont déjà présents (%d ignorés)",
                skipped,
            )
        else:
            logger.info(
                "Seed credit methodology : %d facteurs insérés, %d ignorés.",
                created,
                skipped,
            )
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
