"""Tests unitaires des modèles SQLAlchemy F14 (OfferMatch, MatchAlertSubscription)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.auditable import AUDITABLE_MODELS
from app.models.match_alert_subscription import MatchAlertSubscription
from app.models.offer_match import (
    OFFER_MATCH_BOTTLENECK_VALUES,
    OFFER_MATCH_STATUS_VALUES,
    OfferMatch,
)


def test_bottleneck_whitelist():
    assert OFFER_MATCH_BOTTLENECK_VALUES == frozenset(
        {"fund", "intermediary", "balanced"}
    )


def test_status_whitelist():
    assert OFFER_MATCH_STATUS_VALUES == frozenset(
        {"suggested", "viewed", "dismissed", "converted"}
    )


def test_offer_match_in_auditable_models():
    assert "OfferMatch" in AUDITABLE_MODELS


def test_match_alert_subscription_in_auditable_models():
    assert "MatchAlertSubscription" in AUDITABLE_MODELS


def test_offer_match_table_name():
    assert OfferMatch.__tablename__ == "offer_matches"


def test_match_alert_subscription_table_name():
    assert MatchAlertSubscription.__tablename__ == "match_alerts_subscriptions"


def test_offer_match_columns_present():
    cols = {c.name for c in OfferMatch.__table__.columns}
    expected = {
        "id", "account_id", "project_id", "offer_id",
        "global_score", "fund_score", "intermediary_score",
        "score_breakdown", "bottleneck", "recommended_actions",
        "status", "computed_at", "expires_at", "last_notified_at",
        "created_at", "updated_at",
    }
    assert expected <= cols


def test_offer_match_unique_constraint():
    constraints = OfferMatch.__table__.constraints
    unique_names = {
        c.name for c in constraints if hasattr(c, "name") and c.name
    }
    assert "uq_offer_matches_project_offer" in unique_names


def test_offer_match_indexes_present():
    idx_names = {idx.name for idx in OfferMatch.__table__.indexes}
    assert "idx_offer_matches_project_computed" in idx_names
    assert "idx_offer_matches_account_expires" in idx_names
    assert "idx_offer_matches_offer" in idx_names


def test_match_alert_subscription_unique_project():
    constraints = MatchAlertSubscription.__table__.constraints
    unique_names = {
        c.name for c in constraints if hasattr(c, "name") and c.name
    }
    assert "uq_match_alerts_subscription_project" in unique_names


def test_offer_match_check_constraints_have_names():
    """Les CHECK constraints ont des noms cohérents pour Alembic."""
    check_names = {
        c.name
        for c in OfferMatch.__table__.constraints
        if c.__class__.__name__ == "CheckConstraint" and c.name
    }
    expected = {
        "offer_matches_global_score_chk",
        "offer_matches_fund_score_chk",
        "offer_matches_intermediary_score_chk",
        "offer_matches_bottleneck_chk",
        "offer_matches_status_chk",
    }
    assert expected <= check_names
