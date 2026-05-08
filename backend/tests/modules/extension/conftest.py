"""Fixtures partagées tests F24 extension Chrome."""

# Réexport des fixtures F07 offers (Source, Fund, Intermediary, Offer, ...)
from tests.test_offers.conftest import (  # noqa: F401
    basic_fund,
    basic_fund_intermediary,
    basic_intermediary,
    draft_offer,
    draft_source,
    published_offer,
    two_admins,
    verified_source,
)
