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
        - `fallback_used: bool` : True si la page est inconnue (on s'appuie
          alors uniquement sur le noeud + la whitelist).
        - `node_tools_included: bool` : True si des tools du noeud (intention)
          ont contribue a la base (F048 D1).
        - `truncated: bool` : True si une troncature a ete necessaire.

    F048 (D1) — Selection pilotee par l'intention : la base est l'UNION des
    tools de la page (contexte d'affichage) ET des tools du noeud LangGraph en
    cours d'execution (= intention classifiee par le routeur F013), plus la
    whitelist transverse. ``create_fund_application`` survit ainsi des que le
    routeur route vers le noeud ``financing``/``application``, quelle que soit
    la page. En cas de depassement de la borne, la troncature PRIORISE la
    conservation : whitelist > tools du noeud (intention) > tools de page.
    """
    # `active_entities` est volontairement ignore en V1 (cf. story 10.2 §2).
    _ = active_entities

    available_by_name: dict[str, BaseTool] = {t.name: t for t in all_tools}
    available_names: set[str] = set(available_by_name)

    # (a) Normaliser current_page -> slug.
    slug = normalize_page(current_page)

    # (b) Trois ensembles, bornes au catalogue effectivement disponible.
    whitelist_names = GLOBAL_WHITELIST & available_names
    node_names = set(MODULE_TOOL_MAPPING.get(node_name, frozenset())) & available_names
    page_names: set[str] = set()
    if slug is not None and slug in PAGE_TOOL_MAPPING:
        page_names = set(PAGE_TOOL_MAPPING[slug]) & available_names

    # `fallback_used` reste vrai quand aucune page connue n'est resolue : on
    # s'appuie alors sur le noeud + la whitelist (compat. semantique historique).
    fallback_used = slug is None or slug not in PAGE_TOOL_MAPPING
    node_tools_included = bool(node_names)

    # (c) UNION des trois sources (intention + page + transverse).
    base_names = whitelist_names | node_names | page_names

    # (d) Troncature deterministe priorisee si depassement de la borne.
    truncated = False
    if len(base_names) > MAX_TOOLS_PER_TURN:
        truncated = True
        # Priorite de conservation : whitelist > noeud (intention) > page.
        groups = (
            sorted(whitelist_names),
            sorted(node_names - whitelist_names),
            sorted(page_names - whitelist_names - node_names),
        )
        kept: list[str] = []
        for group in groups:
            for name in group:
                if len(kept) >= MAX_TOOLS_PER_TURN:
                    break
                kept.append(name)
        logger.warning(
            "tool_selector.truncated node=%s slug=%s requested=%d kept=%d",
            node_name, slug, len(base_names), len(kept),
        )
        base_names = set(kept[:MAX_TOOLS_PER_TURN])

    # (e) Materialiser les BaseTool dans un ordre stable (tri par nom).
    ordered_names = sorted(base_names)
    selected: list[BaseTool] = [available_by_name[n] for n in ordered_names]

    # Invariant runtime — un depassement signifie un bug dans le filtrage.
    # `raise` explicite (et non `assert`) pour rester actif sous `python -O`
    # (les assertions y sont supprimees) — cf. tool_selector_config._validate_config.
    if len(selected) > MAX_TOOLS_PER_TURN:
        raise RuntimeError(
            f"select_tools_for_node a retourne {len(selected)} tools "
            f"(>{MAX_TOOLS_PER_TURN}) — bug du selecteur."
        )

    debug_info: dict[str, Any] = {
        "tools_offered": [t.name for t in selected],
        "page_slug": slug,
        "fallback_used": fallback_used,
        "node_tools_included": node_tools_included,
        "truncated": truncated,
    }
    return selected, debug_info
