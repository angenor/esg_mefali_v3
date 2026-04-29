"""Selecteur de tools par contexte de page (story 10.2).

Helper pur (pas d'I/O, pas d'appel LLM) qui filtre la liste des tools
exposes au LLM via `bind_tools(...)` en fonction de :

- la page courante (`current_page`, deja transmis par le frontend) ;
- le noeud LangGraph en cours d'execution (fallback) ;
- une whitelist transverse (`GLOBAL_WHITELIST`).

Le `ToolNode` cote graphe garde TOUJOURS la liste complete par module : on
filtre uniquement ce que le LLM voit, jamais ce que le ToolNode peut executer.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool

from app.graph.tool_selector_config import (
    GLOBAL_WHITELIST,
    MAX_TOOLS_PER_TURN,
    MODULE_TOOL_MAPPING,
    PAGE_TOOL_MAPPING,
    normalize_page,
)

logger = logging.getLogger("app.graph.tool_selector")


def select_tools_for_node(
    node_name: str,
    current_page: str | None,
    all_tools: list[BaseTool],
    active_entities: dict[str, Any] | None = None,
) -> tuple[list[BaseTool], dict[str, Any]]:
    """Filtrer la liste de tools a exposer au LLM pour ce tour.

    Args:
        node_name: Nom du noeud LangGraph appelant (ex `esg_scoring`).
        current_page: Page courante (path Nuxt brut ou slug canonique). Peut
            etre None.
        all_tools: Catalogue complet des tools potentiellement disponibles
            pour ce noeud (typiquement `MODULE_TOOLS + INTERACTIVE_TOOLS +
            GUIDED_TOUR_TOOLS`).
        active_entities: Reserve V2. Accepte mais ignore pour le moment.

    Returns:
        Tuple `(tools_filtres, debug_info)` ou debug_info contient :
        - `tools_offered: list[str]` : noms des tools effectivement retenus.
        - `page_slug: str | None` : slug normalise (None si page inconnue).
        - `fallback_used: bool` : True si MODULE_TOOL_MAPPING a ete utilise.
        - `truncated: bool` : True si une troncature a ete necessaire.
    """
    # `active_entities` est volontairement ignore en V1 (cf. story 10.2 §2).
    _ = active_entities

    available_by_name: dict[str, BaseTool] = {t.name: t for t in all_tools}
    available_names: set[str] = set(available_by_name)

    # (a) Normaliser current_page -> slug.
    slug = normalize_page(current_page)

    # (b)(c) Choix de la base.
    fallback_used = False
    if slug is not None and slug in PAGE_TOOL_MAPPING:
        base_names = set(PAGE_TOOL_MAPPING[slug])
    else:
        base_names = set(MODULE_TOOL_MAPPING.get(node_name, frozenset()))
        fallback_used = True

    # Restreindre aux tools effectivement disponibles dans le catalogue passe.
    base_names &= available_names

    # (d) Ajouter la whitelist transverse (limite aux tools dispos).
    base_names |= (GLOBAL_WHITELIST & available_names)

    # (e) Troncature deterministe si la base depasse MAX_TOOLS_PER_TURN.
    truncated = False
    if len(base_names) > MAX_TOOLS_PER_TURN:
        truncated = True
        whitelist_present = sorted(base_names & GLOBAL_WHITELIST)
        rest = sorted(base_names - GLOBAL_WHITELIST)
        budget = MAX_TOOLS_PER_TURN - len(whitelist_present)
        kept = set(whitelist_present) | set(rest[: max(budget, 0)])
        logger.warning(
            "tool_selector.truncated node=%s slug=%s requested=%d kept=%d",
            node_name, slug, len(base_names), len(kept),
        )
        base_names = kept

    # (f) Materialiser les BaseTool dans un ordre stable (tri par nom).
    ordered_names = sorted(base_names)
    selected: list[BaseTool] = [available_by_name[n] for n in ordered_names]

    # Invariant runtime — un depassement signifie un bug dans le filtrage.
    assert len(selected) <= MAX_TOOLS_PER_TURN, (
        f"select_tools_for_node a retourne {len(selected)} tools "
        f"(>{MAX_TOOLS_PER_TURN}) — bug du selecteur."
    )

    debug_info: dict[str, Any] = {
        "tools_offered": [t.name for t in selected],
        "page_slug": slug,
        "fallback_used": fallback_used,
        "truncated": truncated,
    }
    return selected, debug_info
