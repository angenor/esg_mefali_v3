"""Tests du flux de consentement + declenchement direct dans GUIDED_TOUR_INSTRUCTION.

Story 6.3 — verrouille le contenu normatif du prompt cote LLM pour :
 * Proposer un consentement `ask_interactive_question` AVANT `trigger_guided_tour`
   apres la completion d'un module (AC1).
 * Declencher directement `trigger_guided_tour` sur demande explicite (AC4).
 * Privilegier le consentement en cas d'intent ambigu (AC5).
 * Ne pas insister en cas de refus (AC3).

Pattern : tests deterministes sur le CONTENU du prompt — pas de LLM reel.
Les tests end-to-end du dialogue LLM sont portes par l'epic 8.
"""

from __future__ import annotations

import pytest

from app.prompts.guided_tour import GUIDED_TOUR_INSTRUCTION


# --- Helpers ---


def _post_module_section(text: str) -> str:
    """Extrait la section post-module (proposition) du prompt.

    Supporte 2 ancres (pre- et post-renommage de la regle 1) :
     - Ancienne : « Apres un module (proposition) »
     - Nouvelle (commit 8fd8979 du 2026-04-16) :
       « Proposition de guidage (post-module OU en cours d'echange) »

    On cherche la premiere ancre presente. L'ancre de fin reste
    « Sur demande explicite (declenchement direct) ».
    """
    candidates = [
        "Proposition de guidage (post-module",
        "Apres un module (proposition)",
    ]
    start = -1
    for anchor in candidates:
        idx = text.find(anchor)
        if idx != -1:
            start = idx
            break
    assert start != -1, (
        "Aucune ancre de section post-module trouvee — "
        "la section normative de consentement a ete renommee ou supprimee. "
        f"Ancres testees : {candidates}"
    )
    end = text.find("Sur demande explicite (declenchement direct)", start)
    assert end != -1, (
        "Ancre « Sur demande explicite (declenchement direct) » introuvable — "
        "verifier l'integrite de la section normative."
    )
    return text[start:end]


# --- T-AC1a : chaines exactes du consentement ---


def test_instruction_contains_consent_exact_strings():
    """T-AC1a — labels Oui/Non + options yes/no + tool name presents."""
    expected = [
        "Oui, montre-moi",
        "Non merci",
        '"yes"',
        '"no"',
        "ask_interactive_question",
    ]
    missing = [kw for kw in expected if kw not in GUIDED_TOUR_INSTRUCTION]
    assert not missing, f"Chaines de consentement manquantes : {missing}"


# --- T-AC1b : ordre normatif ask avant trigger dans la section post-module ---


def test_ask_interactive_question_before_trigger_in_post_module_section():
    """T-AC1b — dans la section post-module, ask_interactive_question
    DOIT apparaitre avant trigger_guided_tour (ordre = consentement d'abord).
    """
    section = _post_module_section(GUIDED_TOUR_INSTRUCTION)
    idx_ask = section.find("ask_interactive_question")
    idx_trigger = section.find("trigger_guided_tour")
    assert idx_ask != -1, (
        "ask_interactive_question absent de la section post-module"
    )
    assert idx_trigger != -1, (
        "trigger_guided_tour absent de la section post-module"
    )
    assert idx_ask < idx_trigger, (
        f"Ordre incorrect dans la section post-module : "
        f"ask_interactive_question (pos {idx_ask}) doit preceder "
        f"trigger_guided_tour (pos {idx_trigger})."
    )


def test_post_module_section_links_yes_to_trigger_guided_tour():
    """T-AC1b (renforce) — la section post-module contient la phrase
    canonique liant le choix `yes` a l'appel `trigger_guided_tour`.

    Un simple ordre positionnel ask→trigger ne suffit pas : il faut
    l'enchainement semantique « si yes alors trigger » explicitement
    ecrit, sinon le LLM peut reordonner la narration sans casser le test.
    """
    section = _post_module_section(GUIDED_TOUR_INSTRUCTION).lower()
    # Accepter plusieurs formulations equivalentes du lien conditionnel
    canonical_patterns = [
        ("choisit", "yes", "trigger_guided_tour"),
        ("yes", "tour suivant", "trigger_guided_tour"),
    ]
    matched = any(
        all(token in section for token in pattern)
        for pattern in canonical_patterns
    )
    assert matched, (
        "La section post-module ne lie pas explicitement le choix `yes` a "
        "l'appel `trigger_guided_tour`. Attendu une phrase du type "
        "« si l'utilisateur choisit `yes` au tour suivant, appelle alors "
        "`trigger_guided_tour` »."
    )


# --- T-AC4a : verbes-indicateurs d'intent explicite ---


EXPLICIT_VERBS = ["montre", "guide", "visualise", "fais-moi visiter", "où sont"]


