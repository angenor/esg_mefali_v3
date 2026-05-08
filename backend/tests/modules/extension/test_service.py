"""Tests du service ``app.modules.extension.service`` (F24)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financing import (
    AccessType,
    Fund,
    FundIntermediary,
    FundStatus,
    FundType,
    Intermediary,
    IntermediaryType,
    OrganizationType,
)
from app.models.offer import Offer
from app.modules.extension.service import (
    _extract_patterns,
    _safe_compile,
    list_active_applications,
    match_url,
)


# ----------------------------------------------------------------------
# Helpers internes
# ----------------------------------------------------------------------


class TestExtractPatterns:
    def test_empty(self):
        assert _extract_patterns(None) == []
        assert _extract_patterns([]) == []

    def test_dict_form(self):
        out = _extract_patterns(
            [{"pattern": "^https://x", "scope": "homepage"}]
        )
        assert out == ["^https://x"]

    def test_string_form_compat(self):
        # Si stocké en chaîne brute par compat, accepter aussi.
        assert _extract_patterns(["^https://x"]) == ["^https://x"]

    def test_ignores_non_dict_non_str(self):
        assert _extract_patterns([{"foo": "bar"}, 42]) == []


class TestSafeCompile:
    def test_valid_regex(self):
        assert _safe_compile(r"^https://x") is not None

    def test_invalid_returns_none(self):
        assert _safe_compile(r"^https://[unclosed") is None


# ----------------------------------------------------------------------
# match_url
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_match_url_no_offers_returns_none(db_session: AsyncSession):
    result = await match_url(db_session, "https://anything.example.com")
    assert result is None


@pytest.mark.asyncio
async def test_match_url_single_match_published(
    db_session: AsyncSession,
    published_offer: Offer,
    basic_fund: Fund,
):
    # Patche le pattern sur le fund associé
    basic_fund.url_patterns = [
        {"pattern": r"^https://greenclimate\.fund/.*", "scope": "homepage"}
    ]
    db_session.add(basic_fund)
    await db_session.commit()

    result = await match_url(db_session, "https://greenclimate.fund/programme")
    assert result is not None
    assert result.offer_id == published_offer.id
    assert result.confidence == 1.0


@pytest.mark.asyncio
async def test_match_url_no_match(
    db_session: AsyncSession,
    published_offer: Offer,
    basic_fund: Fund,
):
    basic_fund.url_patterns = [
        {"pattern": r"^https://only-this-site\.com/.*", "scope": "homepage"}
    ]
    db_session.add(basic_fund)
    await db_session.commit()

    result = await match_url(db_session, "https://different-site.com/")
    assert result is None


@pytest.mark.asyncio
async def test_match_url_skips_draft_offers(
    db_session: AsyncSession,
    draft_offer: Offer,
    basic_fund: Fund,
):
    basic_fund.url_patterns = [
        {"pattern": r"^https://x\.com/.*", "scope": "homepage"}
    ]
    db_session.add(basic_fund)
    await db_session.commit()

    result = await match_url(db_session, "https://x.com/page")
    # Aucune offre publiée → None.
    assert result is None


@pytest.mark.asyncio
async def test_match_url_invalid_regex_skipped(
    db_session: AsyncSession,
    published_offer: Offer,
    basic_fund: Fund,
):
    # Mix : un pattern invalide + un valide → on doit toujours matcher.
    basic_fund.url_patterns = [
        {"pattern": r"^https://[broken", "scope": "homepage"},
        {"pattern": r"^https://valid\.com/.*", "scope": "homepage"},
    ]
    db_session.add(basic_fund)
    await db_session.commit()

    result = await match_url(db_session, "https://valid.com/page")
    assert result is not None
    assert result.offer_id == published_offer.id


@pytest.mark.asyncio
async def test_match_url_intermediary_pattern_also_works(
    db_session: AsyncSession,
    published_offer: Offer,
    basic_intermediary: Intermediary,
):
    basic_intermediary.url_patterns = [
        {"pattern": r"^https://boad\.org/.*", "scope": "homepage"}
    ]
    db_session.add(basic_intermediary)
    await db_session.commit()

    result = await match_url(db_session, "https://boad.org/programme")
    assert result is not None
    assert result.offer_id == published_offer.id


@pytest.mark.asyncio
async def test_match_url_priority_direct_intermediary(
    db_session: AsyncSession,
    verified_source,
    basic_fund: Fund,
    basic_intermediary: Intermediary,
):
    # Construit un intermédiaire DIRECT + une offre liée
    direct_inter = Intermediary(
        name="Direct Singleton",
        intermediary_type=IntermediaryType.accredited_entity,
        organization_type=OrganizationType.development_bank,
        country="SN",
        city="Dakar",
        accreditations=[],
        services_offered={},
        eligibility_for_sme={},
        required_documents=[],
        is_active=True,
        code="DIRECT",
        url_patterns=[
            {"pattern": r"^https://shared\.example\.fr/.*", "scope": "homepage"}
        ],
        source_id=verified_source.id,
        publication_status="published",
        version="1.0",
        valid_from=date.today(),
    )
    db_session.add(direct_inter)
    await db_session.commit()

    # Lien fund_intermediary pour DIRECT
    fi = FundIntermediary(
        fund_id=basic_fund.id,
        intermediary_id=direct_inter.id,
        accredited_from=date.today(),
        accreditation_source_id=verified_source.id,
        version="1.0",
        valid_from=date.today(),
    )
    db_session.add(fi)

    # Offre publiée pour DIRECT
    direct_offer = Offer(
        fund_id=basic_fund.id,
        intermediary_id=direct_inter.id,
        name="Direct Offer",
        accepted_languages=["FR"],
        effective_criteria={},
        effective_required_documents=[],
        effective_fees={},
        is_active=True,
        publication_status="published",
        source_id=verified_source.id,
        version="3.0",
        valid_from=date.today(),
    )
    db_session.add(direct_offer)

    # L'autre offre matche aussi le même pattern (via fund.url_patterns)
    basic_fund.url_patterns = [
        {"pattern": r"^https://shared\.example\.fr/.*", "scope": "homepage"}
    ]
    db_session.add(basic_fund)
    await db_session.commit()

    result = await match_url(db_session, "https://shared.example.fr/foo")
    assert result is not None
    # Doit prioriser l'offre liée à l'intermédiaire DIRECT.
    assert result.offer_id == direct_offer.id


# ----------------------------------------------------------------------
# list_active_applications
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_active_applications_filters_inactive(
    db_session: AsyncSession,
    basic_fund: Fund,
):
    """Les statuts ``accepted``/``rejected`` sont exclus."""
    from datetime import datetime, timezone

    from app.models.application import (
        ApplicationStatus,
        FundApplication,
        TargetType,
    )
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)

    active_app = FundApplication(
        user_id=user.id,
        fund_id=basic_fund.id,
        account_id=user.account_id,
        target_type=TargetType.fund_direct,
        status=ApplicationStatus.draft,
        sections={},
        checklist=[],
    )
    accepted_app = FundApplication(
        user_id=user.id,
        fund_id=basic_fund.id,
        account_id=user.account_id,
        target_type=TargetType.fund_direct,
        status=ApplicationStatus.accepted,
        sections={},
        checklist=[],
    )
    db_session.add_all([active_app, accepted_app])
    await db_session.commit()

    items = await list_active_applications(db_session, user.id)
    assert len(items) == 1
    assert items[0].status == "draft"
    assert items[0].status_label_fr == "Brouillon"
    assert "/applications/" in items[0].deep_link
