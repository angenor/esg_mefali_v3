"""Tests unitaires du service company."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import CompanyProfile
from app.modules.company.schemas import CompanyProfileUpdate
from app.modules.company.service import (
    compute_completion,
    get_or_create_profile,
    get_profile,
    update_profile,
)


@pytest.fixture
def user_id() -> uuid.UUID:
    """ID utilisateur de test."""
    return uuid.uuid4()


# ── compute_completion ──────────────────────────────────────────────


class TestComputeCompletion:
    """Tests pour le calcul de complétion."""

    def test_empty_profile_has_country_default(self) -> None:
        """Un profil avec uniquement country rempli a 12.5% identité."""
        profile = CompanyProfile(user_id=uuid.uuid4(), country="Côte d'Ivoire")
        result = compute_completion(profile)

        assert result.identity_completion == 12.5
        assert result.esg_completion == 0.0
        assert result.overall_completion == 6.2  # (12.5 + 0) / 2 arrondi
        assert "country" in result.identity_fields.filled
        assert "company_name" in result.identity_fields.missing

    def test_full_identity_completion(self) -> None:
        """Tous les champs identité remplis = 100%."""
        profile = CompanyProfile(
            user_id=uuid.uuid4(),
            company_name="EcoPlast",
            sector="recyclage",
            sub_sector="plastique",
            employee_count=15,
            annual_revenue_xof=50_000_000,
            year_founded=2018,
            city="Abidjan",
            country="Côte d'Ivoire",
        )
        result = compute_completion(profile)

        assert result.identity_completion == 100.0
        assert len(result.identity_fields.missing) == 0

    def test_full_esg_completion(self) -> None:
        """Tous les champs ESG remplis = 100%."""
        profile = CompanyProfile(
            user_id=uuid.uuid4(),
            has_waste_management=True,
            has_energy_policy=False,
            has_gender_policy=True,
            has_training_program=False,
            has_financial_transparency=True,
            governance_structure="Conseil d'administration",
            environmental_practices="Tri sélectif",
            social_practices="Emploi local",
        )
        result = compute_completion(profile)

        assert result.esg_completion == 100.0
        # Booléens False comptent comme remplis
        assert "has_energy_policy" in result.esg_fields.filled

    def test_overall_is_average(self) -> None:
        """La complétion globale est la moyenne identité + ESG."""
        profile = CompanyProfile(
            user_id=uuid.uuid4(),
            company_name="Test",
            sector="agriculture",
            city="Bamako",
            country="Mali",
            # 4/8 identity = 50%
            has_waste_management=True,
            has_energy_policy=True,
            # 2/8 ESG = 25%
        )
        result = compute_completion(profile)

        assert result.identity_completion == 50.0
        assert result.esg_completion == 25.0
        assert result.overall_completion == 37.5  # (50 + 25) / 2

    def test_empty_string_not_counted(self) -> None:
        """Une chaîne vide n'est pas considérée comme remplie."""
        profile = CompanyProfile(
            user_id=uuid.uuid4(),
            governance_structure="",
            country="Côte d'Ivoire",
        )
        result = compute_completion(profile)

        assert "governance_structure" in result.esg_fields.missing


# ── get_or_create_profile ───────────────────────────────────────────


class TestGetOrCreateProfile:
    """Tests pour la création/récupération du profil."""

    @pytest.mark.asyncio
    async def test_creates_profile_if_not_exists(
        self, db_session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        """Crée un profil initialisé avec le company_name de l'utilisateur."""
        # Créer un utilisateur d'abord (F02 : Account requis)
        from app.models.account import Account
        from app.models.user import User

        account = Account(name="Test Co")
        db_session.add(account)
        await db_session.flush()
        user = User(
            id=user_id,
            email="test@example.com",
            hashed_password="hashed",
            full_name="Test User",
            company_name="Test Co",
            account_id=account.id,
        )
        db_session.add(user)
        await db_session.flush()

        profile = await get_or_create_profile(db_session, user_id)

        assert profile.user_id == user_id
        # Le country n'est plus hardcodé : il est déterminé à l'inscription
        # via géolocalisation IP (ou saisi par l'utilisateur).
        assert profile.country is None
        # Le company_name est backfillé depuis User.company_name pour que
        # le LLM ait accès au nom de l'entreprise dès la première conversation.
        assert profile.company_name == "Test Co"

    @pytest.mark.asyncio
    async def test_returns_existing_profile(
        self, db_session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        """Retourne le profil existant sans en créer un nouveau."""
        from app.models.account import Account
        from app.models.user import User

        account = Account(name="Test Co")
        db_session.add(account)
        await db_session.flush()
        user = User(
            id=user_id,
            email="test2@example.com",
            hashed_password="hashed",
            full_name="Test User",
            company_name="Test Co",
            account_id=account.id,
        )
        db_session.add(user)
        await db_session.flush()

        profile1 = await get_or_create_profile(db_session, user_id)
        profile1.company_name = "EcoPlast"
        await db_session.flush()

        profile2 = await get_or_create_profile(db_session, user_id)
        assert profile2.id == profile1.id
        assert profile2.company_name == "EcoPlast"


# ── update_profile ──────────────────────────────────────────────────


class TestUpdateProfile:
    """Tests pour la mise à jour partielle du profil."""

    @pytest.mark.asyncio
    async def test_partial_update(
        self, db_session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        """Seuls les champs non-null sont mis à jour."""
        from app.models.account import Account
        from app.models.user import User

        account = Account(name="Test")
        db_session.add(account)
        await db_session.flush()
        user = User(
            id=user_id,
            email="test3@example.com",
            hashed_password="hashed",
            full_name="Test",
            company_name="Test",
            account_id=account.id,
        )
        db_session.add(user)
        await db_session.flush()

        profile = await get_or_create_profile(db_session, user_id)

        updates = CompanyProfileUpdate(
            company_name="EcoPlast", sector="recyclage"
        )
        updated_profile, changed = await update_profile(
            db_session, profile, updates
        )

        assert updated_profile.company_name == "EcoPlast"
        assert updated_profile.sector.value == "recyclage"
        # country reste tel qu'il était (None dans ce contexte de test)
        assert updated_profile.country is None
        assert len(changed) == 2
        assert any(c["field"] == "company_name" for c in changed)

    @pytest.mark.asyncio
    async def test_no_change_when_same_value(
        self, db_session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        """Pas de changement quand la valeur est identique."""
        from app.models.account import Account
        from app.models.user import User

        account = Account(name="Test")
        db_session.add(account)
        await db_session.flush()
        user = User(
            id=user_id,
            email="test4@example.com",
            hashed_password="hashed",
            full_name="Test",
            company_name="Test",
            account_id=account.id,
        )
        db_session.add(user)
        await db_session.flush()

        profile = await get_or_create_profile(db_session, user_id)
        profile.city = "Abidjan"
        await db_session.flush()

        updates = CompanyProfileUpdate(city="Abidjan")
        _, changed = await update_profile(db_session, profile, updates)

        assert len(changed) == 0


# ── get_profile ─────────────────────────────────────────────────────


class TestGetProfile:
    """Tests pour la récupération du profil."""

    @pytest.mark.asyncio
    async def test_returns_none_if_not_exists(
        self, db_session: AsyncSession
    ) -> None:
        """Retourne None si le profil n'existe pas."""
        result = await get_profile(db_session, uuid.uuid4())
        assert result is None
