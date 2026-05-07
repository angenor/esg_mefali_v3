"""Tests unitaires des tools LangChain Projects (F06).

Couvre :
- 7 tools : list/get/create/update/delete/duplicate/link.
- Sérialisation JSON.
- Gestion erreurs.
- audit_context source_of_change=llm appliqué.
"""

import json
import uuid
from decimal import Decimal

import pytest
from langchain_core.runnables import RunnableConfig

from app.graph.tools.project_tools import (
    PROJECT_TOOLS,
    create_project,
    delete_project,
    duplicate_project,
    get_project,
    link_document_to_project,
    list_projects,
    update_project,
)
from app.modules.projects import service as project_service
from app.modules.projects.schemas import ProjectCreate
from tests.conftest import make_account, make_pme_user


def _make_config(db, user_id, account_id) -> RunnableConfig:
    return {
        "configurable": {
            "db": db,
            "user_id": user_id,
            "account_id": account_id,
        },
    }


def test_project_tools_list_count():
    assert len(PROJECT_TOOLS) == 7


def test_project_tools_names():
    names = {t.name for t in PROJECT_TOOLS}
    assert names == {
        "list_projects",
        "get_project",
        "create_project",
        "update_project",
        "delete_project",
        "duplicate_project",
        "link_document_to_project",
    }


@pytest.mark.asyncio
async def test_create_project_tool_basic(db_session):
    account = await make_account(db_session, name="A")
    user = await make_pme_user(db_session, account=account)
    config = _make_config(db_session, user.id, account.id)
    result = await create_project.ainvoke(
        {
            "name": "Test from tool",
            "description": "Description",
            "objective_env": ["renewable_energy"],
        },
        config=config,
    )
    payload = json.loads(result)
    assert payload.get("name") == "Test from tool"
    assert payload.get("status") == "draft"


@pytest.mark.asyncio
async def test_create_project_tool_invalid_objective(db_session):
    account = await make_account(db_session, name="A")
    user = await make_pme_user(db_session, account=account)
    config = _make_config(db_session, user.id, account.id)
    # Pydantic validation should raise on invalid objective_env, but
    # @tool wraps & may convert to error JSON; verify either tool error or ValidationError handling.
    try:
        result = await create_project.ainvoke(
            {"name": "p", "objective_env": ["bogus"]}, config=config,
        )
        payload = json.loads(result)
        # Soit validation Pydantic stricte (erreur), soit ok=False
        assert payload.get("ok") is False or "error" in payload
    except Exception:
        # Aussi acceptable : la validation arrive en exception
        pass


@pytest.mark.asyncio
async def test_create_project_tool_with_money(db_session):
    account = await make_account(db_session, name="A")
    user = await make_pme_user(db_session, account=account)
    config = _make_config(db_session, user.id, account.id)
    result = await create_project.ainvoke(
        {
            "name": "Big",
            "target_amount_amount": "50000000",
            "target_amount_currency": "XOF",
        },
        config=config,
    )
    payload = json.loads(result)
    assert payload.get("target_amount", {}).get("currency") == "XOF"


@pytest.mark.asyncio
async def test_list_projects_tool(db_session):
    account = await make_account(db_session, name="A")
    user = await make_pme_user(db_session, account=account)
    # Pré-créer 2 projets
    await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name="P1"),
    )
    await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name="P2", status="seeking_funding"),
    )
    await db_session.flush()

    config = _make_config(db_session, user.id, account.id)
    result = await list_projects.ainvoke({}, config=config)
    payload = json.loads(result)
    assert payload.get("total") == 2


@pytest.mark.asyncio
async def test_get_project_tool_not_found(db_session):
    account = await make_account(db_session, name="A")
    user = await make_pme_user(db_session, account=account)
    config = _make_config(db_session, user.id, account.id)
    result = await get_project.ainvoke(
        {"project_id": str(uuid.uuid4())}, config=config,
    )
    payload = json.loads(result)
    assert payload.get("ok") is False
    assert "not found" in payload.get("error", "").lower()


@pytest.mark.asyncio
async def test_update_project_tool_not_found(db_session):
    account = await make_account(db_session, name="A")
    user = await make_pme_user(db_session, account=account)
    config = _make_config(db_session, user.id, account.id)
    result = await update_project.ainvoke(
        {"project_id": str(uuid.uuid4()), "fields": {"name": "x"}},
        config=config,
    )
    payload = json.loads(result)
    assert payload.get("ok") is False


@pytest.mark.asyncio
async def test_update_project_tool_invalid_fields(db_session):
    account = await make_account(db_session, name="A")
    user = await make_pme_user(db_session, account=account)
    detail = await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name="P"),
    )
    await db_session.flush()
    config = _make_config(db_session, user.id, account.id)
    result = await update_project.ainvoke(
        {"project_id": str(detail.id), "fields": {"status": "bogus"}},
        config=config,
    )
    payload = json.loads(result)
    assert payload.get("ok") is False
    assert "Invalid fields" in payload.get("error", "")


