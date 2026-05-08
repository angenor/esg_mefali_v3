"""Tests F18 — Méthodologie service + endpoint public."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models.credit_alternative import CreditMethodologyFactor
from app.models.source import Source
from app.modules.credit.alternative.methodology_service import (
    list_published_factors,
    total_weight,
)


async def _make_source(db_session, title: str, url: str) -> Source:
    """Crée une Source verified minimaliste pour les tests."""
    captured_by = uuid.uuid4()
    verified_by = uuid.uuid4()
    src = Source(
        url=url,
        title=title,
        publisher="Test",
        version="1.0",
        date_publi=date(2025, 1, 1),
        captured_at=datetime.now(timezone.utc),
        captured_by=captured_by,
        verified_by=verified_by,
        verification_status="verified",
        verified_at=datetime.now(timezone.utc),
        created_by_user_id=captured_by,
    )
    db_session.add(src)
    await db_session.flush()
    return src


@pytest.mark.asyncio
async def test_list_published_filters_drafts(db_session):
    """Seuls les factors publication_status='published' sont retournés (SC-010)."""
    src = await _make_source(db_session, "Test source", "https://example.com/methodo")
    db_session.add(src)
    await db_session.flush()

    f_published = CreditMethodologyFactor(
        version="1.2",
        name="MM Régularité",
        category="mobile_money_flux",
        weight=Decimal("0.150"),
        description="Régularité Mobile Money",
        source_id=src.id,
        publication_status="published",
    )
    f_draft = CreditMethodologyFactor(
        version="1.2",
        name="MM Volume (draft)",
        category="mobile_money_flux",
        weight=Decimal("0.100"),
        description="Volume Mobile Money — draft",
        source_id=src.id,
        publication_status="draft",
    )
    db_session.add_all([f_published, f_draft])
    await db_session.commit()

    factors = await list_published_factors(db_session)
    names = [f.name for f in factors]
    assert "MM Régularité" in names
    assert "MM Volume (draft)" not in names


@pytest.mark.asyncio
async def test_total_weight_computes_sum(db_session):
    src = await _make_source(db_session, "Test source 2", "https://example.com/methodo2")
    db_session.add(src)
    await db_session.flush()

    factors = [
        CreditMethodologyFactor(
            version="1.2",
            name=f"Factor {i}",
            category="mobile_money_flux",
            weight=Decimal("0.100"),
            description="x",
            source_id=src.id,
            publication_status="published",
        )
        for i in range(3)
    ]
    db_session.add_all(factors)
    await db_session.commit()

    published = await list_published_factors(db_session)
    tw = total_weight(published)
    assert tw == Decimal("0.300")


@pytest.mark.asyncio
async def test_methodology_endpoint_public_no_auth(client, db_session):
    """SC-007 — endpoint public accessible sans Bearer."""
    src = await _make_source(db_session, "Méthodologie scoring crédit Mefali", "https://example.com/methodo3")
    db_session.add(src)
    await db_session.flush()

    f = CreditMethodologyFactor(
        version="1.2",
        name="MM Régularité",
        category="mobile_money_flux",
        weight=Decimal("0.150"),
        description="Régularité Mobile Money 30j",
        source_id=src.id,
        publication_status="published",
    )
    db_session.add(f)
    await db_session.commit()

    # Pas de header Authorization
    resp = await client.get("/api/credit/methodology")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == "1.2"
    assert len(body["factors"]) >= 1
    assert all("source_id" in f for f in body["factors"])
