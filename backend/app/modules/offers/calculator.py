"""Calculator F07 — compute_effective_offer (intersection critères, union docs).

Calcule l'`OfferDraft` (résumé d'une offre) à partir d'un couple
(Fund, Intermediary) en appliquant les règles métier suivantes :

- **Intersection critères** : le plus restrictif gagne (max sur ``min_*``,
  min sur ``max_*``, intersection sur listes).
- **Union documents** : déduplication exacte sur ``(title.lower().strip(),
  source_id)`` ; ``mandatory=true`` écrase ``mandatory=false`` sur les
  doublons résiduels.
- **Somme frais** : Money typed (conversion XOF si devises différentes).
- **Somme délais** : ``effective_min = fund_min + intermediary_min`` etc.
- **Hint langues** : ``["EN"]`` si pays anglophone détecté, sinon ``["FR"]``.
- **Détection incohérences** : ``min_amount > max_amount_per_fund`` →
  warning dans ``notes`` (non bloquant).

Le calculator est **stateless** : il ne persiste rien et ne dépend que de
la session SQLAlchemy pour les conversions de devises (F04).
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import Money
from app.models.financing import Fund, FundIntermediary, Intermediary
from app.modules.offers.schemas import OfferDraft

logger = logging.getLogger(__name__)


# Pays anglophones ou non-francophones avec représentation forte (Q5)
ENGLISH_SPEAKING_COUNTRIES: frozenset[str] = frozenset({
    "UK", "US", "USA", "CA", "KE", "GH", "NG", "ZA",
    "DE", "JP", "AU", "NZ", "IE", "GB",
})


# Clés numériques traitées comme « minimum » (le plus grand gagne)
MIN_KEYS: frozenset[str] = frozenset({
    "min_company_age",
    "min_company_age_years",
    "min_revenue",
    "min_revenue_xof",
    "min_amount",
    "min_amount_xof",
    "min_employees",
    "min_esg_score",
})

# Clés numériques traitées comme « maximum » (le plus petit gagne)
MAX_KEYS: frozenset[str] = frozenset({
    "max_company_age",
    "max_company_revenue",
    "max_revenue",
    "max_revenue_xof",
    "max_amount",
    "max_amount_xof",
    "max_employees",
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def compute_effective_offer(
    session: AsyncSession,
    fund_id: UUID,
    intermediary_id: UUID,
) -> OfferDraft:
    """Calcule un OfferDraft pour le couple (fund_id, intermediary_id).

    Lève ``ValueError`` si le fonds ou l'intermédiaire n'existe pas.
    Retourne toujours un draft (jamais persisté). L'admin peut ensuite
    éditer puis créer via ``POST /api/admin/offers``.
    """
    fund = await session.get(Fund, fund_id)
    if fund is None:
        raise ValueError(f"Fonds introuvable : {fund_id}")
    intermediary = await session.get(Intermediary, intermediary_id)
    if intermediary is None:
        raise ValueError(f"Intermédiaire introuvable : {intermediary_id}")

    # FundIntermediary (peut être absent pour le couple DIRECT)
    fi_result = await session.execute(
        select(FundIntermediary).where(
            FundIntermediary.fund_id == fund_id,
            FundIntermediary.intermediary_id == intermediary_id,
        )
    )
    fund_intermediary = fi_result.scalar_one_or_none()

    # Calculs
    eff_criteria = _intersect_criteria(
        fund.eligibility_criteria or {},
        intermediary.eligibility_for_sme or {},
    )
    eff_docs = _union_documents(
        fund.required_documents or [],
        intermediary.required_documents or [],
    )
    eff_fees = await _combine_fees(
        session, fund=fund, intermediary=intermediary,
    )
    proc_min, proc_max = _sum_time_range(
        fund_months=fund.typical_timeline_months,
        interm_min=intermediary.processing_time_days_min,
        interm_max=intermediary.processing_time_days_max,
    )
    disb_min, disb_max = _sum_time_range(
        fund_months=None,  # pas de timeline décaissement côté fund
        interm_min=intermediary.disbursement_time_days_min,
        interm_max=intermediary.disbursement_time_days_max,
    )
    languages_hint = _infer_languages_from_country(intermediary.country)
    notes = _detect_inconsistencies(fund, intermediary, fund_intermediary)

    # Nom auto-généré
    name = f"{fund.name} via {intermediary.name}"[:200]

    # Source suggérée : accreditation_source_id de fund_intermediary si présent,
    # sinon source_id de l'intermédiaire, sinon source_id du fonds.
    suggested_source_id = (
        (fund_intermediary.accreditation_source_id if fund_intermediary else None)
        or intermediary.source_id
        or fund.source_id
    )

    # Target sector : par défaut = secteurs du fonds (admin pourra restreindre)
    target_sector = list(fund.sectors_eligible) if fund.sectors_eligible else None

    return OfferDraft(
        fund_id=fund_id,
        intermediary_id=intermediary_id,
        name=name,
        target_sector=target_sector,
        effective_criteria=eff_criteria,
        effective_required_documents=eff_docs,
        effective_fees=eff_fees,
        effective_processing_time_days_min=proc_min,
        effective_processing_time_days_max=proc_max,
        effective_disbursement_time_days_min=disb_min,
        effective_disbursement_time_days_max=disb_max,
        accepted_languages_hint=languages_hint,
        notes=notes,
        suggested_source_id=suggested_source_id,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _intersect_criteria(
    fund_criteria: dict[str, Any],
    interm_criteria: dict[str, Any],
) -> dict[str, Any]:
    """Intersection critères avec règle « le plus restrictif gagne ».

    - Sur clés ``min_*`` : prendre le max (le plus restrictif).
    - Sur clés ``max_*`` : prendre le min (le plus restrictif).
    - Sur listes : intersection (éléments présents dans les deux).
    - Sur autres types : valeur fund par défaut, sinon intermediary.
    """
    result: dict[str, Any] = {}
    all_keys = set(fund_criteria.keys()) | set(interm_criteria.keys())

    for key in sorted(all_keys):  # tri stable pour déterminisme
        fund_val = fund_criteria.get(key)
        interm_val = interm_criteria.get(key)

        if fund_val is None:
            result[key] = interm_val
            continue
        if interm_val is None:
            result[key] = fund_val
            continue

        # Listes → intersection
        if isinstance(fund_val, list) and isinstance(interm_val, list):
            # Conserver l'ordre du fund pour stabilité
            interm_set = set(interm_val)
            result[key] = [v for v in fund_val if v in interm_set]
            continue

        # Numériques avec règles min/max
        if _is_numeric(fund_val) and _is_numeric(interm_val):
            if key in MIN_KEYS:
                result[key] = max(fund_val, interm_val)
            elif key in MAX_KEYS:
                result[key] = min(fund_val, interm_val)
            else:
                # Numérique sans règle explicite → fund par défaut
                result[key] = fund_val
            continue

        # Autres types : fund par défaut
        result[key] = fund_val

    return result


def _is_numeric(v: Any) -> bool:
    """True pour int / float / Decimal (mais pas bool)."""
    if isinstance(v, bool):
        return False
    return isinstance(v, (int, float, Decimal))


def _union_documents(
    fund_docs: list[dict[str, Any]],
    interm_docs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Union des documents requis avec déduplication exacte.

    Clé de dédup : ``(title.lower().strip(), str(source_id))``.
    Sur les doublons : ``mandatory=true`` écrase ``mandatory=false``.
    """
    deduped: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()

    def _key(doc: dict[str, Any]) -> tuple[str, str]:
        title = str(doc.get("title", "")).lower().strip()
        sid = str(doc.get("source_id") or "")
        return (title, sid)

    for doc_list in (fund_docs, interm_docs):
        for doc in doc_list:
            if not isinstance(doc, dict):
                continue
            k = _key(doc)
            if k in deduped:
                # Doublon : conserver mandatory=true si présent
                existing = deduped[k]
                if doc.get("mandatory") and not existing.get("mandatory"):
                    deduped[k] = {**existing, "mandatory": True}
            else:
                deduped[k] = dict(doc)

    return list(deduped.values())


