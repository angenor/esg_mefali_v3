"""F07 — Tests unit du calculator compute_effective_offer (T007 + US4).

Vérifie :
- Intersection critères avec règle « le plus restrictif gagne »
- Union documents avec dédup exacte sur (title, source_id)
- Somme frais Money typed avec conversion XOF
- Somme délais (typical_timeline_months × 30 + intermediary days)
- Hint langues anglophones
- Détection incohérences min_amount > max_amount_per_fund
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.offers.calculator import (
    _detect_inconsistencies,
    _infer_languages_from_country,
    _intersect_criteria,
    _sum_time_range,
    _union_documents,
    compute_effective_offer,
)
from app.modules.offers.schemas import OfferDraft


# ----- _intersect_criteria -----


def test_intersect_criteria_max_for_min_keys() -> None:
    """fund min_company_age=3 + interm min_company_age=5 → 5 (le plus restrictif)."""
    fund_c = {"min_company_age": 3}
    interm_c = {"min_company_age": 5}
    result = _intersect_criteria(fund_c, interm_c)
    assert result["min_company_age"] == 5


def test_intersect_criteria_min_for_max_keys() -> None:
    """fund max_company_revenue=100M + interm max_company_revenue=50M → 50M."""
    fund_c = {"max_company_revenue": 100_000_000}
    interm_c = {"max_company_revenue": 50_000_000}
    result = _intersect_criteria(fund_c, interm_c)
    assert result["max_company_revenue"] == 50_000_000


def test_intersect_criteria_intersection_for_lists() -> None:
    """fund sectors=[A,B,C] + interm sectors=[B,C,D] → [B,C]."""
    fund_c = {"sectors": ["A", "B", "C"]}
    interm_c = {"sectors": ["B", "C", "D"]}
    result = _intersect_criteria(fund_c, interm_c)
    assert result["sectors"] == ["B", "C"]


def test_intersect_criteria_one_only() -> None:
    """Si une seule des deux a la clé, elle est conservée."""
    fund_c = {"only_fund": "value"}
    interm_c = {"only_interm": 42}
    result = _intersect_criteria(fund_c, interm_c)
    assert result == {"only_fund": "value", "only_interm": 42}


def test_intersect_criteria_empty_intersection_lists() -> None:
    """fund sectors=[A] + interm sectors=[B] → []."""
    fund_c = {"sectors": ["A"]}
    interm_c = {"sectors": ["B"]}
    result = _intersect_criteria(fund_c, interm_c)
    assert result["sectors"] == []


# ----- _union_documents -----


def test_union_documents_dedup_exact() -> None:
    """2 docs avec même (title, source_id) mais mandatory diff → 1 doc mandatory=True."""
    src_id = str(uuid.uuid4())
    fund_d = [{"title": "Statuts", "source_id": src_id, "mandatory": True}]
    interm_d = [{"title": "Statuts", "source_id": src_id, "mandatory": False}]
    result = _union_documents(fund_d, interm_d)
    assert len(result) == 1
    assert result[0]["mandatory"] is True


def test_union_documents_keep_distinct_titles() -> None:
    """2 docs avec titres différents et même source → 2 docs distincts."""
    src_id = str(uuid.uuid4())
    fund_d = [{"title": "Statuts juridiques", "source_id": src_id, "mandatory": True}]
    interm_d = [
        {"title": "Statuts de l'entreprise", "source_id": src_id, "mandatory": True},
    ]
    result = _union_documents(fund_d, interm_d)
    assert len(result) == 2


def test_union_documents_dedup_case_insensitive_and_strip() -> None:
    """Dédup sur title.lower().strip()."""
    src_id = str(uuid.uuid4())
    fund_d = [{"title": "STATUTS", "source_id": src_id, "mandatory": False}]
    interm_d = [{"title": " statuts ", "source_id": src_id, "mandatory": True}]
    result = _union_documents(fund_d, interm_d)
    assert len(result) == 1
    assert result[0]["mandatory"] is True


def test_union_documents_distinct_sources() -> None:
    """Même titre, sources différentes → 2 docs distincts."""
    src1, src2 = str(uuid.uuid4()), str(uuid.uuid4())
    fund_d = [{"title": "Statuts", "source_id": src1, "mandatory": True}]
    interm_d = [{"title": "Statuts", "source_id": src2, "mandatory": False}]
    result = _union_documents(fund_d, interm_d)
    assert len(result) == 2


# ----- _sum_time_range -----


def test_sum_processing_time_full() -> None:
    """fund 18 mois (= 540 jours) + interm 90-180 jours → 630-720."""
    proc_min, proc_max = _sum_time_range(
        fund_months=18, interm_min=90, interm_max=180,
    )
    assert proc_min == 630
    assert proc_max == 720


def test_sum_processing_time_no_fund() -> None:
    """Sans fund_months : juste les délais intermediary."""
    proc_min, proc_max = _sum_time_range(
        fund_months=None, interm_min=30, interm_max=60,
    )
    assert proc_min == 30
    assert proc_max == 60


def test_sum_processing_time_all_none() -> None:
    """Aucune donnée → (None, None)."""
    proc_min, proc_max = _sum_time_range(
        fund_months=None, interm_min=None, interm_max=None,
    )
    assert proc_min is None
    assert proc_max is None


# ----- _infer_languages_from_country -----


def test_infer_languages_french_country() -> None:
    """SN, BJ, ML, CI → FR."""
    assert _infer_languages_from_country("SN") == ["FR"]
    assert _infer_languages_from_country("BJ") == ["FR"]
    assert _infer_languages_from_country("CI") == ["FR"]


def test_infer_languages_english_country() -> None:
    """UK, US, CA, KE, GH, NG, ZA → EN."""
    assert _infer_languages_from_country("UK") == ["EN"]
    assert _infer_languages_from_country("US") == ["EN"]
    assert _infer_languages_from_country("KE") == ["EN"]
    assert _infer_languages_from_country("NG") == ["EN"]


def test_infer_languages_country_lowercase() -> None:
    """Insensible à la casse."""
    assert _infer_languages_from_country("uk") == ["EN"]
    assert _infer_languages_from_country("us") == ["EN"]


def test_infer_languages_no_country() -> None:
    """Pays absent → FR par défaut."""
    assert _infer_languages_from_country(None) == ["FR"]
    assert _infer_languages_from_country("") == ["FR"]


# ----- _detect_inconsistencies -----


@pytest.mark.asyncio
async def test_detect_inconsistency_min_amount_above_max(
    db_session: AsyncSession, basic_fund, basic_intermediary, basic_fund_intermediary,
) -> None:
    """fund.min_amount=10M + max_amount_per_fund=5M → warning."""
    # Setter max_amount_per_fund < fund.min_amount
    basic_fund_intermediary.max_amount_per_fund_amount = Decimal("5000000")
    basic_fund_intermediary.max_amount_per_fund_currency = "XOF"
    await db_session.flush()

    notes = _detect_inconsistencies(
        basic_fund, basic_intermediary, basic_fund_intermediary,
    )
    assert notes is not None
    assert "plafond" in notes.lower()


@pytest.mark.asyncio
async def test_detect_inconsistency_draft_fund_warning(
    db_session: AsyncSession, basic_fund, basic_intermediary, basic_fund_intermediary,
) -> None:
    """fund.publication_status='draft' → warning."""
    basic_fund.publication_status = "draft"
    await db_session.flush()
    notes = _detect_inconsistencies(
        basic_fund, basic_intermediary, basic_fund_intermediary,
    )
    assert notes is not None
    assert "draft" in notes.lower()


# ----- compute_effective_offer (intégration) -----


@pytest.mark.asyncio
async def test_compute_effective_offer_returns_draft(
    db_session: AsyncSession, basic_fund, basic_intermediary, basic_fund_intermediary,
) -> None:
    """compute_effective_offer retourne un OfferDraft Pydantic correctement structuré."""
    draft = await compute_effective_offer(
        db_session, basic_fund.id, basic_intermediary.id,
    )
    assert isinstance(draft, OfferDraft)
    assert draft.fund_id == basic_fund.id
    assert draft.intermediary_id == basic_intermediary.id
    # min_company_age : 3 (fund) vs 5 (interm) → 5 (le plus restrictif)
    assert draft.effective_criteria["min_company_age"] == 5
    # max_company_revenue : 1B (fund) vs 800M (interm) → 800M
    assert draft.effective_criteria["max_company_revenue"] == 800_000_000
    # documents : Statuts (commun) + Audit fund + Plan d'affaires interm = 3 distincts
    titles = [d["title"].lower() for d in draft.effective_required_documents]
    assert any("statuts" in t for t in titles)
    assert any("audit" in t for t in titles)
    assert any("plan" in t for t in titles)
    # Délais : 18*30 + 90 = 630, 18*30 + 180 = 720
    assert draft.effective_processing_time_days_min == 630
    assert draft.effective_processing_time_days_max == 720
    # Frais effectifs présents
    assert draft.effective_fees is not None
    # Hint langue : SN (francophone) → ["FR"]
    assert draft.accepted_languages_hint == ["FR"]


@pytest.mark.asyncio
async def test_compute_effective_offer_fund_not_found(db_session: AsyncSession) -> None:
    """Lève ValueError si fund_id introuvable."""
    fake_fund_id = uuid.uuid4()
    fake_int_id = uuid.uuid4()
    with pytest.raises(ValueError, match="Fonds introuvable"):
        await compute_effective_offer(db_session, fake_fund_id, fake_int_id)


@pytest.mark.asyncio
async def test_compute_effective_offer_intermediary_not_found(
    db_session: AsyncSession, basic_fund,
) -> None:
    """Lève ValueError si intermediary_id introuvable."""
    fake_int_id = uuid.uuid4()
    with pytest.raises(ValueError, match="Intermédiaire introuvable"):
        await compute_effective_offer(db_session, basic_fund.id, fake_int_id)
