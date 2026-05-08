"""F16 — Service de chargement d'un snapshot cohérent de facteurs.

Charge en un seul SELECT (avec JOIN ``sources``) la totalité des facteurs
nécessaires à une simulation et expose un :class:`FactorSnapshot` immuable
(``frozen=True``) qui sert toutes les offres comparées dans un même appel
(invariant FR-017 — snapshot logique unique).

Convention :
- Les facteurs ``status='outdated'`` sont **exclus** par défaut (catalogue
  ne les expose plus comme actifs).
- Les facteurs ``status='draft'`` sont **exclus** (jamais publiés).
- Les facteurs ``status='verified'`` et ``status='pending'`` sont **inclus**.
  Le statut est propagé dans :class:`FactorEntry` pour permettre au
  consommateur d'afficher un avertissement (FR-003 + SC-007).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.simulation_factor import SimulationFactor
from app.models.source import Source


@dataclass(frozen=True)
class SourceRef:
    """Projection légère d'une Source (lecture seule, sérialisable)."""

    id: uuid.UUID
    title: str
    publisher: str | None
    url: str | None
    published_at: date | None
    verification_status: str


@dataclass(frozen=True)
class FactorEntry:
    """Entrée immuable du snapshot."""

    name: str
    value: Decimal
    unit: str
    status: str  # 'verified' | 'pending'
    source_id: uuid.UUID | None
    applies_to: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class FactorSnapshot:
    """Instantané immuable des facteurs de simulation pour un appel donné.

    L'invariant FR-017 garantit que toutes les offres comparées dans un
    même appel partagent ce snapshot.
    """

    factors: Mapping[str, FactorEntry]
    sources: Mapping[uuid.UUID, SourceRef]
    loaded_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def get(self, name: str) -> FactorEntry | None:
        """Lookup par nom logique (None si absent)."""
        return self.factors.get(name)

    def has(self, name: str) -> bool:
        return name in self.factors


# Valeurs par défaut MVP : si un facteur n'est pas seedé en BDD, le service
# tolère son absence et propage un MonetaryFigure dégradé. Ces noms logiques
# sont les **conventions** F16 utilisées par le simulateur.
F16_FACTOR_NAMES: tuple[str, ...] = (
    "default_loan_rate",
    "default_doc_fee_rate",
    "default_guarantee_rate",
    "default_fx_margin_rate",
    "default_payback_months",
    "gain_rate_default",
    # Aliases legacy (déjà seedés via F01) :
    "savings_rate",
    "carbon_impact_per_mxof",
)


async def load_factors_snapshot(
    db: AsyncSession,
    *,
    factor_names: tuple[str, ...] = F16_FACTOR_NAMES,
) -> FactorSnapshot:
    """Charge en un seul SELECT les facteurs et leurs sources.

    Exclut ``draft`` et ``outdated`` ; inclut ``verified`` et ``pending``.
    """
    # SimulationFactor n'a pas de relationship 'source' déclarée — on
    # effectue 2 SELECT (1 sur factors filtré par status/code, 1 sur sources
    # par UUIDs dédupliqués). La cohérence est garantie par la même
    # transaction (snapshot logique unique, FR-017).
    result = await db.execute(
        select(SimulationFactor)
        .where(SimulationFactor.status.in_(("verified", "pending")))
        .where(SimulationFactor.code.in_(list(factor_names)))
    )
    rows = list(result.scalars().all())

    factors: dict[str, FactorEntry] = {}
    source_ids: set[uuid.UUID] = set()
    for sf in rows:
        factors[sf.code] = FactorEntry(
            name=sf.code,
            value=Decimal(str(sf.value)),
            unit=sf.unit,
            status=sf.status,
            source_id=sf.source_id,
        )
        if sf.source_id is not None:
            source_ids.add(sf.source_id)

    # Charger les SourceRef en un SELECT supplémentaire (réservé à
    # ces source_ids dédupliqués).
    sources: dict[uuid.UUID, SourceRef] = {}
    if source_ids:
        src_result = await db.execute(
            select(Source).where(Source.id.in_(list(source_ids)))
        )
        for s in src_result.scalars().all():
            sources[s.id] = SourceRef(
                id=s.id,
                title=s.title,
                publisher=s.publisher,
                url=s.url,
                published_at=s.published_at,
                verification_status=(
                    s.verification_status.value
                    if hasattr(s.verification_status, "value")
                    else str(s.verification_status)
                ),
            )

    return FactorSnapshot(
        factors=MappingProxyType(factors),
        sources=MappingProxyType(sources),
        loaded_at=datetime.now(timezone.utc),
    )
