"""F045 T008 - Test seed_sources_045.

Verifie :
- Idempotence (2 appels -> 0 doublon)
- Presence des 4 sources F01 status='verified' :
  * bceao-taxonomie-verte-2024
  * gcf-strategic-plan-2024-2027
  * gcf-gender-policy-2019
  * un-sdg-10-indicators
- four-eyes CHECK respecte (captured_by != verified_by)
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.source import Source, VerificationStatus
from app.models.user import User


async def _make_admins(db: AsyncSession) -> tuple[User, User]:
    """Cree 2 admins distincts pour la regle four-eyes F01."""
    admin1 = User(
        email=f"admin-captured-{uuid.uuid4().hex[:6]}@mefali-system",
        hashed_password="x",
        full_name="Capture Admin",
        company_name="Mefali System",
        account_id=None,
        role="ADMIN",
    )
    admin2 = User(
        email=f"admin-verifier-{uuid.uuid4().hex[:6]}@mefali-system",
        hashed_password="x",
        full_name="Verify Admin",
        company_name="Mefali System",
        account_id=None,
        role="ADMIN",
    )
    db.add_all([admin1, admin2])
    await db.flush()
    return admin1, admin2


@pytest.mark.asyncio
async def test_seed_sources_045_inserts_4_verified_sources(
    db_session: AsyncSession,
) -> None:
    from app.scripts.seed_sources_045 import seed_sources_045

    captured_by, verified_by = await _make_admins(db_session)

    inserted = await seed_sources_045(
        db_session,
        captured_by_id=captured_by.id,
        verified_by_id=verified_by.id,
    )
    await db_session.flush()
    assert inserted == 4

    result = await db_session.execute(select(Source))
    sources = list(result.scalars().all())
    titles = {s.title for s in sources}
    assert "Taxonomie verte UEMOA — BCEAO 2024" in titles
    assert "GCF Strategic Plan 2024-2027 — Priority Themes" in titles
    assert "GCF Updated Gender Policy 2019" in titles
    assert any("ODD 10" in t or "SDG 10" in t for t in titles)

    # Tous verified
    for s in sources:
        if s.title.startswith(("Taxonomie verte UEMOA", "GCF ", "ODD 10")):
            assert s.verification_status == VerificationStatus.VERIFIED.value
            assert s.verified_by is not None
            assert s.verified_by != s.captured_by  # four-eyes


@pytest.mark.asyncio
async def test_seed_sources_045_is_idempotent(
    db_session: AsyncSession,
) -> None:
    from app.scripts.seed_sources_045 import seed_sources_045

    captured_by, verified_by = await _make_admins(db_session)

    first = await seed_sources_045(
        db_session,
        captured_by_id=captured_by.id,
        verified_by_id=verified_by.id,
    )
    await db_session.flush()
    second = await seed_sources_045(
        db_session,
        captured_by_id=captured_by.id,
        verified_by_id=verified_by.id,
    )
    await db_session.flush()
    assert first == 4
    assert second == 0
