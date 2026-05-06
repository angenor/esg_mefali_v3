"""Tests du service SourceService (F01) — workflow 4-yeux + transitions."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.models.source import VerificationStatus
from app.modules.sources.service import (
    FourEyesViolation,
    InvalidStateTransition,
    SourceNotFound,
    SourceService,
)
from app.schemas.source import SourceCreate, SourceUpdate
from tests.conftest import make_account, make_pme_user


def _make_create_payload(suffix: str = "") -> SourceCreate:
    return SourceCreate(
        url=f"https://ademe.fr/doc{suffix}.pdf",
        title=f"ADEME Doc {suffix}",
        publisher="ADEME",
        version="v23",
        date_publi=date(2024, 1, 1),
    )


@pytest.mark.asyncio
async def test_create_source_sets_captured_by_and_draft(db_session) -> None:
    """create_source assigne captured_by=current_user et statut draft."""
    account = await make_account(db_session)
    user = await make_pme_user(db_session, account=account)
    service = SourceService(db_session)
    src = await service.create_source(
        _make_create_payload(),
        current_user_id=user.id,
        account_id=account.id,
    )
    assert src.verification_status == VerificationStatus.DRAFT.value
    assert src.captured_by == user.id
    assert src.created_by_user_id == user.id
    assert src.account_id == account.id


@pytest.mark.asyncio
async def test_request_verification_transitions_draft_to_pending(db_session) -> None:
    account = await make_account(db_session)
    user = await make_pme_user(db_session, account=account)
    service = SourceService(db_session)
    src = await service.create_source(
        _make_create_payload(), current_user_id=user.id, account_id=account.id,
    )
    src = await service.request_verification(src.id)
    assert src.verification_status == VerificationStatus.PENDING.value


@pytest.mark.asyncio
async def test_request_verification_rejects_non_draft(db_session) -> None:
    account = await make_account(db_session)
    user = await make_pme_user(db_session, account=account)
    service = SourceService(db_session)
    src = await service.create_source(
        _make_create_payload(), current_user_id=user.id, account_id=account.id,
    )
    await service.request_verification(src.id)
    with pytest.raises(InvalidStateTransition):
        await service.request_verification(src.id)


@pytest.mark.asyncio
async def test_verify_rejects_same_user_4yeux(db_session) -> None:
    """Le createur ne peut pas valider sa propre source (4-yeux)."""
    account = await make_account(db_session)
    user = await make_pme_user(db_session, account=account)
    service = SourceService(db_session)
    src = await service.create_source(
        _make_create_payload("a"),
        current_user_id=user.id,
        account_id=account.id,
    )
    await service.request_verification(src.id)
    with pytest.raises(FourEyesViolation):
        await service.verify_source(src.id, current_user_id=user.id)


@pytest.mark.asyncio
async def test_verify_succeeds_with_different_user(db_session) -> None:
    """Validation par admin different = succes."""
    account = await make_account(db_session)
    user_a = await make_pme_user(db_session, account=account, email="a@x.com")
    user_b = await make_pme_user(db_session, account=account, email="b@x.com")
    service = SourceService(db_session)
    src = await service.create_source(
        _make_create_payload("b"),
        current_user_id=user_a.id,
        account_id=account.id,
    )
    await service.request_verification(src.id)
    src = await service.verify_source(src.id, current_user_id=user_b.id)
    assert src.verification_status == VerificationStatus.VERIFIED.value
    assert src.verified_by == user_b.id
    assert src.verified_at is not None


@pytest.mark.asyncio
async def test_verify_rejects_non_pending(db_session) -> None:
    account = await make_account(db_session)
    user_a = await make_pme_user(db_session, account=account, email="a@x.com")
    user_b = await make_pme_user(db_session, account=account, email="b@x.com")
    service = SourceService(db_session)
    src = await service.create_source(
        _make_create_payload("c"),
        current_user_id=user_a.id,
        account_id=account.id,
    )
    # En draft (pas pending)
    with pytest.raises(InvalidStateTransition):
        await service.verify_source(src.id, current_user_id=user_b.id)


@pytest.mark.asyncio
async def test_mark_outdated_requires_reason(db_session) -> None:
    """mark_outdated rejette une raison vide."""
    account = await make_account(db_session)
    user_a = await make_pme_user(db_session, account=account, email="a@x.com")
    user_b = await make_pme_user(db_session, account=account, email="b@x.com")
    service = SourceService(db_session)
    src = await service.create_source(
        _make_create_payload("d"),
        current_user_id=user_a.id,
        account_id=account.id,
    )
    await service.request_verification(src.id)
    await service.verify_source(src.id, current_user_id=user_b.id)
    with pytest.raises(ValueError):
        await service.mark_outdated(src.id, "")


@pytest.mark.asyncio
async def test_mark_outdated_transitions(db_session) -> None:
    account = await make_account(db_session)
    user_a = await make_pme_user(db_session, account=account, email="a@x.com")
    user_b = await make_pme_user(db_session, account=account, email="b@x.com")
    service = SourceService(db_session)
    src = await service.create_source(
        _make_create_payload("e"),
        current_user_id=user_a.id,
        account_id=account.id,
    )
    await service.request_verification(src.id)
    await service.verify_source(src.id, current_user_id=user_b.id)
    src = await service.mark_outdated(src.id, "Nouvelle version disponible")
    assert src.verification_status == VerificationStatus.OUTDATED.value
    assert src.outdated_reason == "Nouvelle version disponible"


@pytest.mark.asyncio
async def test_get_verified_returns_only_verified(db_session) -> None:
    account = await make_account(db_session)
    user_a = await make_pme_user(db_session, account=account, email="a@x.com")
    service = SourceService(db_session)
    src = await service.create_source(
        _make_create_payload("f"),
        current_user_id=user_a.id,
        account_id=account.id,
    )
    # Source draft : doit retourner None pour get_verified.
    assert await service.get_verified(src.id) is None


@pytest.mark.asyncio
async def test_update_only_in_draft(db_session) -> None:
    account = await make_account(db_session)
    user_a = await make_pme_user(db_session, account=account, email="a@x.com")
    user_b = await make_pme_user(db_session, account=account, email="b@x.com")
    service = SourceService(db_session)
    src = await service.create_source(
        _make_create_payload("g"),
        current_user_id=user_a.id,
        account_id=account.id,
    )
    src = await service.update_source(src.id, SourceUpdate(title="Nouveau titre"))
    assert src.title == "Nouveau titre"
    # Pousser en pending
    await service.request_verification(src.id)
    with pytest.raises(InvalidStateTransition):
        await service.update_source(src.id, SourceUpdate(title="Encore nouveau"))


@pytest.mark.asyncio
async def test_get_by_id_returns_none_if_unknown(db_session) -> None:
    service = SourceService(db_session)
    assert await service.get_by_id(uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_search_returns_only_verified(db_session) -> None:
    account = await make_account(db_session)
    user_a = await make_pme_user(db_session, account=account, email="a@x.com")
    user_b = await make_pme_user(db_session, account=account, email="b@x.com")
    service = SourceService(db_session)
    # Source 1 : verified
    s1 = await service.create_source(
        SourceCreate(
            url="https://ademe.fr/electricite.pdf",
            title="ADEME Electricite Reseau",
            publisher="ADEME",
            version="v23",
            date_publi=date(2024, 1, 1),
        ),
        current_user_id=user_a.id,
        account_id=account.id,
    )
    await service.request_verification(s1.id)
    await service.verify_source(s1.id, current_user_id=user_b.id)
    # Source 2 : draft
    await service.create_source(
        SourceCreate(
            url="https://ademe.fr/draft.pdf",
            title="ADEME Draft",
            publisher="ADEME",
            version="v1",
            date_publi=date(2024, 1, 1),
        ),
        current_user_id=user_a.id,
        account_id=account.id,
    )
    results = await service.search("electricite", publisher="ADEME")
    assert len(results) == 1
    assert results[0].id == s1.id


@pytest.mark.asyncio
async def test_list_verified_pagination(db_session) -> None:
    account = await make_account(db_session)
    user_a = await make_pme_user(db_session, account=account, email="a@x.com")
    user_b = await make_pme_user(db_session, account=account, email="b@x.com")
    service = SourceService(db_session)
    for i in range(3):
        s = await service.create_source(
            SourceCreate(
                url=f"https://ok.com/d{i}.pdf",
                title=f"Doc {i}",
                publisher="ADEME",
                version="v1",
                date_publi=date(2024, 1, 1),
            ),
            current_user_id=user_a.id,
            account_id=account.id,
        )
        await service.request_verification(s.id)
        await service.verify_source(s.id, current_user_id=user_b.id)
    items, total = await service.list_verified(publisher="ADEME")
    assert total == 3
    assert len(items) == 3
