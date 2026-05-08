"""F16 — Tests unitaires + intégration du simulateur sourcé multi-offres.

Couvre :
- Schémas Pydantic v2 stricts (validation, dedup, bornes 1..5).
- ``factor_service.load_factors_snapshot`` (frozen, exclusion outdated).
- Fonctions pures ``compute_total_cost``, ``compute_roi``,
  ``compute_carbon_impact``, ``build_timeline`` et ``simulate_offer``.
- Service ``simulate_multi`` (dedup, ranking, dégradation).
- Router ``/api/projects/{id}/simulate-multi`` (200/403/404/422).
- Tool LangChain ``compare_simulations`` (marker SSE F11, erreurs).
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.money import Money
from app.modules.applications.factor_service import (
    FactorEntry,
    FactorSnapshot,
    SourceRef,
    load_factors_snapshot,
)
from app.modules.applications.multi_simulate_service import (
    OfferAccessDeniedError,
    ProjectNotFoundError,
    _rank_offers,
    _total_weeks,
    simulate_multi,
)
from app.modules.applications.simulation_engine import (
    OfferDataMissingError,
    _detect_instrument,
    build_timeline,
    compute_carbon_impact,
    compute_roi,
    compute_total_cost,
    simulate_offer,
)
from app.modules.applications.simulation_schemas import (
    CarbonImpact,
    ComparisonMetadata,
    CostBreakdown,
    DegradedColumn,
    MonetaryFigure,
    MultiSimulateRequest,
    MultiSimulateResponse,
    RoiBreakdown,
    SimulationResult,
    TimelineStep,
)


# =========================================================================
# Helpers — construction d'un snapshot de facteurs
# =========================================================================


SOURCE_ID_DOC = uuid.uuid4()
SOURCE_ID_LOAN = uuid.uuid4()
SOURCE_ID_GUAR = uuid.uuid4()
SOURCE_ID_FX = uuid.uuid4()
SOURCE_ID_PAYBACK = uuid.uuid4()
SOURCE_ID_GAIN = uuid.uuid4()
SOURCE_ID_SECTOR = uuid.uuid4()


def make_snapshot(
    *,
    include: tuple[str, ...] = (
        "default_doc_fee_rate",
        "default_loan_rate",
        "default_guarantee_rate",
        "default_fx_margin_rate",
        "default_payback_months",
        "gain_rate_default",
    ),
    statuses: dict[str, str] | None = None,
) -> FactorSnapshot:
    statuses = statuses or {}
    factor_defs = {
        "default_doc_fee_rate": (Decimal("0.01"), "rate", SOURCE_ID_DOC),
        "default_loan_rate": (Decimal("0.05"), "rate", SOURCE_ID_LOAN),
        "default_guarantee_rate": (
            Decimal("0.10"),
            "rate",
            SOURCE_ID_GUAR,
        ),
        "default_fx_margin_rate": (Decimal("0.02"), "rate", SOURCE_ID_FX),
        "default_payback_months": (
            Decimal("60"),
            "months",
            SOURCE_ID_PAYBACK,
        ),
        "gain_rate_default": (Decimal("0.15"), "rate", SOURCE_ID_GAIN),
    }
    factors: dict[str, FactorEntry] = {}
    sources: dict[uuid.UUID, SourceRef] = {}
    for name in include:
        value, unit, sid = factor_defs[name]
        status = statuses.get(name, "verified")
        factors[name] = FactorEntry(
            name=name,
            value=value,
            unit=unit,
            status=status,
            source_id=sid,
        )
        sources[sid] = SourceRef(
            id=sid,
            title=f"Source mock {name}",
            publisher="mock",
            url=None,
            published_at=date(2024, 1, 1),
            verification_status="verified",
        )
    return FactorSnapshot(
        factors=MappingProxyType(factors),
        sources=MappingProxyType(sources),
    )


def make_project(
    *,
    target_amount: int = 5_000_000,
    currency: str = "XOF",
    duration_months: int = 24,
    expected_impact: Decimal | None = Decimal("12.4"),
    country: str | None = "CI",
) -> MagicMock:
    p = MagicMock()
    p.id = uuid.uuid4()
    p.account_id = uuid.uuid4()
    p.target_amount_amount = Decimal(str(target_amount))
    p.target_amount_currency = currency
    p.duration_months = duration_months
    p.expected_impact_tco2e = expected_impact
    p.location_country = country
    return p


def make_fund(
    *,
    instruments: list[str] | None = None,
    currency: str = "XOF",
    typical_timeline_months: int | None = 6,
    source_id: uuid.UUID | None = None,
) -> MagicMock:
    f = MagicMock()
    f.id = uuid.uuid4()
    f.instruments = instruments or ["pret_concessionnel"]
    f.typical_timeline_months = typical_timeline_months
    f.source_id = source_id or uuid.uuid4()
    f.min_amount_money = Money(amount=Decimal("1000000"), currency=currency)
    f.max_amount_money = Money(
        amount=Decimal("100000000"), currency=currency
    )
    return f


def make_intermediary(
    *,
    processing_min: int | None = 30,
    processing_max: int | None = 60,
    disbursement_min: int | None = 14,
    disbursement_max: int | None = 28,
) -> MagicMock:
    i = MagicMock()
    i.id = uuid.uuid4()
    i.processing_time_days_min = processing_min
    i.processing_time_days_max = processing_max
    i.disbursement_time_days_min = disbursement_min
    i.disbursement_time_days_max = disbursement_max
    return i


def make_offer(
    *,
    fund: MagicMock | None = None,
    intermediary: MagicMock | None = None,
    source_id: uuid.UUID | None = None,
) -> MagicMock:
    o = MagicMock()
    o.id = uuid.uuid4()
    o.fund = fund or make_fund()
    o.intermediary = intermediary or make_intermediary()
    o.source_id = source_id or uuid.uuid4()
    o.effective_processing_time_days_min = None
    o.effective_processing_time_days_max = None
    o.effective_disbursement_time_days_min = None
    o.effective_disbursement_time_days_max = None
    return o


# =========================================================================
# Schémas Pydantic
# =========================================================================


class TestSimulationSchemas:
    def test_multi_request_dedup_preserves_order(self):
        a, b = uuid.uuid4(), uuid.uuid4()
        req = MultiSimulateRequest(offer_ids=[a, a, b, a])
        assert req.offer_ids == [a, b]

    def test_multi_request_max_5(self):
        ids = [uuid.uuid4() for _ in range(6)]
        with pytest.raises(Exception):
            MultiSimulateRequest(offer_ids=ids)

    def test_multi_request_min_1(self):
        with pytest.raises(Exception):
            MultiSimulateRequest(offer_ids=[])

    def test_monetary_figure_extra_forbid(self):
        with pytest.raises(Exception):
            MonetaryFigure(
                amount=Money(amount=Decimal("100"), currency="XOF"),
                unknown_field="x",
            )

    def test_cost_breakdown_total_arithmetic(self):
        cb = CostBreakdown(
            principal=Money(amount=Decimal("1000"), currency="XOF"),
            doc_fee=MonetaryFigure(
                amount=Money(amount=Decimal("10"), currency="XOF"),
                source_id=SOURCE_ID_DOC,
            ),
            total_fees_over_duration=MonetaryFigure(
                amount=Money(amount=Decimal("50"), currency="XOF"),
                source_id=SOURCE_ID_LOAN,
            ),
            guarantee_required=MonetaryFigure(
                amount=Money(amount=Decimal("100"), currency="XOF"),
                source_id=SOURCE_ID_GUAR,
            ),
            fx_margin=MonetaryFigure(
                amount=Money(amount=Decimal("20"), currency="XOF"),
                source_id=SOURCE_ID_FX,
            ),
            total_cost=Money(amount=Decimal("1080"), currency="XOF"),
        )
        # 1000 + 10 + 50 + 20 = 1080 (la garantie n'entre pas)
        assert cb.total_cost.amount == Decimal("1080")

    def test_cost_breakdown_invalid_total_rejected(self):
        with pytest.raises(Exception):
            CostBreakdown(
                principal=Money(amount=Decimal("1000"), currency="XOF"),
                doc_fee=MonetaryFigure(
                    amount=Money(amount=Decimal("10"), currency="XOF"),
                    source_id=SOURCE_ID_DOC,
                ),
                total_fees_over_duration=MonetaryFigure(
                    amount=Money(amount=Decimal("50"), currency="XOF"),
                    source_id=SOURCE_ID_LOAN,
                ),
                guarantee_required=MonetaryFigure(
                    amount=Money(amount=Decimal("100"), currency="XOF"),
                    source_id=SOURCE_ID_GUAR,
                ),
                fx_margin=MonetaryFigure(
                    amount=Money(amount=Decimal("20"), currency="XOF"),
                    source_id=SOURCE_ID_FX,
                ),
                total_cost=Money(
                    amount=Decimal("9999"), currency="XOF"
                ),
            )

    def test_subvention_no_payback(self):
        with pytest.raises(Exception):
            RoiBreakdown(
                instrument="subvention",
                formula_id="x",
                payback_months=12,
                notes_fr="invalide",
            )

    def test_timeline_step_bounds(self):
        with pytest.raises(Exception):
            TimelineStep(
                step_id="preparation",
                label_fr="x",
                weeks_min=10,
                weeks_max=2,
            )


# =========================================================================
# FactorSnapshot
# =========================================================================


class TestFactorSnapshotImmutability:
    def test_snapshot_is_frozen(self):
        snap = make_snapshot()
        with pytest.raises(Exception):
            snap.factors = {}  # type: ignore[misc]

    def test_snapshot_factors_lookup(self):
        snap = make_snapshot()
        assert snap.has("default_loan_rate")
        assert not snap.has("inexistant")
        entry = snap.get("default_loan_rate")
        assert entry is not None
        assert entry.value == Decimal("0.05")

    def test_snapshot_loaded_at_utc(self):
        snap = make_snapshot()
        assert snap.loaded_at.tzinfo is not None
        assert snap.loaded_at.utcoffset().total_seconds() == 0


# =========================================================================
# compute_total_cost (US1)
# =========================================================================


class TestComputeTotalCost:
    def test_nominal_xof(self):
        project = make_project(target_amount=5_000_000, duration_months=24)
        offer = make_offer()
        snap = make_snapshot()
        cost = compute_total_cost(
            project=project, offer=offer, snapshot=snap
        )
        # principal = 5,000,000
        assert cost.principal.amount == Decimal("5000000.00")
        # doc_fee = 5M * 0.01 = 50,000
        assert cost.doc_fee.amount.amount == Decimal("50000.00")
        # total_fees = 5M * 0.05 * (24/12) = 500,000
        assert cost.total_fees_over_duration.amount.amount == Decimal(
            "500000.00"
        )
        # guarantee = 5M * 0.10 = 500,000
        assert cost.guarantee_required.amount.amount == Decimal(
            "500000.00"
        )
        # fund_currency = pme_currency (XOF) → fx = 0
        assert cost.fx_margin.amount.amount == Decimal("0")
        # total_cost = 5M + 50k + 500k + 0 (sans garantie)
        assert cost.total_cost.amount == Decimal("5550000.00")

    def test_source_id_propagated(self):
        project = make_project()
        offer = make_offer()
        snap = make_snapshot()
        cost = compute_total_cost(
            project=project, offer=offer, snapshot=snap
        )
        assert cost.doc_fee.source_id == SOURCE_ID_DOC
        assert cost.total_fees_over_duration.source_id == SOURCE_ID_LOAN
        assert cost.guarantee_required.source_id == SOURCE_ID_GUAR

    def test_factor_status_propagated_pending(self):
        project = make_project()
        offer = make_offer()
        snap = make_snapshot(statuses={"default_doc_fee_rate": "pending"})
        cost = compute_total_cost(
            project=project, offer=offer, snapshot=snap
        )
        assert cost.doc_fee.factor_status == "pending"

    def test_factor_missing_degraded(self):
        project = make_project()
        offer = make_offer()
        # Ne fournit que la garantie : doc_fee + loan + fx absents.
        snap = make_snapshot(include=("default_guarantee_rate",))
        cost = compute_total_cost(
            project=project, offer=offer, snapshot=snap
        )
        assert cost.doc_fee.degraded_reason is not None
        assert cost.total_fees_over_duration.degraded_reason is not None
        # fx_margin reste 0 car devise PME == devise fonds, pas dégradé.
        assert cost.fx_margin.degraded_reason is None

    def test_fx_margin_when_currencies_differ(self):
        project = make_project(currency="EUR")
        # Fund/intermediary en EUR aussi → cohérent avec project_principal
        fund = make_fund(currency="EUR")
        offer = make_offer(fund=fund)
        snap = make_snapshot()
        cost = compute_total_cost(
            project=project, offer=offer, snapshot=snap
        )
        # PME XOF, project en EUR → fx_margin > 0 et sourcé
        assert cost.fx_margin.amount.amount > Decimal("0")
        assert cost.fx_margin.source_id == SOURCE_ID_FX

    def test_project_without_target_amount_raises(self):
        project = make_project()
        project.target_amount_amount = None
        project.target_amount_currency = None
        offer = make_offer()
        snap = make_snapshot()
        with pytest.raises(OfferDataMissingError):
            compute_total_cost(
                project=project, offer=offer, snapshot=snap
            )


# =========================================================================
# compute_roi (US4)
# =========================================================================


class TestComputeRoi:
    def test_subvention_no_payback(self):
        project = make_project()
        fund = make_fund(instruments=["subvention"])
        offer = make_offer(fund=fund)
        snap = make_snapshot()
        roi = compute_roi(
            project=project,
            offer=offer,
            snapshot=snap,
            total_cost=Money(amount=Decimal("5000000"), currency="XOF"),
        )
        assert roi.instrument == "subvention"
        assert roi.payback_months is None
        assert "remboursement" in roi.notes_fr.lower()

    def test_pret_concessionnel_ratio(self):
        project = make_project()
        fund = make_fund(instruments=["pret_concessionnel"])
        offer = make_offer(fund=fund)
        snap = make_snapshot()
        roi = compute_roi(
            project=project,
            offer=offer,
            snapshot=snap,
            total_cost=Money(amount=Decimal("5550000"), currency="XOF"),
        )
        assert roi.instrument == "pret_concessionnel"
        assert roi.payback_months == 60
        assert roi.ratio is not None
        # gain = 5M * 0.15 = 750,000 ; ratio ≈ 750000/5550000 ≈ 0.1351
        assert roi.gain_estimated.amount == Decimal("750000.00")

    def test_equity_no_payback(self):
        project = make_project()
        fund = make_fund(instruments=["equity"])
        offer = make_offer(fund=fund)
        snap = make_snapshot()
        roi = compute_roi(
            project=project,
            offer=offer,
            snapshot=snap,
            total_cost=Money(amount=Decimal("5000000"), currency="XOF"),
        )
        assert roi.instrument == "equity"
        assert roi.payback_months is None

    def test_blending_combines(self):
        project = make_project()
        fund = make_fund(instruments=["blending"])
        offer = make_offer(fund=fund)
        snap = make_snapshot()
        roi = compute_roi(
            project=project,
            offer=offer,
            snapshot=snap,
            total_cost=Money(amount=Decimal("5000000"), currency="XOF"),
        )
        assert roi.instrument == "blending"
        assert "blending" in roi.notes_fr.lower()

    def test_detect_instrument_legacy_alias(self):
        fund = make_fund(instruments=["grant"])
        offer = make_offer(fund=fund)
        assert _detect_instrument(offer) == "subvention"
        fund2 = make_fund(instruments=["loan"])
        offer2 = make_offer(fund=fund2)
        assert _detect_instrument(offer2) == "pret_concessionnel"


# =========================================================================
# compute_carbon_impact (US3)
# =========================================================================


class TestComputeCarbonImpact:
    def test_with_factor_and_estimate(self):
        project = make_project(expected_impact=Decimal("10.0"))
        snap = make_snapshot()
        ci = compute_carbon_impact(
            project=project,
            snapshot=snap,
            sector_factor=Decimal("1.2"),
            sector_factor_source_id=SOURCE_ID_SECTOR,
        )
        assert ci.tco2e_per_year == Decimal("12.0000")
        assert ci.factor_source_id == SOURCE_ID_SECTOR
        assert ci.degraded_reason is None

    def test_no_estimate(self):
        project = make_project(expected_impact=None)
        snap = make_snapshot()
        ci = compute_carbon_impact(project=project, snapshot=snap)
        assert ci.tco2e_per_year is None
        assert ci.degraded_reason == "aucune_estimation_projet"

    def test_no_sector_factor(self):
        project = make_project(expected_impact=Decimal("15.0"))
        snap = make_snapshot()
        ci = compute_carbon_impact(project=project, snapshot=snap)
        # Sans facteur sectoriel : on garde l'estimation projet brute,
        # marqué dégradé.
        assert ci.tco2e_per_year == Decimal("15.0")
        assert ci.degraded_reason == "aucun_facteur_sectoriel_disponible"
        assert ci.is_approximate is True

    def test_is_approximate_propagated(self):
        project = make_project(expected_impact=Decimal("10.0"))
        snap = make_snapshot()
        ci = compute_carbon_impact(
            project=project,
            snapshot=snap,
            sector_factor=Decimal("1.0"),
            sector_factor_source_id=SOURCE_ID_SECTOR,
            is_approximate=True,
        )
        assert ci.is_approximate is True


# =========================================================================
# build_timeline (US3)
# =========================================================================


class TestBuildTimeline:
    def test_4_steps_french(self):
        offer = make_offer()
        timeline = build_timeline(offer=offer)
        assert len(timeline) == 4
        assert [s.step_id for s in timeline] == [
            "preparation",
            "instruction_intermediaire",
            "validation_fonds",
            "decaissement",
        ]
        for step in timeline:
            assert len(step.label_fr) > 0

    def test_weeks_from_intermediary(self):
        intermed = make_intermediary(
            processing_min=14, processing_max=28
        )
        offer = make_offer(intermediary=intermed)
        timeline = build_timeline(offer=offer)
        instr = timeline[1]
        assert instr.weeks_min == 2
        assert instr.weeks_max == 4

    def test_missing_intermediary_data_degraded(self):
        intermed = make_intermediary(
            processing_min=None, processing_max=None
        )
        offer = make_offer(intermediary=intermed)
        timeline = build_timeline(offer=offer)
        instr = timeline[1]
        assert instr.degraded_reason == "delai_intermediaire_non_renseigne"
        assert instr.weeks_min is None

    def test_different_intermediaries_different_timelines(self):
        # Régression FR-007 : 2 offres, 2 timelines distinctes
        i1 = make_intermediary(processing_min=14, processing_max=28)
        i2 = make_intermediary(processing_min=42, processing_max=70)
        o1 = make_offer(intermediary=i1)
        o2 = make_offer(intermediary=i2)
        t1 = build_timeline(offer=o1)
        t2 = build_timeline(offer=o2)
        assert t1[1].weeks_min != t2[1].weeks_min
        assert t1[1].weeks_max != t2[1].weeks_max


# =========================================================================
# simulate_offer (composition)
# =========================================================================


class TestSimulateOffer:
    def test_full_simulation(self):
        project = make_project()
        offer = make_offer()
        snap = make_snapshot()
        result = simulate_offer(
            project=project,
            offer=offer,
            snapshot=snap,
            sector_factor=Decimal("1.0"),
            sector_factor_source_id=SOURCE_ID_SECTOR,
        )
        assert isinstance(result, SimulationResult)
        assert result.offer_id == offer.id
        assert result.project_id == project.id
        assert len(result.timeline) == 4
        assert result.cost_breakdown.total_cost.amount > Decimal("0")
        assert SOURCE_ID_DOC in result.sources_used


# =========================================================================
# multi_simulate_service helpers
# =========================================================================


def _make_simulation_result(
    *, offer_id: uuid.UUID, total_cost: int, weeks_max_total: int
) -> SimulationResult:
    cb = CostBreakdown(
        principal=Money(
            amount=Decimal(str(total_cost - 100)), currency="XOF"
        ),
        doc_fee=MonetaryFigure(
            amount=Money(amount=Decimal("0"), currency="XOF"),
            source_id=SOURCE_ID_DOC,
        ),
        total_fees_over_duration=MonetaryFigure(
            amount=Money(amount=Decimal("100"), currency="XOF"),
            source_id=SOURCE_ID_LOAN,
        ),
        guarantee_required=MonetaryFigure(
            amount=Money(amount=Decimal("0"), currency="XOF"),
            source_id=SOURCE_ID_GUAR,
        ),
        fx_margin=MonetaryFigure(
            amount=Money(amount=Decimal("0"), currency="XOF"),
            source_id=SOURCE_ID_FX,
        ),
        total_cost=Money(amount=Decimal(str(total_cost)), currency="XOF"),
    )
    # 3 étapes non-preparation : on étale weeks_max_total
    per_step = max(1, weeks_max_total // 3)
    timeline = [
        TimelineStep(
            step_id="preparation",
            label_fr="x",
            weeks_min=None,
            weeks_max=None,
            degraded_reason="effort_pme_non_facteur_catalogue",
        ),
        TimelineStep(
            step_id="instruction_intermediaire",
            label_fr="x",
            weeks_min=1,
            weeks_max=per_step,
            source_id=SOURCE_ID_LOAN,
        ),
        TimelineStep(
            step_id="validation_fonds",
            label_fr="x",
            weeks_min=1,
            weeks_max=per_step,
            source_id=SOURCE_ID_LOAN,
        ),
        TimelineStep(
            step_id="decaissement",
            label_fr="x",
            weeks_min=1,
            weeks_max=weeks_max_total - 2 * per_step,
            source_id=SOURCE_ID_LOAN,
        ),
    ]
    return SimulationResult(
        offer_id=offer_id,
        project_id=uuid.uuid4(),
        principal=cb.principal,
        cost_breakdown=cb,
        roi=RoiBreakdown(
            instrument="subvention",
            formula_id="x",
            notes_fr="Pas de remboursement.",
        ),
        carbon_impact=CarbonImpact(),
        timeline=timeline,
        sources_used=[],
        degraded=False,
        computed_at=datetime.now(timezone.utc),
    )


class TestRanking:
    def test_one_offer_no_winner(self):
        oid = uuid.uuid4()
        per_offer = {
            oid: _make_simulation_result(
                offer_id=oid, total_cost=1000, weeks_max_total=10
            )
        }
        cheapest, fastest, degraded = _rank_offers(per_offer)
        assert cheapest is None
        assert fastest is None
        assert degraded == []

    def test_two_offers_cheapest_fastest(self):
        a, b = uuid.uuid4(), uuid.uuid4()
        per_offer = {
            a: _make_simulation_result(
                offer_id=a, total_cost=1000, weeks_max_total=20
            ),
            b: _make_simulation_result(
                offer_id=b, total_cost=2000, weeks_max_total=10
            ),
        }
        cheapest, fastest, degraded = _rank_offers(per_offer)
        assert cheapest == a
        assert fastest == b

    def test_degraded_excluded(self):
        a, b = uuid.uuid4(), uuid.uuid4()
        per_offer: dict = {
            a: _make_simulation_result(
                offer_id=a, total_cost=1000, weeks_max_total=20
            ),
            b: DegradedColumn(
                offer_id=b,
                reason="x",
                computed_at=datetime.now(timezone.utc),
            ),
        }
        cheapest, fastest, degraded = _rank_offers(per_offer)
        # 1 offre nominale → pas de winner
        assert cheapest is None
        assert b in degraded


# =========================================================================
# Tool LangChain compare_simulations
# =========================================================================


class TestCompareSimulationsToolArgs:
    def test_dedup_in_args(self):
        from app.graph.tools.simulation_tools import CompareSimulationsArgs

        a, b = uuid.uuid4(), uuid.uuid4()
        args = CompareSimulationsArgs(
            project_id=uuid.uuid4(), offer_ids=[a, a, b]
        )
        assert args.offer_ids == [a, b]

    def test_max_5(self):
        from app.graph.tools.simulation_tools import CompareSimulationsArgs

        with pytest.raises(Exception):
            CompareSimulationsArgs(
                project_id=uuid.uuid4(),
                offer_ids=[uuid.uuid4() for _ in range(6)],
            )

    def test_extra_forbid(self):
        from app.graph.tools.simulation_tools import CompareSimulationsArgs

        with pytest.raises(Exception):
            CompareSimulationsArgs(
                project_id=uuid.uuid4(),
                offer_ids=[uuid.uuid4()],
                unknown_field=1,
            )


@pytest.mark.asyncio
class TestCompareSimulationsToolBehavior:
    async def test_project_not_found(self):
        from app.graph.tools.simulation_tools import compare_simulations

        with patch(
            "app.graph.tools.simulation_tools.simulate_multi",
            side_effect=ProjectNotFoundError("project_not_found"),
        ), patch(
            "app.graph.tools.simulation_tools.async_session_factory"
        ) as fake_factory:
            session_cm = MagicMock()
            session_cm.__aenter__ = AsyncMock(return_value=MagicMock())
            session_cm.__aexit__ = AsyncMock(return_value=None)
            fake_factory.return_value = session_cm
            out = await compare_simulations.ainvoke(
                {
                    "project_id": str(uuid.uuid4()),
                    "offer_ids": [str(uuid.uuid4())],
                }
            )
            data = json.loads(out)
            assert data["ok"] is False
            assert data["error"] == "project_required"

    async def test_access_denied(self):
        from app.graph.tools.simulation_tools import compare_simulations

        with patch(
            "app.graph.tools.simulation_tools.simulate_multi",
            side_effect=OfferAccessDeniedError("offer_access_denied"),
        ), patch(
            "app.graph.tools.simulation_tools.async_session_factory"
        ) as fake_factory:
            session_cm = MagicMock()
            session_cm.__aenter__ = AsyncMock(return_value=MagicMock())
            session_cm.__aexit__ = AsyncMock(return_value=None)
            fake_factory.return_value = session_cm
            out = await compare_simulations.ainvoke(
                {
                    "project_id": str(uuid.uuid4()),
                    "offer_ids": [str(uuid.uuid4())],
                }
            )
            data = json.loads(out)
            assert data["ok"] is False
            assert data["error"] == "access_denied"

    async def test_success_marker_sse_emitted(self):
        from app.graph.tools.simulation_tools import compare_simulations

        oid = uuid.uuid4()
        pid = uuid.uuid4()
        sim = _make_simulation_result(
            offer_id=oid, total_cost=1000, weeks_max_total=10
        )
        sim = sim.model_copy(update={"project_id": pid})
        meta = ComparisonMetadata(
            cheapest_offer_id=oid,
            fastest_offer_id=oid,
            degraded_offers=[],
            total_offers=1,
        )
        response = MultiSimulateResponse(
            project_id=pid,
            per_offer={oid: sim},
            comparison_metadata=meta,
            factor_snapshot_loaded_at=datetime.now(timezone.utc),
        )
        with patch(
            "app.graph.tools.simulation_tools.simulate_multi",
            new=AsyncMock(return_value=response),
        ), patch(
            "app.graph.tools.simulation_tools.async_session_factory"
        ) as fake_factory:
            session_cm = MagicMock()
            session_cm.__aenter__ = AsyncMock(return_value=MagicMock())
            session_cm.__aexit__ = AsyncMock(return_value=None)
            fake_factory.return_value = session_cm
            out = await compare_simulations.ainvoke(
                {"project_id": str(pid), "offer_ids": [str(oid)]}
            )
        assert "<!--SSE:" in out
        assert "comparison_table" in out
        # JSON court après le marker
        assert '"ok": true' in out
        assert '"compared": 1' in out


# =========================================================================
# Router /api/projects/{id}/simulate-multi (smoke + 422)
# =========================================================================


@pytest.mark.asyncio
class TestSimulateMultiRouter:
    async def test_request_validation_too_many_offers(self, client, override_auth):
        ids = [str(uuid.uuid4()) for _ in range(6)]
        resp = await client.post(
            f"/api/projects/{uuid.uuid4()}/simulate-multi",
            json={"offer_ids": ids},
        )
        assert resp.status_code == 422

    async def test_project_not_found_returns_404(self, client, override_auth):
        # Pas de RLS en SQLite : on patch simulate_multi pour qu'il lève.
        with patch(
            "app.modules.applications.simulate_router.simulate_multi",
            side_effect=ProjectNotFoundError("project_not_found"),
        ):
            resp = await client.post(
                f"/api/projects/{uuid.uuid4()}/simulate-multi",
                json={"offer_ids": [str(uuid.uuid4())]},
            )
            assert resp.status_code == 404

    async def test_offer_access_denied_returns_403(
        self, client, override_auth
    ):
        with patch(
            "app.modules.applications.simulate_router.simulate_multi",
            side_effect=OfferAccessDeniedError("offer_access_denied"),
        ):
            resp = await client.post(
                f"/api/projects/{uuid.uuid4()}/simulate-multi",
                json={"offer_ids": [str(uuid.uuid4())]},
            )
            assert resp.status_code == 403


# =========================================================================
# load_factors_snapshot (BDD réelle SQLite)
# =========================================================================


@pytest.mark.asyncio
class TestSimulateMultiServiceIntegration:
    """Tests d'intégration ``simulate_multi`` avec mocks legers."""

    async def test_validation_too_many(self, db_session):
        with pytest.raises(ValueError, match="max_5_offres"):
            await simulate_multi(
                db_session,
                project_id=uuid.uuid4(),
                offer_ids=[uuid.uuid4() for _ in range(6)],
                account_id=None,
            )

    async def test_validation_zero_after_dedup(self, db_session):
        with pytest.raises(ValueError):
            await simulate_multi(
                db_session,
                project_id=uuid.uuid4(),
                offer_ids=[],
                account_id=None,
            )

    async def test_project_not_found_raises(self, db_session):
        with pytest.raises(ProjectNotFoundError):
            await simulate_multi(
                db_session,
                project_id=uuid.uuid4(),
                offer_ids=[uuid.uuid4()],
                account_id=None,
            )

    async def test_full_pipeline_with_mocks(self):
        """Pipeline simulate_multi avec patchs ciblés sur _load_*."""
        project = make_project()
        offer = make_offer()
        with patch(
            "app.modules.applications.multi_simulate_service._load_project",
            new=AsyncMock(return_value=project),
        ), patch(
            "app.modules.applications.multi_simulate_service._load_offers",
            new=AsyncMock(return_value=[offer]),
        ), patch(
            "app.modules.applications.multi_simulate_service.load_factors_snapshot",
            new=AsyncMock(return_value=make_snapshot()),
        ), patch(
            "app.modules.applications.multi_simulate_service._resolve_sector_factor",
            new=AsyncMock(
                return_value=(Decimal("1.0"), SOURCE_ID_SECTOR, False)
            ),
        ):
            response = await simulate_multi(
                MagicMock(),
                project_id=project.id,
                offer_ids=[offer.id],
                account_id=project.account_id,
            )
        assert response.project_id == project.id
        assert offer.id in response.per_offer
        assert response.comparison_metadata.total_offers == 1

    async def test_dedup_in_service(self):
        project = make_project()
        offer = make_offer()
        with patch(
            "app.modules.applications.multi_simulate_service._load_project",
            new=AsyncMock(return_value=project),
        ), patch(
            "app.modules.applications.multi_simulate_service._load_offers",
            new=AsyncMock(return_value=[offer]),
        ), patch(
            "app.modules.applications.multi_simulate_service.load_factors_snapshot",
            new=AsyncMock(return_value=make_snapshot()),
        ), patch(
            "app.modules.applications.multi_simulate_service._resolve_sector_factor",
            new=AsyncMock(return_value=(None, None, False)),
        ):
            response = await simulate_multi(
                MagicMock(),
                project_id=project.id,
                offer_ids=[offer.id, offer.id, offer.id],
                account_id=project.account_id,
            )
        assert response.comparison_metadata.total_offers == 1

    async def test_offer_inaccessible_raises_access_denied(self):
        project = make_project()
        with patch(
            "app.modules.applications.multi_simulate_service._load_project",
            new=AsyncMock(return_value=project),
        ), patch(
            "app.modules.applications.multi_simulate_service._load_offers",
            new=AsyncMock(return_value=[]),  # 0 offre trouvée
        ):
            with pytest.raises(OfferAccessDeniedError):
                await simulate_multi(
                    MagicMock(),
                    project_id=project.id,
                    offer_ids=[uuid.uuid4()],
                    account_id=project.account_id,
                )

    async def test_degraded_offer_does_not_break_others(self):
        project = make_project()
        offer_ok = make_offer()
        offer_ko = make_offer()
        # Forcer offer_ko à manquer de target_amount → propage degraded
        broken_project = make_project()
        broken_project.id = project.id

        from app.modules.applications import multi_simulate_service as svc
        from app.modules.applications.simulation_engine import (
            OfferDataMissingError,
        )

        # Patch simulate_offer pour faire échouer offer_ko et succès pour ok.
        def fake_simulate(*, project, offer, snapshot, **kw):
            if offer.id == offer_ko.id:
                raise OfferDataMissingError("offer_ko_data_missing")
            return _make_simulation_result(
                offer_id=offer.id, total_cost=1000, weeks_max_total=10
            )

        with patch(
            "app.modules.applications.multi_simulate_service._load_project",
            new=AsyncMock(return_value=project),
        ), patch(
            "app.modules.applications.multi_simulate_service._load_offers",
            new=AsyncMock(return_value=[offer_ok, offer_ko]),
        ), patch(
            "app.modules.applications.multi_simulate_service.load_factors_snapshot",
            new=AsyncMock(return_value=make_snapshot()),
        ), patch(
            "app.modules.applications.multi_simulate_service._resolve_sector_factor",
            new=AsyncMock(return_value=(None, None, False)),
        ), patch(
            "app.modules.applications.multi_simulate_service.simulate_offer",
            side_effect=fake_simulate,
        ):
            response = await simulate_multi(
                MagicMock(),
                project_id=project.id,
                offer_ids=[offer_ok.id, offer_ko.id],
                account_id=project.account_id,
            )
        assert isinstance(response.per_offer[offer_ok.id], SimulationResult)
        assert isinstance(response.per_offer[offer_ko.id], DegradedColumn)
        assert offer_ko.id in response.comparison_metadata.degraded_offers


@pytest.mark.asyncio
class TestLoadFactorsSnapshotDb:
    async def test_returns_empty_when_no_factors(self, db_session):
        snap = await load_factors_snapshot(db_session)
        assert isinstance(snap, FactorSnapshot)
        assert len(snap.factors) == 0

    async def test_loads_seeded_factors(self, db_session):
        from app.models.simulation_factor import SimulationFactor
        from tests.conftest import make_pme_user

        # Crée un user PME + un facteur 'pending' sans source (autorisé en DB).
        user = await make_pme_user(db_session)
        sf = SimulationFactor(
            code="default_loan_rate",
            label="x",
            value=Decimal("0.05"),
            unit="rate",
            scope="UEMOA",
            source_id=None,
            status="pending",
            created_by_user_id=user.id,
        )
        db_session.add(sf)
        await db_session.flush()

        snap = await load_factors_snapshot(db_session)
        assert "default_loan_rate" in snap.factors
        assert snap.factors["default_loan_rate"].status == "pending"
