"""Tests des tools LangChain de sourcage (F01)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.graph.tools.sourcing_tools import (
    cite_source,
    flag_unsourced,
    search_source,
)
from app.models.source import Source, VerificationStatus
from app.models.unsourced_flag import UnsourcedFlag
from tests.conftest import make_account, make_pme_user


async def _make_verified_source(db_session, account, user_a, user_b, *, suffix=""):
    """Helper : creer une source en statut verified directement."""
    src = Source(
        url=f"https://ademe.fr/{suffix}.pdf",
        title=f"ADEME {suffix}",
        publisher="ADEME",
        version="v23",
        date_publi=date(2024, 1, 1),
        captured_by=user_a.id,
        verified_by=user_b.id,
        verification_status=VerificationStatus.VERIFIED.value,
        verified_at=date.today(),
        account_id=account.id,
        created_by_user_id=user_a.id,
    )
    # SQLAlchemy DateTime accepts datetime; date is converted; we use an actual now
    from datetime import datetime, timezone
    src.verified_at = datetime.now(timezone.utc)
    db_session.add(src)
    await db_session.flush()
    return src


@pytest.mark.asyncio
async def test_cite_source_invalid_uuid(db_session) -> None:
    """cite_source rejette un identifiant non-UUID."""
    config = {"configurable": {"db": db_session, "user_id": str(uuid.uuid4())}}
    out = await cite_source.ainvoke({"source_id": "not-uuid"}, config=config)
    assert "invalide" in out.lower() or "erreur" in out.lower()


@pytest.mark.asyncio
async def test_cite_source_unknown_uuid(db_session) -> None:
    """cite_source retourne erreur si l'UUID n'existe pas."""
    account = await make_account(db_session)
    user = await make_pme_user(db_session, account=account)
    config = {"configurable": {"db": db_session, "user_id": str(user.id)}}
    fake_uuid = str(uuid.uuid4())
    out = await cite_source.ainvoke({"source_id": fake_uuid}, config=config)
    assert "introuvable" in out.lower()


@pytest.mark.asyncio
async def test_cite_source_rejects_draft(db_session) -> None:
    """cite_source rejette une source non verified."""
    account = await make_account(db_session)
    user = await make_pme_user(db_session, account=account)
    src = Source(
        url="https://x.com/d.pdf",
        title="Draft",
        publisher="X",
        version="v1",
        date_publi=date(2024, 1, 1),
        captured_by=user.id,
        created_by_user_id=user.id,
        verification_status=VerificationStatus.DRAFT.value,
    )
    db_session.add(src)
    await db_session.flush()
    config = {"configurable": {"db": db_session, "user_id": str(user.id)}}
    out = await cite_source.ainvoke({"source_id": str(src.id)}, config=config)
    assert "verified" in out.lower() or "draft" in out.lower()


@pytest.mark.asyncio
async def test_cite_source_returns_payload_for_verified(db_session) -> None:
    """cite_source retourne les metadonnees d'une source verified."""
    account = await make_account(db_session)
    user_a = await make_pme_user(db_session, account=account, email="a@x.com")
    user_b = await make_pme_user(db_session, account=account, email="b@x.com")
    src = await _make_verified_source(
        db_session, account, user_a, user_b, suffix="ok",
    )
    config = {"configurable": {"db": db_session, "user_id": str(user_a.id)}}
    out = await cite_source.ainvoke({"source_id": str(src.id)}, config=config)
    assert "ADEME" in out
    assert str(src.id) in out


@pytest.mark.asyncio
async def test_search_source_returns_results(db_session) -> None:
    account = await make_account(db_session)
    user_a = await make_pme_user(db_session, account=account, email="a@x.com")
    user_b = await make_pme_user(db_session, account=account, email="b@x.com")
    await _make_verified_source(
        db_session, account, user_a, user_b, suffix="electricite",
    )
    config = {"configurable": {"db": db_session, "user_id": str(user_a.id)}}
    out = await search_source.ainvoke(
        {"query": "ADEME", "publisher": "ADEME"}, config=config,
    )
    assert "ADEME" in out


@pytest.mark.asyncio
async def test_search_source_short_query(db_session) -> None:
    account = await make_account(db_session)
    user = await make_pme_user(db_session, account=account)
    config = {"configurable": {"db": db_session, "user_id": str(user.id)}}
    out = await search_source.ainvoke({"query": "a"}, config=config)
    assert "2 caracteres" in out or "erreur" in out.lower()


@pytest.mark.asyncio
async def test_search_source_no_results(db_session) -> None:
    account = await make_account(db_session)
    user = await make_pme_user(db_session, account=account)
    config = {"configurable": {"db": db_session, "user_id": str(user.id)}}
    out = await search_source.ainvoke({"query": "inexistant zzz"}, config=config)
    assert "aucune" in out.lower()


@pytest.mark.asyncio
async def test_flag_unsourced_logs_in_db(db_session) -> None:
    """flag_unsourced ajoute une entree dans unsourced_flags."""
    account = await make_account(db_session)
    user = await make_pme_user(db_session, account=account)
    config = {"configurable": {"db": db_session, "user_id": str(user.id)}}
    out = await flag_unsourced.ainvoke(
        {
            "claim": "Le secteur informel represente 60% des emplois",
            "reason": "aucune source UEMOA actuelle",
        },
        config=config,
    )
    assert "signalee" in out.lower() or "journalisee" in out.lower()
    flags = (await db_session.execute(select(UnsourcedFlag))).scalars().all()
    assert len(flags) == 1
    assert "secteur informel" in flags[0].claim


@pytest.mark.asyncio
async def test_flag_unsourced_short_claim(db_session) -> None:
    account = await make_account(db_session)
    user = await make_pme_user(db_session, account=account)
    config = {"configurable": {"db": db_session, "user_id": str(user.id)}}
    out = await flag_unsourced.ainvoke(
        {"claim": "x", "reason": "y"}, config=config,
    )
    assert "5 caracteres" in out or "erreur" in out.lower()


@pytest.mark.asyncio
async def test_search_source_limit_capped_at_5(db_session) -> None:
    """limit > 5 est capped a 5."""
    account = await make_account(db_session)
    user_a = await make_pme_user(db_session, account=account, email="a@x.com")
    user_b = await make_pme_user(db_session, account=account, email="b@x.com")
    for i in range(7):
        await _make_verified_source(
            db_session, account, user_a, user_b, suffix=f"src_{i}",
        )
    config = {"configurable": {"db": db_session, "user_id": str(user_a.id)}}
    out = await search_source.ainvoke(
        {"query": "ADEME", "limit": 100}, config=config,
    )
    # Doit afficher au plus 5 resultats
    lines = [l for l in out.split("\n") if l.startswith("- ID")]
    assert len(lines) <= 5
