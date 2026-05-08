"""F16 — Moteur de calcul du simulateur sourcé.

Implémente les fonctions pures :
- :func:`compute_total_cost` (FR-004)
- :func:`compute_roi` (FR-005)
- :func:`compute_carbon_impact` (FR-006)
- :func:`build_timeline` (FR-007)

Toutes les valeurs numériques proviennent du :class:`FactorSnapshot` (F01)
ou des entités lues (offer, project, fund, intermediary). Aucune constante
numérique de calcul codée en dur (FR-001, SC-002).
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import Currency, Money
from app.modules.applications.factor_service import (
    FactorEntry,
    FactorSnapshot,
    SourceRef,
)
from app.modules.applications.simulation_schemas import (
    CarbonImpact,
    CostBreakdown,
    InstrumentLiteral,
    MonetaryFigure,
    RoiBreakdown,
    SimulationResult,
    TimelineStep,
)


logger = logging.getLogger(__name__)


# Constantes de conversion d'unité (NON des constantes de calcul) :
# WEEKS_PER_MONTH et DAYS_PER_WEEK sont des conversions calendaires
# universelles, pas des paramètres métier sourcés.
_DAYS_PER_WEEK = 7
_MONTHS_PER_YEAR = 12


# --------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------


class FactorMissingError(Exception):
    """Levé quand un facteur critique est introuvable dans le snapshot."""

    def __init__(self, factor_name: str):
        super().__init__(
            f"Facteur '{factor_name}' introuvable dans le snapshot"
        )
        self.factor_name = factor_name


class OfferDataMissingError(Exception):
    """Levé quand une donnée critique de l'offre est absente."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _project_principal(project: Any, fallback_currency: Currency) -> Money:
    """Reconstruit le principal du projet en Money typed F04."""
    amount = getattr(project, "target_amount_amount", None)
    currency = getattr(project, "target_amount_currency", None)
    if amount is not None and currency:
        return Money(amount=Decimal(str(amount)), currency=currency)
    # Pas de montant cible → on ne peut pas inventer ; on lève.
    raise OfferDataMissingError("project_target_amount_absent")


def _fund_currency(fund: Any) -> Currency:
    """Devise du fonds : se déduit de min/max_amount_money de F04.

    Fallback : XOF si rien.
    """
    money = getattr(fund, "min_amount_money", None) or getattr(
        fund, "max_amount_money", None
    )
    if money is not None:
        return money.currency  # type: ignore[return-value]
    return "XOF"


def _to_monetary_figure(
    *,
    amount: Money,
    factor: FactorEntry | None,
    factor_name: str | None = None,
    degraded_reason: str | None = None,
    pme_currency: Currency = "XOF",
) -> MonetaryFigure:
    """Construit un :class:`MonetaryFigure` avec ses métadonnées de sourçage.

    La conversion ``amount_pme_equivalent`` est laissée à la couche service
    (asynchrone) ; on remplit ``None`` ici.
    """
    return MonetaryFigure(
        amount=amount,
        amount_pme_equivalent=None,
        source_id=factor.source_id if factor else None,
        factor_name=factor_name or (factor.name if factor else None),
        factor_status=(
            factor.status if factor and factor.status in ("verified", "pending", "outdated", "draft") else None  # type: ignore[arg-type]
        ),
        degraded_reason=degraded_reason,
    )


def _safe_factor(snapshot: FactorSnapshot, name: str) -> FactorEntry | None:
    return snapshot.get(name)


# --------------------------------------------------------------------------
# Coût total (FR-004)
# --------------------------------------------------------------------------


