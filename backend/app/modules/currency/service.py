"""F04 — Service de conversion Money (peg FCFA-EUR + table exchange_rates).

Algorithme :
1. Si paire (XOF, EUR) ou (EUR, XOF) → peg fixe ``FCFA_EUR_PEG``, sans HTTP.
2. Sinon, lecture directe table ``exchange_rates`` (fallback ascendant
   sur ``as_of`` si pas d'entrée pour la date demandée).
3. Sinon, pivot USD systématique : convert(base→USD) puis (USD→quote).
4. Sinon, lever :class:`ConversionPathUnavailableError`.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import FCFA_EUR_PEG
from app.core.money import Currency, Money
from app.models.exchange_rate import ExchangeRate
from app.modules.currency.exceptions import (
    ConversionPathUnavailableError,
    NoRateAvailableError,
)


logger = logging.getLogger(__name__)


# Précision pour la division inverse (cohérent avec Numeric(20, 10) en DB)
_DIVISION_PRECISION = Decimal("0.0000000001")


def _is_peg_pair(base: str, quote: str) -> bool:
    return (base, quote) in {("XOF", "EUR"), ("EUR", "XOF")}


def _convert_peg(money: Money, target: Currency) -> Money:
    """Convertit FCFA↔EUR via le peg fixe ``FCFA_EUR_PEG`` (655.957)."""
    if money.currency == "XOF" and target == "EUR":
        # 1 EUR = 655.957 XOF → 1 XOF = 1/655.957 EUR
        return Money(amount=(money.amount / FCFA_EUR_PEG), currency="EUR")
    if money.currency == "EUR" and target == "XOF":
        return Money(amount=(money.amount * FCFA_EUR_PEG), currency="XOF")
    raise ValueError(f"Not a peg pair: {money.currency}->{target}")


async def get_rate(
    session: AsyncSession,
    base: str,
    quote: str,
    on_date: date | None = None,
) -> Decimal:
    """Retourne le taux ``base→quote`` à une date donnée, fallback ascendant.

    Lève :class:`NoRateAvailableError` si aucun taux n'est trouvé.
    """
    if base == quote:
        return Decimal("1")
    on_date = on_date or date.today()
    result = await session.execute(
        select(ExchangeRate.rate)
        .where(
            ExchangeRate.base_currency == base,
            ExchangeRate.quote_currency == quote,
            ExchangeRate.as_of <= on_date,
        )
        .order_by(desc(ExchangeRate.as_of))
        .limit(1),
    )
    rate = result.scalar_one_or_none()
    if rate is None:
        raise NoRateAvailableError(base, quote)
    return Decimal(str(rate))


async def _try_direct(
    session: AsyncSession,
    base: str,
    quote: str,
    on_date: date | None = None,
) -> Decimal | None:
    """Tente de récupérer un taux direct ; retourne None si pas trouvé."""
    try:
        return await get_rate(session, base, quote, on_date=on_date)
    except NoRateAvailableError:
        return None


async def convert(
    money: Money,
    target: Currency,
    session: AsyncSession,
    on_date: date | None = None,
) -> Money:
    """Convertit un Money vers ``target`` (peg / direct / pivot USD).

    Le résultat est arrondi à 2 décimales (via la validation Pydantic du
    type :class:`Money`).
    """
    if money.currency == target:
        return money

    # 1. Peg fixe (sans HTTP, sans BDD).
    if _is_peg_pair(money.currency, target):
        return _convert_peg(money, target)

    # 2. Direct table.
    direct = await _try_direct(session, money.currency, target, on_date=on_date)
    if direct is not None:
        return Money(amount=(money.amount * direct), currency=target)

    # 3. Pivot USD systématique.
    if money.currency != "USD" and target != "USD":
        to_usd = await _try_direct(session, money.currency, "USD", on_date=on_date)
        from_usd = await _try_direct(session, "USD", target, on_date=on_date)
        # Cas particuliers : peg peut intervenir dans le pivot
        if to_usd is None and money.currency in ("XOF", "EUR"):
            # Conversion via peg puis USD
            try:
                pivot = _convert_peg(money, "EUR" if money.currency == "XOF" else "XOF")
                pivot_to_usd = await _try_direct(
                    session, pivot.currency, "USD", on_date=on_date,
                )
                if pivot_to_usd is not None:
                    to_usd = pivot_to_usd
                    money = pivot
            except ValueError:
                pass
        if to_usd is None or from_usd is None:
            raise ConversionPathUnavailableError(money.currency, target)
        return Money(amount=(money.amount * to_usd * from_usd), currency=target)

    raise ConversionPathUnavailableError(money.currency, target)


async def list_latest_rates(session: AsyncSession) -> list[dict]:
    """Renvoie la liste des taux les plus récents par paire.

    Utilisé par :http:get:`/api/currency/rates/latest`.
    """
    # Sous-requête : MAX(as_of) par paire (base, quote)
    subq = (
        select(
            ExchangeRate.base_currency,
            ExchangeRate.quote_currency,
            func.max(ExchangeRate.as_of).label("max_as_of"),
        )
        .group_by(ExchangeRate.base_currency, ExchangeRate.quote_currency)
        .subquery()
    )
    result = await session.execute(
        select(ExchangeRate)
        .join(
            subq,
            (ExchangeRate.base_currency == subq.c.base_currency)
            & (ExchangeRate.quote_currency == subq.c.quote_currency)
            & (ExchangeRate.as_of == subq.c.max_as_of),
        )
        .order_by(ExchangeRate.base_currency, ExchangeRate.quote_currency),
    )
    rows = list(result.scalars().all())
    return [
        {
            "base_currency": r.base_currency,
            "quote_currency": r.quote_currency,
            "rate": str(r.rate),
            "as_of": r.as_of.isoformat(),
            "source": r.source,
            "fetched_at": r.fetched_at.isoformat(),
        }
        for r in rows
    ]


def get_peg_pairs() -> list[dict]:
    """Renvoie les 2 paires peggées (XOF↔EUR) pour l'API rates/latest."""
    inverse = (Decimal("1") / FCFA_EUR_PEG).quantize(Decimal("0.000001"))
    return [
        {
            "base_currency": "EUR",
            "quote_currency": "XOF",
            "rate": str(FCFA_EUR_PEG),
            "formula": "FCFA_EUR_PEG (Banque de France/BCEAO)",
        },
        {
            "base_currency": "XOF",
            "quote_currency": "EUR",
            "rate": str(inverse),
            "formula": "1 / 655.957",
        },
    ]


