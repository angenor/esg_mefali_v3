"""Tests unitaires du schema ReductionPlanAction (F17 — T004 + T042-T045).

Couvre :
- Action valide avec source_id (sourcee).
- Action valide unsourced explicite.
- Incoherence source_id=None + unsourced=False -> ValidationError.
- Incoherence source_id="<uuid>" + unsourced=True -> ValidationError.
- Bornes title/description/timeline (min/max).
- Plan vide accepte.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.modules.carbon.reduction_plan_schema import (
    ReductionPlan,
    ReductionPlanAction,
)


def _make_action(**overrides) -> dict:
    """Action de base utilisee dans les tests."""
    base = {
        "title": "Passer au solaire",
        "description": (
            "Installation de 5 kWc de panneaux photovoltaiques pour reduire "
            "la consommation reseau de 70%."
        ),
        "estimated_reduction_tco2e": 1.2,
        "cost_estimate_fcfa": 4_500_000,
        "timeline": "6-12 mois",
        "source_id": str(uuid.uuid4()),
        "unsourced": False,
    }
    base.update(overrides)
    return base


# ---------- Actions valides ---------------------------------------------------


def test_reduction_plan_action_with_source_validates() -> None:
    """Action sourcee : source_id non vide + unsourced=False -> OK."""
    action = ReductionPlanAction.model_validate(_make_action())
    assert action.source_id is not None
    assert action.unsourced is False
    assert action.estimated_reduction_tco2e == 1.2


def test_reduction_plan_action_unsourced_validates() -> None:
    """Action explicitement non sourcee : source_id=None + unsourced=True -> OK."""
    payload = _make_action(source_id=None, unsourced=True)
    action = ReductionPlanAction.model_validate(payload)
    assert action.source_id is None
    assert action.unsourced is True


def test_reduction_plan_action_no_cost_estimate_optional() -> None:
    """``cost_estimate_fcfa`` est optionnel (peut etre None)."""
    action = ReductionPlanAction.model_validate(
        _make_action(cost_estimate_fcfa=None)
    )
    assert action.cost_estimate_fcfa is None


# ---------- Incoherences source_id <-> unsourced -----------------------------


def test_reduction_plan_action_inconsistency_source_and_unsourced() -> None:
    """source_id renseigne + unsourced=True -> ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ReductionPlanAction.model_validate(
            _make_action(source_id=str(uuid.uuid4()), unsourced=True)
        )
    assert "source_id" in str(exc_info.value).lower()
    assert "unsourced" in str(exc_info.value).lower()


def test_reduction_plan_action_inconsistency_no_source_and_not_unsourced() -> None:
    """source_id=None + unsourced=False -> ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ReductionPlanAction.model_validate(
            _make_action(source_id=None, unsourced=False)
        )
    assert "source_id" in str(exc_info.value).lower()
    assert "unsourced" in str(exc_info.value).lower()


# ---------- Bornes ------------------------------------------------------------


def test_reduction_plan_action_title_too_long() -> None:
    """title > 200 caracteres -> ValidationError."""
    with pytest.raises(ValidationError):
        ReductionPlanAction.model_validate(_make_action(title="A" * 201))


def test_reduction_plan_action_title_empty() -> None:
    """title vide -> ValidationError."""
    with pytest.raises(ValidationError):
        ReductionPlanAction.model_validate(_make_action(title=""))


def test_reduction_plan_action_description_too_long() -> None:
    """description > 1000 caracteres -> ValidationError."""
    with pytest.raises(ValidationError):
        ReductionPlanAction.model_validate(
            _make_action(description="X" * 1001)
        )


def test_reduction_plan_action_negative_reduction() -> None:
    """estimated_reduction_tco2e < 0 -> ValidationError."""
    with pytest.raises(ValidationError):
        ReductionPlanAction.model_validate(
            _make_action(estimated_reduction_tco2e=-0.5)
        )


def test_reduction_plan_action_negative_cost() -> None:
    """cost_estimate_fcfa < 0 -> ValidationError."""
    with pytest.raises(ValidationError):
        ReductionPlanAction.model_validate(
            _make_action(cost_estimate_fcfa=-1)
        )


def test_reduction_plan_action_timeline_empty() -> None:
    """timeline vide -> ValidationError."""
    with pytest.raises(ValidationError):
        ReductionPlanAction.model_validate(_make_action(timeline=""))


# ---------- ReductionPlan (conteneur) ----------------------------------------


def test_reduction_plan_empty_actions() -> None:
    """Plan vide (actions=[]) accepte."""
    plan = ReductionPlan.model_validate({"actions": []})
    assert plan.actions == []


def test_reduction_plan_default_factory() -> None:
    """Sans champ ``actions`` -> liste vide par defaut."""
    plan = ReductionPlan()
    assert plan.actions == []


def test_reduction_plan_with_mixed_actions() -> None:
    """Plan avec actions sourcees ET unsourced -> OK."""
    plan = ReductionPlan.model_validate(
        {
            "actions": [
                _make_action(),
                _make_action(source_id=None, unsourced=True),
            ]
        }
    )
    assert len(plan.actions) == 2
    assert plan.actions[0].source_id is not None
    assert plan.actions[1].source_id is None
    assert plan.actions[1].unsourced is True


def test_reduction_plan_extra_field_forbidden() -> None:
    """Champ inconnu -> rejete (extra='forbid')."""
    with pytest.raises(ValidationError):
        ReductionPlanAction.model_validate(
            _make_action(unknown_field="oops")
        )