@pytest.mark.parametrize("verb", EXPLICIT_VERBS)
def test_each_explicit_verb_present(verb: str):
    """T-AC4a (par verbe) — chaque verbe-indicateur est documente.

    On normalise en minuscules : le prompt peut ouvrir une phrase par
    une capitale sans invalider la regle.
    """
    assert verb in GUIDED_TOUR_INSTRUCTION.lower(), (
        f"Verbe d'intent explicite manquant : « {verb} »"
    )


def test_at_least_three_explicit_verbs_present():
    """T-AC4a (plancher) — au moins 3 des 5 verbes doivent etre presents.

    Garde-fou en cas de reformulation partielle du prompt — le plancher
    `>= 3` laisse une marge tout en refusant une suppression massive.
    """
    text = GUIDED_TOUR_INSTRUCTION.lower()
    found = [v for v in EXPLICIT_VERBS if v in text]
    assert len(found) >= 3, (
        f"Moins de 3 verbes-indicateurs trouves : {found} "
        f"(liste attendue : {EXPLICIT_VERBS})"
    )


# --- T-AC4b : mapping tour_id -> mot-cle (OR semantique) ---


TOUR_ID_KEYWORDS: list[tuple[str, list[str]]] = [
    ("show_esg_results", ["ESG"]),
    ("show_carbon_results", ["carbone"]),
    ("show_financing_catalog", ["fonds", "financement"]),
    ("show_credit_score", ["credit"]),
    ("show_action_plan", ["plan d'action", "feuille de route"]),
    ("show_dashboard_overview", ["tableau de bord", "dashboard", "vue d'ensemble"]),
]


@pytest.mark.parametrize("tour_id,keywords", TOUR_ID_KEYWORDS)
def test_tour_id_has_mapping_keyword(tour_id: str, keywords: list[str]):
    """T-AC4b — chaque tour_id est associe a au moins un mot-cle
    semantique dans le prompt. On exige la presence simultanee du tour_id
    ET d'au moins un des mots-cles associes.
    """
    assert tour_id in GUIDED_TOUR_INSTRUCTION, (
        f"tour_id absent du prompt : {tour_id}"
    )
    matched = [kw for kw in keywords if kw in GUIDED_TOUR_INSTRUCTION]
    assert matched, (
        f"Aucun mot-cle associe a {tour_id} n'est present dans le prompt. "
        f"Attendu au moins un parmi : {keywords}"
    )


# --- T-AC5 : prudence intent ambigu ---


def test_prompt_mentions_ambiguous_intent_fallback():
    """T-AC5 — le prompt documente la regle « ambigu → consentement ».

    Requiert : mot `explicite` + au moins un marqueur de prudence
    (`ambigu`, `doute`, `privilegie`, `prudence`).
    """
    text = GUIDED_TOUR_INSTRUCTION.lower()
    assert "explicite" in text, (
        "Mot-cle « explicite » absent — le prompt doit qualifier les "
        "intents declenchant le tour direct."
    )
    prudence_markers = ["ambigu", "doute", "privilegie", "prudence"]
    found = [m for m in prudence_markers if m in text]
    assert found, (
        f"Aucun marqueur de prudence trouve (attendu parmi {prudence_markers})"
    )


# --- T-AC3 : pas de relance insistante ---


def test_prompt_has_no_aggressive_relance_keywords():
    """T-AC3 — verification negative : le prompt ne contient aucun mot-cle
    de relance insistante apres un refus (respect du choix utilisateur).

    Liste elargie pour couvrir les variantes usuelles (insistant, relance,
    repropose, propose a nouveau) — le test 6.3 initial etait trop etroit.
    """
    text = GUIDED_TOUR_INSTRUCTION.lower()
    forbidden = [
        "insiste",
        "insistant",
        "reprends",
        "redemande",
        "relance",
        "repropose",
        "propose a nouveau",
    ]
    hits = [kw for kw in forbidden if kw in text]
    assert not hits, (
        f"Le prompt contient des mots-cles de relance insistante : {hits} — "
        f"story 6.3 impose de ne pas relancer un utilisateur qui a refuse."
    )


# --- Presence du lien option yes -> trigger_guided_tour (cas AC2) ---


def test_prompt_links_yes_answer_to_trigger_tour():
    """T-AC2 (indirect) — le prompt rend explicite le lien
    « si l'utilisateur choisit yes au tour suivant → trigger_guided_tour ».

    Ce lien est critique : sans lui, le LLM pourrait repondre en texte libre
    au lieu d'appeler le tool apres un `yes`.
    """
    text = GUIDED_TOUR_INSTRUCTION.lower()
    # Deux formes acceptees : « choisit yes » ou « yes au tour suivant »
    has_linkage = (
        ("yes" in text and "tour suivant" in text)
        or ("yes" in text and "trigger_guided_tour" in text)
    )
    assert has_linkage, (
        "Le prompt ne relie pas explicitement le choix `yes` a l'appel "
        "`trigger_guided_tour` au tour suivant."
    )
