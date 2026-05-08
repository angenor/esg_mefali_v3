"""Fixtures partagées pour les tests F20 Resources."""

from __future__ import annotations

import uuid as _uuid
from datetime import date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.core.security import create_access_token, hash_password
from app.models.financing import Intermediary
from app.models.source import Source, VerificationStatus
from app.models.user import User


pytestmark = pytest.mark.asyncio


async def make_admin(db: AsyncSession, suffix: str = "") -> tuple[User, str]:
    """Crée un user ADMIN + token JWT pour les tests."""
    user = User(
        email=f"admin{suffix}-{_uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pw1234567"),
        full_name=f"Admin{suffix}",
        company_name="ESG",
        role=UserRole.ADMIN.value,
        account_id=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, create_access_token(str(user.id))


async def make_pme(db: AsyncSession) -> tuple[User, str]:
    from app.models.account import Account

    account = Account(name=f"Acct-{_uuid.uuid4().hex[:6]}")
    db.add(account)
    await db.flush()
    user = User(
        email=f"pme-{_uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("pw1234567"),
        full_name="PME User",
        company_name="PME Co",
        role=UserRole.PME.value,
        account_id=account.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, create_access_token(str(user.id))


async def make_verified_source(
    db: AsyncSession, captured_by: _uuid.UUID, verified_by: _uuid.UUID | None = None
) -> Source:
    """Crée une Source verified pour les tests."""
    if verified_by is None:
        # créer un verifier différent
        verifier = User(
            email=f"verif-{_uuid.uuid4().hex[:6]}@test.com",
            hashed_password=hash_password("pw1234567"),
            full_name="Verifier",
            company_name="ESG",
            role=UserRole.ADMIN.value,
            account_id=None,
        )
        db.add(verifier)
        await db.flush()
        verified_by = verifier.id

    source = Source(
        url=f"https://example.com/doc-{_uuid.uuid4().hex[:8]}",
        title="Source de test",
        publisher="UEMOA",
        version="v1.0",
        date_publi=date(2024, 1, 1),
        captured_by=captured_by,
        verified_by=verified_by,
        verification_status=VerificationStatus.VERIFIED.value,
        verified_at=datetime.now(),
        created_by_user_id=captured_by,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


async def make_intermediary(db: AsyncSession) -> Intermediary:
    """Crée un Intermediary minimal pour tester intermediary_guide."""
    from app.models.financing import IntermediaryType, OrganizationType

    inter = Intermediary(
        name=f"BOAD-{_uuid.uuid4().hex[:6]}",
        intermediary_type=IntermediaryType.partner_bank,
        organization_type=OrganizationType.development_bank,
        country="Senegal",
        city="Dakar",
    )
    db.add(inter)
    await db.commit()
    await db.refresh(inter)
    return inter
