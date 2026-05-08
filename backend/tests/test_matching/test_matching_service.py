"""Tests unitaires du service de matching F14.

Couvre les sub-scores déterministes, le bottleneck, et le compute_offer_match
end-to-end avec un Project + Offer minimaux en SQLite.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.modules.financing import matching_service
from app.modules.financing.matching_service import (
    BOTTLENECK_GAP_THRESHOLD,
    MATCHING_WEIGHTS,
    _build_recommended_actions,
    _compute_bottleneck,
    _compute_documents_match,
    _compute_instrument_match,
    _compute_location_match,
    _compute_sector_match,
    _compute_size_match,
)


# ----- Sub-scores -----


def _fake_project(**kwargs):
    """Build a SimpleNamespace project with attributes used by sub-scores."""
    defaults = {
        "objective_env": [],
        "target_amount_amount": None,
        "target_amount_currency": None,
        "location_country": None,
        "financing_structure": None,
        "project_documents": [],
    }
    return SimpleNamespace(**{**defaults, **kwargs})


def _fake_fund(**kwargs):
    defaults = {
        "sectors_eligible": [],
        "min_amount_money": None,
        "max_amount_money": None,
        "eligibility_criteria": {},
        "instruments": [],
    }
    return SimpleNamespace(**{**defaults, **kwargs})


def _fake_offer(effective_required_documents=None):
    return SimpleNamespace(
        effective_required_documents=effective_required_documents or [],
    )


def test_sector_match_no_eligibility_returns_100():
    p = _fake_project(objective_env=["mitigation"])
    f = _fake_fund(sectors_eligible=[])
    assert _compute_sector_match(p, f) == 100


def test_sector_match_hit():
    p = _fake_project(objective_env=["mitigation", "biodiversity"])
    f = _fake_fund(sectors_eligible=["mitigation", "adaptation"])
    assert _compute_sector_match(p, f) == 100


def test_sector_match_miss():
    p = _fake_project(objective_env=["water"])
    f = _fake_fund(sectors_eligible=["mitigation", "adaptation"])
    assert _compute_sector_match(p, f) == 0


def test_sector_match_no_objective_returns_0():
    p = _fake_project(objective_env=[])
    f = _fake_fund(sectors_eligible=["mitigation"])
    assert _compute_sector_match(p, f) == 0


def test_size_match_no_target_neutral():
    p = _fake_project(target_amount_amount=None)
    f = _fake_fund()
    score, mismatch = _compute_size_match(p, f)
    assert score == 50
    assert mismatch is False


def test_size_match_in_range():
    p = _fake_project(
        target_amount_amount=Decimal("5000000"),
        target_amount_currency="XOF",
    )
    f = _fake_fund(
        min_amount_money=SimpleNamespace(
            amount=Decimal("1000000"), currency="XOF",
        ),
        max_amount_money=SimpleNamespace(
            amount=Decimal("10000000"), currency="XOF",
        ),
    )
    score, _ = _compute_size_match(p, f)
    assert score == 100


def test_size_match_currency_mismatch_returns_neutral_with_flag():
    p = _fake_project(
        target_amount_amount=Decimal("5000000"),
        target_amount_currency="XOF",
    )
    f = _fake_fund(
        min_amount_money=SimpleNamespace(
            amount=Decimal("1000"), currency="USD",
        ),
        max_amount_money=SimpleNamespace(
            amount=Decimal("100000"), currency="USD",
        ),
    )
    score, mismatch = _compute_size_match(p, f)
    assert score == 50
    assert mismatch is True


def test_location_match_no_country_neutral():
    p = _fake_project(location_country=None)
    f = _fake_fund()
    assert _compute_location_match(p, f) == 50


def test_location_match_no_eligibility_returns_100():
    p = _fake_project(location_country="SN")
    f = _fake_fund(eligibility_criteria={})
    assert _compute_location_match(p, f) == 100


def test_location_match_hit():
    p = _fake_project(location_country="SN")
    f = _fake_fund(eligibility_criteria={"eligible_countries": ["SN", "CI"]})
    assert _compute_location_match(p, f) == 100


def test_location_match_miss():
    p = _fake_project(location_country="ZA")
    f = _fake_fund(eligibility_criteria={"eligible_countries": ["SN", "CI"]})
    assert _compute_location_match(p, f) == 0


def test_documents_match_no_required_returns_100():
    p = _fake_project(project_documents=[])
    o = _fake_offer(effective_required_documents=[])
    assert _compute_documents_match(p, o) == 100


def test_documents_match_partial():
    p = _fake_project(project_documents=[1, 2])  # 2 docs
    o = _fake_offer(
        effective_required_documents=[{"a": 1}, {"b": 2}, {"c": 3}, {"d": 4}],
    )
    score = _compute_documents_match(p, o)
    assert score == 50  # 2/4 = 0.5 → 50


def test_documents_match_full():
    p = _fake_project(project_documents=[1, 2, 3])
    o = _fake_offer(effective_required_documents=[{"a": 1}, {"b": 2}, {"c": 3}])
    assert _compute_documents_match(p, o) == 100


def test_instrument_match_no_structure_neutral():
    p = _fake_project(financing_structure=None)
    f = _fake_fund(instruments=["subvention"])
    assert _compute_instrument_match(p, f) == 50


def test_instrument_match_no_instruments_returns_100():
    p = _fake_project(financing_structure="subvention")
    f = _fake_fund(instruments=[])
    assert _compute_instrument_match(p, f) == 100


def test_instrument_match_hit():
    p = _fake_project(financing_structure="subvention")
    f = _fake_fund(instruments=["subvention", "pret_concessionnel"])
    assert _compute_instrument_match(p, f) == 100


def test_instrument_match_miss():
    p = _fake_project(financing_structure="equity")
    f = _fake_fund(instruments=["subvention", "pret_concessionnel"])
    assert _compute_instrument_match(p, f) == 0


# ----- Bottleneck -----


def test_bottleneck_balanced_when_diff_within_threshold():
    assert _compute_bottleneck(60, 60) == "balanced"
    assert _compute_bottleneck(60, 50) == "balanced"  # diff=10, balanced (≤ threshold)
    assert _compute_bottleneck(50, 60) == "balanced"


def test_bottleneck_fund_when_fund_lower_by_more_than_threshold():
    assert _compute_bottleneck(40, 60) == "fund"  # diff=-20


def test_bottleneck_intermediary_when_intermediary_lower_by_more_than_threshold():
    assert _compute_bottleneck(80, 50) == "intermediary"  # diff=+30


def test_bottleneck_threshold_value():
    assert BOTTLENECK_GAP_THRESHOLD == 10


# ----- recommended_actions -----


def test_build_recommended_actions_top_3():
    missing = [
        {"label": "Critère 1", "indicator_id": uuid.uuid4()},
        {"label": "Critère 2"},
        {"label": "Critère 3", "referential_code": "GCF"},
        {"label": "Critère 4"},
    ]
    actions = _build_recommended_actions(missing)
    assert len(actions) == 3
    assert "Critère 1" in actions[0]["label"]
    assert "GCF" in actions[2]["label"]


def test_build_recommended_actions_empty():
    assert _build_recommended_actions([]) == []


def test_build_recommended_actions_handles_none_label():
    actions = _build_recommended_actions([{"indicator_code": "ABC"}])
    assert "ABC" in actions[0]["label"]


# ----- Constants -----


def test_matching_weights_total_one():
    assert pytest.approx(sum(MATCHING_WEIGHTS.values()), abs=1e-6) == 1.0


def test_matching_weights_keys():
    assert set(MATCHING_WEIGHTS.keys()) == {
        "sector", "esg", "size", "location", "documents", "instrument",
    }


# ----- compute_offer_match (integration with SQLite) -----


@pytest.mark.asyncio
async def test_compute_offer_match_creates_record(db_session):
    """Compute crée un OfferMatch idempotent (UPSERT)."""
    from app.models.account import Account
    from app.models.financing import Fund, FundType, FundStatus, AccessType
    from app.models.offer import Offer
    from app.models.project import Project
    from app.models.source import Source, PublicationStatus

    # Setup minimal
    account = Account(name="ACME")
    db_session.add(account)
    await db_session.flush()

    project = Project(
        account_id=account.id,
        name="Solar 5M",
        objective_env=["mitigation"],
        status="seeking_funding",
        target_amount_amount=Decimal("5000000"),
        target_amount_currency="XOF",
        location_country="SN",
        financing_structure="subvention",
    )
    db_session.add(project)
    await db_session.flush()

    # User créateur de la Source (4-eyes capture)
    from app.models.user import User
    capturer = User(
        email=f"capturer-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="x",
        full_name="Capturer",
        company_name="ACME",
        account_id=account.id,
    )
    db_session.add(capturer)
    await db_session.flush()

    # Source pour offer (FK NOT NULL)
    from datetime import date
    src = Source(
        title="Test source",
        publisher="Mefali",
        url="https://example.com",
        version="1.0",
        date_publi=date(2024, 1, 1),
        captured_by=capturer.id,
        created_by_user_id=capturer.id,
    )
    db_session.add(src)
    await db_session.flush()

    fund = Fund(
        name="GCF test",
        organization="GCF",
        fund_type=FundType.multilateral,
        description="Test",
        status=FundStatus.active,
        access_type=AccessType.direct,
        sectors_eligible=["mitigation"],
        instruments=["subvention"],
        publication_status=PublicationStatus.PUBLISHED.value,
    )
    db_session.add(fund)
    await db_session.flush()

    # On a besoin d'un Intermediary pour Offer
    from app.models.financing import Intermediary, IntermediaryType, OrganizationType
    inter = Intermediary(
        name="DIRECT",
        intermediary_type=IntermediaryType.accredited_entity,
        organization_type=OrganizationType.development_bank,
        country="SN",
        city="Dakar",
        code="DIRECT",
    )
    db_session.add(inter)
    await db_session.flush()

    offer = Offer(
        fund_id=fund.id,
        intermediary_id=inter.id,
        name="Direct via GCF",
        source_id=src.id,
        publication_status=PublicationStatus.PUBLISHED.value,
        is_active=True,
        effective_required_documents=[],
    )
    db_session.add(offer)
    await db_session.flush()

    # Premier compute : INSERT
    match = await matching_service.compute_offer_match(
        db_session, project_id=project.id, offer_id=offer.id,
    )
    assert match.global_score >= 0
    assert match.bottleneck in {"fund", "intermediary", "balanced"}
    assert match.fund_score >= 0
    assert match.intermediary_score >= 0

    # Second compute : UPSERT in-place (même UUID)
    match2 = await matching_service.compute_offer_match(
        db_session, project_id=project.id, offer_id=offer.id,
    )
    assert match2.id == match.id


@pytest.mark.asyncio
async def test_compute_offer_match_raises_on_missing_project(db_session):
    """compute_offer_match lève sur project inexistant."""
    with pytest.raises(ValueError, match="Project introuvable"):
        await matching_service.compute_offer_match(
            db_session, project_id=uuid.uuid4(), offer_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_subscribe_to_alerts_idempotent(db_session):
    """subscribe_to_alerts est idempotent."""
    from app.models.account import Account
    from app.models.project import Project

    account = Account(name="X")
    db_session.add(account)
    await db_session.flush()

    project = Project(
        account_id=account.id,
        name="P",
        objective_env=["mitigation"],
        status="draft",
    )
    db_session.add(project)
    await db_session.flush()

    sub1 = await matching_service.subscribe_to_alerts(
        db_session, account_id=account.id, project_id=project.id,
    )
    sub2 = await matching_service.subscribe_to_alerts(
        db_session, account_id=account.id, project_id=project.id,
    )
    assert sub1.id == sub2.id


@pytest.mark.asyncio
async def test_update_subscription_partial(db_session):
    """update_subscription accepte payload partiel."""
    from app.models.account import Account
    from app.models.project import Project

    account = Account(name="Y")
    db_session.add(account)
    await db_session.flush()

    project = Project(
        account_id=account.id,
        name="P",
        objective_env=["mitigation"],
        status="draft",
    )
    db_session.add(project)
    await db_session.flush()

    await matching_service.subscribe_to_alerts(
        db_session, account_id=account.id, project_id=project.id,
    )
    sub = await matching_service.update_subscription(
        db_session,
        account_id=account.id,
        project_id=project.id,
        is_active=False,
    )
    assert sub.is_active is False
