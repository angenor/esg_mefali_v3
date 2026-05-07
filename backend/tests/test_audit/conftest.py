"""Fixtures spécifiques aux tests F03 (audit log).

Fournit une fixture ``pg_session`` qui ouvre une connexion PostgreSQL réelle
(via ``DATABASE_URL`` du backend) pour valider les triggers ``BEFORE
UPDATE/DELETE``, la RLS et les ENUMs PG natifs. Les autres tests audit
restent sur SQLite (rapide).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _postgres_available() -> bool:
    """Détecte si PostgreSQL est joignable (pour skip auto)."""
    db_url = settings.database_url
    return db_url.startswith("postgresql")


pg_skip = pytest.mark.skipif(
    not _postgres_available(),
    reason="DATABASE_URL ne pointe pas sur PostgreSQL",
)


@pytest.fixture
async def pg_session() -> AsyncGenerator[AsyncSession, None]:
    """Session PG indépendante par test (engine créé + disposed à chaque fois).

    Évite les problèmes d'event loop fermé causés par le partage d'un engine
    asyncpg entre plusieurs tests.
    """
    db_url = settings.database_url
    if not db_url.startswith("postgresql"):
        pytest.skip("PostgreSQL non disponible")
    engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    session = factory()
    try:
        yield session
    finally:
        await session.rollback()
        await session.close()
        await engine.dispose()


@pytest.fixture
async def pg_user_admin(pg_session: AsyncSession):
    """Crée un Account + un user PME + un user Admin pour les tests PG.

    Retourne (account, pme_user, admin_user) — tous committés (donc visibles
    aux contextes RLS configurés).
    """
    from app.models.account import Account
    from app.models.user import User

    account = Account(name=f"audit-test-{uuid.uuid4().hex[:6]}")
    pg_session.add(account)
    await pg_session.flush()

    pme_user = User(
        email=f"pme-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="x",
        full_name="Test PME",
        company_name="TestCo",
        account_id=account.id,
        role="PME",
    )
    admin_user = User(
        email=f"admin-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="x",
        full_name="Test Admin",
        company_name="Mefali Admin",
        account_id=None,
        role="ADMIN",
    )
    pg_session.add_all([pme_user, admin_user])
    await pg_session.flush()

    # En contexte sans RLS pour les tests : positionner comme admin
    await pg_session.execute(
        text("SELECT set_config('app.current_role', 'ADMIN', true)")
    )
    await pg_session.execute(
        text("SELECT set_config('app.current_user_id', :v, true)"),
        {"v": str(admin_user.id)},
    )
    await pg_session.execute(
        text("SELECT set_config('app.current_account_id', '', true)")
    )

    yield account, pme_user, admin_user
