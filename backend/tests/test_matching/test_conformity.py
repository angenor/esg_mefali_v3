"""Tests de conformité F14 :

- Aucun nouveau code F14 n'écrit dans `fund_matches` (legacy 2 sprints).
- Aucun tool F14 ne mute Skills (catalogue admin-only).
- Tools F14 sont dans tool_selector_config.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


F14_BACKEND_PATHS = [
    "backend/app/modules/financing/matching_service.py",
    "backend/app/modules/financing/matching_router.py",
    "backend/app/modules/financing/matching_schemas.py",
    "backend/app/modules/financing/alerts_service.py",
    "backend/app/graph/tools/matching_tools.py",
    "backend/app/models/offer_match.py",
    "backend/app/models/match_alert_subscription.py",
]

REPO_ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_no_fund_match_writes_in_f14_code():
    """Aucun fichier F14 ne doit contenir db.add(FundMatch(...))
    ni écrire dans la table fund_matches."""
    forbidden_patterns = [
        re.compile(r"\bFundMatch\s*\("),
        re.compile(r'INTO\s+fund_matches\b', re.IGNORECASE),
        re.compile(r"\.fund_matches\s*\.\s*(insert|append|extend)\b"),
    ]
    offences: list[tuple[str, str]] = []
    for path in F14_BACKEND_PATHS:
        try:
            content = _read(path)
        except FileNotFoundError:
            continue
        for pat in forbidden_patterns:
            if pat.search(content):
                offences.append((path, pat.pattern))
    assert not offences, (
        f"F14 code écrit dans fund_matches: {offences}"
    )


def test_no_skill_mutation_in_matching_code():
    """Aucun tool F14 ne mute Skills (interdit catalogue admin)."""
    skill_mutation = re.compile(
        r"\b(create|update|delete|publish|unpublish)_skill\b"
    )
    skill_constructor = re.compile(r"\bSkill\s*\(")
    offences: list[tuple[str, str]] = []
    for path in F14_BACKEND_PATHS:
        try:
            content = _read(path)
        except FileNotFoundError:
            continue
        if skill_mutation.search(content):
            offences.append((path, "skill_mutation"))
        if skill_constructor.search(content):
            offences.append((path, "skill_constructor"))
    assert not offences, f"F14 code mutates Skill: {offences}"


def test_matching_tools_in_tool_selector_config():
    """Les 4 tools F14 sont déclarés dans tool_selector_config."""
    from app.graph.tool_selector_config import (
        MAX_TOOLS_PER_TURN,
        MODULE_TOOL_MAPPING,
        PAGE_TOOL_MAPPING,
    )
    expected = {
        "list_matches_for_project",
        "compare_offers_for_fund_v2",
        "recompute_matches_for_project",
        "get_match_details",
    }
    # Au moins le noeud financing doit avoir tous les 4 (MUTATION + READ).
    assert expected <= MODULE_TOOL_MAPPING["financing"]
    # PAGE_TOOL_MAPPING['profile_projects'] contient au moins le bloc lecture.
    read_set = {
        "list_matches_for_project",
        "compare_offers_for_fund_v2",
        "get_match_details",
    }
    assert read_set <= PAGE_TOOL_MAPPING["profile_projects"]
    assert MAX_TOOLS_PER_TURN >= 26


def test_offer_match_table_in_models_init():
    """OfferMatch + MatchAlertSubscription importables via app.models."""
    from app.models import MatchAlertSubscription, OfferMatch
    assert OfferMatch.__tablename__ == "offer_matches"
    assert MatchAlertSubscription.__tablename__ == "match_alerts_subscriptions"


def test_reminder_type_enum_has_new_offer_alert():
    """L'enum ReminderType expose la valeur new_offer_alert (F14)."""
    from app.models.action_plan import ReminderType
    assert hasattr(ReminderType, "new_offer_alert")
    assert ReminderType.new_offer_alert.value == "new_offer_alert"
