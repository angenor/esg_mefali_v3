"""Tests intégration ``source_of_change`` (T016, T027)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.audit_context import source_of_change_scope
from app.core.constants import AuditAction, AuditSourceOfChange
from app.models.audit_log import AuditLog
from app.models.company import CompanyProfile, SectorEnum
from tests.conftest import make_pme_user


class TestSourceOfChange:
    @pytest.mark.asyncio
    async def test_default_is_manual(self, db_session):
        """Sans scope explicite, source = manual."""
        user = await make_pme_user(db_session)
        await db_session.commit()

        # Pas de source_of_change_scope ouvert : valeur par défaut
        profile = CompanyProfile(
            user_id=user.id,
            account_id=user.account_id,
            company_name="Default",
            sector=SectorEnum.agriculture,
        )
        db_session.add(profile)
        await db_session.commit()

        result = await db_session.execute(
            select(AuditLog).where(AuditLog.entity_id == profile.id)
        )
        rows = result.scalars().all()
        assert any(
            r.source_of_change in (AuditSourceOfChange.manual, "manual")
            for r in rows
        )

    @pytest.mark.asyncio
    async def test_llm_scope_sets_llm(self, db_session):
        user = await make_pme_user(db_session)
        await db_session.commit()

        with source_of_change_scope("llm"):
            profile = CompanyProfile(
                user_id=user.id,
                account_id=user.account_id,
                company_name="LLM-Made",
                sector=SectorEnum.energie,
            )
            db_session.add(profile)
            await db_session.commit()

        result = await db_session.execute(
            select(AuditLog).where(AuditLog.entity_id == profile.id)
        )
        rows = result.scalars().all()
        assert any(
            r.source_of_change in (AuditSourceOfChange.llm, "llm") for r in rows
        )

    @pytest.mark.asyncio
    async def test_admin_scope_sets_admin(self, db_session):
        user = await make_pme_user(db_session)
        await db_session.commit()

        with source_of_change_scope("admin"):
            profile = CompanyProfile(
                user_id=user.id,
                account_id=user.account_id,
                company_name="Admin-Modified",
                sector=SectorEnum.transport,
            )
            db_session.add(profile)
            await db_session.commit()

        result = await db_session.execute(
            select(AuditLog).where(AuditLog.entity_id == profile.id)
        )
        rows = result.scalars().all()
        assert any(
            r.source_of_change in (AuditSourceOfChange.admin, "admin")
            for r in rows
        )


class TestRecordAdminViewIdempotency:
    """Vérifie que record_admin_view est idempotent par requête (T026.d/e)."""

    @pytest.mark.asyncio
    async def test_same_request_same_target_not_duplicated(self, db_session):
        from app.modules.audit.service import AuditService
        from app.models.user import User

        user = await make_pme_user(db_session)
        admin = User(
            email=f"admin-{uuid.uuid4().hex[:6]}@x.com",
            hashed_password="x",
            full_name="Admin",
            company_name="M",
            account_id=None,
            role="ADMIN",
        )
        db_session.add(admin)
        await db_session.commit()

        # Mock request avec state vide
        class FakeRequest:
            class _State:
                pass

            def __init__(self):
                self.state = self._State()
                self.url = type("U", (), {"path": "/api/admin/audit/x"})
                self.client = type("C", (), {"host": "127.0.0.1"})
                self.headers = {"user-agent": "pytest"}

        request = FakeRequest()
        service = AuditService(db_session)
        log1 = await service.record_admin_view(admin, user.account_id, request)
        log2 = await service.record_admin_view(admin, user.account_id, request)
        await db_session.commit()

        # Le second appel doit retourner None (idempotent)
        assert log1 is not None
        assert log2 is None

        # Une seule ligne créée
        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == AuditAction.view_admin,
                AuditLog.entity_id == user.account_id,
            )
        )
        view_logs = result.scalars().all()
        assert len(view_logs) == 1

    @pytest.mark.asyncio
    async def test_distinct_requests_create_new_logs(self, db_session):
        """2 requêtes distinctes → 2 lignes view_admin."""
        from app.modules.audit.service import AuditService
        from app.models.user import User

        user = await make_pme_user(db_session)
        admin = User(
            email=f"admin-{uuid.uuid4().hex[:6]}@x.com",
            hashed_password="x",
            full_name="Admin",
            company_name="M",
            account_id=None,
            role="ADMIN",
        )
        db_session.add(admin)
        await db_session.commit()

        class FakeRequest:
            class _State:
                pass

            def __init__(self):
                self.state = self._State()
                self.url = type("U", (), {"path": "/api/admin/audit/x"})
                self.client = type("C", (), {"host": "127.0.0.1"})
                self.headers = {"user-agent": "pytest"}

        service = AuditService(db_session)
        # 2 requêtes distinctes → 2 logs
        await service.record_admin_view(admin, user.account_id, FakeRequest())
        await service.record_admin_view(admin, user.account_id, FakeRequest())
        await db_session.commit()

        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == AuditAction.view_admin,
                AuditLog.entity_id == user.account_id,
            )
        )
        view_logs = result.scalars().all()
        assert len(view_logs) == 2
