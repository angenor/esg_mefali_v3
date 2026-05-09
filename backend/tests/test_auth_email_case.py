"""Tests TDD pour le fix login email casse-mixte (Bug #2).

Symptôme E2E : ``Angenor99@gmail.com`` était rejeté avec « Identifiants invalides »,
seul ``angenor99@gmail.com`` était accepté.

Stratégie : normaliser l'email à ``.strip().lower()`` côté Pydantic (validators
``@field_validator('email', mode='before')``) sur les schémas Login + Register,
afin de :
- accepter au login n'importe quelle casse fournie par l'utilisateur ;
- garantir que les nouveaux comptes sont stockés en minuscules (idempotent).

Une migration backfill ``UPDATE users SET email = LOWER(email)`` est testée
en intégration séparée.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def user_payload() -> dict:
    """Payload register avec email en CASSE MIXTE (volontairement)."""
    return {
        "email": "Angenor99@Gmail.Com",
        "password": "motdepasse123",
        "full_name": "Angenor",
        "company_name": "TestCorp",
    }


class TestEmailCaseInsensitiveLogin:
    """Login doit être insensible à la casse de l'email."""

    async def test_login_with_uppercase_email_succeeds(
        self, client: AsyncClient, user_payload: dict
    ) -> None:
        """Si l'utilisateur s'inscrit avec ``angenor99@gmail.com`` (lowercase
        canonique), il doit pouvoir se connecter avec ``Angenor99@gmail.com``."""
        register_payload = {**user_payload, "email": "angenor99@gmail.com"}
        register_response = await client.post(
            "/api/auth/register", json=register_payload
        )
        assert register_response.status_code == 201

        login_response = await client.post(
            "/api/auth/login",
            json={
                "email": "Angenor99@gmail.com",  # Casse mixte
                "password": register_payload["password"],
            },
        )

        assert login_response.status_code == 200, login_response.text
        body = login_response.json()
        assert "access_token" in body

    async def test_login_with_full_uppercase_email_succeeds(
        self, client: AsyncClient
    ) -> None:
        """Login avec l'email en MAJUSCULES doit réussir."""
        await client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "password": "motdepasse123",
                "full_name": "Test",
                "company_name": "Co",
            },
        )

        login_response = await client.post(
            "/api/auth/login",
            json={"email": "TEST@EXAMPLE.COM", "password": "motdepasse123"},
        )

        assert login_response.status_code == 200

    async def test_login_with_whitespace_is_stripped(
        self, client: AsyncClient
    ) -> None:
        """Login avec espaces autour de l'email doit réussir (strip)."""
        await client.post(
            "/api/auth/register",
            json={
                "email": "stripme@example.com",
                "password": "motdepasse123",
                "full_name": "Test",
                "company_name": "Co",
            },
        )

        login_response = await client.post(
            "/api/auth/login",
            json={"email": "  stripme@example.com  ", "password": "motdepasse123"},
        )

        assert login_response.status_code == 200


class TestEmailNormalizedAtRegister:
    """Le register doit stocker l'email en minuscules (idempotent)."""

    async def test_register_normalizes_email_to_lowercase(
        self, client: AsyncClient, user_payload: dict, db_session: AsyncSession
    ) -> None:
        """Inscription avec ``Angenor99@Gmail.Com`` → BDD stocke
        ``angenor99@gmail.com``."""
        from sqlalchemy import select

        from app.models.user import User

        response = await client.post("/api/auth/register", json=user_payload)
        assert response.status_code == 201

        result = await db_session.execute(
            select(User.email).where(User.email == "angenor99@gmail.com")
        )
        stored_email = result.scalar_one_or_none()
        assert stored_email == "angenor99@gmail.com", (
            "L'email stocké doit être normalisé en minuscules à l'inscription"
        )

    async def test_register_duplicate_with_different_case_returns_409(
        self, client: AsyncClient
    ) -> None:
        """Inscription avec une casse différente d'un email existant → 409."""
        await client.post(
            "/api/auth/register",
            json={
                "email": "duplicate@example.com",
                "password": "motdepasse123",
                "full_name": "First",
                "company_name": "Co",
            },
        )

        response = await client.post(
            "/api/auth/register",
            json={
                "email": "DUPLICATE@example.com",
                "password": "motdepasse123",
                "full_name": "Second",
                "company_name": "Co",
            },
        )

        assert response.status_code == 409


class TestPydanticValidatorNormalize:
    """Validator Pydantic v2 doit normaliser l'email avant traitement."""

    def test_login_request_lowercases_email(self) -> None:
        """LoginRequest accepte casse mixte et l'expose en minuscules."""
        from app.schemas.auth import LoginRequest

        req = LoginRequest(email="Angenor99@Gmail.Com", password="x")
        assert req.email == "angenor99@gmail.com"

    def test_login_request_strips_whitespace(self) -> None:
        """LoginRequest strip les espaces."""
        from app.schemas.auth import LoginRequest

        req = LoginRequest(email="  user@example.com  ", password="x")
        assert req.email == "user@example.com"

    def test_register_request_lowercases_email(self) -> None:
        """RegisterRequest accepte casse mixte et l'expose en minuscules."""
        from app.schemas.auth import RegisterRequest

        req = RegisterRequest(
            email="Test@Example.COM",
            password="motdepasse123",
            full_name="Test",
            company_name="Co",
        )
        assert req.email == "test@example.com"
