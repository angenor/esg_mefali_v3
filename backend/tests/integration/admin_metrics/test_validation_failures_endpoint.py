"""Tests integration F22 — endpoint admin GET /api/admin/metrics/validation-failures.

Verifie l'agregation des echecs de validation tools et les gates de role.

Reference : ``specs/032-decision-tree-with-retry-eval/contracts/admin_metrics_endpoint.md``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.constants import UserRole
from app.models.tool_call_log import ToolCallLog
from app.models.user import User
from tests.conftest import make_pme_user


pytestmark = pytest.mark.integration


async def _create_admin_user(db_session) -> User:
    admin = User(
        email=f"admin-{uuid.uuid4().hex[:6]}@mefali.com",
        hashed_password="x",
        full_name="Admin",
        company_name="Mefali",
        account_id=None,
        role=UserRole.ADMIN.value,
    )
    db_session.add(admin)
    await db_session.flush()
    return admin


async def _seed_tool_logs(
    db_session,
    user_id: uuid.UUID,
    *,
    success_count: int,
    failure_count: int,
    tool_name: str = "update_company_profile",
    days_ago: int = 1,
) -> None:
    """Insere ``success_count`` succes + ``failure_count`` echecs."""
    base = datetime.now(timezone.utc) - timedelta(days=days_ago)
    for i in range(success_count):
        db_session.add(
            ToolCallLog(
                user_id=user_id,
                conversation_id=None,
                node_name="profiling_node",
                tool_name=tool_name,
                tool_args={},
                status="success",
                created_at=base + timedelta(seconds=i),
                validation_error=None,
            )
        )
    for i in range(failure_count):
        db_session.add(
            ToolCallLog(
                user_id=user_id,
                conversation_id=None,
                node_name="profiling_node",
                tool_name=tool_name,
                tool_args={},
                status="error",
                created_at=base + timedelta(seconds=100 + i),
                validation_error=[
                    {"loc": ["sector"], "msg": "Field required", "type": "missing"}
                ],
            )
        )
    # Commit pour que les inserts soient visibles depuis le ``client`` HTTP
    # (les fixtures SQLite ne partagent pas la transaction implicitement).
    await db_session.commit()


# ─── Test : 200 OK pour Admin ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_can_call_endpoint_returns_200(
    client, db_session, override_auth
) -> None:
    admin = await _create_admin_user(db_session)
    pme = await make_pme_user(db_session)

    await _seed_tool_logs(
        db_session, pme.id, success_count=95, failure_count=5,
    )

    override_auth.id = admin.id
    override_auth.account_id = None
    override_auth.role = UserRole.ADMIN.value

    response = await client.get(
        "/api/admin/metrics/validation-failures?period=7d&limit=10"
    )
    assert response.status_code == 200, response.text
    data = response.json()
    # Champs obligatoires (cf. contract)
    assert data["period"] == "7d"
    assert data["total_calls"] >= 100
    assert data["failure_count"] >= 5
    assert "failure_rate" in data
    assert "top_tools" in data
    assert "alert" in data
    assert data["alert_threshold"] == 0.05


# ─── Test : 403 pour non-Admin ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_non_admin_gets_403(client, db_session, override_auth) -> None:
    pme = await make_pme_user(db_session)
    override_auth.id = pme.id
    override_auth.account_id = pme.account_id
    override_auth.role = UserRole.PME.value

    response = await client.get(
        "/api/admin/metrics/validation-failures?period=7d&limit=10"
    )
    assert response.status_code == 403


# ─── Test : 422 pour params invalides ───────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_period_returns_422(
    client, db_session, override_auth
) -> None:
    admin = await _create_admin_user(db_session)
    override_auth.id = admin.id
    override_auth.account_id = None
    override_auth.role = UserRole.ADMIN.value

    response = await client.get(
        "/api/admin/metrics/validation-failures?period=99d&limit=10"
    )
    assert response.status_code == 422


# ─── Test : failure_rate exact ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_failure_rate_computation(
    client, db_session, override_auth
) -> None:
    admin = await _create_admin_user(db_session)
    pme = await make_pme_user(db_session)

    # 95 success + 5 failure -> rate = 0.05
    await _seed_tool_logs(
        db_session, pme.id, success_count=95, failure_count=5,
    )

    override_auth.id = admin.id
    override_auth.account_id = None
    override_auth.role = UserRole.ADMIN.value

    response = await client.get(
        "/api/admin/metrics/validation-failures?period=7d"
    )
    assert response.status_code == 200
    data = response.json()
    # 0.05 stable (rounded to 3 decimals).
    assert abs(data["failure_rate"] - 0.05) < 0.005


# ─── Test : top_tools agrege ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_top_tools_aggregation_desc(
    client, db_session, override_auth
) -> None:
    admin = await _create_admin_user(db_session)
    pme = await make_pme_user(db_session)

    # tool A : 10 fail, tool B : 3 fail
    await _seed_tool_logs(
        db_session, pme.id, success_count=20, failure_count=10,
        tool_name="batch_save_esg_criteria",
    )
    await _seed_tool_logs(
        db_session, pme.id, success_count=20, failure_count=3,
        tool_name="create_fund_application",
    )

    override_auth.id = admin.id
    override_auth.account_id = None
    override_auth.role = UserRole.ADMIN.value

    response = await client.get(
        "/api/admin/metrics/validation-failures?period=7d&limit=5"
    )
    assert response.status_code == 200
    data = response.json()
    top = data["top_tools"]
    assert len(top) >= 2
    # Ordre desc par nombre d'echecs
    assert top[0]["count"] >= top[1]["count"]
    names = [t["tool_name"] for t in top]
    assert "batch_save_esg_criteria" in names
    assert "create_fund_application" in names


# ─── Test : alert si failure_rate > 0.05 ────────────────────────────────────


@pytest.mark.asyncio
async def test_alert_triggered_above_threshold(
    client, db_session, override_auth
) -> None:
    admin = await _create_admin_user(db_session)
    pme = await make_pme_user(db_session)

    # 80 success + 20 failure -> rate = 0.2 > 0.05
    await _seed_tool_logs(
        db_session, pme.id, success_count=80, failure_count=20,
    )

    override_auth.id = admin.id
    override_auth.account_id = None
    override_auth.role = UserRole.ADMIN.value

    response = await client.get(
        "/api/admin/metrics/validation-failures?period=7d"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["alert"] is True


# ─── Test : 0 logs -> failure_rate=0, top_tools=[], alert=false ─────────────


@pytest.mark.asyncio
async def test_empty_dataset_returns_zero_metrics(
    client, db_session, override_auth
) -> None:
    admin = await _create_admin_user(db_session)
    override_auth.id = admin.id
    override_auth.account_id = None
    override_auth.role = UserRole.ADMIN.value

    response = await client.get(
        "/api/admin/metrics/validation-failures?period=7d"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_calls"] == 0
    assert data["failure_count"] == 0
    assert data["failure_rate"] == 0.0
    assert data["top_tools"] == []
    assert data["alert"] is False


# ─── Test : period filtre la fenetre temporelle ─────────────────────────────


@pytest.mark.asyncio
async def test_period_filters_time_window(
    client, db_session, override_auth
) -> None:
    admin = await _create_admin_user(db_session)
    pme = await make_pme_user(db_session)

    # Logs vieux de 10 jours (hors fenetre 7d)
    await _seed_tool_logs(
        db_session, pme.id, success_count=10, failure_count=2,
        tool_name="update_company_profile", days_ago=10,
    )
    # Logs recents (dans la fenetre 7d)
    await _seed_tool_logs(
        db_session, pme.id, success_count=5, failure_count=1,
        tool_name="batch_save_esg_criteria", days_ago=1,
    )

    override_auth.id = admin.id
    override_auth.account_id = None
    override_auth.role = UserRole.ADMIN.value

    response = await client.get(
        "/api/admin/metrics/validation-failures?period=7d"
    )
    assert response.status_code == 200
    data = response.json()
    # Seuls les logs <= 7 jours doivent etre comptes
    assert data["total_calls"] == 6
    assert data["failure_count"] == 1
