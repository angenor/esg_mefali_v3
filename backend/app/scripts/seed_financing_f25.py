"""Seed wrapper F25 : alimente la BDD financing avec les 12 fonds + 14
intermédiaires + liaisons du module `app.modules.financing.seed`, en y
ajoutant les champs requis post-fondations F01 (`source_id` NOT NULL) et
F07 (`publication_status='published'` pour visibilité côté `/financing`).

Permet d'avoir une base de démonstration réelle pour tester le parcours
PME + admin sans modifier la logique du seed monolithique existant.

Usage :
    source backend/venv/bin/activate
    python -m app.scripts.seed_financing_f25
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date

from sqlalchemy import select

from app.core.constants import UserRole
from app.core.database import async_session_factory
from app.models.financing import (
    FinancingChunk,
    FinancingSourceType,
    Fund,
    FundIntermediary,
    Intermediary,
)
from app.models.source import Source, VerificationStatus
from app.models.user import User
from app.modules.financing.seed import (
    FUND_INTERMEDIARY_LINKS,
    FUNDS_DATA,
    INTERMEDIARIES_DATA,
    _build_chunk_text,
    _build_intermediary_chunk_text,
)

logger = logging.getLogger(__name__)


SEED_SOURCE_TITLE = "Catalogue financement vert UEMOA — Seed Mefali F25"
SEED_SOURCE_URL = "https://mefali.local/seeds/financing/2026-05"


async def _get_or_create_admin_source(db) -> Source:
    """Renvoie une Source vérifiée (la première dispo, ou en crée une).

    Pour le seed F25 on veut une seule source umbrella utilisée par les
    12 fonds + 14 intermédiaires + liaisons. Choisit la première Source
    `verified` trouvée, ou en crée une (avec captured_by/verified_by =
    premier admin disponible).
    """
    src = (
        await db.execute(
            select(Source).where(Source.title == SEED_SOURCE_TITLE).limit(1)
        )
    ).scalars().first()
    if src is not None:
        return src

    src = (
        await db.execute(
            select(Source)
            .where(Source.verification_status == VerificationStatus.VERIFIED.value)
            .limit(1)
        )
    ).scalars().first()
    if src is not None:
        return src

    admin = (
        await db.execute(
            select(User).where(User.role == UserRole.ADMIN.value).limit(1)
        )
    ).scalars().first()
    if admin is None:
        raise RuntimeError(
            "Aucun ADMIN seedé en BDD ; lance `python -m app.scripts.seed_admin` d'abord."
        )

    src = Source(
        url=SEED_SOURCE_URL,
        title=SEED_SOURCE_TITLE,
        publisher="Mefali (seed compilation BOAD / GCF / FEM / AFD / SUNREF)",
        version="2026.05",
        date_publi=date(2026, 5, 1),
        captured_by=admin.id,
        verification_status=VerificationStatus.VERIFIED.value,
        verified_by=admin.id,
    )
    db.add(src)
    await db.flush()
    logger.info("Source umbrella F25 créée (id=%s).", src.id)
    return src


async def seed_financing_f25() -> dict:
    """Seed enrichi F25 : injecte source_id + publication_status published.

    Returns:
        Dict avec compteurs ``funds`` / ``intermediaries`` / ``links``
        et statut ``inserted`` (True si nouveaux objets) / ``existing``.
    """
    async with async_session_factory() as db:
        existing_fund = (await db.execute(select(Fund).limit(1))).scalar_one_or_none()
        if existing_fund is not None:
            existing_count = (
                await db.execute(select(Fund))
            ).scalars().all()
            logger.info(
                "Catalogue déjà présent (%d fonds). Seed F25 idempotent : "
                "rien à faire.",
                len(existing_count),
            )
            inter_count = len(
                (await db.execute(select(Intermediary))).scalars().all()
            )
            link_count = len(
                (await db.execute(select(FundIntermediary))).scalars().all()
            )
            return {
                "inserted": False,
                "funds": len(existing_count),
                "intermediaries": inter_count,
                "links": link_count,
            }

        source = await _get_or_create_admin_source(db)
        source_id = source.id

        # 1. Fonds — patch source_id + publication_status='published'.
        for data in FUNDS_DATA:
            payload = {
                **data,
                "source_id": source_id,
                "publication_status": "published",
            }
            db.add(Fund(**payload))
        await db.flush()

        # 2. Intermédiaires — idem.
        for data in INTERMEDIARIES_DATA:
            payload = {
                **data,
                "source_id": source_id,
                "publication_status": "published",
            }
            db.add(Intermediary(**payload))
        await db.flush()

        # 3. Liaisons — ajout accredited_from + accreditation_source_id.
        today_minus_1y = date(2024, 1, 1)
        for link_data in FUND_INTERMEDIARY_LINKS:
            db.add(
                FundIntermediary(
                    fund_id=link_data["fund_id"],
                    intermediary_id=link_data["intermediary_id"],
                    role=link_data.get("role"),
                    is_primary=link_data.get("is_primary", False),
                    geographic_coverage=link_data.get("geographic_coverage", []),
                    accredited_from=today_minus_1y,
                    accredited_to=None,
                    accreditation_source_id=source_id,
                )
            )
        await db.flush()

        # 4. Chunks RAG (best-effort, embeddings vides — pas bloquant).
        for data in FUNDS_DATA:
            db.add(
                FinancingChunk(
                    source_type=FinancingSourceType.fund,
                    source_id=data["id"],
                    content=_build_chunk_text(data),
                )
            )
        for data in INTERMEDIARIES_DATA:
            db.add(
                FinancingChunk(
                    source_type=FinancingSourceType.intermediary,
                    source_id=data["id"],
                    content=_build_intermediary_chunk_text(data),
                )
            )
        await db.flush()
        await db.commit()

        return {
            "inserted": True,
            "funds": len(FUNDS_DATA),
            "intermediaries": len(INTERMEDIARIES_DATA),
            "links": len(FUND_INTERMEDIARY_LINKS),
        }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = asyncio.run(seed_financing_f25())
    print(f"Seed F25 résultat : {result}")


if __name__ == "__main__":
    main()
