"""Tests unitaires F09 — service email (stub MVP)."""

from __future__ import annotations

import pytest

from app.core.email_service import (
    ConsoleEmailService,
    NoopEmailService,
    build_reset_link,
    get_email_service,
)


pytestmark = pytest.mark.asyncio


async def test_console_backend_returns_success(caplog) -> None:
    service = ConsoleEmailService()
    result = await service.send_password_reset_email(
        user_email="user@example.com",
        reset_link="http://localhost:3000/auth/reset?token=abc",
    )
    assert result.success is True
    assert result.backend == "console"


async def test_noop_backend_returns_success_silently() -> None:
    service = NoopEmailService()
    result = await service.send_password_reset_email(
        user_email="user@example.com",
        reset_link="http://localhost:3000/auth/reset?token=abc",
    )
    assert result.success is True
    assert result.backend == "noop"


async def test_build_reset_link_includes_token() -> None:
    link = build_reset_link("my-token-xyz")
    assert "/auth/reset?token=my-token-xyz" in link


async def test_get_email_service_returns_console_by_default(monkeypatch) -> None:
    monkeypatch.delenv("EMAIL_BACKEND", raising=False)
    service = get_email_service()
    assert isinstance(service, ConsoleEmailService)


async def test_get_email_service_returns_noop_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("EMAIL_BACKEND", "noop")
    service = get_email_service()
    assert isinstance(service, NoopEmailService)
