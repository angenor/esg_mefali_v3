"""Tests du service alertes F14 (notify_new_offer_matches)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.financing.alerts_service import (
    NotificationResult,
    notify_new_offer_matches,
)


@pytest.mark.asyncio
async def test_notify_no_subscriptions(db_session):
    """Sans souscription → 0 reminder."""
    result = await notify_new_offer_matches(db_session)
    assert isinstance(result, NotificationResult)
    assert result.subscriptions_processed == 0
    assert result.reminders_created == 0


@pytest.mark.asyncio
async def test_notify_skips_inactive_subscription(db_session):
    """Souscription inactive → ignorée."""
    from app.models.account import Account
    from app.models.match_alert_subscription import MatchAlertSubscription
    from app.models.project import Project
    from app.models.user import User

    account = Account(name="X")
    db_session.add(account)
    await db_session.flush()

    user = User(
        email=f"u-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="x",
        full_name="U",
        company_name="X",
        account_id=account.id,
    )
    db_session.add(user)

    project = Project(
        account_id=account.id, name="P",
        objective_env=["mitigation"], status="draft",
    )
    db_session.add(project)
    await db_session.flush()

    sub = MatchAlertSubscription(
        account_id=account.id,
        project_id=project.id,
        min_global_score=60,
        is_active=False,
    )
    db_session.add(sub)
    await db_session.flush()

    result = await notify_new_offer_matches(db_session)
    assert result.subscriptions_processed == 0


@pytest.mark.asyncio
async def test_notify_creates_reminder_for_eligible_match(db_session):
    """Match éligible → Reminder créé + last_notified_at set."""
    from app.models.account import Account
    from app.models.action_plan import Reminder
    from app.models.match_alert_subscription import MatchAlertSubscription
    from app.models.offer_match import OfferMatch
    from app.models.project import Project
    from app.models.user import User
    from sqlalchemy import select

    account = Account(name="X")
    db_session.add(account)
    await db_session.flush()

    user = User(
        email=f"u-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="x",
        full_name="U",
        company_name="X",
        account_id=account.id,
    )
    db_session.add(user)

    project = Project(
        account_id=account.id, name="P",
        objective_env=["mitigation"], status="draft",
    )
    db_session.add(project)
    await db_session.flush()

    sub = MatchAlertSubscription(
        account_id=account.id,
        project_id=project.id,
        min_global_score=60,
        is_active=True,
    )
    db_session.add(sub)
    await db_session.flush()

    # Insérer un OfferMatch avec offer_id factice
    match = OfferMatch(
        account_id=account.id,
        project_id=project.id,
        offer_id=uuid.uuid4(),
        global_score=80,
        fund_score=80,
        intermediary_score=80,
        score_breakdown={},
        bottleneck="balanced",
        recommended_actions=[],
        status="suggested",
        computed_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        last_notified_at=None,
    )
    db_session.add(match)
    await db_session.flush()

    # FK offers ondelete RESTRICT empêche INSERT match sans offre dans le
    # vrai schéma ; SQLite n'applique pas FK par défaut, donc le test passe.
    # On valide la mécanique (cron logic).
    result = await notify_new_offer_matches(db_session)
    assert result.subscriptions_processed >= 1
    assert result.reminders_created >= 1
    assert match.last_notified_at is not None


@pytest.mark.asyncio
async def test_notify_idempotent_via_last_notified_at(db_session):
    """Match déjà notifié → pas de nouveau Reminder."""
    from app.models.account import Account
    from app.models.match_alert_subscription import MatchAlertSubscription
    from app.models.offer_match import OfferMatch
    from app.models.project import Project
    from app.models.user import User

    account = Account(name="X")
    db_session.add(account)
    await db_session.flush()

    user = User(
        email=f"u-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="x",
        full_name="U",
        company_name="X",
        account_id=account.id,
    )
    db_session.add(user)

    project = Project(
        account_id=account.id, name="P",
        objective_env=["mitigation"], status="draft",
    )
    db_session.add(project)
    await db_session.flush()

    db_session.add(MatchAlertSubscription(
        account_id=account.id,
        project_id=project.id,
        min_global_score=60,
        is_active=True,
    ))

    # Match déjà notifié
    match = OfferMatch(
        account_id=account.id,
        project_id=project.id,
        offer_id=uuid.uuid4(),
        global_score=80, fund_score=80, intermediary_score=80,
        score_breakdown={}, bottleneck="balanced", recommended_actions=[],
        status="suggested",
        computed_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        last_notified_at=datetime.now(timezone.utc),
    )
    db_session.add(match)
    await db_session.flush()

    result = await notify_new_offer_matches(db_session)
    # Match avec last_notified_at non-null → ignoré
    assert result.reminders_created == 0


@pytest.mark.asyncio
async def test_notify_skips_below_threshold(db_session):
    """Score < min_global_score → pas de Reminder."""
    from app.models.account import Account
    from app.models.match_alert_subscription import MatchAlertSubscription
    from app.models.offer_match import OfferMatch
    from app.models.project import Project
    from app.models.user import User

    account = Account(name="X")
    db_session.add(account)
    await db_session.flush()

    user = User(
        email=f"u-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="x",
        full_name="U",
        company_name="X",
        account_id=account.id,
    )
    db_session.add(user)

    project = Project(
        account_id=account.id, name="P",
        objective_env=["mitigation"], status="draft",
    )
    db_session.add(project)
    await db_session.flush()

    db_session.add(MatchAlertSubscription(
        account_id=account.id,
        project_id=project.id,
        min_global_score=80,
        is_active=True,
    ))

    match = OfferMatch(
        account_id=account.id,
        project_id=project.id,
        offer_id=uuid.uuid4(),
        global_score=50, fund_score=50, intermediary_score=50,
        score_breakdown={}, bottleneck="balanced", recommended_actions=[],
        status="suggested",
        computed_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        last_notified_at=None,
    )
    db_session.add(match)
    await db_session.flush()

    result = await notify_new_offer_matches(db_session)
    assert result.reminders_created == 0
