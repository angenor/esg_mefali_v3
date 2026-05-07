"""Tests intégration endpoints audit (T026, T033, T038, T043)."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_admin, get_current_user
from app.core.constants import AuditAction, AuditSourceOfChange
from app.main import app
from app.models.audit_log import AuditLog
from tests.conftest import make_pme_user


def _override_user(user):
    """Helper : override get_current_user pour retourner le user donné."""

    async def _get():
        return user

    return _get


def _override_admin(user):
    async def _get_a():
        return user

    return _get_a


@pytest.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestEndpointGetMe:
    @pytest.mark.asyncio
    async def test_returns_only_own_logs(self, db_session, client):
        user = await make_pme_user(db_session)
        await db_session.commit()

        # Insère 2 logs : un pour notre compte, un pour un autre compte
        from app.models.account import Account

        other_account = Account(name=f"other-{uuid.uuid4().hex[:6]}")
        db_session.add(other_account)
        await db_session.flush()

        own = AuditLog(
            user_id=user.id,
            account_id=user.account_id,
            entity_type="company_profile",
            entity_id=uuid.uuid4(),
            action=AuditAction.update,
            field="sector",
            old_value="agriculture",
            new_value="energie",
            source_of_change=AuditSourceOfChange.manual,
        )
        other = AuditLog(
            user_id=user.id,
            account_id=other_account.id,
            entity_type="company_profile",
            entity_id=uuid.uuid4(),
            action=AuditAction.create,
            source_of_change=AuditSourceOfChange.manual,
        )
        db_session.add_all([own, other])
        await db_session.commit()

        app.dependency_overrides[get_current_user] = _override_user(user)
        try:
            r = await client.get("/api/audit/me")
            assert r.status_code == 200
            payload = r.json()
            assert payload["total"] == 1
            assert len(payload["events"]) == 1
            assert payload["events"][0]["field"] == "sector"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.asyncio
    async def test_filter_by_action(self, db_session, client):
        user = await make_pme_user(db_session)
        await db_session.commit()

        for _ in range(3):
            db_session.add(
                AuditLog(
                    user_id=user.id,
                    account_id=user.account_id,
                    entity_type="company_profile",
                    entity_id=uuid.uuid4(),
                    action=AuditAction.create,
                    source_of_change=AuditSourceOfChange.manual,
                )
            )
        db_session.add(
            AuditLog(
                user_id=user.id,
                account_id=user.account_id,
                entity_type="company_profile",
                entity_id=uuid.uuid4(),
                action=AuditAction.update,
                field="sector",
                old_value="x",
                new_value="y",
                source_of_change=AuditSourceOfChange.manual,
            )
        )
        await db_session.commit()

        app.dependency_overrides[get_current_user] = _override_user(user)
        try:
            r = await client.get("/api/audit/me?action=create")
            assert r.status_code == 200
            assert r.json()["total"] == 3
            r2 = await client.get("/api/audit/me?action=update")
            assert r2.json()["total"] == 1
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.asyncio
    async def test_pagination(self, db_session, client):
        user = await make_pme_user(db_session)
        await db_session.commit()

        for _ in range(75):
            db_session.add(
                AuditLog(
                    user_id=user.id,
                    account_id=user.account_id,
                    entity_type="company_profile",
                    entity_id=uuid.uuid4(),
                    action=AuditAction.create,
                    source_of_change=AuditSourceOfChange.manual,
                )
            )
        await db_session.commit()

        app.dependency_overrides[get_current_user] = _override_user(user)
        try:
            r = await client.get("/api/audit/me?limit=20&page=1")
            assert r.status_code == 200
            assert r.json()["total"] == 75
            assert len(r.json()["events"]) == 20
            r2 = await client.get("/api/audit/me?limit=20&page=4")
            assert len(r2.json()["events"]) == 15
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.asyncio
    async def test_limit_too_high_rejected(self, db_session, client):
        user = await make_pme_user(db_session)
        await db_session.commit()
        app.dependency_overrides[get_current_user] = _override_user(user)
        try:
            r = await client.get("/api/audit/me?limit=500")
            assert r.status_code == 422
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.asyncio
    async def test_unauth(self, client):
        r = await client.get("/api/audit/me")
        assert r.status_code == 401


class TestEndpointExport:
    @pytest.mark.asyncio
    async def test_csv_returns_bom_and_french_accents(self, db_session, client):
        user = await make_pme_user(db_session)
        await db_session.commit()

        # Avec un accent français dans la valeur
        db_session.add(
            AuditLog(
                user_id=user.id,
                account_id=user.account_id,
                entity_type="company_profile",
                entity_id=uuid.uuid4(),
                action=AuditAction.update,
                field="sector",
                old_value="agriculture",
                new_value="énergie renouvelable",
                source_of_change=AuditSourceOfChange.manual,
            )
        )
        await db_session.commit()

        app.dependency_overrides[get_current_user] = _override_user(user)
        try:
            r = await client.get("/api/audit/me/export?format=csv")
            assert r.status_code == 200
            assert "text/csv" in r.headers["content-type"]
            assert "audit-log-" in r.headers["content-disposition"]
            assert ".csv" in r.headers["content-disposition"]
            # BOM UTF-8 en première position
            assert r.content.startswith(b"\xef\xbb\xbf")
            decoded = r.content.decode("utf-8-sig")
            assert "énergie renouvelable" in decoded
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.asyncio
    async def test_json_returns_array(self, db_session, client):
        user = await make_pme_user(db_session)
        await db_session.commit()

        db_session.add(
            AuditLog(
                user_id=user.id,
                account_id=user.account_id,
                entity_type="company_profile",
                entity_id=uuid.uuid4(),
                action=AuditAction.create,
                source_of_change=AuditSourceOfChange.manual,
            )
        )
        await db_session.commit()

        app.dependency_overrides[get_current_user] = _override_user(user)
        try:
            r = await client.get("/api/audit/me/export?format=json")
            assert r.status_code == 200
            assert "application/json" in r.headers["content-type"]
            data = r.json()
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["entity_type"] == "company_profile"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.asyncio
    async def test_empty_export_returns_empty_csv_or_array(self, db_session, client):
        user = await make_pme_user(db_session)
        await db_session.commit()
        app.dependency_overrides[get_current_user] = _override_user(user)
        try:
            r = await client.get("/api/audit/me/export?format=csv")
            assert r.status_code == 200
            r2 = await client.get("/api/audit/me/export?format=json")
            assert r2.status_code == 200
            assert r2.json() == []
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestAdminEndpoints:
    @pytest.mark.asyncio
    async def test_admin_list_account_creates_view_admin_log(
        self, db_session, client
    ):
        # Créer PME + Admin distincts
        user = await make_pme_user(db_session)
        from app.models.account import Account
        from app.models.user import User

        admin = User(
            email=f"adm-{uuid.uuid4().hex[:6]}@test.com",
            hashed_password="x",
            full_name="Admin",
            company_name="Mefali",
            account_id=None,
            role="ADMIN",
        )
        db_session.add(admin)
        await db_session.commit()

        app.dependency_overrides[get_current_admin] = _override_admin(admin)
        try:
            r = await client.get(f"/api/admin/audit/{user.account_id}")
            assert r.status_code == 200
            payload = r.json()
            # Au moins 1 log = view_admin
            assert payload["total"] >= 1
            view_admin = [
                e for e in payload["events"] if e["action"] == "view_admin"
            ]
            assert len(view_admin) == 1
            assert view_admin[0]["entity_type"] == "account"
            assert view_admin[0]["entity_id"] == str(user.account_id)
            assert view_admin[0]["account_id"] == str(user.account_id)
            assert view_admin[0]["user_id"] == str(admin.id)
            assert view_admin[0]["source_of_change"] == "admin"
            # actor_metadata renseigné
            am = view_admin[0]["actor_metadata"]
            assert am is not None
            assert "endpoint" in am
        finally:
            app.dependency_overrides.pop(get_current_admin, None)

    @pytest.mark.asyncio
    async def test_admin_list_unknown_account_404(self, db_session, client):
        from app.models.user import User

        admin = User(
            email=f"adm-{uuid.uuid4().hex[:6]}@test.com",
            hashed_password="x",
            full_name="Admin",
            company_name="Mefali",
            account_id=None,
            role="ADMIN",
        )
        db_session.add(admin)
        await db_session.commit()

        app.dependency_overrides[get_current_admin] = _override_admin(admin)
        try:
            unknown = uuid.uuid4()
            r = await client.get(f"/api/admin/audit/{unknown}")
            assert r.status_code == 404
        finally:
            app.dependency_overrides.pop(get_current_admin, None)

    @pytest.mark.asyncio
    async def test_admin_global_filter_by_account(self, db_session, client):
        user = await make_pme_user(db_session)
        from app.models.account import Account
        from app.models.user import User

        other_acct = Account(name=f"o-{uuid.uuid4().hex[:6]}")
        db_session.add(other_acct)
        await db_session.flush()
        admin = User(
            email=f"adm-{uuid.uuid4().hex[:6]}@test.com",
            hashed_password="x",
            full_name="Admin",
            company_name="M",
            account_id=None,
            role="ADMIN",
        )
        db_session.add(admin)
        await db_session.flush()

        # 2 logs pour 2 comptes différents
        db_session.add(
            AuditLog(
                user_id=user.id,
                account_id=user.account_id,
                entity_type="company_profile",
                entity_id=uuid.uuid4(),
                action=AuditAction.create,
                source_of_change=AuditSourceOfChange.manual,
            )
        )
        db_session.add(
            AuditLog(
                user_id=user.id,
                account_id=other_acct.id,
                entity_type="company_profile",
                entity_id=uuid.uuid4(),
                action=AuditAction.create,
                source_of_change=AuditSourceOfChange.manual,
            )
        )
        await db_session.commit()

        app.dependency_overrides[get_current_admin] = _override_admin(admin)
        try:
            r = await client.get(
                f"/api/admin/audit?account_id={user.account_id}"
            )
            assert r.status_code == 200
            assert r.json()["total"] == 1
            r2 = await client.get("/api/admin/audit")
            assert r2.json()["total"] == 2
        finally:
            app.dependency_overrides.pop(get_current_admin, None)
