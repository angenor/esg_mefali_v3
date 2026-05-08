"""F18 — Tests du cron de purge post-révocation (SC-008)."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.credit_alternative import (
    CreditPhoto,
    MobileMoneyImport,
    MobileMoneyTransaction,
    PublicDataSource,
)


@pytest.mark.asyncio
async def test_purge_only_expired_rows(db_session):
    """Seules les lignes ``purge_after <= now`` sont effacées (idempotence)."""
    from scripts.purge_revoked_credit_data import purge_revoked_credit_data
    from tests.conftest import make_account

    account = await make_account(db_session)
    past = datetime.now(timezone.utc) - timedelta(days=1)
    future = datetime.now(timezone.utc) + timedelta(days=10)

    src_old = PublicDataSource(
        account_id=account.id,
        source_type="trustpilot",
        url="https://trustpilot.com/old",
        status="declared",
        unused=True,
        purge_after=past,
    )
    src_recent = PublicDataSource(
        account_id=account.id,
        source_type="google_reviews",
        url="https://google.com/recent",
        status="declared",
        unused=True,
        purge_after=future,
    )
    db_session.add_all([src_old, src_recent])
    await db_session.commit()

    report = await purge_revoked_credit_data(db_session)
    assert report["public_data_sources"]["rows"] == 1

    remaining = (
        await db_session.execute(select(PublicDataSource))
    ).scalars().all()
    assert len(remaining) == 1
    assert remaining[0].url.endswith("/recent")


@pytest.mark.asyncio
async def test_purge_idempotent_no_data(db_session):
    """Run sur DB vide → 0 lignes affectées, pas d'erreur."""
    from scripts.purge_revoked_credit_data import purge_revoked_credit_data

    report = await purge_revoked_credit_data(db_session)
    assert report["mobile_money_transactions"]["rows"] == 0
    assert report["credit_photos"]["rows"] == 0
    assert report["public_data_sources"]["rows"] == 0


@pytest.mark.asyncio
async def test_purge_credit_photo_deletes_file(db_session, tmp_path):
    """La purge supprime le fichier disque associé au CreditPhoto."""
    from scripts.purge_revoked_credit_data import purge_revoked_credit_data
    from tests.conftest import make_account

    account = await make_account(db_session)
    photo_path = tmp_path / "photo.jpg"
    photo_path.write_bytes(b"fake-jpeg-data")
    assert photo_path.exists()

    photo = CreditPhoto(
        account_id=account.id,
        file_path=str(photo_path),
        content_hash="hash1",
        quality_status="ok",
        unused=True,
        purge_after=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(photo)
    await db_session.commit()

    report = await purge_revoked_credit_data(db_session)
    assert report["credit_photos"]["rows"] == 1
    assert report["credit_photos"]["files"] == 1
    assert not photo_path.exists()


@pytest.mark.asyncio
async def test_purge_mm_transactions_only(db_session):
    """Purge MM : transactions effacées, import conservé pour audit."""
    from scripts.purge_revoked_credit_data import purge_revoked_credit_data
    from tests.conftest import make_account

    account = await make_account(db_session)
    imp = MobileMoneyImport(
        account_id=account.id,
        provider="wave",
        file_path="/tmp/nonexistent.csv",
        imported_rows=1,
        rejected_rows=0,
        status="completed",
    )
    db_session.add(imp)
    await db_session.flush()
    tx = MobileMoneyTransaction(
        account_id=account.id,
        import_id=imp.id,
        provider="wave",
        transaction_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        direction="incoming",
        amount=Decimal("100"),
        currency="XOF",
        counterparty_hash="h1",
        unused=True,
        purge_after=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(tx)
    await db_session.commit()

    report = await purge_revoked_credit_data(db_session)
    assert report["mobile_money_transactions"]["rows"] == 1

    # L'import reste en BDD (audit) ; les transactions sont parties.
    imports_left = (
        await db_session.execute(select(MobileMoneyImport))
    ).scalars().all()
    assert len(imports_left) == 1
    txs_left = (
        await db_session.execute(select(MobileMoneyTransaction))
    ).scalars().all()
    assert len(txs_left) == 0
