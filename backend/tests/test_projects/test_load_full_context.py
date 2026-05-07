"""Tests de _load_full_context_for_state (F06).

Vérifie le chargement combiné profil + projets actifs pour le state LangGraph.
"""

import pytest

from app.api.chat import _load_full_context_for_state
from app.modules.projects import service as project_service
from app.modules.projects.schemas import ProjectCreate
from tests.conftest import make_account, make_pme_user


@pytest.mark.asyncio
async def test_load_full_context_returns_dict(db_session):
    account = await make_account(db_session, name="A")
    user = await make_pme_user(db_session, account=account)
    await db_session.commit()

    result = await _load_full_context_for_state(db_session, user.id)
    assert isinstance(result, dict)
    assert "profile" in result
    assert "projects" in result
    assert isinstance(result["projects"], list)


@pytest.mark.asyncio
async def test_load_full_context_includes_active_projects(db_session):
    account = await make_account(db_session, name="A")
    user = await make_pme_user(db_session, account=account)
    await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name="Active P", status="seeking_funding"),
    )
    await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name="Cancelled P", status="cancelled"),
    )
    await db_session.commit()

    result = await _load_full_context_for_state(db_session, user.id)
    project_names = {p["name"] for p in result["projects"]}
    assert "Active P" in project_names
    assert "Cancelled P" not in project_names


@pytest.mark.asyncio
async def test_load_full_context_no_account(db_session):
    """User sans account_id → retourne projets vides sans erreur."""
    # Créer un user sans account
    from app.models.user import User
    import uuid
    user = User(
        email=f"noaccnt-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="x",
        full_name="NoAcc",
        company_name="NoAcc",
        account_id=None,
        role="ADMIN",
    )
    db_session.add(user)
    await db_session.flush()

    result = await _load_full_context_for_state(db_session, user.id)
    assert result["projects"] == []
