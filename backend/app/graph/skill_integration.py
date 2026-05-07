"""F23 — Helper d'intégration LangGraph pour les Skills.

Centralise l'enchaînement « load_skills_for_context → fuse_prompt →
select_tools_with_skills → snapshot state[active_skills] » utilisé par les
7 nœuds spécialisés.

Usage type dans un nœud :

    from app.graph.skill_integration import apply_skills_to_node

    fused_prompt, filtered_tools, active_skills = await apply_skills_to_node(
        base_prompt=full_prompt,
        base_tools=filtered_tools,
        state=state,
        intent=last_user_message,
        db=db,
        offer_id=state.get("active_entities", {}).get("offer_id"),
        fund_id=state.get("active_entities", {}).get("fund_id"),
        intermediary_id=state.get("active_entities", {}).get("intermediary_id"),
    )

Ce helper est tolérant aux erreurs : en cas d'absence de skills publiées,
de problème BDD ou de SkillToolMismatchError, il dégrade vers le
comportement original (base_prompt + base_tools + active_skills=None).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.prompt_fusion import (
    SkillToolMismatchError,
    fuse_prompt,
    select_tools_with_skills,
)
from app.graph.skill_loader import load_skills_for_context
from app.graph.state import ConversationState

logger = logging.getLogger(__name__)


def _extract_active_entity(state: ConversationState, key: str) -> str | None:
    """Extrait un id de ``state['active_entities']`` (tolérant aux types)."""
    entities = state.get("active_entities") or {}
    if not isinstance(entities, dict):
        return None
    val = entities.get(key)
    return str(val) if val else None


async def apply_skills_to_node(
    *,
    base_prompt: str,
    base_tools: list[Any],
    state: ConversationState,
    intent: str | None,
    db: AsyncSession | None,
) -> tuple[str, list[Any], list[dict[str, Any]] | None]:
    """Applique skill_loader + fusion + intersection à un nœud.

    Args:
        base_prompt: System prompt déjà construit par le nœud.
        base_tools: Liste de tools déjà filtrés par select_tools_for_node.
        state: État LangGraph courant.
        intent: Dernier message utilisateur (pour matching intent_keywords).
        db: Session async (None → bypass total, retour identité).

    Returns:
        ``(fused_prompt, intersected_tools, active_skills_snapshot)``.
        ``active_skills_snapshot`` vaut ``None`` si aucune skill chargée.
    """
    if db is None:
        return base_prompt, list(base_tools), None

    try:
        skills = await load_skills_for_context(
            page_slug=state.get("current_page"),
            active_module=state.get("active_module"),
            intent=intent,
            offer_id=_extract_active_entity(state, "offer_id"),
            fund_id=_extract_active_entity(state, "fund_id"),
            intermediary_id=_extract_active_entity(state, "intermediary_id"),
            db=db,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[skill_integration] load_skills_for_context a échoué : %s — bypass",
            exc,
        )
        return base_prompt, list(base_tools), None

    if not skills:
        return base_prompt, list(base_tools), None

    try:
        fused = await fuse_prompt(base_prompt, skills, db)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[skill_integration] fuse_prompt a échoué : %s — fallback base_prompt",
            exc,
        )
        fused = base_prompt

    try:
        intersected = select_tools_with_skills(base_tools, skills, allow_fallback=True)
    except SkillToolMismatchError as exc:
        logger.warning(
            "[skill_integration] tool intersection vide : %s — fallback base_tools",
            exc,
        )
        intersected = list(base_tools)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[skill_integration] select_tools a échoué : %s — fallback base_tools",
            exc,
        )
        intersected = list(base_tools)

    snapshot = [
        {
            "id": str(s.id),
            "name": s.name,
            "version": s.version,
        }
        for s in skills
    ]
    return fused, intersected, snapshot
