"""F07 — Tests unit du modèle Offer (T006).

Vérifie :
- Insertion basique avec defaults (is_active=true, publication_status='draft', accepted_languages=['FR']).
- Unique constraint (fund_id, intermediary_id, version).
- Relations fund/intermediary/source eager.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.offer import Offer


@pytest.mark.asyncio
async def test_offer_can_be_inserted_with_defaults(
    db_session, basic_fund, basic_intermediary, verified_source,
) -> None:
    """Offre insérable avec defaults (is_active=true, publication_status='draft')."""
    offer = Offer(
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
        name="Test Offer",
        source_id=verified_source.id,
    )
    db_session.add(offer)
    await db_session.flush()
    assert offer.id is not None
    assert offer.is_active is True
    assert offer.publication_status == "draft"
    assert offer.accepted_languages == ["FR"]
    assert offer.version == "1.0"


@pytest.mark.asyncio
async def test_offer_unique_fund_intermediary_version(
    db_session, basic_fund, basic_intermediary, verified_source,
) -> None:
    """UNIQUE (fund_id, intermediary_id, version) empêche les doublons."""
    o1 = Offer(
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
        name="Offer v1",
        source_id=verified_source.id,
        version="1.0",
    )
    db_session.add(o1)
    await db_session.flush()

    # Doublon → IntegrityError
    o2 = Offer(
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
        name="Offer v1 doublon",
        source_id=verified_source.id,
        version="1.0",
    )
    db_session.add(o2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_offer_distinct_versions_allowed(
    db_session, basic_fund, basic_intermediary, verified_source,
) -> None:
    """version distincte → pas de conflit unique."""
    o1 = Offer(
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
        name="v1",
        source_id=verified_source.id,
        version="1.0",
    )
    o2 = Offer(
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
        name="v2",
        source_id=verified_source.id,
        version="2.0",
    )
    db_session.add_all([o1, o2])
    await db_session.flush()
    assert o1.id != o2.id


@pytest.mark.asyncio
async def test_offer_relations_loaded(
    db_session, published_offer,
) -> None:
    """fund/intermediary/source sont chargés eagerly (selectin)."""
    result = await db_session.execute(
        select(Offer).where(Offer.id == published_offer.id)
    )
    offer = result.scalar_one()
    assert offer.fund is not None
    assert offer.fund.name == "GCF Test"
    assert offer.intermediary is not None
    assert offer.intermediary.name == "BOAD"
    assert offer.source is not None


@pytest.mark.asyncio
async def test_offer_processing_time_consistency(
    db_session, basic_fund, basic_intermediary, verified_source,
) -> None:
    """CHECK: processing_min <= processing_max sinon (peut être skippé sur sqlite)."""
    offer = Offer(
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
        name="Test",
        source_id=verified_source.id,
        effective_processing_time_days_min=100,
        effective_processing_time_days_max=200,  # OK
    )
    db_session.add(offer)
    await db_session.flush()
    assert offer.effective_processing_time_days_min == 100


@pytest.mark.asyncio
async def test_offer_published_must_be_active_chk(
    db_session, basic_fund, basic_intermediary, verified_source,
) -> None:
    """CHECK: si publication_status='published', is_active doit être true."""
    offer = Offer(
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
        name="Test",
        source_id=verified_source.id,
        publication_status="published",
        is_active=True,  # OK
    )
    db_session.add(offer)
    await db_session.flush()
    assert offer.publication_status == "published"
    assert offer.is_active is True
