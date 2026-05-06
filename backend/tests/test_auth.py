"""Tests des endpoints d'authentification et du modèle User.

T019: Tests endpoints auth (register, login, refresh, me)
T020: Tests modèle User (création, unicité email, hashing)

Écrits AVANT l'implémentation (TDD RED phase).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import make_unique_email


# ─── Données de test ──────────────────────────────────────────────────

VALID_USER = {
    "email": "amadou@example.com",
    "password": "motdepasse123",
    "full_name": "Amadou Diallo",
    "company_name": "EcoSolaire SARL",
}


def make_user_data(**overrides: str) -> dict:
    """Créer des données utilisateur avec des valeurs par défaut."""
    data = {**VALID_USER, "email": make_unique_email()}
    data.update(overrides)
    return data


# ─── T019: Tests endpoints auth ──────────────────────────────────────


class TestRegister:
    """Tests POST /api/auth/register."""

    async def test_register_success(self, client: AsyncClient) -> None:
        """Un utilisateur peut s'inscrire avec des données valides."""
        data = make_user_data()
        response = await client.post("/api/auth/register", json=data)

        assert response.status_code == 201
        body = response.json()
        assert body["email"] == data["email"]
        assert body["full_name"] == data["full_name"]
        assert body["company_name"] == data["company_name"]
        assert "id" in body
        assert "created_at" in body
        # Le mot de passe ne doit jamais être retourné
        assert "password" not in body
        assert "hashed_password" not in body

    async def test_register_duplicate_email(self, client: AsyncClient) -> None:
        """L'inscription avec un email existant retourne 409."""
        data = make_user_data()
        await client.post("/api/auth/register", json=data)
        response = await client.post("/api/auth/register", json=data)

        assert response.status_code == 409

    async def test_register_invalid_email(self, client: AsyncClient) -> None:
        """L'inscription avec un email invalide retourne 422."""
        data = make_user_data(email="pas-un-email")
        response = await client.post("/api/auth/register", json=data)

        assert response.status_code == 422

    async def test_register_short_password(self, client: AsyncClient) -> None:
        """L'inscription avec un mot de passe trop court retourne 422."""
        data = make_user_data(password="court")
        response = await client.post("/api/auth/register", json=data)

        assert response.status_code == 422

    async def test_register_missing_fields(self, client: AsyncClient) -> None:
        """L'inscription sans champs requis retourne 422."""
        response = await client.post("/api/auth/register", json={})

        assert response.status_code == 422


class TestLogin:
    """Tests POST /api/auth/login."""

    async def test_login_success(self, client: AsyncClient) -> None:
        """Un utilisateur inscrit peut se connecter."""
        data = make_user_data()
        await client.post("/api/auth/register", json=data)

        response = await client.post(
            "/api/auth/login",
            json={"email": data["email"], "password": data["password"]},
        )

        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        # F02 : access_token_expire_minutes porté à 1440 (24 h) — 86400 s.
        assert body["expires_in"] == 86400

    async def test_login_wrong_password(self, client: AsyncClient) -> None:
        """La connexion avec un mauvais mot de passe retourne 401."""
        data = make_user_data()
        await client.post("/api/auth/register", json=data)

        response = await client.post(
            "/api/auth/login",
            json={"email": data["email"], "password": "mauvais"},
        )

        assert response.status_code == 401

    async def test_login_nonexistent_email(self, client: AsyncClient) -> None:
        """La connexion avec un email inexistant retourne 401."""
        response = await client.post(
            "/api/auth/login",
            json={"email": "inconnu@example.com", "password": "motdepasse123"},
        )

        assert response.status_code == 401


class TestRefresh:
    """Tests POST /api/auth/refresh."""

    async def test_refresh_success(self, client: AsyncClient) -> None:
        """Un refresh token valide retourne un nouveau access token."""
        data = make_user_data()
        await client.post("/api/auth/register", json=data)
        login_response = await client.post(
            "/api/auth/login",
            json={"email": data["email"], "password": data["password"]},
        )
        refresh_token = login_response.json()["refresh_token"]

        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    async def test_refresh_invalid_token(self, client: AsyncClient) -> None:
        """Un refresh token invalide retourne 401."""
        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": "token-invalide"},
        )

        assert response.status_code == 401


class TestMe:
    """Tests GET /api/auth/me."""

    async def test_me_authenticated(self, client: AsyncClient) -> None:
        """Un utilisateur authentifié peut accéder à son profil."""
        data = make_user_data()
        await client.post("/api/auth/register", json=data)
        login_response = await client.post(
            "/api/auth/login",
            json={"email": data["email"], "password": data["password"]},
        )
        token = login_response.json()["access_token"]

        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["email"] == data["email"]
        assert body["full_name"] == data["full_name"]

    async def test_me_no_token(self, client: AsyncClient) -> None:
        """L'accès sans token retourne 401."""
        response = await client.get("/api/auth/me")

        assert response.status_code == 401

    async def test_me_invalid_token(self, client: AsyncClient) -> None:
        """L'accès avec un token invalide retourne 401."""
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer token-invalide"},
        )

        assert response.status_code == 401


# ─── T020: Tests modèle User ─────────────────────────────────────────


class TestUserModel:
    """Tests du modèle User directement via la BDD."""

    async def test_create_user(self, db_session: AsyncSession) -> None:
        """Créer un utilisateur en base de données."""
        from app.models.user import User
        from app.core.security import hash_password

        user = User(
            email=make_unique_email(),
            hashed_password=hash_password("motdepasse123"),
            full_name="Test User",
            company_name="Test Corp",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.id is not None
        assert user.is_active is True
        assert user.created_at is not None

    async def test_password_is_hashed(self, db_session: AsyncSession) -> None:
        """Le mot de passe stocké est hashé, jamais en clair."""
        from app.models.user import User
        from app.core.security import hash_password

        password = "motdepasse123"
        hashed = hash_password(password)

        user = User(
            email=make_unique_email(),
            hashed_password=hashed,
            full_name="Test User",
            company_name="Test Corp",
        )
        db_session.add(user)
        await db_session.commit()

        assert user.hashed_password != password
        assert user.hashed_password.startswith("$2b$")

    async def test_email_uniqueness(self, db_session: AsyncSession) -> None:
        """Deux utilisateurs ne peuvent pas avoir le même email."""
        from sqlalchemy.exc import IntegrityError

        from app.models.user import User
        from app.core.security import hash_password

        email = make_unique_email()
        user1 = User(
            email=email,
            hashed_password=hash_password("pass1234"),
            full_name="User 1",
            company_name="Corp 1",
        )
        db_session.add(user1)
        await db_session.commit()

        user2 = User(
            email=email,
            hashed_password=hash_password("pass5678"),
            full_name="User 2",
            company_name="Corp 2",
        )
        db_session.add(user2)

        with pytest.raises(IntegrityError):
            await db_session.commit()
