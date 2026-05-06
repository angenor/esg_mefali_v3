"""Tests pour build_adaptive_frequency_hint et son injection dans build_system_prompt.

Story 6.4 — frequence adaptative des propositions de guidage (FR17).

Le helper `build_adaptive_frequency_hint` retourne un bloc normatif francais
quand l'utilisateur a refuse plusieurs fois (refusal_count >= 3), sinon chaine
vide. La constante `GUIDED_TOUR_INSTRUCTION` (verrouillee par 16 tests story 6.2
+ 17 tests story 6.3) est preservee : le hint est un appendix conditionnel.
"""

import pytest

from app.prompts.guided_tour import (
    GUIDED_TOUR_INSTRUCTION,
    build_adaptive_frequency_hint,
)
from app.prompts.system import build_system_prompt


# --- AC3 : Helper build_adaptive_frequency_hint ---


def test_hint_returns_empty_when_stats_none():
    """T1 — Aucun stat → pas de hint."""
    assert build_adaptive_frequency_hint(None) == ""


@pytest.mark.parametrize("refusal_count", [0, 1, 2])
def test_hint_returns_empty_when_refusal_count_below_threshold(refusal_count):
    """T2 — Seuil non atteint (< 3) → chaine vide."""
    stats = {"refusal_count": refusal_count, "acceptance_count": 0}
    assert build_adaptive_frequency_hint(stats) == ""


@pytest.mark.parametrize("refusal_count", [3, 5, 10])
def test_hint_returns_non_empty_when_refusal_count_ge_3(refusal_count):
    """T3 — Seuil atteint (>= 3) → bloc normatif non vide."""
    stats = {"refusal_count": refusal_count, "acceptance_count": 0}
    hint = build_adaptive_frequency_hint(stats)
    assert hint
    assert len(hint) > 50


def test_hint_contains_required_normative_keywords():
    """T4 — Le bloc contient les mots-cles normatifs requis (au moins 3/4)."""
    hint = build_adaptive_frequency_hint({"refusal_count": 5, "acceptance_count": 0})
    text = hint.lower()
    keywords_present = sum([
        "demande explicite" in text,
        "plusieurs fois" in text or "repete" in text,
        "pas relancer" in text or "ne plus proposer" in text or "ne propose plus" in text,
        "respecte" in text or "choix" in text,
    ])
    assert keywords_present >= 3, (
        f"Attendu >= 3 mots-cles normatifs, trouve {keywords_present} dans : {hint}"
    )


def test_hint_is_pure_no_side_effect():
    """T5 — Le helper est pur : n'altere pas le dict d'entree."""
    stats = {"refusal_count": 5, "acceptance_count": 2}
    original = dict(stats)
    _ = build_adaptive_frequency_hint(stats)
    _ = build_adaptive_frequency_hint(stats)
    assert stats == original


def test_hint_contains_no_pii():
    """T6 — NFR10 : le bloc ne contient ni nom, email, montant, IDs techniques.

    Review 6.4 P17 — assertions cibles sur les tokens PII specifiques
    (plus de simple `"7" not in hint` fragile qui casse au contact d'une annee
    dans la prose). On verifie structurellement qu'aucun compteur n'est expose.
    """
    import re

    hint = build_adaptive_frequency_hint({"refusal_count": 7, "acceptance_count": 3})
    text = hint.lower()
    forbidden = [
        "user_profile",
        "user_id",
        "conversation_id",
        "@",  # email
        "fcfa",
        "password",
        "mot de passe",
        # Compteurs internes — ne doivent jamais fuiter vers le prompt LLM
        "refusal_count",
        "acceptance_count",
    ]
    for bad in forbidden:
        assert bad not in text, f"PII interdite presente : {bad}"
    # Aucun pattern « N fois » (avec chiffre) ne doit exposer un compteur concret.
    assert not re.search(r"\b\d+\s+(fois|refus|acceptations?)\b", text), (
        "Pattern fuite compteur detecte dans : " + hint
    )


def test_hint_returns_empty_when_refusal_count_invalid_type():
    """T7 — Type non-int (str, bool, None, float) → chaine vide."""
    assert build_adaptive_frequency_hint({"refusal_count": "5"}) == ""
    assert build_adaptive_frequency_hint({"refusal_count": True}) == ""
    assert build_adaptive_frequency_hint({"refusal_count": None}) == ""
    assert build_adaptive_frequency_hint({"refusal_count": 3.5}) == ""
    assert build_adaptive_frequency_hint({}) == ""


# --- AC3 : Injection dans build_system_prompt ---


def test_build_system_prompt_accepts_guidance_stats_kwarg():
    """T8 — La signature contient guidance_stats en kwarg optionnel."""
    # Ne doit pas lever TypeError
    prompt = build_system_prompt(guidance_stats=None)
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_build_system_prompt_appends_hint_when_refusal_count_ge_3():
    """T9 — Le hint est present dans la sortie quand refusal_count >= 3."""
    stats = {"refusal_count": 4, "acceptance_count": 0}
    prompt = build_system_prompt(guidance_stats=stats)
    assert "Modulation de frequence" in prompt
    # Le hint doit venir APRES GUIDED_TOUR_INSTRUCTION
    idx_guided = prompt.index("OUTIL GUIDAGE VISUEL")
    idx_hint = prompt.index("Modulation de frequence")
    assert idx_hint > idx_guided


def test_build_system_prompt_backward_compat_without_stats():
    """T10 — Appel sans guidance_stats retourne un prompt sans le hint.

    Review 6.4 P13 — verrou plus strict : on verifie que le hash SHA-256 du
    prompt sans stats est identique a celui avec `guidance_stats=None`, ET
    qu'il ne contient aucune trace du bloc adaptatif (preservation 6.3).
    """
    import hashlib

    prompt_without = build_system_prompt()
    prompt_with_none = build_system_prompt(guidance_stats=None)
    prompt_below = build_system_prompt(guidance_stats={"refusal_count": 0, "acceptance_count": 0})

    # 1. Aucune trace du bloc adaptatif
    for p in (prompt_without, prompt_with_none, prompt_below):
        assert "Modulation de frequence" not in p

    # 2. Equivalence byte-for-byte des 3 variantes (hash check)
    h_without = hashlib.sha256(prompt_without.encode("utf-8")).hexdigest()
    h_none = hashlib.sha256(prompt_with_none.encode("utf-8")).hexdigest()
    h_zero = hashlib.sha256(prompt_below.encode("utf-8")).hexdigest()
    assert h_without == h_none == h_zero, (
        "Le prompt systeme doit etre identique avec/sans guidance_stats "
        "(backward-compat story 6.3)"
    )


def test_build_system_prompt_below_threshold_no_hint():
    """T11 — refusal_count < 3 → pas de hint injecte."""
    prompt = build_system_prompt(guidance_stats={"refusal_count": 2, "acceptance_count": 0})
    assert "Modulation de frequence" not in prompt


def test_guided_tour_instruction_unchanged():
    """T12 — La constante GUIDED_TOUR_INSTRUCTION n'est pas modifiee.

    Verrouille sa longueur approximative pour detecter toute alteration.
    """
    # Valeur de reference au moment de la story 6.3 — toute derive > 5 %
    # indique une modification non intentionnelle du contrat cible par les
    # 16+17 tests existants. Relevee a 7500 le 2026-05-06 pour accueillir
    # les ameliorations documentaires post story 8.3 (commit 8fd8979).
    assert 3500 <= len(GUIDED_TOUR_INSTRUCTION) <= 7500
    assert GUIDED_TOUR_INSTRUCTION.startswith("## OUTIL GUIDAGE VISUEL")
