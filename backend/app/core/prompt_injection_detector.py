"""F23 — Détecteur d'injection prompt (US5).

Patterns OWASP LLM Top 10 (LLM01:2023 Prompt Injection) appliqués au champ
``prompt_expert`` d'une Skill au moment du save. Approche regex first :
rapide, déterministe, auditable. Faux positifs acceptés ; le validator
remonte une erreur 422 avec ``detected_patterns`` pour que l'admin reformule.

Référence design : ``specs/033-skills-playbooks-metier/research.md`` R3.
"""

from __future__ import annotations

import re

# Liste de patterns initiaux (insensibles à la casse). Évolutif : ajouter
# de nouveaux patterns ici incrémente automatiquement la couverture du validator.
INJECTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "ignore_previous_instructions": re.compile(
        r"ignore\s+(all\s+)?previous\s+instructions?",
        re.IGNORECASE,
    ),
    "new_role": re.compile(
        r"tu\s+es\s+désormais|you\s+are\s+now\s+a",
        re.IGNORECASE,
    ),
    "system_prompt_leak": re.compile(
        r"reveal\s+(your\s+)?(system\s+)?prompt|affiche\s+(le\s+)?prompt\s+système",
        re.IGNORECASE,
    ),
    "user_is_admin": re.compile(
        r"\b(user|i)\s+(am|is)\s+admin\b",
        re.IGNORECASE,
    ),
    "forget_everything": re.compile(
        r"forget\s+(everything|all)",
        re.IGNORECASE,
    ),
    "override_instructions": re.compile(
        r"override\s+(your\s+)?instructions?",
        re.IGNORECASE,
    ),
    "system_tag": re.compile(
        r"<\s*system\s*>",
        re.IGNORECASE,
    ),
    "developer_mode": re.compile(
        r"developer\s+mode|mode\s+développeur",
        re.IGNORECASE,
    ),
    "jailbreak_keywords": re.compile(
        r"\bDAN\b|\bjailbreak\b",
        re.IGNORECASE,
    ),
    "prompt_extraction": re.compile(
        r"repeat\s+(the\s+)?(initial|first)\s+(message|prompt|instructions?)",
        re.IGNORECASE,
    ),
}


def detect_injection_patterns(text: str) -> list[str]:
    """Retourne la liste (déduplicée, ordre stable) des noms de patterns matchés.

    Args:
        text: Texte brut à analyser (typiquement ``prompt_expert`` d'une Skill).

    Returns:
        Liste des noms de patterns matchés, dans l'ordre du catalogue. Liste
        vide si aucun pattern détecté ou texte vide.

    Examples:
        >>> detect_injection_patterns("Ignore previous instructions")
        ['ignore_previous_instructions']
        >>> detect_injection_patterns("Texte normal sur ESG")
        []
    """
    if not text:
        return []
    return [
        name
        for name, pattern in INJECTION_PATTERNS.items()
        if pattern.search(text) is not None
    ]
