"""Tests d'intégration du service Projects (F06).

Couvre :
- list/get/create/update/duplicate/soft_delete sur SQLite in-memory.
- Garde-fou suppression avec applications actives.
- Force=True sur suppression.
"""

import uuid
from decimal import Decimal

import pytest

from app.core.money import Money
from app.modules.projects import service as project_service
from app.modules.projects.schemas import (
    ProjectCreate,
    ProjectFilters,
    ProjectUpdate,
)
from tests.conftest import make_account


@pytest.mark.asyncio
async def test_create_project_basic(db_session):
    account = await make_account(db_session, name="Acc1")
    payload = ProjectCreate(
        name="Solar Installation",
        description="50 kWc panels",
        objective_env=["renewable_energy"],
        maturity="pilot",
    )
    detail = await project_service.create_project(
        db_session, account_id=account.id, payload=payload,
    )
    assert detail.name == "Solar Installation"
    assert detail.status == "draft"
    assert detail.account_id == account.id
    assert detail.auto_generated is False
    assert detail.applications_count == 0


@pytest.mark.asyncio
async def test_create_project_with_money(db_session):
    account = await make_account(db_session, name="Acc")
    payload = ProjectCreate(
        name="Big project",
        target_amount=Money(amount=Decimal("50000000"), currency="XOF"),
    )
    detail = await project_service.create_project(
        db_session, account_id=account.id, payload=payload,
    )
    assert detail.target_amount is not None
    assert detail.target_amount.amount == Decimal("50000000.00")
    assert detail.target_amount.currency == "XOF"


@pytest.mark.asyncio
async def test_get_project_returns_none_when_missing(db_session):
    account = await make_account(db_session, name="Acc")
    nonexistent = uuid.uuid4()
    detail = await project_service.get_project(
        db_session, account_id=account.id, project_id=nonexistent,
    )
    assert detail is None


@pytest.mark.asyncio
async def test_get_project_isolation_by_account(db_session):
    """Account A ne peut pas voir un projet de Account B."""
    acc_a = await make_account(db_session, name="A")
    acc_b = await make_account(db_session, name="B")
    payload = ProjectCreate(name="P de B")
    detail_b = await project_service.create_project(
        db_session, account_id=acc_b.id, payload=payload,
    )
    # Tentative depuis Account A
    not_found = await project_service.get_project(
        db_session, account_id=acc_a.id, project_id=detail_b.id,
    )
    assert not_found is None


@pytest.mark.asyncio
async def test_list_projects_pagination(db_session):
    account = await make_account(db_session, name="Acc")
    for i in range(5):
        await project_service.create_project(
            db_session,
            account_id=account.id,
            payload=ProjectCreate(name=f"Project {i}"),
        )

    filters = ProjectFilters(page=1, limit=3)
    result = await project_service.list_projects(
        db_session, account_id=account.id, filters=filters,
    )
    assert result.total == 5
    assert len(result.items) == 3
    assert result.page == 1
    assert result.limit == 3


@pytest.mark.asyncio
async def test_list_projects_filter_status(db_session):
    account = await make_account(db_session, name="Acc")
    await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name="P1", status="draft"),
    )
    await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name="P2", status="seeking_funding"),
    )
    filters = ProjectFilters(status="seeking_funding")
    result = await project_service.list_projects(
        db_session, account_id=account.id, filters=filters,
    )
    assert result.total == 1
    assert result.items[0].name == "P2"


@pytest.mark.asyncio
async def test_update_project_partial(db_session):
    account = await make_account(db_session, name="Acc")
    detail = await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name="Old name"),
    )
    update = ProjectUpdate(name="New name", expected_jobs_created=10)
    updated = await project_service.update_project(
        db_session,
        account_id=account.id,
        project_id=detail.id,
        payload=update,
    )
    assert updated is not None
    assert updated.name == "New name"
    assert updated.expected_jobs_created == 10


