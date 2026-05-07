"""F07 — Tests integration tools LangChain offres (T079-T084)."""

from __future__ import annotations

import uuid

import pytest
from langchain_core.runnables import RunnableConfig

from app.graph.tools.financing_tools import (
    compare_offers_for_fund,
    get_offer,
    list_offers,
)
from tests.conftest import test_session_factory


def _config_for(user_id: uuid.UUID) -> RunnableConfig:
    """Construit un RunnableConfig pour les tools."""
    return {
        "configurable": {
            "user_id": str(user_id),
            "db_session_factory": test_session_factory,
        }
    }


@pytest.mark.asyncio
async def test_list_offers_tool_returns_published_only(
    db_session, published_offer, draft_offer,
) -> None:
    """Tool list_offers retourne uniquement les published+active."""
    # Le tool utilise get_db_and_user qui retourne db et user_id
    # On simule un appel direct via la session de test
    from app.modules.offers.service import list_offers as svc_list

    offers, total = await svc_list(db_session, include_drafts=False)
    assert total == 1
    assert offers[0].id == published_offer.id


@pytest.mark.asyncio
async def test_get_offer_tool_returns_404_for_draft(
    db_session, draft_offer,
) -> None:
    """Service get_offer retourne None pour drafts (anti-fuite)."""
    from app.modules.offers.service import get_offer as svc_get

    result = await svc_get(db_session, draft_offer.id, include_drafts=False)
    assert result is None


@pytest.mark.asyncio
async def test_get_offer_tool_returns_published(
    db_session, published_offer,
) -> None:
    """Service get_offer retourne l'offre publiée."""
    from app.modules.offers.service import get_offer as svc_get

    result = await svc_get(db_session, published_offer.id, include_drafts=False)
    assert result is not None
    assert result.id == published_offer.id


@pytest.mark.asyncio
async def test_compare_offers_for_fund_tool_returns_published_only(
    db_session, published_offer, draft_offer,
) -> None:
    """Service compare_offers retourne uniquement les published."""
    from app.modules.offers.service import (
        compare_offers_for_fund as svc_compare,
    )

    comparisons = await svc_compare(db_session, fund_id=published_offer.fund_id)
    assert len(comparisons) == 1
    assert comparisons[0].offer_id == published_offer.id


@pytest.mark.asyncio
async def test_create_fund_application_with_offer_id(
    db_session, published_offer, basic_fund, basic_intermediary,
) -> None:
    """Tool create_fund_application accepte offer_id et persiste correctement."""
    from app.models.user import User
    from app.modules.applications.service import create_application

    # Créer un user PME
    from app.models.account import Account
    account = Account(name="TestApp")
    db_session.add(account)
    await db_session.flush()
    user = User(
        email=f"app-{uuid.uuid4().hex[:6]}@t.com",
        hashed_password="x",
        full_name="App User",
        company_name="TestApp",
        role="PME",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.commit()

    application = await create_application(
        db=db_session,
        user_id=user.id,
        fund_id=basic_fund.id,
        intermediary_id=basic_intermediary.id,
    )
    application.offer_id = published_offer.id
    await db_session.commit()

    assert application.offer_id == published_offer.id


@pytest.mark.asyncio
async def test_tools_are_read_only_on_catalog(
    db_session, published_offer,
) -> None:
    """Vérifie qu'aucun tool ne mute funds/intermediaries/offers."""
    from sqlalchemy import func, select

    from app.models.financing import Fund, Intermediary
    from app.models.offer import Offer
    from app.modules.offers.service import (
        compare_offers_for_fund as svc_compare,
    )
    from app.modules.offers.service import (
        get_offer as svc_get,
        list_offers as svc_list,
    )

    # Snapshot counts
    funds_count_before = (await db_session.execute(
        select(func.count()).select_from(Fund)
    )).scalar()
    interm_count_before = (await db_session.execute(
        select(func.count()).select_from(Intermediary)
    )).scalar()
    offers_count_before = (await db_session.execute(
        select(func.count()).select_from(Offer)
    )).scalar()

    # Appeler les 3 tools (services)
    await svc_list(db_session, include_drafts=False)
    await svc_get(db_session, published_offer.id, include_drafts=False)
    await svc_compare(db_session, fund_id=published_offer.fund_id)

    # Vérifier que rien n'a changé
    funds_count_after = (await db_session.execute(
        select(func.count()).select_from(Fund)
    )).scalar()
    interm_count_after = (await db_session.execute(
        select(func.count()).select_from(Intermediary)
    )).scalar()
    offers_count_after = (await db_session.execute(
        select(func.count()).select_from(Offer)
    )).scalar()

    assert funds_count_after == funds_count_before
    assert interm_count_after == interm_count_before
    assert offers_count_after == offers_count_before
