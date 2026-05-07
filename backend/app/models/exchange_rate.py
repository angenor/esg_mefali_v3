"""F04 — Modèle SQLAlchemy ExchangeRate.

Référentiel public global (pas d'``account_id``) qui stocke les taux de
change pour les paires de devises non-peggées (USD, GBP, JPY).
La paire FCFA-EUR n'est JAMAIS stockée (peg fixe via ``FCFA_EUR_PEG``).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class ExchangeRate(UUIDMixin, Base):
    """Taux de change entre deux devises à une date donnée.

    Une ligne = un taux pour ``(base_currency, quote_currency, as_of)``.
    Le calcul ``1 base = rate * quote`` (multiplicateur).
    """

    __tablename__ = "exchange_rates"

    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "base_currency IN ('XOF', 'EUR', 'USD', 'GBP', 'JPY')",
            name="exchange_rates_base_currency_chk",
        ),
        CheckConstraint(
            "quote_currency IN ('XOF', 'EUR', 'USD', 'GBP', 'JPY')",
            name="exchange_rates_quote_currency_chk",
        ),
        CheckConstraint("rate > 0", name="exchange_rates_rate_positive_chk"),
        UniqueConstraint(
            "base_currency", "quote_currency", "as_of",
            name="exchange_rates_pair_uniq",
        ),
        Index(
            "exchange_rates_lookup_idx",
            "base_currency", "quote_currency", "as_of",
        ),
    )
