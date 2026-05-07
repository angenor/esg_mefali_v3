"""F23 — Helper d'invocation graphe pour ``eval_runner``.

Module séparé pour faciliter le mocking dans les tests unitaires.

En production, cette fonction invoque réellement le graphe LangGraph avec
un contexte construit à partir du cas du golden_examples. Pour les tests
unitaires, on stube ``app.modules.skills.eval_runner._invoke_llm_for_case``
qui appelle ce helper.

Note MVP F23 : l'implémentation production complète (avec checkpointer
isolé, dry-run mode, etc.) est définie dans le plan technique mais le runner
unitaire n'a besoin que d'un retour fallback safe (pas d'invocation réelle
sans clé OpenRouter ni contexte BDD complet).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from app.models.skill import Skill

logger = logging.getLogger(__name__)


async def invoke_graph_for_case(
    case: dict[str, Any],
    skill: Skill,
) -> tuple[str | None, dict[str, Any]]:
    """Invoque le graphe LangGraph pour un cas et retourne ``(tool_called, payload)``.

    En production : construit un :class:`ConversationState`, appelle le nœud
    correspondant à ``skill.domain``, capture le tool effectivement invoqué.

    Pour le MVP F23, en l'absence d'une clé OpenRouter active OU dans un
    environnement de test/CI sans LLM, retourne un fallback safe ``(None, {})``.
    Le test gating réel passe par la calibration manuelle de la skill.
    """
    if not os.environ.get("OPENROUTER_API_KEY"):
        logger.info(
            "[eval_runner] OPENROUTER_API_KEY absent — retour fallback (None, {})"
        )
        return (None, {})

    # En production, on appellerait ici le graphe via streamlit_invoke ou similaire.
    # Pour limiter le scope MVP F23, on log et on retourne un fallback safe ;
    # l'implémentation complète sera ajoutée dans un futur PR (F23.5).
    logger.warning(
        "[eval_runner] invocation réelle du graphe non implémentée en MVP F23 ; "
        "retour fallback (None, {})"
    )
    return (None, {})
