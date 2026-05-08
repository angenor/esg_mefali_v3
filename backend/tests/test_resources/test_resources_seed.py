"""F20 — Tests du seed des ressources MVP."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resources.seed import (
    SeedResult,
    _build_seeds,
    seed_resources,
)
from tests.test_resources.conftest import (
    make_admin,
    make_intermediary,
    make_verified_source,
)

pytestmark = pytest.mark.asyncio


class TestSeed:
    async def test_seed_no_source_no_op(self, db_session: AsyncSession) -> None:
        admin, _ = await make_admin(db_session)
        result = await seed_resources(db_session, admin.id, publish=False)
        assert isinstance(result, SeedResult)
        # Sans source verified, le seed ne fait rien.
        assert result.inserted == 0

    async def test_seed_inserts_resources(self, db_session: AsyncSession) -> None:
        admin, _ = await make_admin(db_session)
        await make_verified_source(db_session, admin.id)
        result = await seed_resources(db_session, admin.id, publish=False)
        await db_session.commit()
        assert result.inserted >= 10  # ≥ 5 guides + 3 templates + 2 FAQ

    async def test_seed_idempotent(self, db_session: AsyncSession) -> None:
        admin, _ = await make_admin(db_session)
        await make_verified_source(db_session, admin.id)
        first = await seed_resources(db_session, admin.id, publish=False)
        await db_session.commit()
        second = await seed_resources(db_session, admin.id, publish=False)
        await db_session.commit()
        assert second.inserted == 0
        assert second.skipped >= first.inserted

    async def test_seed_with_intermediary_includes_guides(
        self, db_session: AsyncSession
    ) -> None:
        admin, _ = await make_admin(db_session)
        await make_verified_source(db_session, admin.id)
        # Créer un intermédiaire BOAD-like pour tester l'inclusion des fiches.
        from app.models.financing import IntermediaryType, OrganizationType, Intermediary

        boad = Intermediary(
            name="BOAD",
            intermediary_type=IntermediaryType.partner_bank,
            organization_type=OrganizationType.development_bank,
            country="Senegal",
            city="Dakar",
        )
        db_session.add(boad)
        await db_session.commit()
        result = await seed_resources(db_session, admin.id, publish=False)
        await db_session.commit()
        assert result.inserted >= 11  # +1 fiche BOAD


class TestBuildSeeds:
    def test_build_seeds_includes_all_types(self) -> None:
        import uuid as _u

        seeds = _build_seeds(
            _u.uuid4(),
            {"uemoa_taxonomie": _u.uuid4()},
            {},
        )
        types = {s["type"] for s in seeds}
        assert "guide" in types
        assert "template_doc" in types
        assert "faq" in types