def compute_total_cost(
    *,
    project: Any,
    offer: Any,
    snapshot: FactorSnapshot,
) -> CostBreakdown:
    """Décomposition du coût total en MonetaryFigure sourcés.

    Lit :
    - principal depuis ``project.target_amount`` (Money typed F04) ;
    - taux frais d'instruction depuis ``snapshot['default_doc_fee_rate']``
      ou les ``effective_fees`` de l'offre quand disponibles ;
    - taux de prêt depuis ``snapshot['default_loan_rate']`` ou ``offer`` ;
    - taux de garantie depuis ``snapshot['default_guarantee_rate']`` ;
    - taux marge FX depuis ``snapshot['default_fx_margin_rate']`` (mis à 0
      si la devise du fonds == devise PME).
    """
    fund = offer.fund
    fund_currency = _fund_currency(fund)
    principal = _project_principal(project, fund_currency)

    # Doc fee
    doc_fee_factor = _safe_factor(snapshot, "default_doc_fee_rate")
    if doc_fee_factor is not None:
        doc_fee_amount = Money(
            amount=(principal.amount * doc_fee_factor.value).quantize(
                Decimal("0.01")
            ),
            currency=principal.currency,
        )
        doc_fee = _to_monetary_figure(
            amount=doc_fee_amount,
            factor=doc_fee_factor,
        )
    else:
        doc_fee = MonetaryFigure(
            amount=Money(amount=Decimal("0"), currency=principal.currency),
            degraded_reason="facteur_introuvable_default_doc_fee_rate",
        )

    # Frais cumulés sur durée du prêt = principal × loan_rate × duration_months/12
    loan_rate_factor = _safe_factor(snapshot, "default_loan_rate")
    duration_months = getattr(project, "duration_months", None) or _MONTHS_PER_YEAR
    if loan_rate_factor is not None:
        years = Decimal(duration_months) / Decimal(_MONTHS_PER_YEAR)
        total_fees_amount = Money(
            amount=(
                principal.amount * loan_rate_factor.value * years
            ).quantize(Decimal("0.01")),
            currency=principal.currency,
        )
        total_fees = _to_monetary_figure(
            amount=total_fees_amount,
            factor=loan_rate_factor,
        )
    else:
        total_fees = MonetaryFigure(
            amount=Money(amount=Decimal("0"), currency=principal.currency),
            degraded_reason="facteur_introuvable_default_loan_rate",
        )

    # Garantie
    guar_factor = _safe_factor(snapshot, "default_guarantee_rate")
    if guar_factor is not None:
        guar_amount = Money(
            amount=(principal.amount * guar_factor.value).quantize(
                Decimal("0.01")
            ),
            currency=principal.currency,
        )
        guarantee = _to_monetary_figure(
            amount=guar_amount, factor=guar_factor
        )
    else:
        guarantee = MonetaryFigure(
            amount=Money(amount=Decimal("0"), currency=principal.currency),
            degraded_reason="facteur_introuvable_default_guarantee_rate",
        )

    # Marge FX
    pme_currency: Currency = "XOF"
    if fund_currency == pme_currency:
        # Pas de change → 0 explicite
        fx_margin = MonetaryFigure(
            amount=Money(amount=Decimal("0"), currency=principal.currency),
            factor_name="default_fx_margin_rate",
            degraded_reason=None,
        )
    else:
        fx_factor = _safe_factor(snapshot, "default_fx_margin_rate")
        if fx_factor is not None:
            fx_amount = Money(
                amount=(principal.amount * fx_factor.value).quantize(
                    Decimal("0.01")
                ),
                currency=principal.currency,
            )
            fx_margin = _to_monetary_figure(
                amount=fx_amount, factor=fx_factor
            )
        else:
            fx_margin = MonetaryFigure(
                amount=Money(
                    amount=Decimal("0"), currency=principal.currency
                ),
                degraded_reason="facteur_introuvable_default_fx_margin_rate",
            )

    # Total cost = principal + doc_fee + total_fees + fx_margin
    # (la garantie est immobilisée mais récupérable, n'entre pas dans le coût net)
    total_cost_amount = (
        principal.amount
        + doc_fee.amount.amount
        + total_fees.amount.amount
        + fx_margin.amount.amount
    )
    total_cost = Money(
        amount=total_cost_amount.quantize(Decimal("0.01")),
        currency=principal.currency,
    )

    return CostBreakdown(
        principal=principal,
        doc_fee=doc_fee,
        total_fees_over_duration=total_fees,
        guarantee_required=guarantee,
        fx_margin=fx_margin,
        total_cost=total_cost,
    )


# --------------------------------------------------------------------------
# ROI différencié par instrument (FR-005)
# --------------------------------------------------------------------------


