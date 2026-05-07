"""F23 — Script CLI pour seeder les 3 skills MVP critiques.

Idempotent : check les noms existants avant insert.

Usage :
    cd backend
    source venv/bin/activate
    python scripts/seed_skills.py
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

from sqlalchemy import select  # noqa: E402

from app.core.database import async_session_factory  # noqa: E402
from app.models.user import User  # noqa: E402
from app.modules.skills.seed import seed_skills  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def main() -> int:
    async with async_session_factory() as session:
        # Recherche un admin pour created_by.
        admin_stmt = select(User).where(User.role == "ADMIN").limit(1)
        admin = (await session.execute(admin_stmt)).scalar_one_or_none()
        if admin is None:
            logger.error(
                "Aucun admin trouvé en BDD. Créez d'abord un User role=ADMIN "
                "(via admin invite ou seed)."
            )
            return 1

        inserted = await seed_skills(session, default_creator_id=admin.id)
        await session.commit()
        if inserted == 0:
            logger.info("Seed skills : toutes les 3 skills sont déjà présentes.")
        else:
            logger.info("Seed skills : %d skills insérées.", inserted)
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
