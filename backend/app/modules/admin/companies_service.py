"""Service admin /companies (F09 PRIO 3).

Vue overview cross-tenant pour consultation admin (read-only). Chaque
appel à :func:`get_company_overview` déclenche un audit log ``view_admin``
via :func:`log_view_admin_dedup` (F03), avec dédup quotidienne pour éviter
de polluer le journal côté PME.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.application import FundApplication
from app.models.attestation import Attestation
from app.models.carbon import CarbonAssessment
from app.models.company import CompanyProfile
from app.models.credit import CreditScore
from app.models.esg import ESGAssessment
from app.models.project import Project
from app.models.user import User
from app.modules.admin.audit_helpers import log_view_admin_dedup

logger = logging.getLogger(__name__)


class AccountNotFoundError(Exception):
    """L'account ciblé n'existe pas."""


def _serialize_company_profile(profile: CompanyProfile | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "id": profile.id,
        "company_name": profile.company_name,
        "sector": profile.sector.value if profile.sector else None,
        "sub_sector": profile.sub_sector,
        "employee_count": profile.employee_count,
        "year_founded": profile.year_founded,
        "city": profile.city,
        "country": profile.country,
        "annual_revenue_xof": profile.annual_revenue_xof,
        "annual_revenue_amount": (
            float(profile.annual_revenue_amount)
            if profile.annual_revenue_amount is not None
            else None
        ),
        "annual_revenue_currency": profile.annual_revenue_currency,
        "archived": profile.archived,
        "updated_at": profile.updated_at,
    }


def _serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": getattr(user, "full_name", None),
        "role": user.role,
        "is_active": getattr(user, "is_active", True),
        "created_at": user.created_at,
    }


def _serialize_project(project: Project) -> dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "status": project.status,
        "maturity": project.maturity,
        "target_amount": (
            float(project.target_amount_amount)
            if project.target_amount_amount is not None
            else None
        ),
        "target_currency": project.target_amount_currency,
        "created_at": project.created_at,
    }


def _serialize_application(app: FundApplication) -> dict[str, Any]:
    status_val = app.status
    if hasattr(status_val, "value"):
        status_val = status_val.value
    return {
        "id": app.id,
        "fund_id": app.fund_id,
        "status": status_val,
        "created_at": app.created_at,
        "submitted_at": app.submitted_at,
    }


def _serialize_attestation(att: Attestation) -> dict[str, Any]:
    return {
        "id": att.id,
        "display_id": att.display_id,
        "attestation_type": att.attestation_type,
        "valid_from": att.valid_from,
        "valid_until": att.valid_until,
        "revoked_at": att.revoked_at,
        "revoked_reason": att.revoked_reason,
        "created_at": att.created_at,
    }


async def get_company_overview(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    admin_id: uuid.UUID,
) -> dict[str, Any]:
    """Agrège la vue overview d'un account PME pour consultation admin.

    Déclenche un audit log ``view_admin`` (F03) avec dédup quotidienne.
    """
    # 1. Vérifier que l'account existe.
    res = await db.execute(select(Account).where(Account.id == account_id))
    account = res.scalar_one_or_none()
    if account is None:
        raise AccountNotFoundError(f"Account {account_id} introuvable")

    # 2. Charger les entités liées en parallèle (séquentiel ici pour
    # simplicité — asyncio.gather possible mais ajoute peu sur SQLite).
    profile_res = await db.execute(
        select(CompanyProfile).where(CompanyProfile.account_id == account_id)
    )
    profile = profile_res.scalar_one_or_none()

    users_res = await db.execute(
        select(User).where(User.account_id == account_id).order_by(User.created_at)
    )
    users = users_res.scalars().all()

    projects_res = await db.execute(
        select(Project)
        .where(Project.account_id == account_id)
        .order_by(Project.created_at.desc())
        .limit(50)
    )
    projects = projects_res.scalars().all()

    apps_res = await db.execute(
        select(FundApplication)
        .where(FundApplication.account_id == account_id)
        .order_by(FundApplication.created_at.desc())
        .limit(50)
    )
    applications = apps_res.scalars().all()

    esg_res = await db.execute(
        select(func.count(ESGAssessment.id)).where(
            ESGAssessment.account_id == account_id
        )
    )
    esg_count = esg_res.scalar_one() or 0

    carbon_res = await db.execute(
        select(func.count(CarbonAssessment.id)).where(
            CarbonAssessment.account_id == account_id
        )
    )
    carbon_count = carbon_res.scalar_one() or 0

    credit_res = await db.execute(
        select(func.count(CreditScore.id)).where(CreditScore.account_id == account_id)
    )
    credit_count = credit_res.scalar_one() or 0

    att_res = await db.execute(
        select(Attestation)
        .where(Attestation.account_id == account_id)
        .order_by(Attestation.created_at.desc())
        .limit(20)
    )
    attestations = att_res.scalars().all()

    # 3. Audit log view_admin avec dédup.
    await log_view_admin_dedup(
        db,
        admin_id=admin_id,
        account_id=account_id,
    )
    await db.flush()

    return {
        "account": {
            "id": account.id,
            "name": account.name,
            "is_active": account.is_active,
            "plan": account.plan,
            "deletion_scheduled_at": account.deletion_scheduled_at,
            "deleted_at": account.deleted_at,
            "created_at": account.created_at,
        },
        "company_profile": _serialize_company_profile(profile),
        "users": [_serialize_user(u) for u in users],
        "projects": [_serialize_project(p) for p in projects],
        "applications": [_serialize_application(a) for a in applications],
        "scores": {
            "esg_assessments_count": esg_count,
            "carbon_assessments_count": carbon_count,
            "credit_scores_count": credit_count,
        },
        "attestations": [_serialize_attestation(a) for a in attestations],
    }


async def list_accounts(
    db: AsyncSession,
    *,
    is_active: bool | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Liste paginée des comptes PME pour le back-office."""
    stmt = select(Account)
    count_stmt = select(func.count(Account.id))
    if is_active is not None:
        stmt = stmt.where(Account.is_active == is_active)
        count_stmt = count_stmt.where(Account.is_active == is_active)
    if q:
        pattern = f"%{q.lower()}%"
        stmt = stmt.where(func.lower(Account.name).like(pattern))
        count_stmt = count_stmt.where(func.lower(Account.name).like(pattern))

    offset = (page - 1) * page_size
    stmt = stmt.order_by(Account.created_at.desc()).offset(offset).limit(page_size)
    items = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one() or 0

    return {
        "items": [
            {
                "id": a.id,
                "name": a.name,
                "is_active": a.is_active,
                "plan": a.plan,
                "created_at": a.created_at,
                "deletion_scheduled_at": a.deletion_scheduled_at,
            }
            for a in items
        ],
        "total": total,
        "page": page,
        "limit": page_size,
    }
