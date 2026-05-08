"""Tests F18 — Modèles SQLAlchemy."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.core.auditable import AUDITABLE_MODELS, EXEMPT_MODELS
from app.models.credit_alternative import (
    CreditMethodologyFactor,
    CreditPhoto,
    MobileMoneyAnalysis,
    MobileMoneyImport,
    MobileMoneyTransaction,
    PublicDataSource,
)


def test_auditable_models_includes_f18_tenant():
    """F18 — entités tenant tracées par audit log F03."""
    assert "MobileMoneyImport" in AUDITABLE_MODELS
    assert "MobileMoneyTransaction" in AUDITABLE_MODELS
    assert "CreditPhoto" in AUDITABLE_MODELS
    assert "PublicDataSource" in AUDITABLE_MODELS


def test_exempt_models_includes_f18_artifacts():
    """F18 — artefacts/catalogue exemptés."""
    assert "MobileMoneyAnalysis" in EXEMPT_MODELS
    assert "CreditMethodologyFactor" in EXEMPT_MODELS


@pytest.mark.asyncio
async def test_create_mm_import_persists(db_session):
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)
    imp = MobileMoneyImport(
        account_id=user.account_id,
        provider="wave",
        file_path="/uploads/test.csv",
        imported_rows=10,
        rejected_rows=0,
        status="completed",
    )
    db_session.add(imp)
    await db_session.commit()
    assert imp.id is not None
    assert imp.provider == "wave"


@pytest.mark.asyncio
async def test_create_mm_transaction_unique_dedup(db_session):
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)
    imp = MobileMoneyImport(
        account_id=user.account_id,
        provider="wave",
        file_path="/uploads/test.csv",
        status="completed",
    )
    db_session.add(imp)
    await db_session.flush()

    common = dict(
        account_id=user.account_id,
        import_id=imp.id,
        provider="wave",
        transaction_date=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
        direction="incoming",
        amount=Decimal("1000.00"),
        currency="XOF",
        counterparty_hash="a" * 64,
    )
    db_session.add(MobileMoneyTransaction(**common))
    await db_session.commit()

    # Deuxième insertion identique → IntegrityError UNIQUE
    db_session.add(MobileMoneyTransaction(**common))
    with pytest.raises(Exception):  # noqa: BLE001
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_credit_photo_unique_content_hash(db_session):
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)
    photo1 = CreditPhoto(
        account_id=user.account_id,
        file_path="/uploads/p1.jpg",
        content_hash="b" * 64,
        quality_status="pending",
    )
    db_session.add(photo1)
    await db_session.commit()

    photo2 = CreditPhoto(
        account_id=user.account_id,
        file_path="/uploads/p2.jpg",
        content_hash="b" * 64,  # même hash → rejeté
        quality_status="pending",
    )
    db_session.add(photo2)
    with pytest.raises(Exception):  # noqa: BLE001
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_public_data_source_create(db_session):
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)
    src = PublicDataSource(
        account_id=user.account_id,
        source_type="google_my_business",
        url="https://maps.google.com/?cid=123",
        declared_rating=Decimal("4.3"),
        declared_reviews_count=27,
        status="declared",
    )
    db_session.add(src)
    await db_session.commit()
    assert src.id is not None
    assert src.declared_rating == Decimal("4.3")
