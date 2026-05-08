"""F18 — Tests des tools LangChain crédit alternatif (lecture seule)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.graph.tools.credit_alternative_tools import (
    CREDIT_ALTERNATIVE_TOOLS,
    get_credit_methodology,
    get_mobile_money_kpis,
    list_public_data_sources,
)
from app.models.consent import Consent
from app.models.credit_alternative import (
    CreditMethodologyFactor,
    MobileMoneyAnalysis,
    PublicDataSource,
)
from app.models.source import Source


def _make_runnable_config(db_session, user_id):
    """Construire un RunnableConfig minimal pour les tools."""
    return {"configurable": {"db": db_session, "user_id": str(user_id)}}


async def _make_source(db_session) -> Source:
    captured_by = uuid.uuid4()
    verified_by = uuid.uuid4()
    src = Source(
        url="https://example.com/test-tool",
        title="Test source",
        publisher="BCEAO",
        version="1.0",
        date_publi=date(2025, 1, 1),
        captured_at=datetime.now(timezone.utc),
        captured_by=captured_by,
        verified_by=verified_by,
        verification_status="verified",
        verified_at=datetime.now(timezone.utc),
        created_by_user_id=captured_by,
    )
    db_session.add(src)
    await db_session.flush()
    return src


@pytest.mark.asyncio
async def test_credit_alternative_tools_export_3_tools():
    """Le module exporte exactement 3 tools (lecture seule)."""
    assert len(CREDIT_ALTERNATIVE_TOOLS) == 3
    names = {t.name for t in CREDIT_ALTERNATIVE_TOOLS}
    assert names == {
        "get_credit_methodology",
        "get_mobile_money_kpis",
        "list_public_data_sources",
    }


@pytest.mark.asyncio
async def test_no_mutation_in_tool_names():
    """Conformity : aucun tool ne mute le catalogue (pattern interdit)."""
    forbidden = {"create", "update", "delete", "publish", "verify"}
    for t in CREDIT_ALTERNATIVE_TOOLS:
        first = t.name.split("_")[0]
        assert first not in forbidden, f"Tool {t.name} viole la lecture seule"


@pytest.mark.asyncio
async def test_get_credit_methodology_returns_published_factors(db_session):
    """Le tool lit les facteurs publiés (pas les drafts)."""
    src = await _make_source(db_session)
    factor = CreditMethodologyFactor(
        version="1.2",
        name="MM Régularité 30j",
        category="mobile_money_flux",
        weight=Decimal("0.150"),
        description="Régularité MM",
        source_id=src.id,
        publication_status="published",
    )
    db_session.add(factor)
    await db_session.commit()

    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)
    await db_session.commit()

    config = _make_runnable_config(db_session, user.id)
    result = await get_credit_methodology.ainvoke({}, config=config)
    assert "MM Régularité 30j" in result
    assert "1.2" in result


@pytest.mark.asyncio
async def test_get_mobile_money_kpis_requires_consent(db_session):
    """Sans consent actif, le tool retourne un message clair."""
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)
    await db_session.commit()

    config = _make_runnable_config(db_session, user.id)
    result = await get_mobile_money_kpis.ainvoke({}, config=config)
    # Pas de consent → message de redirection vers /mes-donnees/consentements
    assert "consentement" in result.lower() or "Consentement" in result


@pytest.mark.asyncio
async def test_get_mobile_money_kpis_returns_data_with_consent(db_session):
    """Avec consent actif, le tool retourne les KPIs."""
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)
    consent = Consent(
        account_id=user.account_id,
        user_id=user.id,
        consent_type="mobile_money_analysis",
        granted=True,
        legal_basis="consent",
        version="1.0",
    )
    analysis = MobileMoneyAnalysis(
        account_id=user.account_id,
        methodology_version="1.2",
        kpis={
            "monthly_volume_avg": "10000.00",
            "regularity_30d": 0.85,
            "growth_12m": 0.10,
            "avg_balance_estimate": "5000.00",
            "transaction_count": 42,
            "top_counterparties": [],
        },
        consent_active=True,
    )
    db_session.add_all([consent, analysis])
    await db_session.commit()

    config = _make_runnable_config(db_session, user.id)
    result = await get_mobile_money_kpis.ainvoke({}, config=config)
    assert "10000.00" in result
    assert "0.85" in result
    assert "42 transactions" in result


@pytest.mark.asyncio
async def test_list_public_data_sources_empty_returns_message(db_session):
    """Sans source déclarée + consent actif → message d'incitation."""
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)
    consent = Consent(
        account_id=user.account_id,
        user_id=user.id,
        consent_type="public_data_analysis",
        granted=True,
        legal_basis="consent",
        version="1.0",
    )
    db_session.add(consent)
    await db_session.commit()

    config = _make_runnable_config(db_session, user.id)
    result = await list_public_data_sources.ainvoke({}, config=config)
    assert "Aucune source publique" in result
