"""F23 — Validator du payload SkillCreate / SkillUpdate.

Valide :
- Cap tokens (prompt_expert ≤ 5000, procedure ≤ 3000) via tiktoken.
- Anti-injection (cf. ``app.core.prompt_injection_detector``).
- Tool whitelist : tous les noms doivent appartenir à ``ALL_TOOL_NAMES``.
- Sources : tous les UUIDs doivent référencer une Source ``verified``.

Référence : ``specs/033-skills-playbooks-metier/data-model.md`` validators.
"""

from __future__ import annotations

import logging
from uuid import UUID

import tiktoken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.prompt_injection_detector import detect_injection_patterns
from app.models.source import Source, VerificationStatus
from app.modules.skills.exceptions import (
    InjectionDetectedError,
    SourceNotFoundError,
    SourceNotVerifiedError,
    TokensLimitExceededError,
    UnknownToolError,
)
from app.modules.skills.schemas import SkillCreate, SkillUpdate

logger = logging.getLogger(__name__)


# Caps tokens (cf. data-model.md).
PROMPT_EXPERT_MAX_TOKENS: int = 5_000
PROCEDURE_MAX_TOKENS: int = 3_000


# Encoder cl100k_base partagé.
_ENCODER: tiktoken.Encoding | None = None


def _get_encoder() -> tiktoken.Encoding:
    global _ENCODER
    if _ENCODER is None:
        _ENCODER = tiktoken.get_encoding("cl100k_base")
    return _ENCODER


def _count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_get_encoder().encode(text))


def _collect_all_tool_names() -> set[str]:
    """Énumère TOUS les noms de tools LangChain enregistrés dans l'application.

    Lazy import : on ne charge les modules tools qu'à l'appel pour éviter les
    cycles d'import au boot.
    """
    from app.graph.tools.action_plan_tools import ACTION_PLAN_TOOLS
    from app.graph.tools.application_tools import APPLICATION_TOOLS
    from app.graph.tools.carbon_tools import CARBON_TOOLS
    from app.graph.tools.chat_tools import CHAT_TOOLS
    from app.graph.tools.credit_tools import CREDIT_TOOLS
    from app.graph.tools.document_tools import DOCUMENT_TOOLS
    from app.graph.tools.esg_tools import ESG_TOOLS
    from app.graph.tools.financing_tools import FINANCING_TOOLS
    from app.graph.tools.guided_tour_tools import GUIDED_TOUR_TOOLS
    from app.graph.tools.interactive_tools import INTERACTIVE_TOOLS
    from app.graph.tools.memory_tools import MEMORY_TOOLS
    from app.graph.tools.profiling_tools import PROFILING_TOOLS
    from app.graph.tools.project_tools import PROJECT_TOOLS
    from app.graph.tools.sourcing_tools import SOURCING_TOOLS
    from app.graph.tools.visualization_tools import VISUALIZATION_TOOLS

    all_groups = (
        ACTION_PLAN_TOOLS,
        APPLICATION_TOOLS,
        CARBON_TOOLS,
        CHAT_TOOLS,
        CREDIT_TOOLS,
        DOCUMENT_TOOLS,
        ESG_TOOLS,
        FINANCING_TOOLS,
        GUIDED_TOUR_TOOLS,
        INTERACTIVE_TOOLS,
        MEMORY_TOOLS,
        PROFILING_TOOLS,
        PROJECT_TOOLS,
        SOURCING_TOOLS,
        VISUALIZATION_TOOLS,
    )
    names: set[str] = set()
    for group in all_groups:
        for tool in group:
            tool_name = getattr(tool, "name", None) or getattr(tool, "__name__", None)
            if tool_name:
                names.add(tool_name)
    return names


async def _validate_tokens(payload_dict: dict) -> None:
    prompt_expert = payload_dict.get("prompt_expert")
    if prompt_expert:
        n = _count_tokens(prompt_expert)
        if n > PROMPT_EXPERT_MAX_TOKENS:
            raise TokensLimitExceededError(
                "prompt_expert", n, PROMPT_EXPERT_MAX_TOKENS
            )
    procedure = payload_dict.get("procedure")
    if procedure:
        n = _count_tokens(procedure)
        if n > PROCEDURE_MAX_TOKENS:
            raise TokensLimitExceededError("procedure", n, PROCEDURE_MAX_TOKENS)


async def _validate_anti_injection(payload_dict: dict) -> None:
    for field in ("prompt_expert", "procedure"):
        text = payload_dict.get(field)
        if not text:
            continue
        patterns = detect_injection_patterns(text)
        if patterns:
            logger.warning(
                "[skills.validator] injection patterns détectés sur '%s' : %s",
                field,
                patterns,
            )
            raise InjectionDetectedError(patterns)


async def _validate_tool_whitelist(payload_dict: dict) -> None:
    whitelist = payload_dict.get("tool_whitelist")
    if not whitelist:
        return
    known = _collect_all_tool_names()
    for tool_name in whitelist:
        if tool_name not in known:
            raise UnknownToolError(tool_name)


async def _validate_sources(payload_dict: dict, db: AsyncSession) -> None:
    sources_ids = payload_dict.get("sources") or []
    if not sources_ids:
        return
    # Normalisation UUID.
    normalized: list[UUID] = []
    for raw in sources_ids:
        try:
            normalized.append(UUID(str(raw)))
        except (ValueError, TypeError) as exc:
            raise SourceNotFoundError(raw) from exc
    if not normalized:
        return
    stmt = select(Source).where(Source.id.in_(normalized))
    result = await db.execute(stmt)
    found = {s.id: s for s in result.scalars().all()}
    for sid in normalized:
        if sid not in found:
            raise SourceNotFoundError(sid)
        src = found[sid]
        if src.verification_status != VerificationStatus.VERIFIED.value:
            raise SourceNotVerifiedError(sid, src.verification_status)


async def validate_skill_payload(
    payload: SkillCreate | SkillUpdate,
    db: AsyncSession,
) -> None:
    """Lance toutes les validations métier sur le payload.

    Lève :
    - :class:`TokensLimitExceededError`
    - :class:`InjectionDetectedError`
    - :class:`UnknownToolError`
    - :class:`SourceNotFoundError`
    - :class:`SourceNotVerifiedError`

    En cas de succès, retourne ``None``.
    """
    payload_dict = payload.model_dump(exclude_unset=True, mode="python")
    await _validate_tokens(payload_dict)
    await _validate_anti_injection(payload_dict)
    await _validate_tool_whitelist(payload_dict)
    await _validate_sources(payload_dict, db)