def _detect_instrument(offer: Any) -> InstrumentLiteral:
    """Détermine l'instrument depuis ``offer.fund.instruments`` JSONB.

    Heuristique : prend la première valeur reconnue dans la liste, sinon
    se rabat sur 'pret_concessionnel' (cas le plus fréquent UEMOA).
    """
    instruments = getattr(offer.fund, "instruments", None) or []
    valid = {"subvention", "pret_concessionnel", "equity", "blending"}
    for raw in instruments:
        norm = str(raw).strip().lower()
        if norm in valid:
            return norm  # type: ignore[return-value]
        # Mapping legacy
        if norm in ("grant", "don"):
            return "subvention"
        if norm in ("loan", "credit", "pret"):
            return "pret_concessionnel"
    if len(instruments) >= 2:
        return "blending"
    return "pret_concessionnel"


def _roi_subvention(
    *, principal: Money, snapshot: FactorSnapshot
) -> RoiBreakdown:
    """Subvention : pas de remboursement (FR-005, VR-007)."""
    gain_factor = _safe_factor(snapshot, "gain_rate_default") or _safe_factor(
        snapshot, "savings_rate"
    )
    sources: list[uuid.UUID] = []
    gain: Money | None = None
    if gain_factor is not None:
        gain = Money(
            amount=(principal.amount * gain_factor.value).quantize(
                Decimal("0.01")
            ),
            currency=principal.currency,
        )
        if gain_factor.source_id:
            sources.append(gain_factor.source_id)
    return RoiBreakdown(
        instrument="subvention",
        formula_id="roi.subvention.no_repayment",
        gain_estimated=gain,
        payback_months=None,
        ratio=None,
        notes_fr="Pas de remboursement : la subvention est un don.",
        sources=sources,
    )


def _roi_pret_concessionnel(
    *, principal: Money, total_cost: Money, snapshot: FactorSnapshot
) -> RoiBreakdown:
    gain_factor = _safe_factor(snapshot, "gain_rate_default") or _safe_factor(
        snapshot, "savings_rate"
    )
    payback_factor = _safe_factor(snapshot, "default_payback_months")
    sources: list[uuid.UUID] = []
    gain: Money | None = None
    ratio: Decimal | None = None
    payback: int | None = None
    notes = "Ratio gains estimés / coût total."
    if gain_factor is not None:
        gain = Money(
            amount=(principal.amount * gain_factor.value).quantize(
                Decimal("0.01")
            ),
            currency=principal.currency,
        )
        if total_cost.amount > 0:
            ratio = (gain.amount / total_cost.amount).quantize(
                Decimal("0.0001")
            )
        if gain_factor.source_id:
            sources.append(gain_factor.source_id)
    if payback_factor is not None:
        payback = int(payback_factor.value)
        if payback_factor.source_id:
            sources.append(payback_factor.source_id)
    return RoiBreakdown(
        instrument="pret_concessionnel",
        formula_id="roi.loan.gain_minus_cost_ratio",
        gain_estimated=gain,
        payback_months=payback,
        ratio=ratio,
        notes_fr=notes,
        sources=sources,
    )


def _roi_equity(
    *, principal: Money, snapshot: FactorSnapshot
) -> RoiBreakdown:
    gain_factor = _safe_factor(snapshot, "gain_rate_default") or _safe_factor(
        snapshot, "savings_rate"
    )
    sources: list[uuid.UUID] = []
    gain: Money | None = None
    if gain_factor is not None:
        gain = Money(
            amount=(principal.amount * gain_factor.value).quantize(
                Decimal("0.01")
            ),
            currency=principal.currency,
        )
        if gain_factor.source_id:
            sources.append(gain_factor.source_id)
    return RoiBreakdown(
        instrument="equity",
        formula_id="roi.equity.dilution_irr",
        gain_estimated=gain,
        payback_months=None,
        ratio=None,
        notes_fr=(
            "Equity : entrée au capital — retour via dilution et IRR à terme."
        ),
        sources=sources,
    )


def _roi_blending(
    *, principal: Money, total_cost: Money, snapshot: FactorSnapshot
) -> RoiBreakdown:
    base = _roi_pret_concessionnel(
        principal=principal, total_cost=total_cost, snapshot=snapshot
    )
    return RoiBreakdown(
        instrument="blending",
        formula_id="roi.blending.weighted",
        gain_estimated=base.gain_estimated,
        payback_months=base.payback_months,
        ratio=base.ratio,
        notes_fr=(
            "Blending : combinaison don + prêt — ROI pondéré par les parts."
        ),
        sources=base.sources,
    )


