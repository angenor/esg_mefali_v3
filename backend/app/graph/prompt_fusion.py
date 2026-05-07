"""F23 — Fusion prompt + intersection tool whitelist (US2).

Compose le system prompt final en injectant 1 ou 2 sections "SKILL ACTIVE"
au-dessus de la base. Calcule l'intersection des tools de la page avec les
whitelists des skills actives.

Référence : ``specs/033-skills-playbooks-metier/research.md`` R4 (tiktoken),
``data-model.md`` Lifecycle.

Cap budget tokens : si la fusion dépasse ``MAX_TOTAL_TOKENS`` (12 000), on
réduit à 1 skill au lieu de 2 pour éviter de saturer le contexte LLM.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import tiktoken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import Source

logger = logging.getLogger(__name__)


# Cap budget (cf. plan.md "Constraints").
MAX_TOTAL_TOKENS: int = 12_000

# Encoder tiktoken — partagé (init coûteuse).
_ENCODER: tiktoken.Encoding | None = None


def _get_encoder() -> tiktoken.Encoding:
    global _ENCODER
    if _ENCODER is None:
        _ENCODER = tiktoken.get_encoding("cl100k_base")
    return _ENCODER


def _count_tokens(text: str) -> int:
    """Retourne le nombre de tokens (cl100k_base, compatible Claude/GPT-4)."""
    if not text:
        return 0
    return len(_get_encoder().encode(text))


class SkillToolMismatchError(Exception):
    """Levée quand l'intersection ``base_tools ∩ skill.tool_whitelist`` est vide.

    Attributes:
        skill_name: Nom de la skill concernée.
        base_tool_names: Tools disponibles côté nœud.
        whitelist: Tools listés par la skill.
    """

    def __init__(
        self,
        skill_name: str,
        base_tool_names: list[str],
        whitelist: list[str],
    ) -> None:
        self.skill_name = skill_name
        self.base_tool_names = base_tool_names
        self.whitelist = whitelist
        super().__init__(
            f"Aucun tool en commun entre la skill '{skill_name}' "
            f"(whitelist={whitelist}) et le nœud (tools={base_tool_names})"
        )


async def _resolve_sources(
    source_ids: list[Any],
    db: AsyncSession,
) -> list[Source]:
    """Charge les Sources référencées par UUID. Tolère les ids invalides."""
    if not source_ids:
        return []
    valid_uuids: list[uuid.UUID] = []
    for sid in source_ids:
        try:
            valid_uuids.append(uuid.UUID(str(sid)))
        except (ValueError, TypeError):
            logger.warning("[prompt_fusion] source UUID invalide ignoré: %r", sid)
            continue
    if not valid_uuids:
        return []
    stmt = select(Source).where(Source.id.in_(valid_uuids))
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _format_sources_block(sources: list[Source]) -> str:
    if not sources:
        return ""
    lines = ["**Sources de référence :**"]
    for s in sources:
        publisher = getattr(s, "publisher", "—")
        title = getattr(s, "title", "—")
        url = getattr(s, "url", "")
        lines.append(f"- [{publisher}] {title} ({url})".rstrip(" ()"))
    return "\n".join(lines)


def _build_skill_section(skill: Any, sources: list[Source]) -> str:
    """Construit la section ``## SKILL ACTIVE`` pour une skill donnée."""
    parts: list[str] = []
    parts.append(f"## SKILL ACTIVE: {skill.name} (v{skill.version})")
    parts.append("")
    parts.append("**Prompt expert :**")
    parts.append(skill.prompt_expert)
    parts.append("")
    parts.append("**Procédure :**")
    parts.append(skill.procedure)
    sources_block = _format_sources_block(sources)
    if sources_block:
        parts.append("")
        parts.append(sources_block)
    return "\n".join(parts)


async def fuse_prompt(
    base_system_prompt: str,
    skills: list[Any],
    db: AsyncSession,
) -> str:
    """Fusionne ``base_system_prompt`` avec 0, 1 ou 2 sections SKILL ACTIVE.

    Si la somme des tokens (base + skills) dépasse ``MAX_TOTAL_TOKENS``,
    réduit à 1 skill (la première de la liste, qui est la plus spécifique
    selon le loader).

    Args:
        base_system_prompt: System prompt de base (du nœud LangGraph).
        skills: Liste de Skills déjà filtrées par le loader (≤ 2 attendues).
        db: Session SQLAlchemy async pour résoudre les sources.

    Returns:
        System prompt fusionné (string).
    """
    if not skills:
        return base_system_prompt

    base_tokens = _count_tokens(base_system_prompt)

    sections: list[str] = []
    running_tokens = base_tokens
    for skill in skills:
        sources = await _resolve_sources(skill.sources or [], db)
        section = _build_skill_section(skill, sources)
        section_tokens = _count_tokens(section)
        if running_tokens + section_tokens > MAX_TOTAL_TOKENS and sections:
            # On a déjà au moins 1 skill chargée et on dépasse le budget en
            # ajoutant celle-ci → on tronque à ce qui est déjà chargé.
            logger.info(
                "[prompt_fusion] cap budget (%d tokens) atteint après %d skill(s); "
                "skill '%s' ignorée",
                MAX_TOTAL_TOKENS,
                len(sections),
                skill.name,
            )
            break
        sections.append(section)
        running_tokens += section_tokens

    if not sections:
        return base_system_prompt
    return "\n\n".join(sections + [base_system_prompt])


def select_tools_with_skills(
    base_tools: list[Any],
    skills: list[Any],
    *,
    allow_fallback: bool = True,
) -> list[Any]:
    """Calcule l'intersection ``base_tools ∩ ⋃ skill.tool_whitelist``.

    Args:
        base_tools: Tools du nœud (avant intersection).
        skills: Skills actives (≤ 2 attendues).
        allow_fallback: Si True, retourne ``base_tools`` quand l'intersection
            est vide (fallback safe). Si False, lève
            :class:`SkillToolMismatchError`.

    Returns:
        Liste de tools, sous-ensemble de ``base_tools``.
    """
    if not skills:
        return list(base_tools)

    # Union des whitelists.
    union_whitelist: set[str] = set()
    for skill in skills:
        for tool_name in skill.tool_whitelist or []:
            union_whitelist.add(tool_name)

    if not union_whitelist:
        return list(base_tools)

    intersected = [t for t in base_tools if getattr(t, "name", None) in union_whitelist]

    if not intersected:
        # Audit : on a au moins une skill mais rien en commun.
        skill_names = ", ".join(getattr(s, "name", "?") for s in skills)
        base_names = [getattr(t, "name", "?") for t in base_tools]
        whitelist = sorted(union_whitelist)
        if not allow_fallback:
            raise SkillToolMismatchError(skill_names, base_names, whitelist)
        logger.warning(
            "[prompt_fusion] intersection vide pour skills [%s] ; fallback "
            "vers base_tools (whitelist=%s, base=%s)",
            skill_names,
            whitelist,
            base_names,
        )
        return list(base_tools)

    return intersected
