"""F09 PRIO 3 — Script idempotent de publication des entités catalogue.

Contexte. La migration Alembic 035 ajoute ``publication_status='draft'``
par défaut. Les fonds/intermédiaires/etc. déjà en BDD avant la migration
sont donc en draft, même s'ils sont effectivement utilisés en prod.

Ce script passe en ``published`` toutes les entités catalogue dont **toutes
les sources liées sont verified**. Il est idempotent : les entités déjà
``published`` sont ignorées.

Usage::

    cd backend
    source venv/bin/activate
    python -m scripts.seed_publish_existing_catalog --dry-run   # preview
    python -m scripts.seed_publish_existing_catalog              # apply

Tables concernées (cf. PUBLICATION_TABLES_WITH_STATUS) :
- funds, intermediaries, offers
- referentials, indicators, criteria
- emission_factors, simulation_factors, required_documents
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)


# Tables catalogue + nom singulier pour le préfixe audit_log.
TABLES = (
    ("funds", "fund"),
    ("intermediaries", "intermediary"),
    ("offers", "offer"),
    ("referentials", "referential"),
    ("indicators", "indicator"),
    ("criteria", "criterion"),
    ("emission_factors", "emission_factor"),
    ("simulation_factors", "simulation_factor"),
    ("required_documents", "required_document"),
)


async def _list_drafts(db, table: str) -> list[dict[str, Any]]:
    """Liste les entités draft de la table donnée."""
    query = text(f"SELECT id, source_id FROM {table} WHERE publication_status = 'draft'")
    res = await db.execute(query)
    return [{"id": row[0], "source_id": row[1]} for row in res.all()]


async def _source_is_verified(db, source_id: uuid.UUID | str | None) -> bool:
    if source_id is None:
        return False
    res = await db.execute(
        text("SELECT verification_status FROM sources WHERE id = :id"),
        {"id": str(source_id)},
    )
    row = res.first()
    return bool(row and str(row[0]) == "verified")


async def _try_publish(
    db,
    table: str,
    entity_id: uuid.UUID,
    dry_run: bool,
) -> tuple[bool, str | None]:
    """Tente d'UPDATE l'entité en published. Retourne (ok, error_message)."""
    if dry_run:
        return True, "dry-run"
    try:
        await db.execute(
            text(
                f"UPDATE {table} SET publication_status = 'published' "
                "WHERE id = :id AND publication_status = 'draft'"
            ),
            {"id": str(entity_id)},
        )
        await db.commit()
        return True, None
    except (IntegrityError, DBAPIError) as exc:
        await db.rollback()
        return False, str(exc)


async def run(dry_run: bool = False) -> dict[str, dict[str, int]]:
    """Run le batch publish. Retourne stats par table."""
    from app.core.database import settings  # type: ignore

    engine = create_async_engine(settings.async_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    stats: dict[str, dict[str, int]] = {}

    async with factory() as db:
        for table, _ in TABLES:
            stat = {"checked": 0, "published": 0, "skipped_no_source": 0, "skipped_unverified": 0, "errors": 0}
            try:
                drafts = await _list_drafts(db, table)
            except DBAPIError as exc:
                logger.warning("table %s introuvable ou requête échouée: %s", table, exc)
                stats[table] = {"errors": 1, "checked": 0, "published": 0, "skipped_no_source": 0, "skipped_unverified": 0}
                continue

            for entity in drafts:
                stat["checked"] += 1
                source_id = entity.get("source_id")
                if source_id is None:
                    stat["skipped_no_source"] += 1
                    continue
                ok = await _source_is_verified(db, source_id)
                if not ok:
                    stat["skipped_unverified"] += 1
                    continue
                published, err = await _try_publish(db, table, entity["id"], dry_run)
                if published:
                    stat["published"] += 1
                else:
                    stat["errors"] += 1
                    logger.warning("publish %s.%s failed: %s", table, entity["id"], err)
            stats[table] = stat

    await engine.dispose()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Publie en cascade les entités catalogue dont toutes les sources "
            "liées sont verified. Idempotent."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Liste seulement les entités candidates sans appliquer.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    stats = asyncio.run(run(dry_run=args.dry_run))

    print("\n=== Récapitulatif F09 seed_publish ===")
    total_published = 0
    total_skipped = 0
    for table, s in stats.items():
        print(
            f"  {table:24s} checked={s['checked']:4d} "
            f"published={s['published']:4d} "
            f"skip_no_src={s['skipped_no_source']:4d} "
            f"skip_unverif={s['skipped_unverified']:4d} "
            f"errors={s['errors']:4d}"
        )
        total_published += s["published"]
        total_skipped += s["skipped_no_source"] + s["skipped_unverified"]
    print(f"\nTotal published: {total_published}")
    print(f"Total skipped : {total_skipped}")
    if args.dry_run:
        print("\n(dry-run — aucune mutation appliquée)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
