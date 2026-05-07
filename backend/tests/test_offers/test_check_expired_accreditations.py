"""F07 — Tests integration pour le cron check_expired_accreditations (US5).

Vérifie :
- Désactive offre publiée si fund_intermediary.accredited_to passé.
- Idempotence (2 exécutions).
- Préserve offres avec accréditation valide.
- Préserve offres avec accredited_to=NULL.
- audit_log enrichi avec metadata complète.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.models.audit_log import AuditLog
from app.models.financing import FundIntermediary
from app.models.offer import Offer

from scripts import check_expired_accreditations


@pytest.fixture
async def expired_pair(
    db_session, basic_fund, basic_intermediary, verified_source,
):
    """Crée un FundIntermediary avec accredited_to dans le passé."""
    # Supprimer le fixture basic_fund_intermediary s'il existe
    fi = FundIntermediary(
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
        accredited_from=date.today() - timedelta(days=400),
        accredited_to=date.today() - timedelta(days=30),  # expiré il y a 30j
        accreditation_source_id=verified_source.id,
        version="1.0",
        valid_from=date.today(),
    )
    db_session.add(fi)
    await db_session.commit()
    return fi


@pytest.fixture
async def expired_offer(
    db_session, basic_fund, basic_intermediary, expired_pair,
    verified_source,
):
    """Crée une offre published+active liée au expired_pair."""
    offer = Offer(
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
        name="Expired Offer",
        is_active=True,
        publication_status="published",
        source_id=verified_source.id,
        version="6.0",
        valid_from=date.today(),
    )
    db_session.add(offer)
    await db_session.commit()
    return offer


@pytest.mark.asyncio
async def test_deactivates_expired_offer(
    db_session, expired_offer, monkeypatch,
) -> None:
    """Le cron désactive l'offre liée à une accréditation expirée."""
    # Monkey-patch async_session_factory pour réutiliser la session de test
    from tests.conftest import test_session_factory
    monkeypatch.setattr(
        "scripts.check_expired_accreditations.async_session_factory",
        test_session_factory,
    )

    summary = await check_expired_accreditations.run()
    assert summary["deactivated"] == 1

    # Re-fetch offer (refresh pour forcer reload depuis la base)
    await db_session.refresh(expired_offer)
    assert expired_offer.is_active is False
    assert expired_offer.publication_status == "draft"


@pytest.mark.asyncio
async def test_cron_idempotent(
    db_session, expired_offer, monkeypatch,
) -> None:
    """2 exécutions consécutives → seul 1 audit_log créé."""
    from tests.conftest import test_session_factory
    monkeypatch.setattr(
        "scripts.check_expired_accreditations.async_session_factory",
        test_session_factory,
    )

    s1 = await check_expired_accreditations.run()
    s2 = await check_expired_accreditations.run()

    assert s1["deactivated"] == 1
    assert s2["deactivated"] == 0  # idempotent


@pytest.mark.asyncio
async def test_keeps_valid_offers_unchanged(
    db_session, basic_fund, basic_intermediary, verified_source, monkeypatch,
) -> None:
    """Accréditation future → offre reste published+active."""
    from app.models.financing import FundIntermediary

    fi = FundIntermediary(
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
        accredited_from=date.today() - timedelta(days=10),
        accredited_to=date.today() + timedelta(days=365),  # futur
        accreditation_source_id=verified_source.id,
        version="1.0",
        valid_from=date.today(),
    )
    db_session.add(fi)

    offer = Offer(
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
        name="Valid Offer",
        is_active=True,
        publication_status="published",
        source_id=verified_source.id,
        version="7.0",
        valid_from=date.today(),
    )
    db_session.add(offer)
    await db_session.commit()

    from tests.conftest import test_session_factory
    monkeypatch.setattr(
        "scripts.check_expired_accreditations.async_session_factory",
        test_session_factory,
    )

    summary = await check_expired_accreditations.run()
    assert summary["deactivated"] == 0

    await db_session.refresh(offer)
    assert offer.is_active is True
    assert offer.publication_status == "published"


@pytest.mark.asyncio
async def test_keeps_null_accredited_to_unchanged(
    db_session, basic_fund, basic_intermediary, verified_source, monkeypatch,
) -> None:
    """Accréditation accredited_to=NULL → offre reste publiée."""
    from app.models.financing import FundIntermediary

    fi = FundIntermediary(
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
        accredited_from=date.today() - timedelta(days=10),
        accredited_to=None,
        accreditation_source_id=verified_source.id,
        version="1.0",
        valid_from=date.today(),
    )
    db_session.add(fi)

    offer = Offer(
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
        name="Null Offer",
        is_active=True,
        publication_status="published",
        source_id=verified_source.id,
        version="8.0",
        valid_from=date.today(),
    )
    db_session.add(offer)
    await db_session.commit()

    from tests.conftest import test_session_factory
    monkeypatch.setattr(
        "scripts.check_expired_accreditations.async_session_factory",
        test_session_factory,
    )

    summary = await check_expired_accreditations.run()
    assert summary["deactivated"] == 0


@pytest.mark.asyncio
async def test_audit_log_metadata_complete(
    db_session, expired_offer, monkeypatch,
) -> None:
    """Audit log contient metadata fund_id, intermediary_id, accredited_to."""
    from tests.conftest import test_session_factory
    monkeypatch.setattr(
        "scripts.check_expired_accreditations.async_session_factory",
        test_session_factory,
    )

    await check_expired_accreditations.run()
    await db_session.commit()

    # Vérifier qu'au moins une entrée audit_log a été créée
    result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.entity_type == "offer")
        .where(AuditLog.entity_id == expired_offer.id)
    )
    logs = list(result.scalars().all())
    assert len(logs) >= 1
    log = logs[0]
    assert log.actor_metadata is not None
    assert "accreditation_source_id" in log.actor_metadata
    assert "accredited_to" in log.actor_metadata
    assert "fund_id" in log.actor_metadata
    assert "intermediary_id" in log.actor_metadata
