"""Tests F09 — catalog_publish_helper (publish d'entités catalogue)."""

from __future__ import annotations

import uuid as _uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.core.security import hash_password
from app.models.financing import Fund, FundStatus
from app.models.user import User
from app.modules.admin.catalog_publish_helper import (
    EntityNotFoundError,
    PublishGatingError,
    publish_entity,
)


pytestmark = pytest.mark.asyncio


async def _make_admin(db: AsyncSession) -> User:
    user = User(
        email=f"admin-{_uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pw1234567"),
        full_name="A",
        company_name="ESG",
        role=UserRole.ADMIN.value,
        account_id=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _make_fund(db: AsyncSession) -> Fund:
    from app.models.financing import AccessType, FundType
    fund = Fund(
        name=f"Test Fund {_uuid.uuid4().hex[:4]}",
        organization="Test Org",
        description="Test description",
        fund_type=FundType.multilateral,
        status=FundStatus.active,
        access_type=AccessType.direct,
    )
    db.add(fund)
    await db.commit()
    await db.refresh(fund)
    return fund


async def test_publish_entity_unknown_raises(db_session: AsyncSession) -> None:
    admin = await _make_admin(db_session)
    with pytest.raises(EntityNotFoundError):
        await publish_entity(
            db_session,
            entity_type="fund",
            entity_id=_uuid.uuid4(),
            admin_id=admin.id,
        )


async def test_publish_entity_unknown_type_raises(
    db_session: AsyncSession,
) -> None:
    admin = await _make_admin(db_session)
    with pytest.raises(ValueError, match="entity_type inconnu"):
        await publish_entity(
            db_session,
            entity_type="not_a_valid_type",
            entity_id=_uuid.uuid4(),
            admin_id=admin.id,
        )


async def test_publish_entity_success_on_sqlite(
    db_session: AsyncSession,
) -> None:
    """Sur SQLite (sans triggers), le publish réussit toujours."""
    admin = await _make_admin(db_session)
    fund = await _make_fund(db_session)
    result = await publish_entity(
        db_session,
        entity_type="fund",
        entity_id=fund.id,
        admin_id=admin.id,
    )
    await db_session.commit()
    assert result["entity_type"] == "fund"
    assert result["publication_status"] == "published"
