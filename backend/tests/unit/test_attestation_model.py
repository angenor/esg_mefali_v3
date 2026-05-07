"""Tests unitaires modèle Attestation (F08 — T007)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.auditable import AUDITABLE_MODELS, Auditable
from app.models.attestation import Attestation


def _make_payload() -> dict:
    return {
        "scores": {
            "combined": 73,
            "solvability": 68,
            "green_impact": 78,
            "esg_global": 65,
        },
        "projects_summary": [],
    }


def _now() -> datetime:
    return datetime.now(tz=timezone.utc).replace(microsecond=0)


@pytest.mark.asyncio
async def test_attestation_in_auditable_models():
    """``Attestation`` est dans la whitelist AUDITABLE_MODELS (F03)."""
    assert "Attestation" in AUDITABLE_MODELS


@pytest.mark.asyncio
async def test_attestation_inherits_auditable():
    """``Attestation`` est marquée Auditable."""
    assert issubclass(Attestation, Auditable)


@pytest.mark.asyncio
async def test_attestation_create_basic(db_session):
    """Création OK avec tous les champs requis."""
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session, full_name="Fatou", company_name="Eco PME")
    valid_from = _now()
    a = Attestation(
        account_id=user.account_id,
        user_id=user.id,
        attestation_type="combined",
        payload=_make_payload(),
        referential_snapshot=[{"name": "ESG Mefali", "version": "1.2"}],
        pdf_path="/uploads/attestations/pdfs/abc.pdf",
        pdf_hash_sha256="a" * 64,
        signature_ed25519="dGVzdA==",
        public_key_id="v1",
        qr_code_path="/uploads/attestations/qr/abc.png",
        valid_from=valid_from,
        valid_until=valid_from + timedelta(days=365),
        verification_url="https://esg-mefali.com/verify/abc",
        display_id="ATT-2026-00001",
    )
    db_session.add(a)
    await db_session.commit()
    await db_session.refresh(a)

    assert a.id is not None
    assert a.attestation_type == "combined"
    assert a.public_key_id == "v1"
    assert a.revoked_at is None


@pytest.mark.asyncio
async def test_attestation_table_name():
    assert Attestation.__tablename__ == "attestations"


@pytest.mark.asyncio
async def test_attestation_unique_display_id(db_session):
    """``display_id`` est UNIQUE (contrainte BDD)."""
    from sqlalchemy.exc import IntegrityError

    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)
    common = {
        "account_id": user.account_id,
        "user_id": user.id,
        "attestation_type": "credit_score",
        "payload": _make_payload(),
        "referential_snapshot": [],
        "pdf_path": "/x.pdf",
        "pdf_hash_sha256": "0" * 64,
        "signature_ed25519": "sig==",
        "qr_code_path": "/x.png",
        "valid_from": _now(),
        "valid_until": _now() + timedelta(days=365),
        "verification_url": "https://esg-mefali.com/verify/dup",
    }
    a1 = Attestation(display_id="ATT-2026-00099", **common)
    db_session.add(a1)
    await db_session.commit()

    a2 = Attestation(display_id="ATT-2026-00099", **{**common, "user_id": user.id})
    db_session.add(a2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_attestation_revoke_fields(db_session):
    """Révocation peuple les 3 champs revoked_*."""
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)
    a = Attestation(
        account_id=user.account_id,
        user_id=user.id,
        attestation_type="combined",
        payload=_make_payload(),
        referential_snapshot=[],
        pdf_path="/p.pdf",
        pdf_hash_sha256="1" * 64,
        signature_ed25519="sig",
        qr_code_path="/p.png",
        valid_from=_now(),
        valid_until=_now() + timedelta(days=365),
        verification_url="https://esg-mefali.com/verify/x",
        display_id="ATT-2026-00010",
    )
    db_session.add(a)
    await db_session.commit()

    a.revoked_at = _now()
    a.revoked_reason = "Mise à jour majeure du profil"
    a.revoked_by_user_id = user.id
    await db_session.commit()
    await db_session.refresh(a)
    assert a.revoked_at is not None
    assert a.revoked_reason == "Mise à jour majeure du profil"


@pytest.mark.asyncio
async def test_attestation_relations_lazy_noload(db_session):
    """Les relations user/account/revoked_by_user sont en lazy='noload'."""
    user_rel = Attestation.user
    # SQLAlchemy expose lazy via property/Mapped descriptor.
    assert getattr(user_rel.property, "lazy", None) == "noload"
