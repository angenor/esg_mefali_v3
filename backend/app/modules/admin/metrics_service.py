"""Service admin /metrics (F09 PRIO 3).

Agrégation des métriques globales pour le dashboard admin :
- Sources : total / draft / pending / verified / outdated
- Comptes PME : total / actifs / désactivés / nouveaux 30j
- Candidatures : par statut, taux soumission
- Attestations : émises / révoquées / actives
- LLM costs : placeholder (post-MVP — agrégation tool_call_logs).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.application import FundApplication
from app.models.attestation import Attestation
from app.models.source import Source

logger = logging.getLogger(__name__)


async def _count_sources_by_status(db: AsyncSession) -> dict[str, int]:
    """Compte les sources par verification_status."""
    res = await db.execute(
        select(Source.verification_status, func.count(Source.id)).group_by(
            Source.verification_status
        )
    )
    breakdown: dict[str, int] = {}
    for verif_status, n in res.all():
        key = verif_status.value if hasattr(verif_status, "value") else str(verif_status)
        breakdown[key] = int(n)
    return breakdown


async def _count_accounts(db: AsyncSession) -> dict[str, int]:
    """Compte les comptes PME par statut + nouveaux 30j."""
    total_res = await db.execute(select(func.count(Account.id)))
    total = int(total_res.scalar_one() or 0)

    active_res = await db.execute(
        select(func.count(Account.id)).where(Account.is_active == True)  # noqa: E712
    )
    active = int(active_res.scalar_one() or 0)

    inactive_res = await db.execute(
        select(func.count(Account.id)).where(Account.is_active == False)  # noqa: E712
    )
    inactive = int(inactive_res.scalar_one() or 0)

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    new_res = await db.execute(
        select(func.count(Account.id)).where(Account.created_at >= cutoff)
    )
    new_30d = int(new_res.scalar_one() or 0)

    deletion_res = await db.execute(
        select(func.count(Account.id)).where(
            Account.deletion_scheduled_at.is_not(None)
        )
    )
    pending_deletion = int(deletion_res.scalar_one() or 0)

    return {
        "total": total,
        "active": active,
        "inactive": inactive,
        "new_30d": new_30d,
        "pending_deletion": pending_deletion,
    }


async def _count_applications(db: AsyncSession) -> dict[str, Any]:
    """Compte les candidatures par statut + taux soumission."""
    res = await db.execute(
        select(FundApplication.status, func.count(FundApplication.id)).group_by(
            FundApplication.status
        )
    )
    by_status: dict[str, int] = {}
    total = 0
    for status_v, n in res.all():
        key = status_v.value if hasattr(status_v, "value") else str(status_v)
        n_int = int(n)
        by_status[key] = n_int
        total += n_int

    submitted_keys = {
        "submitted_to_fund",
        "submitted_to_intermediary",
        "under_review",
        "accepted",
        "rejected",
    }
    submitted = sum(by_status.get(k, 0) for k in submitted_keys)
    submission_rate = (submitted / total) if total > 0 else 0.0

    return {
        "total": total,
        "by_status": by_status,
        "submission_rate": round(submission_rate, 3),
    }


async def _count_attestations(db: AsyncSession) -> dict[str, int]:
    """Compte les attestations actives / révoquées / total."""
    total_res = await db.execute(select(func.count(Attestation.id)))
    total = int(total_res.scalar_one() or 0)

    revoked_res = await db.execute(
        select(func.count(Attestation.id)).where(Attestation.revoked_at.is_not(None))
    )
    revoked = int(revoked_res.scalar_one() or 0)

    now = datetime.now(timezone.utc)
    active_res = await db.execute(
        select(func.count(Attestation.id)).where(
            Attestation.revoked_at.is_(None),
            Attestation.valid_until > now,
        )
    )
    active = int(active_res.scalar_one() or 0)

    expired_res = await db.execute(
        select(func.count(Attestation.id)).where(
            Attestation.revoked_at.is_(None),
            Attestation.valid_until <= now,
        )
    )
    expired = int(expired_res.scalar_one() or 0)

    return {
        "total": total,
        "active": active,
        "revoked": revoked,
        "expired": expired,
    }


async def compute_overview(db: AsyncSession) -> dict[str, Any]:
    """Calcule l'agrégation complète des métriques admin overview."""
    sources_breakdown = await _count_sources_by_status(db)
    sources_total = sum(sources_breakdown.values())

    accounts_data = await _count_accounts(db)
    applications_data = await _count_applications(db)
    attestations_data = await _count_attestations(db)

    return {
        "sources": {
            "total": sources_total,
            "breakdown": sources_breakdown,
        },
        "accounts": accounts_data,
        "applications": applications_data,
        "attestations": attestations_data,
        "llm_costs": {
            "note": "Placeholder — agrégation par jour/mois à activer post-MVP",
            "available": False,
        },
        "generated_at": datetime.now(timezone.utc),
    }
