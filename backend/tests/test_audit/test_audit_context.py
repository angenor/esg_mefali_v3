"""Tests unitaires pour ``app.core.audit_context`` (T005)."""

from __future__ import annotations

import asyncio

import pytest

from app.core.audit_context import (
    current_source_of_change,
    get_current_source_of_change,
    set_source_of_change,
    source_of_change_scope,
)


class TestDefaultValue:
    def test_default_is_manual(self) -> None:
        # Comme la ContextVar peut avoir été modifiée par un autre test,
        # on valide la valeur par défaut via .get(default).
        assert current_source_of_change.get("manual") == "manual"


class TestSetAndGet:
    def test_set_then_read(self) -> None:
        token = set_source_of_change("llm")
        try:
            assert get_current_source_of_change() == "llm"
        finally:
            current_source_of_change.reset(token)

    def test_set_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            set_source_of_change("invalid_value")  # type: ignore[arg-type]

    def test_get_returns_manual_when_corrupted(self) -> None:
        token = current_source_of_change.set("invalid")
        try:
            # get_current_source_of_change garde-fou
            assert get_current_source_of_change() == "manual"
        finally:
            current_source_of_change.reset(token)


class TestSourceOfChangeScope:
    def test_scope_sets_and_resets(self) -> None:
        before = current_source_of_change.get("manual")
        with source_of_change_scope("admin"):
            assert get_current_source_of_change() == "admin"
        assert current_source_of_change.get("manual") == before

    def test_scope_resets_on_exception(self) -> None:
        before = current_source_of_change.get("manual")
        with pytest.raises(RuntimeError):
            with source_of_change_scope("llm"):
                assert get_current_source_of_change() == "llm"
                raise RuntimeError("boom")
        assert current_source_of_change.get("manual") == before


class TestAsyncIsolation:
    """Vérifie que la ContextVar est bien isolée entre 2 tasks asyncio."""

    @pytest.mark.asyncio
    async def test_two_tasks_have_distinct_values(self) -> None:
        captured: dict[str, str] = {}

        async def task(name: str, value: str) -> None:
            with source_of_change_scope(value):  # type: ignore[arg-type]
                # Yield le contrôle pour s'assurer que les 2 tasks
                # se suspendent en même temps.
                await asyncio.sleep(0)
                captured[name] = get_current_source_of_change()
                await asyncio.sleep(0)
                # Lecture finale après suspension : valeur stable.
                captured[name + "_after"] = get_current_source_of_change()

        await asyncio.gather(
            task("a", "llm"),
            task("b", "admin"),
        )

        assert captured["a"] == "llm"
        assert captured["a_after"] == "llm"
        assert captured["b"] == "admin"
        assert captured["b_after"] == "admin"

    @pytest.mark.asyncio
    async def test_scope_does_not_leak_to_caller(self) -> None:
        # Le caller voit la valeur par défaut avant et après le scope.
        before = get_current_source_of_change()

        async def inner() -> None:
            with source_of_change_scope("llm"):
                assert get_current_source_of_change() == "llm"

        await inner()
        # Après l'inner, le scope est sorti : valeur restaurée pour le caller.
        assert get_current_source_of_change() == before
