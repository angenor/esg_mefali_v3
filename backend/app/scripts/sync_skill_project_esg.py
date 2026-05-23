"""F047 (US3 fix) — Synchroniser la skill F23 `skill_project_esg_assessment`
en base avec le contenu actuel de `app.modules.skills.seed._build_seeds`.

Idempotent : si la skill n'existe pas, NOOP (laisser le seed.py s'en charger
au prochain startup). Si elle existe, on rafraîchit `prompt_expert`,
`procedure`, `tool_whitelist` et `golden_examples` (les seuls champs
touchés par le bug US3). Le `status` (DRAFT/PUBLISHED) et `version` sont
préservés.

Usage::

    cd backend && source venv/bin/activate
    python -m app.scripts.sync_skill_project_esg
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.database import async_session_factory  # noqa: E402
from app.models.skill import Skill  # noqa: E402
from app.modules.skills.seed import _build_seeds  # noqa: E402

logging.basicConfig(level=logging.INFO, format="[sync-skill] %(message)s")
logger = logging.getLogger(__name__)

# F047 bugfix US3 (2026-05-23) : sync étendu aux 3 skills MVP. F047 a touché
# `skill_esg_diagnostic.activation_rules` (resserrement intent_keywords pour
# éviter de matcher les demandes projet) ET `skill_project_esg_assessment`
# (procedure + intent_keywords + golden_examples). Lancer ce script après
# modification de seed.py pour aligner la BDD sans reseed complet.
TARGET_NAMES = (
    "skill_esg_diagnostic",
    "skill_project_esg_assessment",
    "skill_score_gcf",
    "skill_dossier_gcf_via_boad",
)

# Champs synchronisés. `activation_rules` est inclus car le bugfix US3 modifie
# les intent_keywords (mécanique de scoring F23).
SYNCED_FIELDS = (
    "prompt_expert",
    "procedure",
    "tool_whitelist",
    "golden_examples",
    "activation_rules",
)


async def sync_one(db: AsyncSession, name: str) -> bool:
    """Met à jour une skill si elle existe ; retourne True si modifiée."""
    skill = (
        await db.execute(select(Skill).where(Skill.name == name))
    ).scalar_one_or_none()
    if skill is None:
        logger.info("%s introuvable en BDD — seed.py au prochain startup.", name)
        return False

    seed = next(
        (s for s in _build_seeds(uuid.uuid4()) if s["name"] == name),
        None,
    )
    if seed is None:
        logger.warning("%s introuvable dans _build_seeds — skip.", name)
        return False

    changed = False
    for field in SYNCED_FIELDS:
        current = getattr(skill, field, None)
        new_value = seed.get(field)
        if current != new_value:
            setattr(skill, field, new_value)
            changed = True
            logger.info("[%s]  - %s mis à jour", name, field)

    if changed:
        logger.info("[%s] synchronisée (status préservé=%s).", name, skill.status)
    else:
        logger.info("[%s] déjà à jour.", name)
    return changed


async def main() -> None:
    async with async_session_factory() as db:
        any_changed = False
        for name in TARGET_NAMES:
            if await sync_one(db, name):
                any_changed = True
        if any_changed:
            await db.commit()
            logger.info("Commit effectué.")
        else:
            logger.info("Aucune modification ; pas de commit.")


if __name__ == "__main__":
    asyncio.run(main())
