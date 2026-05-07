"""Tests TDD pour F22 — DECISION_TREE et ANTI_PATTERNS dans BASE_PROMPT.

Vérifie :
- la présence des 5 sections de l'arbre de décision ;
- la présence d'au moins 5 anti-patterns explicites (NE FAIS PAS / Anti) ;
- le budget tokens (croissance < 25 % vs baseline figé en JSON).

Réf : ``specs/032-decision-tree-with-retry-eval/spec.md`` FR-001/FR-002.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from app.prompts.system import ANTI_PATTERNS, BASE_PROMPT, DECISION_TREE


pytestmark = pytest.mark.unit


BASELINE_PATH = (
    Path(__file__).parent / "_tokens_baseline.json"
).resolve()


# ─── 1. Présence des sections ───────────────────────────────────────────────


def test_decision_tree_section_present_in_base_prompt() -> None:
    """Le BASE_PROMPT contient l'en-tête de l'arbre de décision."""
    assert "## ARBRE DE DÉCISION TOOL — RÈGLES OBLIGATOIRES" in BASE_PROMPT


def test_anti_patterns_section_present_in_base_prompt() -> None:
    """Le BASE_PROMPT contient l'en-tête des anti-patterns."""
    assert "## ANTI-PATTERNS À ÉVITER" in BASE_PROMPT


def test_decision_tree_constant_has_5_sections() -> None:
    """``DECISION_TREE`` couvre les 5 axes : Question fermée, Visualisation,
    Mutation métier, Affirmation factuelle, Chaînage de tools."""
    required_topics = (
        "Question fermée",
        "Visualisation",
        "Mutation",
        "Affirmation",
        "Chaînage",
    )
    missing = [t for t in required_topics if t not in DECISION_TREE]
    assert not missing, f"Sections manquantes dans DECISION_TREE : {missing}"


# ─── 2. Anti-patterns ───────────────────────────────────────────────────────


def test_anti_patterns_has_at_least_5_explicit_anti_examples() -> None:
    """``ANTI_PATTERNS`` doit lister au moins 5 cas explicites NE FAIS PAS."""
    # Compte les occurrences de patterns explicites de prohibition.
    matches = re.findall(r"NE FAIS PAS|NE PAS\b|JAMAIS\b", ANTI_PATTERNS)
    assert len(matches) >= 5, (
        f"ANTI_PATTERNS doit contenir >= 5 marqueurs (NE FAIS PAS/JAMAIS), "
        f"trouvé {len(matches)}"
    )


def test_anti_patterns_covers_5_critical_anti_examples() -> None:
    """Couvre les 5 anti-exemples du spec (chiffre nu, question texte, delete,
    radar pour 1 chiffre, modification catalogue)."""
    keywords = (
        "cite_source",       # chiffre sans cite_source
        "ask_",              # question fermée en texte libre
        "ask_yes_no",        # delete sans confirmation destructive
        "radar",             # radar pour 1 chiffre
        "catalogue",         # modification du catalogue (sources)
    )
    missing = [k for k in keywords if k not in ANTI_PATTERNS]
    assert not missing, f"Anti-exemples manquants : {missing}"


# ─── 3. Budget tokens (gate +25 %) ──────────────────────────────────────────


def _baseline_data() -> dict:
    """Charge la baseline ou crée un placeholder au premier run."""
    if BASELINE_PATH.exists():
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    # Placeholder — sera mis à jour explicitement par T013 après vérification.
    return {"base_prompt_chars": 0}


def test_base_prompt_token_budget_under_125_percent_baseline() -> None:
    """Le BASE_PROMPT ne doit pas dépasser de plus de 25 % la baseline gelée.

    Si la baseline est absente (premier run), créer le fichier baseline avec
    la taille actuelle ; à partir du second run, la croissance > 25 % échoue.

    Le baseline est régénérable (cf. T013) en supprimant le fichier ou en
    mettant à jour la valeur après revue de prompt.
    """
    current = len(BASE_PROMPT)
    data = _baseline_data()
    base = int(data.get("base_prompt_chars", 0))

    if base == 0 or os.getenv("F22_REGENERATE_BASELINE") == "1":
        # Première exécution OU régénération explicite : enregistrer la baseline.
        BASELINE_PATH.write_text(
            json.dumps({"base_prompt_chars": current}, indent=2),
            encoding="utf-8",
        )
        pytest.skip(
            f"Baseline F22 initialisée à {current} caractères. "
            "Re-run pour exécuter la gate."
        )

    threshold = int(base * 1.25)
    assert current <= threshold, (
        f"BASE_PROMPT a grossi de {current - base} caractères "
        f"({(current / base - 1) * 100:.1f}%), au-delà de la gate +25 % "
        f"(baseline={base}, max={threshold}). Régénérer ``_tokens_baseline.json`` "
        "uniquement après revue de prompt explicite."
    )