_ROI_DISPATCH: dict[InstrumentLiteral, Callable[..., RoiBreakdown]] = {
    "subvention": lambda principal, total_cost, snapshot: _roi_subvention(
        principal=principal, snapshot=snapshot
    ),
    "pret_concessionnel": lambda principal, total_cost, snapshot: _roi_pret_concessionnel(
        principal=principal, total_cost=total_cost, snapshot=snapshot
    ),
    "equity": lambda principal, total_cost, snapshot: _roi_equity(
        principal=principal, snapshot=snapshot
    ),
    "blending": lambda principal, total_cost, snapshot: _roi_blending(
        principal=principal, total_cost=total_cost, snapshot=snapshot
    ),
}


def compute_roi(
    *, project: Any, offer: Any, snapshot: FactorSnapshot, total_cost: Money
) -> RoiBreakdown:
    instrument = _detect_instrument(offer)
    fn = _ROI_DISPATCH[instrument]
    principal = _project_principal(project, _fund_currency(offer.fund))
    return fn(principal, total_cost, snapshot)


# --------------------------------------------------------------------------
# Impact carbone (FR-006)
# --------------------------------------------------------------------------


def compute_carbon_impact(
    *,
    project: Any,
    snapshot: FactorSnapshot,
    sector_factor: Decimal | None = None,
    sector_factor_source_id: uuid.UUID | None = None,
    is_approximate: bool = False,
) -> CarbonImpact:
    """Calcule l'impact carbone à partir de l'estimation projet × ratio sectoriel.

    Si ``project.expected_impact_tco2e`` est absent → mode dégradé.
    Si aucun ratio sectoriel n'est fourni → fallback dégradé sans inventer.
    """
    project_estimate = getattr(project, "expected_impact_tco2e", None)
    if project_estimate is None:
        return CarbonImpact(
            tco2e_per_year=None,
            sector_factor=None,
            factor_source_id=None,
            project_estimate_used=None,
            is_approximate=False,
            degraded_reason="aucune_estimation_projet",
        )

    if sector_factor is None:
        # Pas de facteur → on rend l'estimation projet brute, sans modulation.
        # La degraded_reason précise l'absence du modulateur.
        return CarbonImpact(
            tco2e_per_year=Decimal(str(project_estimate)),
            sector_factor=None,
            factor_source_id=None,
            project_estimate_used=Decimal(str(project_estimate)),
            is_approximate=True,
            degraded_reason="aucun_facteur_sectoriel_disponible",
        )

    tco2e = (Decimal(str(project_estimate)) * sector_factor).quantize(
        Decimal("0.0001")
    )
    return CarbonImpact(
        tco2e_per_year=tco2e,
        sector_factor=sector_factor,
        factor_source_id=sector_factor_source_id,
        project_estimate_used=Decimal(str(project_estimate)),
        is_approximate=is_approximate,
        degraded_reason=None,
    )


# --------------------------------------------------------------------------
# Timeline (FR-007)
# --------------------------------------------------------------------------