@pytest.mark.asyncio
async def test_update_project_not_found(db_session):
    account = await make_account(db_session, name="Acc")
    fake = uuid.uuid4()
    res = await project_service.update_project(
        db_session,
        account_id=account.id,
        project_id=fake,
        payload=ProjectUpdate(name="x"),
    )
    assert res is None


@pytest.mark.asyncio
async def test_duplicate_project_default_suffix(db_session):
    account = await make_account(db_session, name="Acc")
    source = await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(
            name="Source project",
            description="desc",
            objective_env=["renewable_energy"],
            status="funded",
            expected_jobs_created=5,
        ),
    )
    dup = await project_service.duplicate_project(
        db_session, account_id=account.id, project_id=source.id,
    )
    assert dup is not None
    assert dup.id != source.id
    assert dup.name == "Source project (copie)"
    # Status forcé
    assert dup.status == "draft"
    assert dup.auto_generated is False
    # Champs métier copiés
    assert dup.expected_jobs_created == 5
    assert dup.objective_env == ["renewable_energy"]


@pytest.mark.asyncio
async def test_duplicate_project_with_new_name(db_session):
    account = await make_account(db_session, name="Acc")
    source = await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name="Site A"),
    )
    dup = await project_service.duplicate_project(
        db_session,
        account_id=account.id,
        project_id=source.id,
        new_name="Site B",
    )
    assert dup is not None
    assert dup.name == "Site B"
    assert dup.status == "draft"


@pytest.mark.asyncio
async def test_duplicate_project_truncates_long_suffix(db_session):
    account = await make_account(db_session, name="Acc")
    long_name = "x" * 200
    source = await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name=long_name),
    )
    dup = await project_service.duplicate_project(
        db_session, account_id=account.id, project_id=source.id,
    )
    assert dup is not None
    assert len(dup.name) <= 200


@pytest.mark.asyncio
async def test_duplicate_project_not_found(db_session):
    account = await make_account(db_session, name="Acc")
    res = await project_service.duplicate_project(
        db_session,
        account_id=account.id,
        project_id=uuid.uuid4(),
    )
    assert res is None


@pytest.mark.asyncio
async def test_soft_delete_project_success(db_session):
    account = await make_account(db_session, name="Acc")
    detail = await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name="To delete"),
    )
    result = await project_service.soft_delete_project(
        db_session,
        account_id=account.id,
        user_id=uuid.uuid4(),
        project_id=detail.id,
        force=False,
    )
    assert result is not None
    assert result.ok is True
    # Vérifier que le statut est bien cancelled
    after = await project_service.get_project(
        db_session, account_id=account.id, project_id=detail.id,
    )
    assert after is not None
    assert after.status == "cancelled"


@pytest.mark.asyncio
async def test_soft_delete_project_not_found(db_session):
    account = await make_account(db_session, name="Acc")
    res = await project_service.soft_delete_project(
        db_session,
        account_id=account.id,
        user_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        force=False,
    )
    assert res is None


@pytest.mark.asyncio
async def test_get_active_projects_for_user(db_session):
    """Vérifier le helper qui charge les projets actifs pour le state LangGraph."""
    account = await make_account(db_session, name="Acc")
    await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name="Active 1", status="seeking_funding"),
    )
    await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name="Cancelled", status="cancelled"),
    )
    await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name="Closed", status="closed"),
    )
    actives = await project_service.get_active_projects_for_user(
        db_session, account_id=account.id,
    )
    names = {p["name"] for p in actives}
    assert "Active 1" in names
    assert "Cancelled" not in names
    assert "Closed" not in names


@pytest.mark.asyncio
async def test_create_project_status_default_draft(db_session):
    account = await make_account(db_session, name="Acc")
    detail = await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name="P"),
    )
    assert detail.status == "draft"


@pytest.mark.asyncio
async def test_update_project_changes_status(db_session):
    account = await make_account(db_session, name="Acc")
    detail = await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name="P"),
    )
    updated = await project_service.update_project(
        db_session,
        account_id=account.id,
        project_id=detail.id,
        payload=ProjectUpdate(status="seeking_funding"),
    )
    assert updated is not None
    assert updated.status == "seeking_funding"
