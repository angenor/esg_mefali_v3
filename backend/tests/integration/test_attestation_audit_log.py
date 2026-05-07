"""Tests audit log F03 sur Attestation (F08 — T024)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from tests.conftest import make_pme_user


async def _create_credit_score(db_session, user):
    from app.models.credit import ConfidenceLabel, CreditScore

    score = CreditScore(
        user_id=user.id,
        account_id=user.account_id,
        version=1,
        solvability_score=68.0,
        green_impact_score=78.0,
        combined_score=73.0,
        score_breakdown={},
        data_sources={},
        confidence_level=0.85,
        confidence_label=ConfidenceLabel.good,
        generated_at=datetime.now(tz=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(score)
    await db_session.commit()


def _cleanup(a):
    Path(a.pdf_path).unlink(missing_ok=True)
    Path(a.qr_code_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_create_attestation_emits_audit_log_create(db_session):
    """Création d'une attestation → audit_log.action='create'."""
    user = await make_pme_user(db_session)
    await _create_credit_score(db_session, user)

    from app.modules.attestations.service import generate_attestation

    a = await generate_attestation(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        attestation_type="credit_score",
        source_of_change="manual",
    )

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "attestations",
            AuditLog.entity_id == a.id,
        )
    )
    logs = result.scalars().all()
    create_logs = [log for log in logs if log.action == "create"]
    assert len(create_logs) >= 1, f"Pas d'audit_log create trouvé: {[(l.action, l.field) for l in logs]}"
    _cleanup(a)


@pytest.mark.asyncio
async def test_create_attestation_audit_log_source_manual(db_session):
    """source_of_change='manual' tracé."""
    user = await make_pme_user(db_session)
    await _create_credit_score(db_session, user)

    from app.modules.attestations.service import generate_attestation

    a = await generate_attestation(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        attestation_type="credit_score",
        source_of_change="manual",
    )
    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "attestations",
            AuditLog.entity_id == a.id,
            AuditLog.action == "create",
        )
    )
    log = result.scalars().first()
    assert log is not None
    assert log.source_of_change == "manual"
    _cleanup(a)


@pytest.mark.asyncio
async def test_create_attestation_audit_log_source_llm(db_session):
    """source_of_change='llm' tracé (génération via tool LLM)."""
    user = await make_pme_user(db_session)
    await _create_credit_score(db_session, user)

    from app.modules.attestations.service import generate_attestation

    a = await generate_attestation(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        attestation_type="credit_score",
        source_of_change="llm",
    )
    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "attestations",
            AuditLog.entity_id == a.id,
            AuditLog.action == "create",
        )
    )
    log = result.scalars().first()
    assert log is not None
    assert log.source_of_change == "llm"
    _cleanup(a)


@pytest.mark.asyncio
async def test_revoke_attestation_emits_audit_log_update(db_session):
    """Révocation → audit_log avec mutation des champs revoked_*."""
    user = await make_pme_user(db_session)
    await _create_credit_score(db_session, user)

    from app.modules.attestations.service import (
        generate_attestation,
        revoke_attestation,
    )

    a = await generate_attestation(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        attestation_type="credit_score",
    )
    await revoke_attestation(
        db_session,
        account_id=user.account_id,
        user_id=user.id,
        attestation_id=a.id,
        reason="Mise à jour majeure du profil",
    )

    # Le mixin Auditable trace les UPDATEs champ-par-champ.
    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "attestations",
            AuditLog.entity_id == a.id,
        )
    )
    logs = result.scalars().all()
    # On doit trouver au moins 1 create + 1+ update sur revoked_at, revoked_reason, revoked_by_user_id.
    actions = [log.action for log in logs]
    assert "create" in actions
    assert any(action == "update" for action in actions), f"Pas d'update trouvé: {actions}"
    _cleanup(a)
