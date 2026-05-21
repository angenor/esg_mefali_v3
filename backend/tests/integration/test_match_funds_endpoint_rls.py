"""F045 T025 - Test isolation RLS F02 sur POST /match-funds.

Un appelant ne doit pas pouvoir matcher un projet d'un autre account
-> 404 silencieux (pas de fuite d'existence).
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_match_funds_endpoint_returns_404_for_other_account_project(
    client: AsyncClient,
    db_session: AsyncSession,
    override_auth,
) -> None:
    from app.models.account import Account
    from app.models.project import Project

    # Account A (proprietaire du projet)
    account_a = Account(name="Account A")
    # Account B (appelant)
    account_b = Account(name="Account B")
    db_session.add_all([account_a, account_b])
    await db_session.flush()

    project = Project(
        account_id=account_a.id,
        name="Projet de A",
    )
    db_session.add(project)
    await db_session.commit()

    # L'appelant authentifie est account_b
    override_auth.account_id = account_b.id
    override_auth.role = "PME"

    resp = await client.post(
        f"/api/projects/{project.id}/match-funds",
    )
    assert resp.status_code == 404, (
        f"RLS F02 doit retourner 404 silencieux, recu {resp.status_code}"
    )
