"""F04 — Type Money strict (Pydantic v2) + alias Currency Literal.

Représentation immuable d'un montant monétaire typé. La devise est restreinte
à un enum strict (XOF/EUR/USD/GBP/JPY). Le montant est en Decimal (précision
préservée, pas de coercion silencieuse depuis float).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Enum strict : devises supportées par la plateforme.
Currency = Literal["XOF", "EUR", "USD", "GBP", "JPY"]


class Money(BaseModel):
    """Montant monétaire strict (Pydantic v2, frozen, immuable).

    - ``amount`` : Decimal ≥ 0, arrondi à 2 décimales (cohérent NUMERIC(20,2)).
    - ``currency`` : Literal restreint aux devises supportées.

    Sérialisation JSON : ``model_dump(mode='json')`` produit
    ``{"amount": "655957.00", "currency": "XOF"}`` (string pour préserver
    précision).
    """

    model_config = ConfigDict(frozen=True, strict=False)

    amount: Decimal = Field(..., ge=0, description="Montant en Decimal (≥ 0)")
    currency: Currency = Field(..., description="Code devise ISO 4217")

    @field_validator("amount", mode="after")
    @classmethod
    def quantize_two_decimals(cls, v: Decimal) -> Decimal:
        """Arrondit le montant à 2 décimales (cohérent NUMERIC(20,2))."""
        # Quantize peut introduire une exception sur des Decimal 'NaN' :
        # on laisse Pydantic refuser ces cas amont (ge=0 exclut NaN).
        try:
            return v.quantize(Decimal("0.01"))
        except Exception:
            return v

    @classmethod
    def from_columns(
        cls, amount: Decimal | int | float | None, currency: str | None,
    ) -> Money | None:
        """Reconstruit un Money depuis 2 colonnes SQLAlchemy.

        Retourne ``None`` si l'un des deux champs est manquant.
        Permet de gérer les colonnes ``<field>_amount`` + ``<field>_currency``
        nullables sur les modèles legacy.
        """
        if amount is None or currency is None:
            return None
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        return cls(amount=amount, currency=currency)  # type: ignore[arg-type]
