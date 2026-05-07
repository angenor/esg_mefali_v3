"""F23 — Tests unitaires ``app.graph.prompt_fusion`` (T016, US2)."""

from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace

import pytest

from app.graph.prompt_fusion import (
    SkillToolMismatchError,
    _count_tokens,
    fuse_prompt,
    select_tools_with_skills,
)


pytestmark = pytest.mark.asyncio


def _mock_skill(
    *,
    name: str = "skill_test",
    version: str = "1.0.0",
    prompt_expert: str = "Tu es un expert ESG.",
    procedure: str = "1. Faire X. 2. Faire Y.",
    tool_whitelist: list[str] | None = None,
    sources: list[str] | None = None,
):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        version=version,
        prompt_expert=prompt_expert,
        procedure=procedure,
        tool_whitelist=tool_whitelist or [],
        sources=sources or [],
    )


class TestCountTokens:
    """Comptage tiktoken cl100k_base."""

    def test_count_simple_text(self) -> None:
        assert _count_tokens("Hello world") > 0

    def test_count_empty(self) -> None:
        assert _count_tokens("") == 0

    def test_count_grows_with_text(self) -> None:
        assert _count_tokens("hello world hello world") > _count_tokens("hello world")


class TestFusePrompt:
    """Fusion du system prompt avec 0/1/2 skills."""

    async def test_no_skills_returns_base_unchanged(self, db_session) -> None:
        base = "You are a helpful assistant."
        out = await fuse_prompt(base, [], db_session)
        assert out == base

    async def test_single_skill_inserts_section(self, db_session) -> None:
        skill = _mock_skill(name="skill_esg", version="1.2.3")
        out = await fuse_prompt("BASE PROMPT", [skill], db_session)
        assert "BASE PROMPT" in out
        assert "## SKILL ACTIVE" in out
        assert "skill_esg" in out
        assert "1.2.3" in out
        assert "Tu es un expert ESG." in out
        assert "1. Faire X." in out

    async def test_two_skills_two_sections(self, db_session) -> None:
        s1 = _mock_skill(name="skill_a", prompt_expert="A prompt")
        s2 = _mock_skill(name="skill_b", prompt_expert="B prompt")
        out = await fuse_prompt("BASE", [s1, s2], db_session)
        assert out.count("## SKILL ACTIVE") == 2
        assert "skill_a" in out
        assert "skill_b" in out

    async def test_token_budget_truncates_to_one_skill(self, db_session) -> None:
        # Création d'un huge prompt > 12k tokens combiné.
        huge = "lorem ipsum " * 4000  # ~8000 tokens (~2 tokens/word)
        s1 = _mock_skill(name="skill_huge1", prompt_expert=huge)
        s2 = _mock_skill(name="skill_huge2", prompt_expert=huge)
        out = await fuse_prompt("BASE", [s1, s2], db_session)
        # Cap : si le total excède 12k tokens, charge 1 skill au lieu de 2.
        assert out.count("## SKILL ACTIVE") <= 1


class TestSelectToolsWithSkills:
    """Intersection page tools ∩ skill whitelist."""

    def _tool(self, name: str):
        return SimpleNamespace(name=name)

    def test_no_skills_returns_base_tools(self) -> None:
        base = [self._tool("a"), self._tool("b")]
        out = select_tools_with_skills(base, [])
        assert [t.name for t in out] == ["a", "b"]

    def test_intersection(self) -> None:
        base = [self._tool("a"), self._tool("b"), self._tool("c")]
        skill = _mock_skill(tool_whitelist=["a", "b", "d"])
        out = select_tools_with_skills(base, [skill])
        names = {t.name for t in out}
        assert names == {"a", "b"}

    def test_two_skills_union_of_whitelists(self) -> None:
        base = [self._tool("a"), self._tool("b"), self._tool("c"), self._tool("d")]
        s1 = _mock_skill(tool_whitelist=["a", "b"])
        s2 = _mock_skill(tool_whitelist=["c"])
        out = select_tools_with_skills(base, [s1, s2])
        names = {t.name for t in out}
        assert names == {"a", "b", "c"}

    def test_empty_intersection_raises_and_falls_back(self) -> None:
        """Intersection vide : retourne base_tools avec audit (fallback)."""
        base = [self._tool("a")]
        skill = _mock_skill(tool_whitelist=["x"])
        # Comportement : raise puis caller catch ; ici on teste que l'exception
        # est levée explicitement pour audit.
        with pytest.raises(SkillToolMismatchError):
            select_tools_with_skills(base, [skill], allow_fallback=False)

    def test_empty_intersection_with_fallback_returns_base(self) -> None:
        base = [self._tool("a")]
        skill = _mock_skill(tool_whitelist=["x"])
        out = select_tools_with_skills(base, [skill], allow_fallback=True)
        assert [t.name for t in out] == ["a"]
