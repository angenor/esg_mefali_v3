"""Tests unitaires du modele Source (F01)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.source import Source, VerificationStatus
from app.models.user import User
from tests.conftest import make_account, make_pme_user


def _make_admin_user(account_id):
    """Helper : creer un User admin (account_id NULL)."""
    return User(
        email=f"admin-{date.today().isoformat()}@x.com",
        hashed_password="x",
        full_name="Admin",
        company_name="N/A",
        role="ADMIN",
        account_id=None,
    )


@pytest.mark.asyncio
async def test_source_create_default_status_draft(db_session) -> None:
    """A la creation, verification_status = 'draft'."""
    account = await make_account(db_session)
    user = await make_pme_user(db_session, account=account)
    src = Source(
        url="https://example.com/doc.pdf",
        title="Doc test",
        publisher="ADEME",
        version="v1",
        date_publi=date(2024, 1, 1),
        captured_by=user.id,
        created_by_user_id=user.id,
    )
    db_session.add(src)
    await db_session.flush()
    assert src.verification_status == VerificationStatus.DRAFT.value


@pytest.mark.asyncio
async def test_source_url_must_be_unique(db_session) -> None:
    """URL UNIQUE empeche les doublons."""
    account = await make_account(db_session)
    user = await make_pme_user(db_session, account=account)
    s1 = Source(
        url="https://example.com/dup.pdf",
        title="A",
        publisher="X",
        version="v1",
        date_publi=date(2024, 1, 1),
        captured_by=user.id,
        created_by_user_id=user.id,
    )
    s2 = Source(
        url="https://example.com/dup.pdf",
        title="B",
        publisher="Y",
        version="v2",
        date_publi=date(2024, 2, 1),
        captured_by=user.id,
        created_by_user_id=user.id,
    )
    db_session.add(s1)
    await db_session.flush()
    db_session.add(s2)
    with pytest.raises((IntegrityError, Exception)):
        await db_session.flush()


@pytest.mark.asyncio
async def test_source_status_enum_values() -> None:
    """L'enum VerificationStatus expose les 4 valeurs attendues."""
    assert VerificationStatus.DRAFT.value == "draft"
    assert VerificationStatus.PENDING.value == "pending"
    assert VerificationStatus.VERIFIED.value == "verified"
    assert VerificationStatus.OUTDATED.value == "outdated"
