"""F04 — Endpoints publics du module currency.

- ``GET /api/currency/rates/latest`` (auth=None) : taux les plus récents.
- ``POST /api/currency/convert`` (auth=None) : conversion Money.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.money import Money
from app.modules.currency import service as currency_service
from app.modules.currency.exceptions import (
    ConversionPathUnavailableError,
    NoRateAvailableError,
)
from app.modules.currency.schemas import (
    ConvertRequest,
    ConvertResponse,
    RatesLatestResponse,
)


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/rates/latest", response_model=RatesLatestResponse)
async def list_latest_rates(
    db: AsyncSession = Depends(get_db),
) -> RatesLatestResponse:
    """Liste tous les taux les plus récents par paire + paires peggées."""
    rates = await currency_service.list_latest_rates(db)
    pegs = currency_service.get_peg_pairs()
    return RatesLatestResponse(rates=rates, peg_pairs=pegs)


@router.post("/convert", response_model=ConvertResponse)
async def convert_currency(
    body: ConvertRequest,
    db: AsyncSession = Depends(get_db),
) -> ConvertResponse:
    """Convertit ``amount`` de ``source_currency`` vers ``target_currency``."""
    source_money = Money(amount=body.amount, currency=body.source_currency)
    try:
        target_money = await currency_service.convert(
            source_money, body.target_currency, db, on_date=body.date,
        )
    except NoRateAvailableError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConversionPathUnavailableError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Méthode utilisée (heuristique simple).
    if (body.source_currency, body.target_currency) in {
        ("XOF", "EUR"), ("EUR", "XOF"),
    }:
        method = "peg_fixed"
        rate_date = None
    elif body.source_currency == "USD" or body.target_currency == "USD":
        method = "table"
        rate_date = body.date
    else:
        method = "pivot_usd"
        rate_date = body.date

    rate_used = (
        target_money.amount / body.amount
        if body.amount and body.amount > 0
        else Decimal("0")
    )

    return ConvertResponse(
        source=source_money,
        target=target_money,
        rate_used=str(rate_used),
        method=method,
        rate_date=rate_date,
    )
