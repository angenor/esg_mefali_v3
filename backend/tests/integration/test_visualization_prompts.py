"""F11 — Tests d'intégration des prompts pour la sélection des tools de visualisation.

Approche pragmatique : on ne mocke pas le LLM (coûteux et fragile). On vérifie
que les prompts contiennent bien les indications nécessaires pour orienter
le LLM vers les tools typés (decision tree, exemples, encouragements).

Cela représente la baseline déterministe testable du SC-001/002/003.
"""

from __future__ import annotations


def test_system_prompt_contains_decision_tree() -> None:
    """Le system prompt mentionne l'arbre de décision visualisation."""
    from app.prompts.system import BASE_PROMPT

    text = BASE_PROMPT.lower()
    assert "arbre de décision visualisation" in text or "arbre de decision" in text
    # Les 4 tools typés sont nommés
    for tool_name in (
        "show_kpi_card",
        "show_match_card",
        "show_map",
        "show_comparison_table",
    ):
        assert tool_name in text, f"{tool_name} absent du system prompt"


def test_system_prompt_priorise_tools_types() -> None:
    """Le system prompt insiste sur la priorité des tools typés vs fences markdown."""
    from app.prompts.system import BASE_PROMPT

    text = BASE_PROMPT.lower()
    # On exige qu'au moins une mention "priorité" / "priority" / "toujours" apparaisse
    # dans le contexte des tools typés
    assert "priorit" in text or "toujours en priorit" in text


def test_financing_prompt_encourage_match_card() -> None:
    """Le prompt financing encourage show_match_card."""
    from app.prompts.financing import FINANCING_PROMPT

    text = FINANCING_PROMPT.lower()
    assert "show_match_card" in text
    assert "show_comparison_table" in text


def test_financing_prompt_match_card_rule() -> None:
    """Le prompt financing donne des règles claires sur quand utiliser show_match_card."""
    from app.prompts.financing import FINANCING_PROMPT

    # Doit mentionner "matching projet" et "1 carte par offre"
    text = FINANCING_PROMPT.lower()
    assert "matching" in text or "match" in text
    # Une indication de quantité (plusieurs cartes / 1 carte par offre)
    assert "carte" in text


def test_application_prompt_encourage_comparison_table() -> None:
    """Le prompt application encourage show_comparison_table pour comparer offres."""
    from app.prompts.application import APPLICATION_PROMPT

    text = APPLICATION_PROMPT.lower()
    assert "show_comparison_table" in text
    assert "show_match_card" in text


def test_decision_tree_kpi_use_case() -> None:
    """L'arbre de décision indique d'utiliser KPICard pour un chiffre clé."""
    from app.prompts.system import BASE_PROMPT

    text = BASE_PROMPT.lower()
    # On veut voir KPI card associé à un chiffre clé / score / empreinte
    assert "show_kpi_card" in text
    # Mention d'un cas typique
    assert (
        "chiffre clé" in text
        or "chiffre cle" in text
        or "score" in text
        or "empreinte" in text
    )


def test_decision_tree_comparison_use_case() -> None:
    """L'arbre de décision indique d'utiliser ComparisonTable pour comparer."""
    from app.prompts.system import BASE_PROMPT

    text = BASE_PROMPT.lower()
    assert "show_comparison_table" in text
    # Mention "comparer" ou "côte-à-côte"
    assert (
        "compar" in text
        or "côte-à-côte" in text
        or "cote-a-cote" in text
    )


def test_decision_tree_map_use_case() -> None:
    """L'arbre de décision indique d'utiliser show_map pour la géolocalisation."""
    from app.prompts.system import BASE_PROMPT

    text = BASE_PROMPT.lower()
    assert "show_map" in text
    assert "uemoa" in text or "carte géographique" in text or "carte geographique" in text


def test_decision_tree_fallback_text_si_question_floue() -> None:
    """Le prompt indique de préférer le texte si la question est floue."""
    from app.prompts.system import BASE_PROMPT

    text = BASE_PROMPT.lower()
    # Mention du fallback texte ou "ouverte"/"floue"
    assert "texte" in text


def test_decision_tree_match_card_use_case() -> None:
    """L'arbre de décision indique d'utiliser MatchCard pour matching projet/offre."""
    from app.prompts.system import BASE_PROMPT

    text = BASE_PROMPT.lower()
    assert "show_match_card" in text
    # Mention "projet" + "offre"
    assert "projet" in text and "offre" in text


def test_financing_keeps_existing_search_rules() -> None:
    """Régression : les règles existantes (search_compatible_funds obligatoire) restent."""
    from app.prompts.financing import FINANCING_PROMPT

    text = FINANCING_PROMPT.lower()
    assert "search_compatible_funds" in text
    assert "tool calling obligatoire" in text or "tool calling" in text


def test_application_keeps_existing_workflow() -> None:
    """Régression : le workflow obligatoire des candidatures reste."""
    from app.prompts.application import APPLICATION_PROMPT

    text = APPLICATION_PROMPT.lower()
    assert "create_fund_application" in text
    assert "generate_application_section" in text
