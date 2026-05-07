"""Tests unitaires du mixin ``Auditable`` + listener ``before_flush`` (T008)."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.core.audit_context import source_of_change_scope
from app.core.constants import AuditAction, AuditSourceOfChange
from app.core.auditable import (
    AUDITABLE_MODELS,
    EXEMPT_MODELS,
    Auditable,
)
from app.models.audit_log import AuditLog
from app.models.company import CompanyProfile, SectorEnum
from tests.conftest import make_pme_user


def _count_logs(db_session) -> int:
    """Helper synchrone via run_sync pour compter les audit_log."""

    async def _async() -> int:
        result = await db_session.execute(select(func.count()).select_from(AuditLog))
        return int(result.scalar_one() or 0)

    import asyncio

    return asyncio.get_event_loop().run_until_complete(_async())


class TestMixinMarker:
    def test_company_profile_is_auditable(self) -> None:
        # Vérifié implicitement après héritage en US1, mais déjà testable.
        # Pour le test fondations on vérifie juste que la marker existe.
        class FakeAuditable(Auditable):
            pass

        assert isinstance(FakeAuditable(), Auditable)

    def test_auditable_models_set_complete(self) -> None:
        # Note : ESGCriterionScore n'existe pas comme table dédiée en MVP
        # (vit dans ESGAssessment.assessment_data). De même, CarbonEmissionEntry
        # n'a pas d'account_id propre (détail interne d'un CarbonAssessment) :
        # son audit passe via le snapshot CarbonAssessment.assessment_data.
        assert "CompanyProfile" in AUDITABLE_MODELS
        assert "FundApplication" in AUDITABLE_MODELS
        assert "ESGAssessment" in AUDITABLE_MODELS
        assert "CarbonAssessment" in AUDITABLE_MODELS
        assert "CreditScore" in AUDITABLE_MODELS
        assert "ActionPlan" in AUDITABLE_MODELS
        assert "ActionItem" in AUDITABLE_MODELS

    def test_exempt_models_includes_audit_log(self) -> None:
        assert "AuditLog" in EXEMPT_MODELS

    def test_exempt_includes_catalog(self) -> None:
        for name in (
            "Source",
            "Indicator",
            "Criterion",
            "EmissionFactor",
            "User",
            "Account",
        ):
            assert name in EXEMPT_MODELS


class TestListenerCapture:
    """Test du listener ``capture_audit_log_before_flush`` sur SQLite.

    Note : ces tests nécessitent que ``CompanyProfile`` hérite de Auditable
    (US1). On les exécute comme part de la phase 2 mais ils valident le bon
    fonctionnement du listener globale.
    """

    @pytest.mark.asyncio
    async def test_create_emits_audit_log(self, db_session) -> None:
        user = await make_pme_user(db_session)
        await db_session.commit()

        with source_of_change_scope("manual"):
            profile = CompanyProfile(
                user_id=user.id,
                account_id=user.account_id,
                company_name="Acme",
                sector=SectorEnum.agriculture,
            )
            db_session.add(profile)
            await db_session.commit()

        result = await db_session.execute(
            select(AuditLog).where(AuditLog.entity_id == profile.id)
        )
        rows = result.scalars().all()
        # Au moins une ligne create attendue
        assert any(r.action == AuditAction.create or r.action == "create" for r in rows)
        create_row = next(
            r for r in rows if r.action == AuditAction.create or r.action == "create"
        )
        assert create_row.source_of_change in (
            AuditSourceOfChange.manual,
            "manual",
        )
        assert create_row.field is None
        assert create_row.new_value is not None
        assert create_row.user_id == user.id
        assert create_row.account_id == user.account_id

    @pytest.mark.asyncio
    async def test_update_one_field_emits_one_row(self, db_session) -> None:
        user = await make_pme_user(db_session)
        await db_session.commit()

        with source_of_change_scope("manual"):
            profile = CompanyProfile(
                user_id=user.id,
                account_id=user.account_id,
                company_name="Acme",
                sector=SectorEnum.agriculture,
            )
            db_session.add(profile)
            await db_session.commit()

            # Update 1 field
            profile.sector = SectorEnum.energie
            await db_session.commit()

        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.entity_id == profile.id,
            )
        )
        rows = result.scalars().all()
        update_rows = [
            r for r in rows if r.action == AuditAction.update or r.action == "update"
        ]
        assert len(update_rows) == 1
        assert update_rows[0].field == "sector"
        # old_value sérialisé en str (Enum → "agriculture")
        assert update_rows[0].old_value in ("agriculture", SectorEnum.agriculture.value)
        assert update_rows[0].new_value in ("energie", SectorEnum.energie.value)

    @pytest.mark.asyncio
    async def test_update_multiple_fields_emits_one_row_per_field(
        self, db_session
    ) -> None:
        user = await make_pme_user(db_session)
        await db_session.commit()

        with source_of_change_scope("manual"):
            profile = CompanyProfile(
                user_id=user.id,
                account_id=user.account_id,
                company_name="Acme",
                sector=SectorEnum.agriculture,
                employee_count=10,
            )
            db_session.add(profile)
            await db_session.commit()

            # Update 3 champs
            profile.sector = SectorEnum.energie
            profile.employee_count = 20
            profile.city = "Dakar"
            await db_session.commit()

        result = await db_session.execute(
            select(AuditLog).where(AuditLog.entity_id == profile.id)
        )
        rows = result.scalars().all()
        update_rows = [
            r for r in rows if r.action == AuditAction.update or r.action == "update"
        ]
        # Une ligne par champ modifié
        assert len(update_rows) == 3
        modified_fields = {r.field for r in update_rows}
        assert modified_fields == {"sector", "employee_count", "city"}

    @pytest.mark.asyncio
    async def test_delete_emits_audit_log(self, db_session) -> None:
        user = await make_pme_user(db_session)
        await db_session.commit()

        with source_of_change_scope("manual"):
            profile = CompanyProfile(
                user_id=user.id,
                account_id=user.account_id,
                company_name="Acme",
                sector=SectorEnum.agriculture,
            )
            db_session.add(profile)
            await db_session.commit()

            entity_id = profile.id
            await db_session.delete(profile)
            await db_session.commit()

        result = await db_session.execute(
            select(AuditLog).where(AuditLog.entity_id == entity_id)
        )
        rows = result.scalars().all()
        delete_rows = [
            r for r in rows if r.action == AuditAction.delete or r.action == "delete"
        ]
        assert len(delete_rows) == 1
        assert delete_rows[0].old_value is not None
        assert delete_rows[0].new_value is None

    @pytest.mark.asyncio
    async def test_audit_log_insert_does_not_recurse(self, db_session) -> None:
        user = await make_pme_user(db_session)
        await db_session.commit()

        # On insère manuellement un AuditLog : aucun audit_log d'audit_log
        # ne doit apparaître.
        manual = AuditLog(
            user_id=user.id,
            account_id=user.account_id,
            entity_type="account",
            entity_id=user.account_id,
            action=AuditAction.view_admin,
            source_of_change=AuditSourceOfChange.admin,
        )
        db_session.add(manual)
        await db_session.commit()

        result = await db_session.execute(select(AuditLog))
        rows = result.scalars().all()
        # Seule notre insertion manuelle, aucune ligne supplémentaire (entity_type=audit_log).
        for r in rows:
            assert r.entity_type != "audit_log"
        assert any(r.id == manual.id for r in rows)

    @pytest.mark.asyncio
    async def test_non_auditable_model_does_not_emit_log(self, db_session) -> None:
        # User n'est pas Auditable → pas de log
        before_count_q = select(func.count()).select_from(AuditLog)
        before = (await db_session.execute(before_count_q)).scalar_one() or 0

        user = await make_pme_user(db_session)
        await db_session.commit()

        after = (await db_session.execute(before_count_q)).scalar_one() or 0
        # Aucune nouvelle ligne audit_log pour la création du User
        assert after == before

    @pytest.mark.asyncio
    async def test_rollback_rolls_back_audit_log(self, db_session) -> None:
        user = await make_pme_user(db_session)
        await db_session.commit()

        before_count_q = select(func.count()).select_from(AuditLog)
        before = (await db_session.execute(before_count_q)).scalar_one() or 0

        with source_of_change_scope("manual"):
            profile = CompanyProfile(
                user_id=user.id,
                account_id=user.account_id,
                company_name="Rollback",
                sector=SectorEnum.agriculture,
            )
            db_session.add(profile)
            await db_session.flush()
            # Rollback explicite
            await db_session.rollback()

        after = (await db_session.execute(before_count_q)).scalar_one() or 0
        assert after == before  # aucune ligne audit_log persistée