async def _combine_fees(
    session: AsyncSession,
    *,
    fund: Fund,
    intermediary: Intermediary,
) -> dict[str, Any]:
    """Somme cumulée des frais Money typed (conversion XOF si nécessaire).

    Format de retour ::

        {
          "total_min": {"amount": "...", "currency": "XOF"},
          "total_max": {"amount": "...", "currency": "XOF"},
          "breakdown": [
            {"label": "Frais intermédiaire (doc fee)",
             "amount": Money, "source": "intermediary"},
            ...
          ]
        }
    """
    breakdown: list[dict[str, Any]] = []
    total_min = Decimal("0")
    total_max = Decimal("0")

    fees_struct = (intermediary.fees_structured or {}) if intermediary else {}

    # 1. doc_fee_amount intermediary (Money typed)
    doc_fee = fees_struct.get("doc_fee_amount")
    if isinstance(doc_fee, dict):
        try:
            money = Money(
                amount=Decimal(str(doc_fee.get("amount", 0))),
                currency=doc_fee.get("currency", "XOF"),
            )
            money_xof = await _to_xof(session, money)
            breakdown.append({
                "label": "Frais de dossier intermédiaire",
                "amount": str(money_xof.amount),
                "currency": money_xof.currency,
                "source": "intermediary",
            })
            total_min += money_xof.amount
            total_max += money_xof.amount
        except Exception:  # noqa: BLE001
            logger.warning("doc_fee_amount invalide pour intermediary %s", intermediary.id)

    # 2. fee_rate_min/max — appliqué sur fund.max_amount (estimation cap)
    rate_min = fees_struct.get("fee_rate_min")
    rate_max = fees_struct.get("fee_rate_max")
    fund_amount_money = fund.max_amount_money or fund.min_amount_money
    if (rate_min is not None or rate_max is not None) and fund_amount_money is not None:
        amount_xof = await _to_xof(session, fund_amount_money)
        try:
            if rate_min is not None:
                rate_min_dec = Decimal(str(rate_min))
                fee_min = amount_xof.amount * rate_min_dec
                total_min += fee_min
                breakdown.append({
                    "label": f"Taux intermédiaire ({rate_min_dec * 100:.2f}%)",
                    "amount": str(fee_min.quantize(Decimal('0.01'))),
                    "currency": "XOF",
                    "source": "intermediary",
                })
            if rate_max is not None:
                rate_max_dec = Decimal(str(rate_max))
                fee_max = amount_xof.amount * rate_max_dec
                # On remplace total_max par cette valeur si > total_min
                # (les rates min/max représentent une fourchette)
                if rate_min is None or rate_max_dec > Decimal(str(rate_min)):
                    # Différentiel : ajouter (max - déjà compté)
                    if rate_min is not None:
                        delta = (rate_max_dec - Decimal(str(rate_min))) * amount_xof.amount
                        total_max = total_max + delta
                    else:
                        total_max = total_min + fee_max
                    breakdown.append({
                        "label": f"Taux max intermédiaire ({rate_max_dec * 100:.2f}%)",
                        "amount": str(fee_max.quantize(Decimal('0.01'))),
                        "currency": "XOF",
                        "source": "intermediary",
                    })
        except Exception:  # noqa: BLE001
            logger.warning("fee_rate invalide pour intermediary %s", intermediary.id)

    # 3. Frais fond (legacy) : extraire depuis fund.eligibility_criteria si présent
    fund_fee_rate = (fund.eligibility_criteria or {}).get("fee_rate")
    if fund_fee_rate is not None and fund_amount_money is not None:
        try:
            amount_xof = await _to_xof(session, fund_amount_money)
            fee_rate_dec = Decimal(str(fund_fee_rate))
            fee_amount = amount_xof.amount * fee_rate_dec
            total_min += fee_amount
            total_max += fee_amount
            breakdown.append({
                "label": f"Frais fonds ({fee_rate_dec * 100:.2f}%)",
                "amount": str(fee_amount.quantize(Decimal('0.01'))),
                "currency": "XOF",
                "source": "fund",
            })
        except Exception:  # noqa: BLE001
            logger.warning("fee_rate fund invalide pour fund %s", fund.id)

    # Si total_max == 0 mais total_min > 0 → max == min (fee_rate unique)
    if total_max == 0 and total_min > 0:
        total_max = total_min

    return {
        "total_min": {
            "amount": str(total_min.quantize(Decimal("0.01"))),
            "currency": "XOF",
        } if total_min > 0 else None,
        "total_max": {
            "amount": str(total_max.quantize(Decimal("0.01"))),
            "currency": "XOF",
        } if total_max > 0 else None,
        "breakdown": breakdown,
    }


