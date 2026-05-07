"""F23 — Exceptions métier du module Skills."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.modules.skills.schemas import SkillEvalReport


class SkillNotFoundError(Exception):
    """La Skill n'existe pas (id inconnu)."""

    def __init__(self, skill_id: UUID) -> None:
        self.skill_id = skill_id
        super().__init__(f"Skill not found: {skill_id}")


class InsufficientGoldenExamplesError(Exception):
    """Moins de 5 golden_examples → eval gating impossible."""

    def __init__(self, actual: int, minimum: int = 5) -> None:
        self.actual = actual
        self.minimum = minimum
        super().__init__(
            f"Insufficient golden_examples: {actual} (minimum required: {minimum})"
        )


class EvalGatingFailedError(Exception):
    """Le rapport eval n'atteint pas le seuil de réussite (gate failed)."""

    def __init__(self, report: "SkillEvalReport") -> None:
        self.report = report
        super().__init__(
            f"Eval gate failed: success_rate={report.success_rate:.2f} "
            f"< threshold={report.threshold:.2f}"
        )


class EvalTimeoutError(Exception):
    """Le run d'eval a dépassé le timeout global."""

    def __init__(self, elapsed_seconds: float) -> None:
        self.elapsed_seconds = elapsed_seconds
        super().__init__(f"Eval timeout after {elapsed_seconds:.1f}s")


class SkillToolMismatchError(Exception):
    """Le whitelist d'une skill ne contient aucun tool connu (validator)."""

    def __init__(
        self,
        skill_name: str,
        base_tools: list[str] | None = None,
        whitelist: list[str] | None = None,
    ) -> None:
        self.skill_name = skill_name
        self.base_tools = base_tools or []
        self.whitelist = whitelist or []
        super().__init__(
            f"Skill '{skill_name}' tool_whitelist incompatible (whitelist={whitelist}, "
            f"available={base_tools})"
        )


class InjectionDetectedError(Exception):
    """Le validator a détecté un pattern d'injection dans prompt_expert."""

    def __init__(self, detected_patterns: list[str]) -> None:
        self.detected_patterns = detected_patterns
        super().__init__(
            f"Prompt injection patterns detected: {detected_patterns}"
        )


class TokensLimitExceededError(Exception):
    """Le champ dépasse la limite de tokens autorisée."""

    def __init__(self, field: str, actual: int, max_tokens: int) -> None:
        self.field = field
        self.actual = actual
        self.max_tokens = max_tokens
        super().__init__(
            f"Field '{field}' exceeds {max_tokens} tokens (actual: {actual})"
        )


class SourceNotFoundError(Exception):
    """Une Source référencée par UUID n'existe pas."""

    def __init__(self, source_id: UUID) -> None:
        self.source_id = source_id
        super().__init__(f"Source not found: {source_id}")


class SourceNotVerifiedError(Exception):
    """Une Source référencée n'est pas en état 'verified'."""

    def __init__(self, source_id: UUID, current_status: str) -> None:
        self.source_id = source_id
        self.current_status = current_status
        super().__init__(
            f"Source {source_id} is not verified (current status: {current_status})"
        )


class UnknownToolError(Exception):
    """Le tool_whitelist contient un nom de tool inconnu."""

    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"Unknown tool name: {tool_name!r}")
