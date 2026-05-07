"""Matching helpers communs pour le golden set (F22) et l'eval gating (F23).

Ces fonctions sont volontairement extrêmement simples et stables : elles sont
appelées à la fois par le runner LLM eval (`tests/llm_eval/test_eval_runner.py`)
et par le service production `app/modules/skills/eval_runner.py`. La duplication
serait dangereuse car les deux flux (CI et publication runtime) doivent partager
exactement les mêmes critères de comparaison.

Décision design (cf. research.md R8) : "match_tool_called" accepte une whitelist
de tools acceptables (string OR list), "match_payload_contains" est un subset
match shallow (pour rester pédagogique et facile à raisonner par les admins).
"""

from __future__ import annotations

from typing import Any


def match_tool_called(actual: str | None, expected: str | list[str]) -> bool:
    """Compare le tool effectivement appelé avec l'expected (string ou liste).

    Args:
        actual: Nom du tool réellement invoqué par le LLM (None si fallback texte).
        expected: Nom unique attendu OU liste de noms acceptables (whitelist tolérante).

    Returns:
        True si ``actual`` ∈ expected (et ``actual`` non None).

    Examples:
        >>> match_tool_called("create_fund_application", "create_fund_application")
        True
        >>> match_tool_called("search_funds", ["create_fund_application", "search_funds"])
        True
        >>> match_tool_called(None, "create_fund_application")
        False
    """
    if actual is None:
        return False
    if isinstance(expected, list):
        return actual in expected
    return actual == expected


def match_payload_contains(
    actual: dict[str, Any] | None,
    expected: dict[str, Any] | None,
) -> bool:
    """Retourne True si toutes les clés/valeurs ``expected`` sont présentes dans ``actual``.

    Comparaison shallow (top-level uniquement). Si ``expected`` est ``None`` ou vide,
    retourne True (aucune contrainte de payload). Pour des matchings plus complexes
    (subset récursif), voir ``tests/llm_eval/conftest.py:subset_match``.

    Args:
        actual: Payload réellement passé au tool (dict ou None).
        expected: Subset de clés/valeurs attendues (dict ou None).

    Returns:
        True si tous les ``(k, v)`` de ``expected`` matchent ``actual[k] == v``.
    """
    if expected is None or len(expected) == 0:
        return True
    if actual is None:
        return False
    for key, value in expected.items():
        if key not in actual:
            return False
        if actual[key] != value:
            return False
    return True