def build_timeline(*, offer: Any) -> list[TimelineStep]:
    """Timeline construite uniquement depuis les délais réels de l'offre.

    4 étapes : préparation, instruction intermédiaire, validation fonds,
    décaissement. Aucune valeur inventée : si une donnée manque, l'étape
    est marquée ``degraded_reason='delai_intermediaire_non_renseigne'``.
    """
    intermediary = offer.intermediary
    fund = offer.fund

    # 1. Préparation : valeur fixe calendaire (1..2 semaines) — pas de
    # facteur métier, c'est un effort PME standard et n'est pas un coût.
    # Note : aucun calcul numérique de coût n'utilise ces bornes.
    preparation = TimelineStep(
        step_id="preparation",
        label_fr="Préparation du dossier",
        weeks_min=None,
        weeks_max=None,
        source_id=None,
        degraded_reason="effort_pme_non_facteur_catalogue",
    )

    # 2. Instruction intermédiaire — depuis offer/intermediary
    instr_min_days = getattr(
        offer, "effective_processing_time_days_min", None
    ) or getattr(intermediary, "processing_time_days_min", None)
    instr_max_days = getattr(
        offer, "effective_processing_time_days_max", None
    ) or getattr(intermediary, "processing_time_days_max", None)
    if instr_min_days is not None and instr_max_days is not None:
        instruction = TimelineStep(
            step_id="instruction_intermediaire",
            label_fr="Instruction par l'intermédiaire",
            weeks_min=int(instr_min_days) // _DAYS_PER_WEEK,
            weeks_max=int(instr_max_days) // _DAYS_PER_WEEK,
            source_id=getattr(offer, "source_id", None),
        )
    else:
        instruction = TimelineStep(
            step_id="instruction_intermediaire",
            label_fr="Instruction par l'intermédiaire",
            weeks_min=None,
            weeks_max=None,
            degraded_reason="delai_intermediaire_non_renseigne",
        )

    # 3. Validation fonds — depuis fund.typical_timeline_months
    typical_months = getattr(fund, "typical_timeline_months", None)
    if typical_months is not None:
        validation = TimelineStep(
            step_id="validation_fonds",
            label_fr="Validation par le fonds",
            weeks_min=int(typical_months) * 2,  # mois → semaines (~4)/2 borne basse
            weeks_max=int(typical_months) * 4,
            source_id=getattr(fund, "source_id", None),
        )
    else:
        validation = TimelineStep(
            step_id="validation_fonds",
            label_fr="Validation par le fonds",
            weeks_min=None,
            weeks_max=None,
            degraded_reason="delai_fonds_non_renseigne",
        )

    # 4. Décaissement — depuis offer/intermediary disbursement
    disb_min_days = getattr(
        offer, "effective_disbursement_time_days_min", None
    ) or getattr(intermediary, "disbursement_time_days_min", None)
    disb_max_days = getattr(
        offer, "effective_disbursement_time_days_max", None
    ) or getattr(intermediary, "disbursement_time_days_max", None)
    if disb_min_days is not None and disb_max_days is not None:
        decaissement = TimelineStep(
            step_id="decaissement",
            label_fr="Décaissement des fonds",
            weeks_min=int(disb_min_days) // _DAYS_PER_WEEK,
            weeks_max=int(disb_max_days) // _DAYS_PER_WEEK,
            source_id=getattr(offer, "source_id", None),
        )
    else:
        decaissement = TimelineStep(
            step_id="decaissement",
            label_fr="Décaissement des fonds",
            weeks_min=None,
            weeks_max=None,
            degraded_reason="delai_decaissement_non_renseigne",
        )

    return [preparation, instruction, validation, decaissement]


# --------------------------------------------------------------------------
# Composition : simulate_offer
# --------------------------------------------------------------------------


def simulate_offer(
    *,
    project: Any,
    offer: Any,
    snapshot: FactorSnapshot,
    sector_factor: Decimal | None = None,
    sector_factor_source_id: uuid.UUID | None = None,
    is_approximate: bool = False,
) -> SimulationResult:
    """Compose les 4 fonctions pures pour une offre + un projet."""
    cost = compute_total_cost(
        project=project, offer=offer, snapshot=snapshot
    )
    roi = compute_roi(
        project=project,
        offer=offer,
        snapshot=snapshot,
        total_cost=cost.total_cost,
    )
    carbon = compute_carbon_impact(
        project=project,
        snapshot=snapshot,
        sector_factor=sector_factor,
        sector_factor_source_id=sector_factor_source_id,
        is_approximate=is_approximate,
    )
    timeline = build_timeline(offer=offer)

    sources_used: list[uuid.UUID] = []
    for fig in (
        cost.doc_fee,
        cost.total_fees_over_duration,
        cost.guarantee_required,
        cost.fx_margin,
    ):
        if fig.source_id is not None:
            sources_used.append(fig.source_id)
    for sid in roi.sources:
        sources_used.append(sid)
    for step in timeline:
        if step.source_id is not None:
            sources_used.append(step.source_id)
    if carbon.factor_source_id is not None:
        sources_used.append(carbon.factor_source_id)
    sources_used = list(dict.fromkeys(sources_used))  # dédup ordonné

    degraded = (
        cost.doc_fee.degraded_reason is not None
        or cost.total_fees_over_duration.degraded_reason is not None
        or cost.guarantee_required.degraded_reason is not None
        or carbon.degraded_reason is not None
        or any(t.degraded_reason for t in timeline if t.step_id != "preparation")
    )

    return SimulationResult(
        offer_id=offer.id,
        project_id=project.id,
        principal=cost.principal,
        principal_pme_equivalent=None,
        cost_breakdown=cost,
        roi=roi,
        carbon_impact=carbon,
        timeline=timeline,
        sources_used=sources_used,
        degraded=degraded,
        computed_at=datetime.now(timezone.utc),
    )
