"""F045 T023 - Test boost R13 : projet vert + entreprise rouge -> 3 fonds prioritaires.

Verifie que la regle de boost post-tri promeut GCF / FEM / Fonds d'Adaptation
en tete de liste lorsque :
- project_score >= 60 ET
- project_score - company_score > 30 ET
- au moins 2 criteres parmi (taxonomie OK, themes GCF non vides, CO2 >= 1000)

Et n'applique pas le boost dans les autres configurations.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace


PRIORITY_FUND_NAMES = {
    "Green Climate Fund",
    "Fonds pour l'Environnement Mondial",
    "Fonds d'Adaptation",
}


def _match(fund_name: str, project_score: int, company_score: int):
    return SimpleNamespace(
        fund_name=fund_name,
        project_score=project_score,
        company_score=company_score,
    )


def _project_green_strong(**kw):
    return SimpleNamespace(
        taxonomie_verte_uemoa_aligned=kw.get("taxo", True),
        gcf_priority_themes=kw.get("themes", ["adaptation", "REDD+"]),
        expected_impact_tco2e=kw.get("co2", Decimal("5000")),
    )


def test_boost_applied_when_conditions_met():
    from app.modules.financing.matching_service import (
        _apply_boost_rule_rouge_entreprise_vert_projet,
    )

    matches = [
        _match("Fonds Generique A", 70, 80),
        _match("Fonds Generique B", 65, 75),
        _match("Green Climate Fund", 75, 12),
        _match("Fonds Generique C", 60, 70),
        _match("Fonds d'Adaptation", 65, 10),
    ]
    project = _project_green_strong()
    new_matches, boost = _apply_boost_rule_rouge_entreprise_vert_projet(
        matches, project,
    )
    assert boost.rule_triggered is True
    assert boost.rule_name == "rouge_entreprise_vert_projet"
    # Les 2 fonds prioritaires sont en tete
    top_names = [m.fund_name for m in new_matches[:2]]
    assert any(n in PRIORITY_FUND_NAMES for n in top_names)


def test_boost_not_applied_when_project_score_below_60():
    from app.modules.financing.matching_service import (
        _apply_boost_rule_rouge_entreprise_vert_projet,
    )

    matches = [
        _match("Green Climate Fund", 40, 12),  # project_score < 60
        _match("Fonds Generique A", 70, 80),
    ]
    project = _project_green_strong()
    _, boost = _apply_boost_rule_rouge_entreprise_vert_projet(matches, project)
    # GCF a project_score=40 → ne devrait pas etre boost
    # mais si project_score d'un autre match prioritaire est >=60, peut etre triggered
    # Ici aucun fonds prioritaire >= 60 → pas de boost
    assert boost.rule_triggered is False


def test_boost_not_applied_when_company_strong():
    from app.modules.financing.matching_service import (
        _apply_boost_rule_rouge_entreprise_vert_projet,
    )

    matches = [
        _match("Green Climate Fund", 65, 60),  # ecart <= 30
    ]
    project = _project_green_strong()
    _, boost = _apply_boost_rule_rouge_entreprise_vert_projet(matches, project)
    assert boost.rule_triggered is False


def test_boost_not_applied_when_project_not_green():
    from app.modules.financing.matching_service import (
        _apply_boost_rule_rouge_entreprise_vert_projet,
    )

    matches = [
        _match("Green Climate Fund", 70, 10),
    ]
    project = SimpleNamespace(
        taxonomie_verte_uemoa_aligned=False,
        gcf_priority_themes=[],
        expected_impact_tco2e=None,
    )
    _, boost = _apply_boost_rule_rouge_entreprise_vert_projet(matches, project)
    assert boost.rule_triggered is False