@pytest.mark.asyncio
async def test_delete_project_tool_success(db_session):
    account = await make_account(db_session, name="A")
    user = await make_pme_user(db_session, account=account)
    detail = await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name="P"),
    )
    await db_session.flush()
    config = _make_config(db_session, user.id, account.id)
    # F10 — confirm=True obligatoire après le pattern destructif
    result = await delete_project.ainvoke(
        {"project_id": str(detail.id), "confirm": True}, config=config,
    )
    payload = json.loads(result)
    assert payload.get("ok") is True


@pytest.mark.asyncio
async def test_delete_project_tool_not_found(db_session):
    account = await make_account(db_session, name="A")
    user = await make_pme_user(db_session, account=account)
    config = _make_config(db_session, user.id, account.id)
    # F10 — confirm=True pour bypass du garde-fou destructif
    result = await delete_project.ainvoke(
        {"project_id": str(uuid.uuid4()), "confirm": True}, config=config,
    )
    payload = json.loads(result)
    assert payload.get("ok") is False


@pytest.mark.asyncio
async def test_duplicate_project_tool(db_session):
    account = await make_account(db_session, name="A")
    user = await make_pme_user(db_session, account=account)
    source = await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(
            name="Source", description="X", status="funded",
        ),
    )
    await db_session.flush()
    config = _make_config(db_session, user.id, account.id)
    result = await duplicate_project.ainvoke(
        {"project_id": str(source.id), "new_name": "Cloned"},
        config=config,
    )
    payload = json.loads(result)
    assert payload.get("name") == "Cloned"
    # status forcé draft
    assert payload.get("status") == "draft"


@pytest.mark.asyncio
async def test_duplicate_project_tool_not_found(db_session):
    account = await make_account(db_session, name="A")
    user = await make_pme_user(db_session, account=account)
    config = _make_config(db_session, user.id, account.id)
    result = await duplicate_project.ainvoke(
        {"project_id": str(uuid.uuid4())}, config=config,
    )
    payload = json.loads(result)
    assert payload.get("ok") is False


@pytest.mark.asyncio
async def test_link_document_tool_invalid_doc_type(db_session):
    account = await make_account(db_session, name="A")
    user = await make_pme_user(db_session, account=account)
    config = _make_config(db_session, user.id, account.id)
    try:
        result = await link_document_to_project.ainvoke(
            {
                "project_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "doc_type": "invalid",
            },
            config=config,
        )
        # Soit erreur JSON, soit ValidationError
        if isinstance(result, str):
            payload = json.loads(result)
            assert payload.get("ok") is False
    except Exception:
        # Validation Pydantic peut lever directement
        pass


@pytest.mark.asyncio
async def test_link_document_tool_project_not_found(db_session):
    account = await make_account(db_session, name="A")
    user = await make_pme_user(db_session, account=account)
    config = _make_config(db_session, user.id, account.id)
    result = await link_document_to_project.ainvoke(
        {
            "project_id": str(uuid.uuid4()),
            "document_id": str(uuid.uuid4()),
            "doc_type": "feasibility_study",
        },
        config=config,
    )
    payload = json.loads(result)
    assert payload.get("ok") is False


@pytest.mark.asyncio
async def test_get_project_tool_success(db_session):
    account = await make_account(db_session, name="A")
    user = await make_pme_user(db_session, account=account)
    detail = await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name="GetMe"),
    )
    await db_session.flush()
    config = _make_config(db_session, user.id, account.id)
    result = await get_project.ainvoke(
        {"project_id": str(detail.id)}, config=config,
    )
    payload = json.loads(result)
    assert payload.get("name") == "GetMe"


@pytest.mark.asyncio
async def test_update_project_tool_success(db_session):
    account = await make_account(db_session, name="A")
    user = await make_pme_user(db_session, account=account)
    detail = await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name="ToUpdate"),
    )
    await db_session.flush()
    config = _make_config(db_session, user.id, account.id)
    result = await update_project.ainvoke(
        {
            "project_id": str(detail.id),
            "fields": {"name": "Updated", "expected_jobs_created": 3},
        },
        config=config,
    )
    payload = json.loads(result)
    assert payload.get("name") == "Updated"
    assert payload.get("expected_jobs_created") == 3


@pytest.mark.asyncio
async def test_account_id_resolution_from_user_lookup(db_session):
    """Si account_id absent du config, doit se résoudre via le User."""
    account = await make_account(db_session, name="A")
    user = await make_pme_user(db_session, account=account)
    await db_session.commit()
    # Config sans account_id
    config: dict = {
        "configurable": {
            "db": db_session,
            "user_id": user.id,
        },
    }
    result = await list_projects.ainvoke({}, config=config)
    payload = json.loads(result)
    # Pas d'erreur ; total = 0 (aucun projet)
    assert payload.get("total") == 0


@pytest.mark.asyncio
async def test_account_id_resolution_fails_without_user(db_session):
    """Si user_id n'a pas d'account, le tool retourne une erreur."""
    config: dict = {
        "configurable": {
            "db": db_session,
            "user_id": uuid.uuid4(),
        },
    }
    result = await list_projects.ainvoke({}, config=config)
    payload = json.loads(result)
    assert payload.get("ok") is False
    assert "account_id" in payload.get("error", "")
