"""F18 — Test d'intégration : révocation consentement → hook crédit alternatif."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.consent import Consent
from app.models.credit_alternative import (
    MobileMoneyImport,
    MobileMoneyTransaction,
    PublicDataSource,
)
from app.modules.me.service import revoke_consent


@pytest.mark.asyncio
async def test_revoke_consent_marks_mm_data_unused_e2e(db_session):
    """SC-008 — révocation MM via me/service.revoke_consent → hook s'active."""
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)
    consent = Consent(
        account_id=user.account_id,
        user_id=user.id,
        consent_type="mobile_money_analysis",
        granted=True,
        legal_basis="consent",
        version="1.0",
    )
    imp = MobileMoneyImport(
        account_id=user.account_id,
        provider="wave",
        file_path="/tmp/dummy.csv",
        imported_rows=1,
        rejected_rows=0,
        status="completed",
    )
    db_session.add_all([consent, imp])
    await db_session.flush()
    tx = MobileMoneyTransaction(
        account_id=user.account_id,
        import_id=imp.id,
        provider="wave",
        transaction_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        direction="incoming",
        amount=Decimal("1000.00"),
        currency="XOF",
        counterparty_hash="hash1",
        unused=False,
    )
    db_session.add(tx)
    await db_session.commit()

    response = await revoke_consent(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        consent_type="mobile_money_analysis",
    )
    await db_session.commit()
    assert response.granted is False

    # La transaction MM doit être marquée unused.
    await db_session.refresh(tx)
    assert tx.unused is True
    assert tx.purge_after is not None


@pytest.mark.asyncio
async def test_revoke_consent_public_data_e2e(db_session):
    """Révocation public_data_analysis → PublicDataSource marqué unused."""
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)
    consent = Consent(
        account_id=user.account_id,
        user_id=user.id,
        consent_type="public_data_analysis",
        granted=True,
        legal_basis="consent",
        version="1.0",
    )
    src = PublicDataSource(
        account_id=user.account_id,
        source_type="trustpilot",
        url="https://trustpilot.com/x",
        status="declared",
        unused=False,
    )
    db_session.add_all([consent, src])
    await db_session.commit()

    await revoke_consent(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        consent_type="public_data_analysis",
    )
    await db_session.commit()

    await db_session.refresh(src)
    assert src.unused is True


@pytest.mark.asyncio
async def test_revoke_consent_other_type_no_side_effect(db_session):
    """Révocation product_communications → no-op sur les tables crédit."""
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)
    consent = Consent(
        account_id=user.account_id,
        user_id=user.id,
        consent_type="product_communications",
        granted=True,
        legal_basis="consent",
        version="1.0",
    )
    src = PublicDataSource(
        account_id=user.account_id,
        source_type="trustpilot",
        url="https://trustpilot.com/x",
        status="declared",
        unused=False,
    )
    db_session.add_all([consent, src])
    await db_session.commit()

    await revoke_consent(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        consent_type="product_communications",
    )
    await db_session.commit()

    await db_session.refresh(src)
    # PublicDataSource non concerné par ce consent → reste actif.
    assert src.unused is False