async def _to_xof(session: AsyncSession, money: Money) -> Money:
    """Convertit un Money vers XOF si nécessaire. Fallback : retourne tel quel."""
    if money.currency == "XOF":
        return money
    try:
        from app.modules.currency import service as currency_service
        return await currency_service.convert(money, "XOF", session)
    except Exception:  # noqa: BLE001
        logger.warning(
            "Conversion %s → XOF échouée pour %s, fallback identité",
            money.currency, money.amount,
        )
        return money


def _sum_time_range(
    *,
    fund_months: int | None,
    interm_min: int | None,
    interm_max: int | None,
) -> tuple[int | None, int | None]:
    """Somme des délais : fund (en mois × 30) + intermediary (en jours).

    Retourne ``(min, max)``. None si aucune donnée disponible.
    """
    fund_days = fund_months * 30 if fund_months is not None else None

    if fund_days is None and interm_min is None and interm_max is None:
        return None, None

    fund_days = fund_days or 0
    i_min = interm_min if interm_min is not None else (interm_max or 0)
    i_max = interm_max if interm_max is not None else (interm_min or 0)

    return fund_days + i_min, fund_days + i_max


def _infer_languages_from_country(country: str | None) -> list[str]:
    """Infère les langues acceptées depuis le pays de l'intermédiaire.

    Pays anglophones → ``["EN"]``, sinon → ``["FR"]``.
    """
    if not country:
        return ["FR"]
    code = country.upper().strip()
    if code in ENGLISH_SPEAKING_COUNTRIES:
        return ["EN"]
    return ["FR"]


