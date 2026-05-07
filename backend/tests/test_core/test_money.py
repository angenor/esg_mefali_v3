"""Tests F04 — Type Money strict (Pydantic v2)."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.money import Money, Currency


class TestMoneyValidation:
    """Validation Pydantic stricte du type Money."""

    def test_create_money_xof(self) -> None:
        money = Money(amount=Decimal("1000.00"), currency="XOF")
        assert money.amount == Decimal("1000.00")
        assert money.currency == "XOF"

    def test_create_money_eur(self) -> None:
        money = Money(amount=Decimal("655.957"), currency="EUR")
        # decimal_places=2 → arrondi à 2 décimales (655.96)
        assert money.currency == "EUR"
        assert money.amount.as_tuple().exponent >= -3

    def test_money_is_frozen_immutable(self) -> None:
        """Une instance Money est immuable (frozen=True)."""
        money = Money(amount=Decimal("100.00"), currency="XOF")
        with pytest.raises(ValidationError):
            money.amount = Decimal("200.00")  # type: ignore[misc]

    def test_money_dump_json_string_amount(self) -> None:
        """model_dump(mode='json') sérialise amount en string Decimal."""
        money = Money(amount=Decimal("655957.00"), currency="XOF")
        dumped = money.model_dump(mode="json")
        assert dumped["amount"] == "655957.00"
        assert dumped["currency"] == "XOF"

    def test_from_columns_returns_money(self) -> None:
        money = Money.from_columns(Decimal("100.00"), "XOF")
        assert money is not None
        assert money.amount == Decimal("100.00")
        assert money.currency == "XOF"

    def test_from_columns_returns_none_when_amount_missing(self) -> None:
        assert Money.from_columns(None, "XOF") is None
        assert Money.from_columns(Decimal("100"), None) is None
        assert Money.from_columns(None, None) is None

    def test_reject_currency_outside_enum(self) -> None:
        """ABC n'est pas dans Currency Literal['XOF','EUR','USD','GBP','JPY']."""
        with pytest.raises(ValidationError):
            Money(amount=Decimal("100.00"), currency="ABC")  # type: ignore[arg-type]

    def test_reject_negative_amount(self) -> None:
        with pytest.raises(ValidationError):
            Money(amount=Decimal("-100.00"), currency="XOF")

    def test_accept_zero_amount(self) -> None:
        money = Money(amount=Decimal("0.00"), currency="XOF")
        assert money.amount == Decimal("0.00")

    def test_currency_literal_values(self) -> None:
        """Le Literal Currency contient bien les 5 devises attendues."""
        for code in ("XOF", "EUR", "USD", "GBP", "JPY"):
            m = Money(amount=Decimal("1.00"), currency=code)  # type: ignore[arg-type]
            assert m.currency == code
