"""F045 - Seed des 4 sources F01 obligatoires pour le matching projet-centric.

Idempotent : SELECT-before-INSERT par URL (UNIQUE index ``sources_url_uniq_idx``).

Sources seedees (status='verified', four-eyes captured_by != verified_by) :
1. Taxonomie verte UEMOA - BCEAO 2024 (R1, regulatory_taxonomy)
2. GCF Strategic Plan 2024-2027 - Priority Themes (R2)
3. GCF Updated Gender Policy 2019 (R3)
4. ODD 10 - Reduce Inequality - UN Statistics Indicators (R4)

Reference : research.md R1+R2+R3+R4+R10, data-model.md §4.

Usage::

    cd backend && source venv/bin/activate
    python -m app.scripts.seed_sources_045

Ou via API/script depuis un test :

    inserted = await seed_sources_045(db, captured_by_id=..., verified_by_id=...)
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

# Permet d'executer le script depuis n'importe quel repertoire.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.database import async_session_factory  # noqa: E402
from app.models.source import Source, VerificationStatus  # noqa: E402
from app.models.user import User  # noqa: E402

logger = logging.getLogger(__name__)


SEED_SOURCES_045: list[dict] = [
    {
        "url": "https://www.bceao.int/sites/default/files/taxonomie-verte-uemoa-2024.pdf",
        "title": "Taxonomie verte UEMOA — BCEAO 2024",
        "publisher": "BCEAO",
        "version": "1.0",
        "date_publi": date(2024, 1, 1),
        "section": "Activités vertes éligibles UEMOA",
    },
    {
        "url": "https://www.greenclimate.fund/sites/default/files/document/gcf-strategic-plan-2024-2027.pdf",
        "title": "GCF Strategic Plan 2024-2027 — Priority Themes",
        "publisher": "Green Climate Fund",
        "version": "2024-2027",
        "date_publi": date(2024, 1, 1),
        "section": "Result Areas — atténuation, adaptation, cross-cutting",
    },
    {
        "url": "https://www.greenclimate.fund/document/updated-gender-policy-2019",
        "title": "GCF Updated Gender Policy 2019",
        "publisher": "Green Climate Fund",
        "version": "2019",
        "date_publi": date(2019, 7, 1),
        "section": "Gender mainstreaming, gender-responsive projects",
    },
    {
        "url": "https://unstats.un.org/sdgs/metadata/?Text=&Goal=10",
        "title": "ODD 10 — Reduce Inequality — UN Statistics Indicators",
        "publisher": "UN Statistics Division",
        "version": "2023-09",
        "date_publi": date(2023, 9, 1),
        "section": "Indicateurs vulnérabilité (femmes, jeunes, handicapés, réfugiés, déplacés)",
    },
]


async def _get_existing_urls(db: AsyncSession) -> set[str]:
    urls = [s["url"] for s in SEED_SOURCES_045]
    result = await db.execute(select(Source.url).where(Source.url.in_(urls)))
    return {row[0] for row in result.all()}


async def _ensure_two_admins(db: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Retourne 2 UUID d'admins distincts (cree un admin technique si besoin).

    Suit le pattern F23 seed_skills : utilise les admins existants ou cree
    ``admin-verifier@mefali-system`` comme second admin.
    """
    result = await db.execute(
        select(User).where(User.role == "ADMIN").limit(2)
    )
    admins = list(result.scalars().all())

    if len(admins) >= 2:
        return admins[0].id, admins[1].id

    if len(admins) == 0:
        raise RuntimeError(
            "seed_sources_045 : aucun admin trouve en BDD ; creez d'abord un "
            "admin via ``python -m app.scripts.seed_admin``."
        )

    # 1 admin existant -> on cree admin-verifier@mefali-system
    captured_by = admins[0]
    verifier = User(
        email="admin-verifier@mefali-system",
        hashed_password="!disabled!",
        full_name="Mefali System — Verifier Technique",
        company_name="Mefali System",
        account_id=None,
        role="ADMIN",
    )
    db.add(verifier)
    await db.flush()
    return captured_by.id, verifier.id


async def seed_sources_045(
    db: AsyncSession,
    *,
    captured_by_id: uuid.UUID | None = None,
    verified_by_id: uuid.UUID | None = None,
) -> int:
    """Insere les 4 sources F045 si absentes. Retourne le nb insere.

    Args:
        db: Session async.
        captured_by_id: UUID admin createur. Si None, auto-resolu via
            ``_ensure_two_admins``.
        verified_by_id: UUID admin verifier (different de captured_by_id pour
            respecter le CHECK F01 four-eyes).

    Returns:
        Nombre de sources effectivement inserees (0..4).
    """
    if captured_by_id is None or verified_by_id is None:
        captured_by_id, verified_by_id = await _ensure_two_admins(db)

    if captured_by_id == verified_by_id:
        raise ValueError(
            "seed_sources_045 : captured_by_id et verified_by_id doivent etre "
            "differents (CHECK F01 four-eyes)."
        )

    existing = await _get_existing_urls(db)
    now = datetime.now(timezone.utc)

    inserted = 0
    for seed in SEED_SOURCES_045:
        if seed["url"] in existing:
            logger.info("[seed_sources_045] %s deja present, skip", seed["url"])
            continue
        source = Source(
            url=seed["url"],
            title=seed["title"],
            publisher=seed["publisher"],
            version=seed["version"],
            date_publi=seed["date_publi"],
            section=seed.get("section"),
            captured_by=captured_by_id,
            created_by_user_id=captured_by_id,
            verified_by=verified_by_id,
            verified_at=now,
            verification_status=VerificationStatus.VERIFIED.value,
        )
        db.add(source)
        inserted += 1
        logger.info("[seed_sources_045] %s inseree", seed["title"])

    await db.flush()
    return inserted


async def _main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    async with async_session_factory() as session:
        inserted = await seed_sources_045(session)
        await session.commit()
        if inserted == 0:
            logger.info("Seed sources_045 : 4 sources deja toutes presentes.")
        else:
            logger.info("Seed sources_045 : %d sources F01 inserees.", inserted)
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
