"""Fixtures partagées pour les tests F047 ESG-projet."""

from __future__ import annotations

import uuid

import pytest

from app.models.project import Project
from app.scripts.seed_sources_047 import seed_sources_047
from tests.conftest import make_account, make_pme_user


@pytest.fixture
async def pme_account(db_session):
    return await make_account(db_session, name="TestPME-F047")


@pytest.fixture
async def pme_user(db_session, pme_account):
    return await make_pme_user(
        db_session,
        email=f"pme-{uuid.uuid4().hex[:6]}@test",
        company_name="TestPME-F047",
        account=pme_account,
    )


@pytest.fixture
async def seed_047(db_session):
    """Seed 3 sources + 3 référentiels + 46 critères pour les tests US1."""
    from app.models.user import User

    a1 = User(
        email=f"admin1-{uuid.uuid4().hex[:6]}@mefali",
        hashed_password="x",
        full_name="Admin 1",
        company_name="Mefali",
        account_id=None,
        role="ADMIN",
    )
    a2 = User(
        email=f"admin2-{uuid.uuid4().hex[:6]}@mefali",
        hashed_password="x",
        full_name="Admin 2",
        company_name="Mefali",
        account_id=None,
        role="ADMIN",
    )
    db_session.add_all([a1, a2])
    await db_session.flush()
    await seed_sources_047(db_session, captured_by_id=a1.id, verified_by_id=a2.id)


@pytest.fixture
async def project(db_session, pme_user, seed_047):
    p = Project(
        account_id=pme_user.account_id,
        name="Projet test F047",
        description="Coopérative agricole agroforesterie Togo",
        objective_env=["mitigation"],
        status="draft",
    )
    db_session.add(p)
    await db_session.flush()
    return p