def _detect_inconsistencies(
    fund: Fund,
    intermediary: Intermediary,
    fund_intermediary: FundIntermediary | None,
) -> str | None:
    """Détecte incohérences et retourne un texte de warning (ou None).

    Cas couverts :
    - ``fund.min_amount > fund_intermediary.max_amount_per_fund``
    - ``fund.publication_status='draft'`` ou ``intermediary.publication_status='draft'``
    """
    warnings: list[str] = []

    # 1. Incohérence cap intermédiaire vs min fonds
    if fund_intermediary is not None:
        max_per_fund = fund_intermediary.max_amount_per_fund_money
        fund_min = fund.min_amount_money
        if max_per_fund is not None and fund_min is not None:
            try:
                # Comparaison sur même devise (XOF par défaut)
                if max_per_fund.currency == fund_min.currency:
                    if max_per_fund.amount < fund_min.amount:
                        warnings.append(
                            f"Avertissement : le plafond de l'intermédiaire "
                            f"({max_per_fund.amount} {max_per_fund.currency}) est inférieur "
                            f"au minimum du fonds ({fund_min.amount} {fund_min.currency}). "
                            f"Vérifier l'éligibilité réelle."
                        )
            except Exception:  # noqa: BLE001
                pass

    # 2. Statuts draft
    if fund.publication_status == "draft":
        warnings.append(
            "Attention : le fonds est en draft, l'offre ne pourra pas être publiée "
            "tant qu'il n'est pas publié."
        )
    if intermediary.publication_status == "draft":
        warnings.append(
            "Attention : l'intermédiaire est en draft, l'offre ne pourra pas être publiée "
            "tant qu'il n'est pas publié."
        )

    return "\n".join(warnings) if warnings else None
