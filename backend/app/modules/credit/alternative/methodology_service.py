"""F18 — Service méthodologie scoring crédit (lecture publique)."""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit_alternative import CreditMethodologyFactor

logger = logging.getLogger(__name__)

DEFAULT_VERSION = "1.2"


async def list_published_factors(
    db: AsyncSession, version: str | None = None
) -> list[CreditMethodologyFactor]:
    """Liste les facteurs publiés (publication_status='published').

    SC-010 : tout chiffre exposé est rattaché à une source vérifiée F01
    (FK ``source_id`` NOT NULL).
    """
    stmt = select(CreditMethodologyFactor).where(
        CreditMethodologyFactor.publication_status == "published"
    )
    if version is not None:
        stmt = stmt.where(CreditMethodologyFactor.version == version)
    stmt = stmt.order_by(CreditMethodologyFactor.category, CreditMethodologyFactor.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


def total_weight(factors: list[CreditMethodologyFactor]) -> Decimal:
    """Somme des poids (info indicative, pas de contrainte stricte)."""
    return sum((f.weight for f in factors), Decimal("0"))


__all__ = ["list_published_factors", "total_weight", "DEFAULT_VERSION"]
