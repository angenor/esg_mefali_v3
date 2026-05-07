"""Service Offers (F07) — CRUD + transitions publication_status.

Note : aucun mixin Auditable (catalogue exempt, cohérent F03 policy).
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import Money
from app.models.financing import Fund, Intermediary
from app.models.offer import Offer
from app.models.source import Source
from app.modules.offers.calculator import compute_effective_offer
from app.modules.offers.schemas import (
    OfferComparison,
    OfferCreate,
    OfferDraft,
    OfferUpdate,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


async def list_offers(
    session: AsyncSession,
    *,
    fund_id: UUID | None = None,
    intermediary_id: UUID | None = None,
    theme: str | None = None,
    instrument: str | None = None,
    country: str | None = None,
    language: str | None = None,
    include_drafts: bool = False,
    sort: str = "name",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Offer], int]:
    """Liste paginée des offres.

    Par défaut filtre strict ``publication_status='published' AND is_active=true``.
    Si ``include_drafts=True`` (admin only), retourne aussi les drafts.
    """
    query = select(Offer)

    # Filtre publication
    if not include_drafts:
        query = query.where(
            and_(
                Offer.publication_status == "published",
                Offer.is_active.is_(True),
            )
        )

    # Filtres optionnels
    if fund_id is not None:
        query = query.where(Offer.fund_id == fund_id)
    if intermediary_id is not None:
        query = query.where(Offer.intermediary_id == intermediary_id)

    # Filtre country : via intermediary
    if country is not None:
        query = query.join(Intermediary, Offer.intermediary_id == Intermediary.id)
        query = query.where(Intermediary.country == country)

    # Tri
    if sort == "processing_time":
        query = query.order_by(Offer.effective_processing_time_days_min.asc())
    else:
        query = query.order_by(Offer.name.asc())

    # Total avant pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Pagination
    query = query.limit(min(limit, 100)).offset(offset)
    result = await session.execute(query)
    items = list(result.scalars().all())

    return items, total


async def get_offer(
    session: AsyncSession,
    offer_id: UUID,
    *,
    include_drafts: bool = False,
) -> Offer | None:
    """Récupère une offre par ID.

    Par défaut retourne None si l'offre est en draft (anti-fuite côté API
    publique). Si ``include_drafts=True`` (admin only), retourne aussi les drafts.
    """
    offer = await session.get(Offer, offer_id)
    if offer is None:
        return None
    if not include_drafts:
        if offer.publication_status != "published" or not offer.is_active:
            return None
    return offer


async def compare_offers_for_fund(
    session: AsyncSession,
    fund_id: UUID,
) -> list[OfferComparison]:
    """Retourne toutes les offres publiées+actives pour un fonds.

    Format optimisé pour l'affichage côte-à-côte d'un comparateur.
    """
    query = (
        select(Offer)
        .where(
            and_(
                Offer.fund_id == fund_id,
                Offer.publication_status == "published",
                Offer.is_active.is_(True),
            )
        )
        .order_by(Offer.name.asc())
    )
    result = await session.execute(query)
    offers = list(result.scalars().all())

    comparisons: list[OfferComparison] = []
    for offer in offers:
        intermediary = offer.intermediary
        # Money typed depuis effective_fees JSONB
        total_min_money = _money_from_dict(
            (offer.effective_fees or {}).get("total_min")
        )
        total_max_money = _money_from_dict(
            (offer.effective_fees or {}).get("total_max")
        )

        comparisons.append(OfferComparison(
            offer_id=offer.id,
            name=offer.name,
            intermediary_id=intermediary.id,
            intermediary_name=intermediary.name,
            intermediary_country=intermediary.country,
            intermediary_code=intermediary.code,
            accepted_languages=offer.accepted_languages or ["FR"],
            effective_fees_total_min=total_min_money,
            effective_fees_total_max=total_max_money,
            effective_processing_time_days_min=offer.effective_processing_time_days_min,
            effective_processing_time_days_max=offer.effective_processing_time_days_max,
            effective_disbursement_time_days_min=offer.effective_disbursement_time_days_min,
            effective_disbursement_time_days_max=offer.effective_disbursement_time_days_max,
            success_rate=float(intermediary.success_rate) if intermediary.success_rate else None,
            documents_count=len(offer.effective_required_documents or []),
            publication_status=offer.publication_status,
            is_active=offer.is_active,
        ))
    return comparisons


def _money_from_dict(d: Any) -> Money | None:
    """Reconstruit un Money depuis un dict {amount, currency}. None si invalide."""
    if not isinstance(d, dict):
        return None
    try:
        return Money(
            amount=Decimal(str(d.get("amount", 0))),
            currency=d.get("currency", "XOF"),
        )
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Write (admin)
# ---------------------------------------------------------------------------


async def create_offer(
    session: AsyncSession,
    payload: OfferCreate,
) -> Offer:
    """Crée une offre depuis un draft édité.

    Lève ``ValueError`` si le couple ``(fund_id, intermediary_id, version)``
    existe déjà.
    """
    # Vérifier unicité
    existing_query = select(Offer).where(
        Offer.fund_id == payload.fund_id,
        Offer.intermediary_id == payload.intermediary_id,
        Offer.version == payload.version,
    )
    existing_result = await session.execute(existing_query)
    if existing_result.scalar_one_or_none() is not None:
        raise ValueError(
            f"Une offre existe déjà pour le couple "
            f"(fund_id={payload.fund_id}, intermediary_id={payload.intermediary_id}, "
            f"version={payload.version})"
        )

    offer = Offer(
        fund_id=payload.fund_id,
        intermediary_id=payload.intermediary_id,
        name=payload.name,
        accepted_languages=payload.accepted_languages,
        target_sector=payload.target_sector,
        effective_criteria=payload.effective_criteria,
        effective_required_documents=payload.effective_required_documents,
        effective_fees=payload.effective_fees,
        effective_processing_time_days_min=payload.effective_processing_time_days_min,
        effective_processing_time_days_max=payload.effective_processing_time_days_max,
        effective_disbursement_time_days_min=payload.effective_disbursement_time_days_min,
        effective_disbursement_time_days_max=payload.effective_disbursement_time_days_max,
        notes=payload.notes,
        is_active=False,  # Default draft → inactif
        publication_status=payload.publication_status,
        source_id=payload.source_id,
        version=payload.version,
        valid_from=date.today(),
    )
    session.add(offer)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError(f"Erreur d'intégrité : {exc.orig}") from exc

    await session.refresh(offer, ["fund", "intermediary", "source"])
    return offer


async def update_offer(
    session: AsyncSession,
    offer_id: UUID,
    payload: OfferUpdate,
) -> tuple[Offer | None, list[str]]:
    """Met à jour une offre. Retourne ``(offer, missing_prerequisites)``.

    Si transition ``draft → published`` détectée, vérifie les prérequis :
    - ``fund.publication_status='published'``
    - ``intermediary.publication_status='published'``
    - ``fund_intermediary.accredited_to IS NULL OR > today`` (sauf cas DIRECT)
    - ``source.verification_status='verified'``

    Si un prérequis manque → retourne ``(None, [missing_prereqs])`` sans persister.
    """
    offer = await session.get(Offer, offer_id)
    if offer is None:
        return None, []

    # Mises à jour partielles
    update_data = payload.model_dump(exclude_unset=True)

    # Vérifier transition draft → published
    if (
        update_data.get("publication_status") == "published"
        and offer.publication_status == "draft"
    ):
        missing = await _check_publication_prerequisites(session, offer, payload)
        if missing:
            return None, missing
        # Si bascule en published, is_active doit aussi être true (cohérence CHECK)
        if "is_active" not in update_data:
            update_data["is_active"] = True

    for key, value in update_data.items():
        setattr(offer, key, value)

    await session.flush()
    await session.refresh(offer, ["fund", "intermediary", "source"])
    return offer, []


async def _check_publication_prerequisites(
    session: AsyncSession,
    offer: Offer,
    payload: OfferUpdate,
) -> list[str]:
    """Vérifie les prérequis de publication. Retourne la liste des manques."""
    missing: list[str] = []

    # Refresh fund/intermediary pour avoir leurs publication_status à jour
    fund = await session.get(Fund, offer.fund_id)
    intermediary = await session.get(Intermediary, offer.intermediary_id)
    source_id = payload.source_id or offer.source_id
    source = await session.get(Source, source_id) if source_id else None

    if fund is None or fund.publication_status != "published":
        missing.append("fund_not_published")
    if intermediary is None or intermediary.publication_status != "published":
        missing.append("intermediary_not_published")

    # Vérifier accreditation_to (sauf cas DIRECT)
    if intermediary is not None and intermediary.code != "DIRECT":
        from app.models.financing import FundIntermediary
        fi_result = await session.execute(
            select(FundIntermediary).where(
                FundIntermediary.fund_id == offer.fund_id,
                FundIntermediary.intermediary_id == offer.intermediary_id,
            )
        )
        fi = fi_result.scalar_one_or_none()
        if fi is not None:
            if fi.accredited_to is not None and fi.accredited_to <= date.today():
                missing.append("accreditation_expired")

    if source is None or source.verification_status != "verified":
        missing.append("source_not_verified")

    return missing


async def compute_offer_preview(
    session: AsyncSession,
    fund_id: UUID,
    intermediary_id: UUID,
) -> OfferDraft:
    """Wrapper pour l'endpoint admin POST /api/admin/offers/compute.

    Délègue au calculator (pas de persistance).
    """
    return await compute_effective_offer(session, fund_id, intermediary_id)
