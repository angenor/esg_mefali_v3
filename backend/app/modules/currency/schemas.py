"""F04 — Schémas Pydantic pour le module currency."""

from __future__ import annotations

import datetime as _dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.money import Currency, Money


class ConvertRequest(BaseModel):
    """Body pour POST /api/currency/convert."""

    model_config = ConfigDict(arbitrary_types_allowed=False)

    amount: Decimal = Field(..., ge=0, description="Montant à convertir (≥ 0)")
    source_currency: Currency
    target_currency: Currency
    date: _dt.date | None = Field(
        default=None, description="Date du taux (défaut today)",
    )


class ConvertResponse(BaseModel):
    """Résultat d'une conversion."""

    source: Money
    target: Money
    rate_used: str = Field(..., description="Taux multiplicateur appliqué (string)")
    method: Literal["peg_fixed", "table", "pivot_usd"]
    rate_date: _dt.date | None = Field(default=None)


class RateEntry(BaseModel):
    """Entrée taux pour /api/currency/rates/latest."""

    base_currency: Currency
    quote_currency: Currency
    rate: str
    as_of: str
    source: str
    fetched_at: str


class PegEntry(BaseModel):
    """Entrée peggée (XOF↔EUR) pour /api/currency/rates/latest."""

    base_currency: Currency
    quote_currency: Currency
    rate: str
    formula: str


class RatesLatestResponse(BaseModel):
    rates: list[RateEntry]
    peg_pairs: list[PegEntry]


class FetchStatusResponse(BaseModel):
    """Réponse pour GET /api/admin/currency/fetch-status."""

    last_success_at: str | None
    last_failure_at: str | None
    last_error_message: str | None
    daily_quota_used: int
    daily_quota_max: int
    pairs_known: int


class ErrorResponse(BaseModel):
    detail: str