async def fetch_status_summary(session: AsyncSession) -> dict:
    """Retourne le résumé d'état pour l'endpoint admin fetch-status."""
    result = await session.execute(
        select(func.max(ExchangeRate.fetched_at)),
    )
    last_success = result.scalar_one_or_none()

    today_utc = datetime.now(timezone.utc).date()
    quota_result = await session.execute(
        select(
            func.count(
                func.distinct(
                    func.concat(
                        ExchangeRate.base_currency, "/",
                        ExchangeRate.quote_currency,
                    ),
                ),
            ),
        ).where(
            ExchangeRate.fetched_at >= datetime.combine(today_utc, datetime.min.time(), tzinfo=timezone.utc),
        ),
    )
    daily_used = quota_result.scalar_one_or_none() or 0

    pairs_result = await session.execute(
        select(
            func.count(
                func.distinct(
                    func.concat(
                        ExchangeRate.base_currency, "/",
                        ExchangeRate.quote_currency,
                    ),
                ),
            ),
        ),
    )
    pairs_known = pairs_result.scalar_one_or_none() or 0

    return {
        "last_success_at": last_success.isoformat() if last_success else None,
        "last_failure_at": _LAST_FAILURE.get("at"),
        "last_error_message": _LAST_FAILURE.get("msg"),
        "daily_quota_used": int(daily_used),
        "daily_quota_max": 50,  # cf. EXCHANGERATE_DAILY_QUOTA_MAX
        "pairs_known": int(pairs_known),
    }


# État process-local pour observabilité MVP (cf. R-14).
# Mémoire seulement, pas persistant.
_LAST_FAILURE: dict[str, str | None] = {"at": None, "msg": None}


def record_failure(message: str) -> None:
    _LAST_FAILURE["at"] = datetime.now(timezone.utc).isoformat()
    _LAST_FAILURE["msg"] = message


def reset_failure_state() -> None:
    """Utile pour les tests (assure un état déterministe)."""
    _LAST_FAILURE["at"] = None
    _LAST_FAILURE["msg"] = None


async def should_fetch(session: AsyncSession, ttl_hours: int = 24) -> bool:
    """Détermine si un fetch HTTP doit être déclenché (cap 1/jour, FR-032)."""
    result = await session.execute(select(func.max(ExchangeRate.fetched_at)))
    last = result.scalar_one_or_none()
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last) > timedelta(hours=ttl_hours)
