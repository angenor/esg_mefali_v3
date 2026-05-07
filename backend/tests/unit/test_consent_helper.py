"""F05 — Tests du helper ``require_consent`` (T008).

Vérifie :
- Lève 403 quand aucun consentement n'existe.
- Lève 403 quand le consentement est révoqué.
- No-op quand le consentement est actif.
- Message en français + metadata structurée (consent_type, settings_url).
- Couverture des 7 types valides.
- Lève 422 pour un type invalide (défense en profondeur).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.core.consent import require_consent
from app.models.account import Account
from app.models.consent import CONSENT_TYPE_VALUES, Consent
from app.models.user import User


async def _make_account_user(db_session) -> tuple[Account, User]:
    account = Account(name="ReqC")
    db_session.add(account)
    await db_session.flush()
    user = User(
        email="rq@example.com",
        hashed_password="x",
        full_name="Rq",
        company_name="ReqC",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()
    return account, user


@pytest.mark.asyncio
async def test_require_consent_raises_403_when_no_consent(db_session) -> None:
    account, _ = await _make_account_user(db_session)
    with pytest.raises(HTTPException) as exc:
        await require_consent(db_session, account.id, "mobile_money_analysis")
    assert exc.value.status_code == 403
    assert "Mobile Money" in exc.value.detail["detail"]
    assert exc.value.detail["consent_type"] == "mobile_money_analysis"
    assert exc.value.detail["settings_url"] == "/mes-donnees/consentements"


@pytest.mark.asyncio
async def test_require_consent_raises_403_when_revoked(db_session) -> None:
    account, user = await _make_account_user(db_session)
    db_session.add(
        Consent(
            account_id=account.id,
            user_id=user.id,
            consent_type="public_data_analysis",
            granted=True,
            granted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            revoked_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            legal_basis="consent",
            version="v1.0",
        )
    )
    await db_session.flush()
    with pytest.raises(HTTPException) as exc:
        await require_consent(db_session, account.id, "public_data_analysis")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_consent_passes_when_active(db_session) -> None:
    account, user = await _make_account_user(db_session)
    db_session.add(
        Consent(
            account_id=account.id,
            user_id=user.id,
            consent_type="profile_analysis",
            granted=True,
            legal_basis="contract",
            version="v1.0",
        )
    )
    await db_session.flush()
    # Ne doit pas lever
    await require_consent(db_session, account.id, "profile_analysis")


@pytest.mark.asyncio
async def test_require_consent_invalid_type_raises_422(db_session) -> None:
    account, _ = await _make_account_user(db_session)
    with pytest.raises(HTTPException) as exc:
        await require_consent(db_session, account.id, "totally_invalid_type")
    assert exc.value.status_code == 422
    assert exc.value.detail["consent_type"] == "totally_invalid_type"
    assert isinstance(exc.value.detail["valid_types"], list)


@pytest.mark.asyncio
@pytest.mark.parametrize("consent_type", CONSENT_TYPE_VALUES)
async def test_require_consent_supports_all_7_types(
    db_session, consent_type
) -> None:
    """Couvre les 7 valeurs de l'enum sans erreur."""
    account, user = await _make_account_user(db_session)
    db_session.add(
        Consent(
            account_id=account.id,
            user_id=user.id,
            consent_type=consent_type,
            granted=True,
            legal_basis="consent",
            version="v1.0",
        )
    )
    await db_session.flush()
    await require_consent(db_session, account.id, consent_type)
