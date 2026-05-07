"""F04 — Script CLI : fetch des taux exchangerate-api.com (free tier).

Usage::

    python -m app.scripts.fetch_exchange_rates [--force]

Cap dur 1 fetch/jour : si la table ``exchange_rates`` contient déjà une
ligne datée < 24h, le script skip silencieusement (sauf ``--force``).

Mode dégradé : si ``EXCHANGERATE_API_KEY`` est vide, le script log un
warning et exit 0 (utile en dev).
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.exchange_rate import ExchangeRate
from app.modules.currency.exceptions import FetchFailedError
from app.modules.currency.service import (
    record_failure,
    reset_failure_state,
    should_fetch,
)


logger = logging.getLogger(__name__)


# Devises ciblées (depuis USD, base de exchangerate-api.com).
TARGET_CURRENCIES = ("XOF", "EUR", "GBP", "JPY")


async def fetch_one_shot(
    session: AsyncSession, force: bool = False,
) -> dict:
    """Fetch HTTP unique exchangerate-api.com et insère les paires en BDD.

    Retourne ``{inserted: int, source: str, as_of: date}``.
    """
    if not settings.exchangerate_api_key:
        logger.warning("EXCHANGERATE_API_KEY empty — skipping fetch (degraded mode)")
        return {"inserted": 0, "source": "skipped_no_key", "as_of": None}

    if not force and not await should_fetch(session):
        logger.info("Daily fetch cap reached — skipping (use --force to override)")
        return {"inserted": 0, "source": "skipped_cap", "as_of": None}

    url = (
        f"{settings.exchangerate_api_base_url.rstrip('/')}"
        f"/{settings.exchangerate_api_key}/latest/USD"
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        msg = f"{type(e).__name__}: {e}"
        logger.error("EXCHANGERATE_FETCH_FAILED: %s", msg)
        record_failure(msg)
        raise FetchFailedError(msg) from e

    rates_dict = payload.get("conversion_rates") or payload.get("rates") or {}
    if not rates_dict:
        msg = "missing conversion_rates field in API response"
        logger.error("EXCHANGERATE_FETCH_FAILED: %s", msg)
        record_failure(msg)
        raise FetchFailedError(msg)

    today = date.today()
    inserted = 0
    for target in TARGET_CURRENCIES:
        if target not in rates_dict:
            logger.warning("Currency %s missing from API response", target)
            continue
        rate_value = Decimal(str(rates_dict[target]))
        if rate_value <= 0:
            continue

        # Insert direct USD→target.
        await _upsert_rate(
            session, "USD", target, rate_value, today,
            source="exchangerate-api.com",
        )
        # Dérivation paire inverse target→USD.
        inverse = (Decimal("1") / rate_value).quantize(Decimal("0.0000000001"))
        await _upsert_rate(
            session, target, "USD", inverse, today, source="computed",
        )
        inserted += 2

    await session.commit()
    reset_failure_state()
    logger.info(
        "F04 exchange_rates fetch OK — %d entries inserted/updated", inserted,
    )
    return {"inserted": inserted, "source": "exchangerate-api.com", "as_of": today}


async def _upsert_rate(
    session: AsyncSession, base: str, quote: str, rate: Decimal,
    as_of: date, source: str,
) -> None:
    """Insère ou met à jour le taux pour la paire à la date donnée."""
    existing = await session.execute(
        select(ExchangeRate).where(
            ExchangeRate.base_currency == base,
            ExchangeRate.quote_currency == quote,
            ExchangeRate.as_of == as_of,
        ),
    )
    row = existing.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if row is not None:
        row.rate = rate
        row.fetched_at = now
        row.source = source
    else:
        session.add(
            ExchangeRate(
                id=uuid.uuid4(),
                base_currency=base,
                quote_currency=quote,
                rate=rate,
                as_of=as_of,
                source=source,
                fetched_at=now,
            ),
        )


async def main(force: bool = False) -> int:
    logging.basicConfig(level=logging.INFO)
    async with async_session_factory() as session:
        try:
            await fetch_one_shot(session, force=force)
        except FetchFailedError as e:
            logger.error("Fetch failed: %s", e)
            return 1
    return 0


if __name__ == "__main__":
    force = "--force" in sys.argv
    sys.exit(asyncio.run(main(force=force)))
