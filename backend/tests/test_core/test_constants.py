"""Tests F04 — Constantes monétaires (FCFA_EUR_PEG)."""

from decimal import Decimal

from app.core.constants import FCFA_EUR_PEG


def test_fcfa_eur_peg_value() -> None:
    """Le peg fixe FCFA-EUR (Banque de France/BCEAO) vaut exactement 655,957."""
    assert FCFA_EUR_PEG == Decimal("655.957")


def test_fcfa_eur_peg_type_is_decimal() -> None:
    assert isinstance(FCFA_EUR_PEG, Decimal)


def test_fcfa_eur_peg_is_positive() -> None:
    assert FCFA_EUR_PEG > 0
