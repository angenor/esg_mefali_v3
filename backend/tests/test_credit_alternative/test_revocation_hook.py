"""F18 — Tests du hook de révocation consentement (SC-008)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models.credit_alternative import (
    CreditPhoto,
    MobileMoneyAnalysis,
    MobileMoneyImport,
    MobileMoneyTransaction,
    PublicDataSource,
)
from app.modules.credit.alternative.revocation_hook import (
    PURGE_DELAY_DAYS,
    mark_credit_data_unused_on_revoke,
)


async def _make_account(db_session):
    from tests.conftest import make_account

    return await make_account(db_session)


async def _make_mm_chain(db_session, account_id):
    """Crée 1 import + 2 transactions + 1 analyse Mobile Money."""
    imp = MobileMoneyImport(
        account_id=account_id,
        provider="wave",
        file_path="/tmp/dummy.csv",
        imported_rows=2,
        rejected_rows=0,
        status="completed",
    )
    db_session.add(imp)
    await db_session.flush()
    for i in range(2):
        tx = MobileMoneyTransaction(
            account_id=account_id,
            import_id=imp.id,
            provider="wave",
            transaction_date=datetime(2025, 1, i + 1, tzinfo=timezone.utc),
            direction="incoming",
            amount=Decimal("1000.00"),
            currency="XOF",
            counterparty_hash=f"hash{i}",
            unused=False,
        )
        db_session.add(tx)
    analysis = MobileMoneyAnalysis(
        account_id=account_id,
        methodology_version="1.2",
        kpis={"transaction_count": 2},
        consent_active=True,
    )
    db_session.add(analysis)
    await db_session.flush()
    return imp, analysis


@pytest.mark.asyncio
async def test_revocation_marks_mm_transactions_unused(db_session):
    """SC-008 — révocation MM → toutes les transactions marquées unused + purge_after."""
    account = await _make_account(db_session)
    await _make_mm_chain(db_session, account.id)
    await db_session.commit()

    affected = await mark_credit_data_unused_on_revoke(
        db_session, account_id=account.id, consent_type="mobile_money_analysis"
    )
    await db_session.commit()

    assert affected["mobile_money_transactions"] == 2
    assert affected["mobile_money_analyses"] == 1

    from sqlalchemy import select

    txs = (
        await db_session.execute(
            select(MobileMoneyTransaction).where(
                MobileMoneyTransaction.account_id == account.id
            )
        )
    ).scalars().all()
    assert all(t.unused for t in txs)
    assert all(t.purge_after is not None for t in txs)
    # purge_after ~ +30j (SQLite peut perdre la TZ : on tolère naive)
    pa = txs[0].purge_after
    if pa.tzinfo is None:
        pa = pa.replace(tzinfo=timezone.utc)
    delta = (pa - datetime.now(timezone.utc)).days
    assert PURGE_DELAY_DAYS - 1 <= delta <= PURGE_DELAY_DAYS

    analysis = (
        await db_session.execute(
            select(MobileMoneyAnalysis).where(
                MobileMoneyAnalysis.account_id == account.id
            )
        )
    ).scalar_one()
    assert analysis.consent_active is False


@pytest.mark.asyncio
async def test_revocation_public_data_marks_unused(db_session):
    """Révocation public_data → sources marquées unused."""
    account = await _make_account(db_session)
    src = PublicDataSource(
        account_id=account.id,
        source_type="google_my_business",
        url="https://google.com/maps/dummy",
        declared_rating=Decimal("4.3"),
        declared_reviews_count=27,
        status="declared",
        unused=False,
    )
    db_session.add(src)
    await db_session.commit()

    affected = await mark_credit_data_unused_on_revoke(
        db_session, account_id=account.id, consent_type="public_data_analysis"
    )
    await db_session.commit()
    assert affected["public_data_sources"] == 1

    await db_session.refresh(src)
    assert src.unused is True
    assert src.purge_after is not None


@pytest.mark.asyncio
async def test_revocation_photos_marks_unused(db_session):
    """Révocation photos → CreditPhoto marqués unused."""
    account = await _make_account(db_session)
    photo = CreditPhoto(
        account_id=account.id,
        file_path="/tmp/photo.jpg",
        content_hash="abc123",
        quality_status="ok",
        unused=False,
    )
    db_session.add(photo)
    await db_session.commit()

    affected = await mark_credit_data_unused_on_revoke(
        db_session, account_id=account.id, consent_type="photos_ia_analysis"
    )
    await db_session.commit()
    assert affected["credit_photos"] == 1

    await db_session.refresh(photo)
    assert photo.unused is True


@pytest.mark.asyncio
async def test_revocation_other_consent_type_is_noop(db_session):
    """Révocation profile_analysis → no-op sur les tables crédit alternatif."""
    account = await _make_account(db_session)
    affected = await mark_credit_data_unused_on_revoke(
        db_session,
        account_id=account.id,
        consent_type="profile_analysis",
    )
    assert affected == {}


@pytest.mark.asyncio
async def test_revocation_idempotent(db_session):
    """Appeler 2x ne re-traite pas les lignes déjà unused."""
    account = await _make_account(db_session)
    src = PublicDataSource(
        account_id=account.id,
        source_type="trustpilot",
        url="https://trustpilot.com/x",
        status="declared",
        unused=False,
    )
    db_session.add(src)
    await db_session.commit()

    first = await mark_credit_data_unused_on_revoke(
        db_session, account_id=account.id, consent_type="public_data_analysis"
    )
    await db_session.commit()
    assert first["public_data_sources"] == 1

    second = await mark_credit_data_unused_on_revoke(
        db_session, account_id=account.id, consent_type="public_data_analysis"
    )
    await db_session.commit()
    assert second["public_data_sources"] == 0  # idempotent
